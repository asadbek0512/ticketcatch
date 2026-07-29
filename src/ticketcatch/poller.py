import asyncio
import logging
from collections import defaultdict
from datetime import datetime

from .config import settings
from .db import active_watches, get_session, init_db, last_cheapest
from .models import PriceQuote, Watch, route_key, utcnow
from .notifier import format_digest, send_text
from .search import fetch_offers
from .sources import Quote, SearchOpts

log = logging.getLogger("ticketcatch")


def _group_key(watch: Watch) -> tuple[str, str, str]:
    """Watches share one fetch only when the *price* would be identical: same route and day, bought
    from the same country in the same money. Two users watching ICN→TAS from Korea and from
    Uzbekistan are two different questions with two different answers."""
    return (
        route_key(watch.origin, watch.destination, watch.depart_date),
        watch.currency,
        watch.market,
    )


def _to_quote_rows(rkey: str, offers: list[Quote], captured_at: datetime) -> list[PriceQuote]:
    """All rows in one poll batch share a single captured_at so last_cheapest can group them."""
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


async def _poll_group(key: tuple[str, str, str], watchers: list[Watch], stats: dict) -> None:
    rkey, currency, market = key
    first = watchers[0]
    opts = SearchOpts.of(currency=currency, market=market)
    try:
        offers = await fetch_offers(first.origin, first.destination, first.depart_date, opts)
    except Exception as e:
        log.error("route failed %s: %s", rkey, e)
        stats["errors"] += 1
        return
    if not offers:
        log.warning("no offers for %s", rkey)
        stats["errors"] += 1
        return
    stats["offers"] += len(offers)

    captured_at = utcnow().replace(microsecond=0)
    cheapest = _to_quote_rows(rkey, offers[: settings.top_n], captured_at)

    async with get_session() as s:
        previous = await last_cheapest(s, rkey, currency)
        for row in cheapest:  # persist the new snapshot as price history
            s.add(row)
        await s.commit()

    for w in watchers:
        try:
            if await send_text(w.user_id, format_digest(w, cheapest, previous), preview=True):
                stats["sent"] += 1
        except Exception as e:
            log.error("notify failed for watch %s: %s", w.pk, e)
            stats["errors"] += 1


async def poll_once() -> dict:
    """One full cycle: every distinct route+market fetched once, then fanned out to its watchers."""
    await init_db()
    stats = {"routes": 0, "offers": 0, "sent": 0, "errors": 0}

    async with get_session() as s:
        watches = await active_watches(s)
    if not watches:
        log.info("no active watches")
        return stats

    by_group: dict[tuple[str, str, str], list[Watch]] = defaultdict(list)
    for w in watches:
        by_group[_group_key(w)].append(w)
    stats["routes"] = len(by_group)

    # Routes run in parallel because a cycle is mostly spent waiting on someone else's server. The
    # cap is what stops a hundred watches from opening a hundred simultaneous searches; the browser
    # sources are rationed further by their own semaphore.
    gate = asyncio.Semaphore(max(1, settings.route_concurrency))

    async def guarded(key: tuple[str, str, str], watchers: list[Watch]) -> None:
        async with gate:
            await _poll_group(key, watchers, stats)

    await asyncio.gather(*(guarded(k, v) for k, v in by_group.items()))
    log.info("poll done: %s", stats)
    return stats


async def loop() -> None:
    while True:
        try:
            await poll_once()
        except Exception as e:
            log.exception("poll cycle crashed: %s", e)
        await asyncio.sleep(settings.poll_interval_seconds)
