import re
from datetime import date

from ..browser import BrowserUnavailable, new_page
from . import Quote, SearchOpts, SourceError, airline_name

SOURCE = "tripcom"
# Trip.com has no public API and blocks plain HTTP with an Akamai challenge, so this source drives
# a real headless browser and reads the rendered result board. It is the one big OTA that answers
# from our server at all (Skyscanner serves a robot check even in a browser), and it regularly
# undercuts the others on the same flight.
#
# The regional front matters: Trip.com prices the same seat differently per point of sale, and the
# ticket is bought from MARKET. On ICN-TAS the .kr front ran ~0.9% under .us and matched what the
# user sees in their own browser, so the front follows MARKET rather than being pinned to English.
# The cost is that its airline names come back in the local language — hence _airline() below.
HOST = "https://{market}.trip.com"
SEARCH = (
    "{host}/flights/showfarefirst?dcity={origin}&acity={destination}&ddate={depart}"
    "&triptype={triptype}&class=y&quantity=1&locale=en-US&curr={currency}"
)
# A round trip adds the return date and flips the trip type. The board still lists one card per
# outbound option, priced for the pair — same shape as one-way, so the parser is unchanged.
RETURN_SEARCH = SEARCH + "&rdate={ret}"
# Sort tabs are "recommended | nonstop first | cheapest", and the page opens on recommended — which
# is not the cheapest board. The testid is language-independent; the visible label is not.
CHEAPEST_TAB = "[data-testid=sort_bar_title_cheapest]"
CARD = "div.result-item"
NAV_TIMEOUT = 60_000
CARDS_TIMEOUT = 90_000
SETTLE_MS = 6_000  # prices stream in after the first cards render
RESORT_MS = 6_000  # switching sort tabs re-fetches the board
SCROLL_STEPS = 14
SCROLL_PX = 5_000
SCROLL_WAIT_MS = 1_800
IDLE_SCROLLS = 3  # the board pauses mid-load, so one flat pass doesn't mean the end

# One pass over the rendered board. Everything read here is a stable data-testid or data-attribute,
# not a hashed class name — Trip.com re-hashes its CSS classes on every build.
_EXTRACT = """
() => Array.from(document.querySelectorAll('div.result-item')).map(el => {
  const text = s => { const e = el.querySelector(s); return e ? e.textContent.trim() : ''; };
  const price = el.querySelector('[data-testid^="flight_price"]');
  return {
    price: price ? price.getAttribute('data-price') : null,
    // The rendered price, symbol and all. data-price is a bare number, so this is the only place
    // the board says which money it is quoting — see _renders_currency().
    price_text: price ? price.textContent.trim() : '',
    // The logo filename is the IATA code — the only carrier identifier on the card that isn't
    // written in the front's own language.
    codes: Array.from(el.querySelectorAll('img.logo-img'))
      .map(e => (e.getAttribute('src') || '').split('/').pop().split('.')[0]),
    times: Array.from(el.querySelectorAll('[data-testid^="flight-time-"]'))
      .map(e => e.getAttribute('data-testid').slice(12)),
    duration: text('[data-testid=flightInfoDuration]'),
    stops: text('[data-testid=stopInfoText]'),
    checked_bag: !!el.querySelector('[data-label-track=FREE_CHECKED_BAGGAGE]'),
  };
})
"""

# The regional front writes its labels in the local language and ignores every locale override we
# tried, so the two numeric fields are read in whichever language they arrive: "7h 40m" / "7시간 40분",
# "Nonstop" / "직항", "2 stops in …" / "2회 경유". A stop count with no digits ("6h 40m in Beijing",
# "베이징 경유") is a single stop — hence the anchored patterns, which must not pick up the digits
# in a layover duration.
_HOURS = re.compile(r"(\d+)\s*(?:h\b|시간)")
_MINUTES = re.compile(r"(\d+)\s*(?:m\b|분)")
_STOP_COUNT = re.compile(r"^(\d+)\s*(?:stops?\b|회)")
_NONSTOP = ("nonstop", "direct", "직항")


async def fetch(
    origin: str,
    destination: str,
    depart: date,
    opts: SearchOpts | None = None,
    ret: date | None = None,
) -> list[Quote]:
    """Trip.com's own result board for that route and day, priced for the buyer's market."""
    opts = opts or SearchOpts.of()
    url = (RETURN_SEARCH if ret else SEARCH).format(
        host=HOST.format(market=opts.market),
        origin=origin.lower(),
        destination=destination.lower(),
        depart=depart.isoformat(),
        currency=opts.currency.upper(),
        triptype="rt" if ret else "ow",
        ret=ret.isoformat() if ret else "",
    )

    try:
        # The browser is shared process-wide and rationed by a semaphore, so this line may wait
        # for a free slot instead of starting a second Chromium.
        async with new_page() as page:
            await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            try:
                await page.wait_for_selector(CARD, timeout=CARDS_TIMEOUT)
            except Exception as e:
                raise SourceError(f"tripcom: no results rendered for {origin}-{destination}") from e
            await page.wait_for_timeout(SETTLE_MS)
            # Both boards, because neither is a superset: "recommended" is the only one carrying
            # the small direct carriers (Qanot Sharq, Uzbekistan Airways), while "cheapest" surfaces
            # long multi-stop fares the first board hides. Overlap is dropped by the poller's dedupe.
            rows = await _harvest(page)
            if await _sort_by_price(page):
                rows += await _harvest(page)
    except BrowserUnavailable as e:  # keep the other sources alive on a host without the browser
        raise SourceError(f"tripcom: {e}") from e

    shown = next((r.get("price_text") or "" for r in rows if r.get("price_text")), "")
    if shown and not _renders_currency(shown, opts.currency):
        # The front ignored curr= and priced the board in something else. Trip.com has no Uzbek
        # point of sale, for instance, and uz.trip.com quietly answers in Polish złoty — labelling
        # "PLN 897" as 897 so'm is not a small error, it is a number that destroys the whole point
        # of a price bot. Losing one source is the cheap outcome here.
        raise SourceError(
            f"tripcom: asked for {opts.currency.upper()}, board shows {shown!r} — dropping"
        )

    quotes = [q for row in rows if (q := _to_quote(row, url, opts))]
    if not quotes:
        raise SourceError(f"tripcom: 0 offers for {origin}-{destination} {depart.isoformat()}")
    return quotes


