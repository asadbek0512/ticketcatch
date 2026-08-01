import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from . import schedule
from .config import settings
from .db import (
    active_watches,
    alerting_watches,
    get_preference,
    get_session,
    init_db,
    last_cheapest,
    recent_deal,
    record_deal,
    typical_price,
)
from .models import PriceQuote, Watch, route_key, utcnow
from .notifier import discount_percent, format_alert, format_deal, format_digest, send_text
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

    try:
        await _announce(rkey, first, cheapest)
    except Exception as e:  # the channel is a nice-to-have; it never breaks someone's digest
        log.warning("deal announce failed %s: %s", rkey, e)


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


async def _announce(rkey: str, watch: Watch, rows: list[PriceQuote]) -> None:
    """Post a genuinely good fare to the public channel, if there is one and it is genuinely good.

    Every guard here answers the same question — would a stranger be glad this arrived? A price is
    only news against a route's own history, so a route with no history is never announced; a
    channel that reposts the same bargain every twelve hours is a channel people mute; and a fare
    that isn't clearly under the usual is just a price, which nobody subscribed for."""
    if not settings.deals_channel_id:
        return
    best = rows[0]
    async with get_session() as s:
        typical = await typical_price(s, rkey, best.currency)
        if typical is None:
            return
        if discount_percent(typical, best.price) < settings.deal_discount_percent:
            return
        posted = await recent_deal(s, rkey, settings.deal_repeat_hours)
        if posted is not None and best.price >= posted.price:
            return  # already announced, and this is no better than what we announced
        text = format_deal(watch, rows, typical)
        if not await send_text(settings.deals_channel_id, text, preview=True):
            return
        await record_deal(s, rkey, best.price, best.currency)
    log.info("announced deal %s at %s", rkey, best.price)


SEND, RESET, SKIP = "send", "reset", "skip"


def alert_decision(threshold: int | None, alerted_price: int | None, price: int) -> str:
    """What to do about one watch at one price — the whole judgement, with no database in it.

    SEND once when the fare crosses the target, and again only if it goes lower still. RESET when it
    climbs back above, because forgetting the last alert is what lets the next dip count as news.
    SKIP otherwise: a fare that sits under the target for a week is one message, not a hundred and
    sixty-eight, and the difference between those two bots is whether anyone leaves it installed."""
    if threshold is None:
        return SKIP
    if price > threshold:
        return RESET if alerted_price is not None else SKIP
    if alerted_price is not None and price >= alerted_price:
        return SKIP
    return SEND


async def _alert_group(key: tuple[str, str, str], watchers: list[Watch], stats: dict) -> None:
    """Price one route and tell whoever asked to be told, if the number they named has arrived."""
    rkey, currency, market = key
    first = watchers[0]
    try:
        offers = await fetch_offers(
            first.origin,
            first.destination,
            first.depart_date,
            SearchOpts.of(currency=currency, market=market),
            ret=first.return_date,
        )
    except Exception as e:
        log.error("alert scan failed %s: %s", rkey, e)
        stats["errors"] += 1
        return
    if not offers:
        return

    rows = _to_quote_rows(rkey, offers[: settings.top_n], utcnow().replace(microsecond=0))
    best = rows[0]
    async with get_session() as s:
        for w in watchers:
            verdict = alert_decision(w.threshold_price, w.alerted_price, best.price)
            if verdict == RESET:
                w.alerted_price = None
                s.add(w)
                continue
            if verdict == SKIP:
                continue
            lang = (await get_preference(s, w.user_id)).lang
            try:
                if await send_text(w.user_id, format_alert(w, rows, lang=lang), preview=True):
                    stats["alerts"] += 1
            except Exception as e:
                log.error("alert failed for watch %s: %s", w.pk, e)
                stats["errors"] += 1
                continue
            w.alerted_price = best.price
            s.add(w)
        await s.commit()


async def alert_scan() -> dict:
    """Check target-price watches between digests, so "under 400,000" arrives when it happens.

    Only watches carrying a threshold are scanned. That is what keeps this affordable: the user has
    told us, in a number, that this route is worth looking at more often than twice a day, and
    everyone else's route costs nothing here. The full source set is used rather than the cheap JSON
    one — an alert quoting a price the cheapest seller has already beaten would be the same broken
    promise this whole feature exists to keep."""
    stats = {"routes": 0, "alerts": 0, "errors": 0}
    async with get_session() as s:
        watches = await alerting_watches(s)
    if not watches:
        return stats

    by_group: dict[tuple[str, str, str], list[Watch]] = defaultdict(list)
    for w in watches:
        by_group[_group_key(w)].append(w)
    stats["routes"] = len(by_group)

    gate = asyncio.Semaphore(max(1, settings.route_concurrency))

    async def guarded(key: tuple[str, str, str], watchers: list[Watch]) -> None:
        async with gate:
            await _alert_group(key, watchers, stats)

    await asyncio.gather(*(guarded(k, v) for k, v in by_group.items()))
    if stats["alerts"] or stats["errors"]:
        log.info("alert scan: %s", stats)
    return stats


HEARTBEAT_FILE = Path(settings.db_path).parent / ".poll_heartbeat"


def _beat() -> None:
    """Touch a file after every tick so the watchdog can tell "alive" from "quiet".

    Since each watch is priced at its owner's hour, twelve hours can pass with nothing written to
    the database and nothing wrong — the old watchdog read that silence as a dead poller and cried
    wolf twice a day. This file separates the two questions: the heartbeat says the loop is still
    turning (checked in minutes), the price table says the searches still find something (checked
    in days). It is written even when a cycle raised, because a loop that keeps failing is a
    different fault from a loop that stopped, and only the price check should catch it."""
    try:
        HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_FILE.touch()
    except OSError as e:  # a watchdog file is never worth killing the poller over
        log.warning("could not write heartbeat: %s", e)


async def loop() -> None:
    """Wake often, work rarely. The tick is short so that a delivery hour is never missed by more
    than one tick; the actual scraping still happens twice a day per watch, at the hour its owner
    chose. Sleeping for twelve hours instead would tie everyone's digest to whenever this process
    was last restarted, which is how prices used to arrive at four in the morning."""
    last_scan = 0.0
    while True:
        try:
            await poll_once(only_due=True)
        except Exception as e:
            log.exception("poll cycle crashed: %s", e)
        # Target-price watches are checked on their own, slower clock, in between digests. A monotonic
        # clock rather than a wall one: this must not fire a burst of scans because the server's time
        # was corrected, and it must survive the daylight-saving jump that moves everyone's slot.
        now = asyncio.get_running_loop().time()
        if now - last_scan >= settings.alert_scan_seconds:
            last_scan = now
            try:
                await alert_scan()
            except Exception as e:
                log.exception("alert scan crashed: %s", e)
        _beat()
        await asyncio.sleep(settings.poll_tick_seconds)
