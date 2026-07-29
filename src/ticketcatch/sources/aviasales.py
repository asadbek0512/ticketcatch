from datetime import date

from ..config import settings
from . import Quote, SearchOpts, SourceError, airline_name, fetch_json

SOURCE = "aviasales"
# Travelpayouts "Aviasales Data API" — cheapest tickets for a route+date. Free with a token.
API = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
AVIASALES_WEB = "https://www.aviasales.com"
LIMIT = 30


async def fetch(
    origin: str, destination: str, depart: date, opts: SearchOpts | None = None
) -> list[Quote]:
    """Cheapest one-way offers for origin->destination on the given day, sorted by price."""
    opts = opts or SearchOpts.of()
    if not settings.travelpayouts_token:
        raise SourceError("aviasales: TRAVELPAYOUTS_TOKEN not set")

    params = {
        "origin": origin.upper(),
        "destination": destination.upper(),
        "departure_at": depart.isoformat(),
        "currency": opts.currency,
        "one_way": "true",
        "sorting": "price",
        "limit": LIMIT,
        "token": settings.travelpayouts_token,
    }
    payload = await fetch_json(API, params=params)
    rows = payload.get("data") or []
    if not rows:
        raise SourceError(f"aviasales: 0 offers for {origin}-{destination} {depart.isoformat()}")

    quotes: list[Quote] = []
    for row in rows:
        price = row.get("price")
        if not isinstance(price, (int, float)):
            continue
        quotes.append(
            Quote(
                source=SOURCE,
                price=int(price),
                currency=str(row.get("currency") or opts.currency).lower(),
                airline=airline_name(str(row.get("airline") or "")),
                flight_number=f"{row.get('airline') or ''}{row.get('flight_number') or ''}",
                depart_at=_stamp(row.get("departure_at")),
                deep_link=_deep_link(row.get("link")),
                stops=_int(row.get("transfers")),
                duration_min=_int(row.get("duration")),
            )
        )
    if not quotes:
        raise SourceError(f"aviasales: offers had no usable price for {origin}-{destination}")
    return quotes


def _int(value) -> int | None:
    return value if isinstance(value, int) else None


def _stamp(raw: str | None) -> str:
    """API sends '2026-08-15T22:55:00+09:00'; the digest only needs day + local clock time."""
    if not raw:
        return ""
    day, _, rest = raw.partition("T")
    return f"{day} {rest[:5]}".strip() if rest else day


def _deep_link(link: str | None) -> str:
    """The API returns a relative search path; prefix the host and attach the affiliate marker."""
    if not link:
        return AVIASALES_WEB
    url = AVIASALES_WEB + link if link.startswith("/") else link
    if settings.travelpayouts_marker:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}marker={settings.travelpayouts_marker}"
    return url
