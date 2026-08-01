"""One search: every source at once, merged, deduped, cached. Shared by the poller and the menu."""

import asyncio
import logging
import re
from datetime import date, timedelta

from .config import settings
from .db import cached_offers, get_session, store_offers
from .models import route_key
from .registry import SOURCES
from .sources import Quote, SearchOpts, airline_name, kiwi

log = logging.getLogger("ticketcatch")

CALENDAR_DAYS = 8  # days shown in the cheapest-day strip
CALENDAR_LOOKBACK = 3  # how far before the chosen date the strip starts
CALENDAR_CONCURRENCY = 4


def cache_key(
    origin: str, destination: str, depart: date, opts: SearchOpts, ret: date | None = None
) -> str:
    """Route + point of sale: the same flight has a different price bought from another country.

    The return date is part of the key because a round trip is priced as a pair — its fare is not
    the one-way fare, so the two searches must never share a cache entry."""
    base = f"{route_key(origin, destination, depart)}|{opts.key}"
    return f"{base}|r{ret.isoformat()}" if ret else base


async def fetch_offers(
    origin: str,
    destination: str,
    depart: date,
    opts: SearchOpts | None = None,
    max_age: int | None = None,
    ret: date | None = None,
) -> list[Quote]:
    """Cheapest-first offers for one route and day.

    Sources run concurrently, so the board takes as long as the slowest site rather than the sum
    of all four. A source that fails is logged and skipped, never fatal: a partial board still
    answers "what does this cost today", an exception answers nothing.

    Results are cached per route+day+market, so ten people asking the same question cost one
    search. Pass max_age=0 to force a live fetch."""
    opts = opts or SearchOpts.of()
    key = cache_key(origin, destination, depart, opts, ret)
    ttl = settings.cache_ttl_seconds if max_age is None else max_age

    async with get_session() as session:
        hit = await cached_offers(session, key, ttl)
    if hit:
        log.info("cache hit %s (%s offers)", key, len(hit))
        return hit

    results = await asyncio.gather(
        *(
            _run(name, fetch, origin, destination, depart, opts, ret)
            for name, fetch in SOURCES.items()
        )
    )
    merged = dedupe([_named(q) for batch in results for q in batch])
    if merged:
        async with get_session() as session:
            await store_offers(session, key, merged)
    return merged


_CARRIER_CODE = re.compile(r"^[A-Z0-9]{2}$")


def _named(quote: Quote) -> Quote:
    """Turn leftover carrier codes into names, once every source has reported.

    Trip.com can only read a code off the logo, and the code→name directory is filled in by Google
    and Kiwi. Now that the sources run concurrently there is no guaranteed order between them, so
    the lookup happens here — after the gather, when the directory is complete — instead of inside
    a parser that might have finished first. Anything that isn't a two-character code is already a
    name and is left alone."""
    if not quote.airline:
        return quote
    parts = [p.strip() for p in quote.airline.split(",")]
    quote.airline = ", ".join(airline_name(p) if _CARRIER_CODE.match(p) else p for p in parts)
    return quote


async def _run(
    name: str, fetch, origin: str, destination: str, depart: date, opts, ret: date | None
) -> list[Quote]:
    try:
        return await fetch(origin, destination, depart, opts, ret)
    except Exception as e:  # one dead source must not take the whole board down
        log.error("source failed [%s] %s-%s: %s", name, origin, destination, e)
        return []


INLINE_TIMEOUT = 6.0  # Telegram drops an inline answer that takes longer than about ten seconds


