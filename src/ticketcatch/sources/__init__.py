import asyncio
import random
from dataclasses import dataclass
from datetime import date

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
}

_MIN_JITTER = 0.4
_MAX_JITTER = 1.6


@dataclass
class Quote:
    """One normalized flight offer — every source maps its response into this shape."""

    source: str
    price: int
    currency: str
    airline: str = ""
    flight_number: str = ""
    depart_at: str = ""
    deep_link: str = ""
    stops: int | None = None  # 0 = nonstop; None = source doesn't say
    duration_min: int | None = None  # total travel time, minutes
    bags: int | None = None  # checked bags the price already includes


# IATA code -> airline name, learned at runtime from whichever source ships a directory
# (Google does). Sources that only report codes look up names here so "SC" reads "Shandong".
AIRLINE_NAMES: dict[str, str] = {}


def airline_name(code: str) -> str:
    return AIRLINE_NAMES.get(code.upper(), code)


class SourceError(RuntimeError):
    """Raised when a source returns zero offers — fail loud, never silently skip a route."""


async def fetch_json(url: str, params: dict | None = None) -> dict:
    """Single human-paced GET returning JSON. Caller decides cadence; we add small jitter."""
    await asyncio.sleep(random.uniform(_MIN_JITTER, _MAX_JITTER))
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


# A source is: async fetch(origin, destination, depart_date) -> list[Quote]
FetchArgs = tuple[str, str, date]
