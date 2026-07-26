import re
from datetime import date

from ..config import settings
from . import Quote, SourceError

SOURCE = "tripcom"
# Trip.com has no public API and blocks plain HTTP with an Akamai challenge, so this source drives
# a real headless browser and reads the rendered result board. It is the one big OTA that answers
# from our server at all (Skyscanner serves a robot check even in a browser), and it regularly
# undercuts the others on the same flight.
HOST = "https://us.trip.com"  # the .us front gives English airline names; curr= still sets the price
SEARCH = (
    "{host}/flights/showfarefirst?dcity={origin}&acity={destination}&ddate={depart}"
    "&triptype=ow&class=y&quantity=1&locale=en-US&curr={currency}"
)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1500, "height": 1100}
CARD = "div.result-item"
NAV_TIMEOUT = 60_000
CARDS_TIMEOUT = 90_000
SETTLE_MS = 6_000  # prices stream in after the first cards render
SCROLL_STEPS = 10  # the board lazy-loads; stop early once the count stops growing
SCROLL_PX = 4_000
SCROLL_WAIT_MS = 2_000

# One pass over the rendered board. Everything read here is a stable data-testid or data-attribute,
# not a hashed class name — Trip.com re-hashes its CSS classes on every build.
_EXTRACT = """
() => Array.from(document.querySelectorAll('div.result-item')).map(el => {
  const text = s => { const e = el.querySelector(s); return e ? e.textContent.trim() : ''; };
  const price = el.querySelector('[data-testid^="flight_price"]');
  return {
    price: price ? price.getAttribute('data-price') : null,
    airline: Array.from(el.querySelectorAll('[data-testid=flights-name]'))
      .map(e => e.textContent.trim()).join(', '),
    times: Array.from(el.querySelectorAll('[data-testid^="flight-time-"]'))
      .map(e => e.getAttribute('data-testid').slice(12)),
    duration: text('[data-testid=flightInfoDuration]'),
    stops: text('[data-testid=stopInfoText]'),
    checked_bag: !!el.querySelector('[data-label-track=FREE_CHECKED_BAGGAGE]'),
  };
})
"""

_DURATION = re.compile(r"(?:(\d+)h)?\s*(?:(\d+)m)?")
_STOPS = re.compile(r"^(\d+)\s+stops?")


async def fetch(origin: str, destination: str, depart: date) -> list[Quote]:
    """Trip.com's own result board for that route and day, priced in our currency."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:  # keep the other sources alive on a host without the browser
        raise SourceError(f"tripcom: playwright not installed ({e})") from e

    url = SEARCH.format(
        host=HOST,
        origin=origin.lower(),
        destination=destination.lower(),
        depart=depart.isoformat(),
        currency=settings.currency.upper(),
    )

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = await browser.new_context(user_agent=UA, locale="en-US", viewport=VIEWPORT)
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            try:
                await page.wait_for_selector(CARD, timeout=CARDS_TIMEOUT)
            except Exception as e:
                raise SourceError(f"tripcom: no results rendered for {origin}-{destination}") from e
            await page.wait_for_timeout(SETTLE_MS)
            await _scroll_to_end(page)
            rows = await page.evaluate(_EXTRACT)
        finally:
            await browser.close()

    quotes = [q for row in rows if (q := _to_quote(row, url))]
    if not quotes:
        raise SourceError(f"tripcom: 0 offers for {origin}-{destination} {depart.isoformat()}")
    return quotes


async def _scroll_to_end(page) -> None:
    seen = 0
    for _ in range(SCROLL_STEPS):
        await page.mouse.wheel(0, SCROLL_PX)
        await page.wait_for_timeout(SCROLL_WAIT_MS)
        count = await page.locator(CARD).count()
        if count == seen:
            return
        seen = count


def _to_quote(row: dict, url: str) -> Quote | None:
    price = row.get("price")
    if not price:
        return None
    return Quote(
        source=SOURCE,
        price=round(float(price)),
        currency=settings.currency.lower(),
        airline=row.get("airline") or "",
        flight_number="",  # the collapsed card doesn't carry it; dedupe falls back to departure time
        depart_at=_stamp((row.get("times") or [None])[0]),
        deep_link=url,  # Trip.com has no per-itinerary link until the card is opened
        stops=_stops(row.get("stops") or ""),
        duration_min=_duration(row.get("duration") or ""),
        bags=1 if row.get("checked_bag") else None,  # absent label means unknown, not zero
    )


def _stamp(raw: str | None) -> str:
    """'2026-08-15 16:35:00' -> '2026-08-15 16:35' (local time at the departure airport)."""
    return raw[:16] if raw else ""


def _stops(raw: str) -> int | None:
    """'Nonstop' | '3 stops in Beijing, Hangzhou, Xi'an' | '6h 40m in Beijing' (a single stop)."""
    if not raw:
        return None
    if "nonstop" in raw.lower():
        return 0
    match = _STOPS.match(raw)
    return int(match.group(1)) if match else 1


def _duration(raw: str) -> int | None:
    """'7h 40m' -> 460."""
    match = _DURATION.match(raw.strip())
    if not match or not any(match.groups()):
        return None
    hours, minutes = match.groups()
    return int(hours or 0) * 60 + int(minutes or 0)