async def quick_offers(
    origin: str,
    destination: str,
    depart: date,
    opts: SearchOpts | None = None,
    ret: date | None = None,
) -> list[Quote]:
    """A fast, partial board for inline mode — cache first, then the JSON source alone.

    Inline queries fire while someone is still typing and must be answered in seconds, so the four
    browser-driven minutes a real search costs are not on the table. What is on the table is honest:
    prices someone else's search already paid for, or Kiwi's, which answers over HTTP. A full board
    found in the shared cache beats our partial one and is preferred; our own result is kept apart
    from it so a one-source answer can never be served to the poller as if it were the whole market.

    Returns [] rather than raising. An empty inline answer offers to open the bot, which is a better
    outcome than an error inside somebody else's group chat."""
    opts = opts or SearchOpts.of()
    full_key = cache_key(origin, destination, depart, opts, ret)
    async with get_session() as session:
        for key in (full_key, f"inline|{full_key}"):
            hit = await cached_offers(session, key, settings.cache_ttl_seconds)
            if hit:
                return hit

    try:
        offers = await asyncio.wait_for(
            kiwi.fetch(origin, destination, depart, opts, ret), INLINE_TIMEOUT
        )
    except Exception as e:
        log.info("inline search gave up %s-%s: %s", origin, destination, e)
        return []

    merged = dedupe([_named(q) for q in offers])
    if merged:
        async with get_session() as session:
            await store_offers(session, f"inline|{full_key}", merged)
    return merged


def calendar_days(around: date) -> list[date]:
    """The strip of days to price, never starting before tomorrow."""
    start = max(around - timedelta(days=CALENDAR_LOOKBACK), date.today() + timedelta(days=1))
    return [start + timedelta(days=i) for i in range(CALENDAR_DAYS)]


async def day_prices(
    origin: str,
    destination: str,
    around: date,
    opts: SearchOpts | None = None,
    ret: date | None = None,
) -> list[tuple[date, int | None]]:
    """Cheapest fare per day around a date — the "am I flying on the wrong day?" answer.

    Only Kiwi is asked. Pricing eight days through all four sources would mean eight browser runs
    for a hint, and Kiwi is the JSON one: fast, and the source whose fares proved most accurate."""
    opts = opts or SearchOpts.of()
    days = calendar_days(around)
    key = f"days|{origin.upper()}-{destination.upper()}-{days[0].isoformat()}|{opts.key}"
    if ret:
        # On a round trip the strip prices "leave this day, come back on the fixed return date",
        # which is a different question — and a different cache entry — from the one-way strip.
        key = f"{key}|r{ret.isoformat()}"

    async with get_session() as session:
        hit = await cached_offers(session, key, settings.cache_ttl_seconds)
    if hit:
        found = {q.depart_at: q.price for q in hit}
        return [(day, found.get(day.isoformat())) for day in days]

    gate = asyncio.Semaphore(CALENDAR_CONCURRENCY)

    async def cheapest(day: date) -> int | None:
        async with gate:
            try:
                offers = await kiwi.fetch(origin, destination, day, opts, ret)
            except Exception as e:
                log.warning("calendar day failed %s %s: %s", origin, day, e)
                return None
        return min((o.price for o in offers), default=None)

    prices = await asyncio.gather(*(cheapest(day) for day in days))
    strip = list(zip(days, prices))

    priced = [
        Quote(source=kiwi.SOURCE, price=p, currency=opts.currency, depart_at=d.isoformat())
        for d, p in strip
        if p is not None
    ]
    if priced:
        async with get_session() as session:
            await store_offers(session, key, priced)
    return strip


def dedupe(offers: list[Quote]) -> list[Quote]:
    """Sources overlap — the same physical flight can come back from several of them. Keep the
    cheapest quote per flight so the digest reads like a booking board, not a log.

    Identity is (departure time, stops) rather than the flight number: sources disagree on the
    number (codeshares) or omit it entirely, but on one route and day two itineraries almost never
    leave at the same minute with the same number of stops. That is what makes the comparison work
    — the same seat quoted by three sites collapses to the cheapest of the three.

    On a round trip the return leg joins the key, because two trips can share an outbound flight
    and come back on different ones — collapsing those would hide the cheaper pairing."""
    best: dict[tuple, Quote] = {}
    for o in offers:
        key = (
            (o.depart_at, o.stops, o.return_at)
            if o.depart_at
            else (o.flight_number or o.airline, None, o.return_at)
        )
        if key not in best or o.price < best[key].price:
            best[key] = o
    return sorted(best.values(), key=lambda o: o.price)
