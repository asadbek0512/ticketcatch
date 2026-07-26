import asyncio
import json
from datetime import date

from fast_flights import FlightQuery, Passengers, create_query, fetch_flights_html
from selectolax.lexbor import LexborHTMLParser

from ..config import settings
from . import AIRLINE_NAMES, Quote, SourceError

SOURCE = "google"
# Google Flights returns the live, airline-by-airline board a booking site shows — real fares,
# real flight numbers, real stop counts. fast-flights only parses the "other flights" bucket,
# so we read the raw JSON payload ourselves and take BOTH buckets.
_BUCKET_TOP = 2  # "Top departing flights"
_BUCKET_REST = 3  # everything else on that date
_SCRIPT = r"script.ds\:1"


async def fetch(origin: str, destination: str, depart: date) -> list[Quote]:
    """One live Google Flights search → one Quote per itinerary, cheapest-first upstream."""
    return await asyncio.to_thread(_fetch_sync, origin, destination, depart)


def _fetch_sync(origin: str, destination: str, depart: date) -> list[Quote]:
    query = create_query(
        flights=[
            FlightQuery(
                date=depart.isoformat(),
                from_airport=origin.upper(),
                to_airport=destination.upper(),
            )
        ],
        trip="one-way",
        seat="economy",
        passengers=Passengers(adults=1),
        currency=settings.currency.upper(),
    )
    try:
        html = fetch_flights_html(query)
    except Exception as e:
        raise SourceError(f"google: fetch failed — {e}") from e

    payload = _payload(html)
    _learn_airlines(payload)
    link = query.url()
    quotes: list[Quote] = []
    for bucket in (_BUCKET_TOP, _BUCKET_REST):
        quotes.extend(_parse_bucket(payload, bucket, link))

    if not quotes:
        raise SourceError(f"google: 0 offers for {origin}-{destination} {depart.isoformat()}")
    return quotes


def _payload(html: str) -> list:
    """Google ships the results as a JS blob in a single <script class="ds:1"> tag."""
    script = LexborHTMLParser(html).css_first(_SCRIPT)
    if script is None:
        raise SourceError("google: results script not found (page shape changed or blocked)")
    try:
        raw = script.text().split("data:", 1)[1].rsplit(",", 1)[0]
        return json.loads(raw)
    except (IndexError, ValueError) as e:
        raise SourceError(f"google: payload unreadable — {e}") from e


def _learn_airlines(payload: list) -> None:
    """Google ships an [code, name] directory with every search — share it with code-only sources."""
    try:
        for code, name in payload[7][1][1]:
            AIRLINE_NAMES[str(code).upper()] = str(name)
    except (IndexError, TypeError, ValueError):
        pass


def _parse_bucket(payload: list, index: int, link: str) -> list[Quote]:
    """Each bucket is [ [itinerary, ...] , ...]; a malformed row is skipped, never fatal."""
    bucket = payload[index] if len(payload) > index else None
    rows = bucket[0] if isinstance(bucket, list) and bucket and isinstance(bucket[0], list) else []

    quotes: list[Quote] = []
    for row in rows:
        try:
            quotes.append(_to_quote(row, link))
        except (IndexError, KeyError, TypeError):
            continue
    return quotes


def _to_quote(row: list, link: str) -> Quote:
    itinerary, price = row[0], row[1][0][1]
    return Quote(
        source=SOURCE,
        price=int(price),
        currency=settings.currency.lower(),
        airline=", ".join(itinerary[1]) or itinerary[0],
        flight_number=_flight_number(itinerary),
        depart_at=_stamp(itinerary[4], itinerary[5]),
        deep_link=link,
        stops=max(len(itinerary[2] or []) - 1, 0),  # legs - 1; index 12 is not the stop count
        duration_min=itinerary[9],
    )


def _flight_number(itinerary: list) -> str:
    """Marketing carrier + number of the first leg, e.g. OZ573."""
    segments = itinerary[2] or []
    if not segments:
        return ""
    carrier = segments[0][22] or []
    return f"{carrier[0] or ''}{carrier[1] or ''}".strip()


def _stamp(day: list | None, clock: list | None) -> str:
    """Google gives [y, m, d] and [h, m] (minute omitted when :00) — render as ISO-ish local time."""
    if not day:
        return ""
    stamp = f"{day[0]:04d}-{day[1]:02d}-{day[2]:02d}"
    if clock:
        hour = clock[0] or 0
        minute = clock[1] if len(clock) > 1 and clock[1] else 0
        stamp += f" {hour:02d}:{minute:02d}"
    return stamp
