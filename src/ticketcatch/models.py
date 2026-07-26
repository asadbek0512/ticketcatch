from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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


class PriceQuote(SQLModel, table=True):
    """A single captured price for a route+date. Kept as history so we can say '↓ $30 cheaper'."""

    pk: int | None = Field(default=None, primary_key=True)
    route_key: str = Field(index=True)  # models.route_key(...) — user-independent
    source: str = ""  # google | aviasales
    price: int = 0
    currency: str = "usd"
    airline: str = ""
    flight_number: str = ""
    depart_at: str = ""  # source's raw departure timestamp
    deep_link: str = ""
    stops: int | None = None  # 0 = nonstop
    duration_min: int | None = None
    captured_at: datetime = Field(default_factory=utcnow, index=True)
