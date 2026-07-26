import asyncio
import logging
from collections import defaultdict
from datetime import datetime

from .config import settings
from .db import active_watches, get_session, init_db, last_cheapest
from .models import PriceQuote, Watch, route_key, utcnow
from .notifier import format_digest, send_text
from .registry import SOURCES
from .sources import Quote, SourceError

log = logging.getLogger("ticketcatch")


async def _fetch_route(origin: str, destination: str, depart) -> list[Quote]:
    """Query every registered source for one route+date and merge their offers. A failing
    source is logged and skipped so one dead source never blanks the whole route."""
    merged: list[Quote] = []
    for name, fetch in SOURCES.items():
        try:
            merged.extend(await fetch(origin, destination, depart))
        except (SourceError, Exception) as e:  # fail loud per-source, keep others alive
            log.error("source failed [%s] %s-%s: %s", name, origin, destination, e)
    return merged


def _dedupe(offers: list[Quote]) -> list[Quote]:
    """Sources overlap — the same physical flight can come back from several of them. Keep the
    cheapest quote per (flight, departure) so the digest reads like a booking board, not a log."""
    best: dict[tuple, Quote] = {}
    for o in offers:
        key = (o.flight_number or o.airline, o.depart_at)
        if key not in best or o.price < best[key].price:
            best[key] = o
    return sorted(best.values(), key=lambda o: o.price)


def _to_quote_rows(rkey: str, offers: list[Quote], captured_at: datetime) -> list[PriceQuote]:
    """All rows of one poll batch share a single captured_at so last_cheapest can group them."""
    return [
        PriceQuote(
            route_key=rkey,
            source=o.source,
            price=o.price,
            currency=o.currency,
            airline=o.airline,
            flight_number=o.flight_number,
            depart_at=o.depart_at,
            deep_link=o.deep_link,
            stops=o.stops,
            duration_min=o.duration_min,
            bags=o.bags,
            captured_at=captured_at,
        )
        for o in offers
    ]


async def poll_once() -> dict:
    await init_db()
    stats = {"watches": 0, "routes": 0, "offers": 0, "sent": 0, "empty": 0, "errors": 0}

    async with get_session() as s:
        watches = await active_watches(s)
    stats["watches"] = len(watches)

    # Group watches by route so an identical route+date is queried once, then fanned out.
    by_route: dict[str, list[Watch]] = defaultdict(list)
    for w in watches:
        by_route[route_key(w.origin, w.destination, w.depart_date)].append(w)
    stats["routes"] = len(by_route)

    for rkey, watchers in by_route.items():
        first = watchers[0]
        offers = await _fetch_route(first.origin, first.destination, first.depart_date)
        if not offers:
            stats["empty"] += 1
            continue
        stats["offers"] += len(offers)

        offers = _dedupe(offers)
        captured_at = utcnow().replace(microsecond=0)
        cheapest = _to_quote_rows(rkey, offers[: settings.top_n], captured_at)

        async with get_session() as s:
            previous = await last_cheapest(s, rkey, settings.currency.lower())
            for row in cheapest:  # persist the new snapshot as price history
                s.add(row)
            await s.commit()

        for w in watchers:
            try:
                text = format_digest(w, cheapest, previous)
                if await send_text(w.user_id, text, preview=True):
                    stats["sent"] += 1
            except Exception as e:
                log.error("notify failed for watch %s: %s", w.pk, e)
                stats["errors"] += 1

    log.info("poll done: %s", stats)
    return stats


async def loop() -> None:
    while True:
        try:
            await poll_once()
        except Exception as e:
            log.exception("poll cycle crashed: %s", e)
        await asyncio.sleep(settings.poll_interval_seconds)