# What each currency looks like once a rendered price has had its digits taken away. Only the marks
# Trip.com actually prints — this is a check that the board agrees with us, not a currency library.
_CURRENCY_MARKS: dict[str, tuple[str, ...]] = {
    "krw": ("₩", "원", "krw"),
    "usd": ("$", "usd"),
    # "so'm" arrives here as "som": the apostrophe is stripped with the digit separators, since
    # Swiss-style grouping writes 1'234 and we cannot keep one without keeping the other.
    "uzs": ("uzs", "som", "sum", "сўм", "сум"),
    "rub": ("₽", "rub", "руб"),
    "eur": ("€", "eur"),
    "kzt": ("₸", "kzt"),
    "try": ("₺", "try", "tl"),
    "jpy": ("¥", "円", "jpy"),
    "aed": ("aed", "د.إ"),
    "gbp": ("£", "gbp"),
}
_PRICE_NOISE = re.compile(r"[\d\s,. ']+")
_ANY_CODE = re.compile(r"[A-Z]{3}")


def _renders_currency(price_text: str, currency: str) -> bool:
    """Does the board's own price label agree with the currency we asked for?

    Strip the number and what remains is the money: "347,500원" leaves 원, "PLN 897" leaves PLN. A
    match is required, and a three-letter code belonging to someone else is an outright veto — that
    is what catches a front silently falling back to a currency we never asked about."""
    mark = _PRICE_NOISE.sub("", price_text).strip()
    if not mark:
        return False
    wanted = _CURRENCY_MARKS.get(currency.lower())
    if not wanted:  # a currency we hold no marks for: nothing to check it against, so don't guess
        return True
    lowered = mark.lower()
    # A three-letter run is only foreign if it is neither our code nor one of our own spelled-out
    # marks — "som" is the word so'm, not somebody else's currency code.
    foreign = {
        c
        for c in _ANY_CODE.findall(mark.upper())
        if c.lower() != currency.lower() and c.lower() not in wanted
    }
    return not foreign and any(m in lowered for m in wanted)


async def _harvest(page) -> list[dict]:
    await _scroll_to_end(page)
    return await page.evaluate(_EXTRACT)


async def _sort_by_price(page) -> bool:
    """Switch to the cheapest board. Never fails the source — a missing tab just means one board."""
    try:
        tab = page.locator(CHEAPEST_TAB).first
        if not await tab.count():
            return False
        await tab.click()
        await page.wait_for_timeout(RESORT_MS)
        return True
    except Exception:
        return False


async def _scroll_to_end(page) -> None:
    """The board lazy-loads on scroll; stop once the count holds still for a few passes."""
    seen, idle = 0, 0
    for _ in range(SCROLL_STEPS):
        await page.mouse.wheel(0, SCROLL_PX)
        await page.wait_for_timeout(SCROLL_WAIT_MS)
        count = await page.locator(CARD).count()
        if count == seen:
            idle += 1
            if idle >= IDLE_SCROLLS:
                return
        else:
            idle = 0
        seen = count


def _to_quote(row: dict, url: str, opts: SearchOpts) -> Quote | None:
    price = row.get("price")
    if not price:
        return None
    return Quote(
        source=SOURCE,
        price=round(float(price)),
        currency=opts.currency,
        airline=_airline(row.get("codes") or []),
        flight_number="",  # the collapsed card doesn't carry it; dedupe falls back to departure time
        depart_at=_stamp((row.get("times") or [None])[0]),
        deep_link=url,  # Trip.com has no per-itinerary link until the card is opened
        stops=_stops(row.get("stops") or ""),
        duration_min=_duration(row.get("duration") or ""),
        bags=1 if row.get("checked_bag") else None,  # absent label means unknown, not zero
    )


def _airline(codes: list[str]) -> str:
    """Carrier logos in card order -> 'Asiana Airlines, China Eastern'. The names come from the
    shared directory the other sources fill in, so the digest stays in one language."""
    seen = list(dict.fromkeys(c for c in codes if c))
    return ", ".join(airline_name(c) for c in seen)


def _stamp(raw: str | None) -> str:
    """'2026-08-15 16:35:00' -> '2026-08-15 16:35' (local time at the departure airport)."""
    return raw[:16] if raw else ""


def _stops(raw: str) -> int | None:
    """'Nonstop' | '직항' | '3 stops in Beijing, …' | '2회 경유' | '6h 40m in Beijing' (one stop)."""
    text = raw.strip()
    if not text:
        return None
    if any(token in text.lower() for token in _NONSTOP):
        return 0
    match = _STOP_COUNT.match(text)
    return int(match.group(1)) if match else 1


def _duration(raw: str) -> int | None:
    """'7h 40m' | '7시간 40분' -> 460."""
    hours = _HOURS.search(raw)
    minutes = _MINUTES.search(raw)
    if not hours and not minutes:
        return None
    total = (int(hours.group(1)) if hours else 0) * 60 + (int(minutes.group(1)) if minutes else 0)
    return total or None
