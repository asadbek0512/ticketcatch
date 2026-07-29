import asyncio
import random
from dataclasses import dataclass
from datetime import date

import httpx

from ..config import settings

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


@dataclass(frozen=True)
class SearchOpts:
    """Point of sale for one search: where the ticket is bought and in what money.

    The same seat costs different amounts depending on the country you buy from, so this travels
    with every request instead of being read from the global settings. That is what lets one
    process serve a user in Korea and a user in Uzbekistan their own real prices."""

    currency: str = "krw"
    market: str = "kr"

    @classmethod
    def of(cls, currency: str | None = None, market: str | None = None) -> "SearchOpts":
        """Build from user values, falling back to the configured defaults."""
        return cls(
            currency=(currency or settings.currency).lower(),
            market=(market or settings.market).lower(),
        )

    @property
    def key(self) -> str:
        return f"{self.currency}@{self.market}"


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
# Carrier code -> readable name, filled in by whichever sources ship a directory (Google, Kiwi).
# Sources that only expose a code — or a name in the wrong language, as the Korean Trip.com front
# does — resolve through here so one shared lookup keeps the digest in one language.
AIRLINE_NAMES: dict[str, str] = {}


def airline_name(code: str) -> str:
    return AIRLINE_NAMES.get(code.upper(), code.upper())


def learn_airline(code: str | None, name: str | None) -> None:
    if code and name and str(code).upper() != str(name).upper():
        AIRLINE_NAMES.setdefault(str(code).upper(), str(name))


class SourceError(RuntimeError):
    """Raised when a source returns zero offers — fail loud, never silently skip a route."""


async def fetch_json(url: str, params: dict | None = None) -> dict:
    """Single human-paced GET returning JSON. Caller decides cadence; we add small jitter."""
    await asyncio.sleep(random.uniform(_MIN_JITTER, _MAX_JITTER))
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


# A source is: async fetch(origin, destination, depart_date, opts) -> list[Quote]
FetchArgs = tuple[str, str, date, SearchOpts]
