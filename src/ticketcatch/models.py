from datetime import date, datetime, timedelta, timezone

from sqlmodel import Field, SQLModel

from .config import settings

DEFAULT_LEAD_DAYS = 30  # a first-time menu opens on a date far enough out to have fares


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def default_depart() -> date:
    return date.today() + timedelta(days=DEFAULT_LEAD_DAYS)


def default_lang() -> str:
    return settings.default_lang


def default_currency() -> str:
    return settings.currency.lower()


def default_market() -> str:
    return settings.market.lower()


def route_key(origin: str, destination: str, depart: date) -> str:
    """Stable per-route+date key so an identical route is queried once and fanned out to
    every watcher, independent of which user asked for it."""
    return f"{origin.upper()}-{destination.upper()}-{depart.isoformat()}"


class Watch(SQLModel, table=True):
    """One user's standing request: watch this route + date, alert me when it's cheap."""

    pk: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)  # telegram chat id
    origin: str = "ICN"
    destination: str = "TAS"
    depart_date: date = Field(index=True)
    threshold_price: int | None = None  # fire a special alert when the cheapest drops below this
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    # Copied off the user's Preference when the watch is created, not read live: the alert
    # "↓ 40,000 KRW cheaper" only means anything if every capture of this watch is priced the
    # same way, so changing your currency later must not rewrite the history of an old watch.
    currency: str = Field(default_factory=default_currency)
    market: str = Field(default_factory=default_market)
    lang: str = Field(default_factory=default_lang)


class Preference(SQLModel, table=True):
    """What the menu is currently pointed at, per user. Kept in the DB rather than in FSM state
    so the route a user picked survives a bot restart — the menu reopens where they left it."""

    pk: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True, unique=True)  # telegram chat id
    origin: str = "ICN"
    destination: str = "TAS"
    depart_date: date = Field(default_factory=default_depart)
    lang: str = Field(default_factory=default_lang)
    currency: str = Field(default_factory=default_currency)
    market: str = Field(default_factory=default_market)  # country the ticket is bought from
    searches: int = 0  # how many live searches this user has run — feeds /stats, not billing


class PriceQuote(SQLModel, table=True):
    """A single captured price for a route+date. Kept as history so we can say '↓ $30 cheaper'."""

    pk: int | None = Field(default=None, primary_key=True)
    route_key: str = Field(index=True)  # models.route_key(...) — user-independent
    source: str = ""  # kiwi | google
    price: int = 0
    currency: str = "usd"
    airline: str = ""
    flight_number: str = ""
    depart_at: str = ""  # source's raw departure timestamp
    deep_link: str = ""
    stops: int | None = None  # 0 = nonstop
    duration_min: int | None = None
    bags: int | None = None  # checked bags included in the price
    captured_at: datetime = Field(default_factory=utcnow, index=True)


class SearchCache(SQLModel, table=True):
    """One finished search, reusable for CACHE_TTL_SECONDS.

    Ten people asking for ICN→TAS on the same day should cost one browser run, not ten. It lives
    in the DB rather than in memory on purpose: the bot and the poller are separate processes, so
    a route the poller just refreshed answers the menu instantly, and vice versa."""

    pk: int | None = Field(default=None, primary_key=True)
    cache_key: str = Field(index=True)  # route + currency + market — prices differ by all three
    payload: str = ""  # JSON list of Quote dicts
    created_at: datetime = Field(default_factory=utcnow, index=True)
