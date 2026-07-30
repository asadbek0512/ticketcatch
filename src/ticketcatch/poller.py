import asyncio
import logging
from collections import defaultdict
from datetime import datetime

from . import schedule
from .config import settings
from .db import active_watches, get_preference, get_session, init_db, last_cheapest
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
        route_key(watch.origin, watch.destination, watch.depart_date, watch.return_date),
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
            return_at=o.return_at,
            return_stops=o.return_stops,
            captured_at=captured_at,
        )
        for o in offers
    ]


async def _poll_group(key: tuple[str, str, str], watchers: list[Watch], stats: dict) -> None:
    rkey, currency, market = key
    first = watchers[0]
    opts = SearchOpts.of(currency=currency, market=market)
    try:
        offers = await fetch_offers(
            first.origin, first.destination, first.depart_date, opts, ret=first.return_date
        )
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
        # Read each watcher's language at send time rather than trusting the copy on the watch:
        # switching language in Settings has to change the next digest, not just the menu.
        langs = {w.user_id: (await get_preference(s, w.user_id)).lang for w in watchers}

    for w in watchers:
        try:
            digest = format_digest(w, cheapest, previous, lang=langs.get(w.user_id))
            if await send_text(w.user_id, digest, preview=True):
                stats["sent"] += 1
        except Exception as e:
            log.error("notify failed for watch %s: %s", w.pk, e)
            stats["errors"] += 1


async def _due_watches(watches: list[Watch]) -> list[Watch]:
    """The watches whose owner's delivery hour has come round. Everything else costs nothing this
    tick: not scraped, not sent, not woken up."""
    due: list[Watch] = []
    now = utcnow()
    async with get_session() as s:
        for w in watches:
            pref = await get_preference(s, w.user_id)
            if schedule.is_due(now, pref.tz, pref.notify_hour, w.last_sent_at):
                due.append(w)
    return due


async def _mark_sent(watches: list[Watch]) -> None:
    """Remember that this slot has been served, so the remaining ticks of the same hour stay quiet."""
    now = utcnow()
    async with get_session() as s:
        for w in watches:
            w.last_sent_at = now
            s.add(w)
        await s.commit()


async def poll_once(only_due: bool = False) -> dict:
    """One full cycle: every distinct route+market fetched once, then fanned out to its watchers.

    only_due is what the loop uses — each user hears from us at their own hour. A manual
    `python -m ticketcatch poll` ignores the schedule, because someone running it by hand is
    asking for prices now."""
    await init_db()
    stats = {"routes": 0, "offers": 0, "sent": 0, "errors": 0}

    async with get_session() as s:
        watches = await active_watches(s)
    if only_due:
        watches = await _due_watches(watches)
    if not watches:
        log.info("no watches due" if only_due else "no active watches")
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
    await _mark_sent(watches)
    log.info("poll done: %s", stats)
    return stats


async def loop() -> None:
    """Wake often, work rarely. The tick is short so that a delivery hour is never missed by more
    than one tick; the actual scraping still happens twice a day per watch, at the hour its owner
    chose. Sleeping for twelve hours instead would tie everyone's digest to whenever this process
    was last restarted, which is how prices used to arrive at four in the morning."""
    while True:
        try:
            await poll_once(only_due=True)
        except Exception as e:
            log.exception("poll cycle crashed: %s", e)
        await asyncio.sleep(settings.poll_tick_seconds)
