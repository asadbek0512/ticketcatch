from datetime import date
from urllib.parse import quote_plus

import httpx

from ..config import settings
from . import Quote, SourceError

SOURCE = "duffel"
# Duffel Flight Offers API. Unlike the Travelpayouts cached-cheapest endpoint, a single
# offer_request returns EVERY airline's live offer for the route+date — the full schedule.
API = "https://api.duffel.com/air/offer_requests"
DUFFEL_VERSION = "v2"
CABIN_CLASS = "economy"
TIMEOUT = 40  # live airline search is slower than a cache lookup


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.duffel_token}",
        "Duffel-Version": DUFFEL_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def fetch(origin: str, destination: str, depart: date) -> list[Quote]:
    """Live offers for origin->destination on the given day, one Quote per airline offer."""
    if not settings.duffel_token:
        raise SourceError("duffel: DUFFEL_TOKEN not set")

    body = {
        "data": {
            "slices": [
                {
                    "origin": origin.upper(),
                    "destination": destination.upper(),
                    "departure_date": depart.isoformat(),
                }
            ],
            "passengers": [{"type": "adult"}],
            "cabin_class": CABIN_CLASS,
        }
    }
    # return_offers=true inlines the offers so we avoid a second round trip.
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=_headers()) as client:
        resp = await client.post(API, params={"return_offers": "true"}, json=body)
    if resp.status_code not in (200, 201):
        raise SourceError(f"duffel: HTTP {resp.status_code} — {resp.text[:200]}")

    offers = (resp.json().get("data") or {}).get("offers") or []
    if not offers:
        raise SourceError(f"duffel: 0 offers for {origin}-{destination} {depart.isoformat()}")

    deep_link = _google_flights(origin, destination, depart)
    quotes: list[Quote] = []
    for offer in offers:
        price = _to_int(offer.get("total_amount"))
        if price is None:
            continue
        quotes.append(
            Quote(
                source=SOURCE,
                price=price,
                currency=str(offer.get("total_currency") or settings.currency).lower(),
                airline=_airline(offer),
                flight_number=_flight_number(offer),
                depart_at=_depart_at(offer),
                deep_link=deep_link,
            )
        )
    if not quotes:
        raise SourceError(f"duffel: offers had no usable price for {origin}-{destination}")
    return _cheapest_per_flight(quotes)


def _cheapest_per_flight(quotes: list[Quote]) -> list[Quote]:
    """Duffel returns several fare offers per physical flight; collapse them to one row per
    flight (cheapest fare) so the digest reads like a real departure schedule, not a fare dump."""
    best: dict[tuple[str, str], Quote] = {}
    for q in quotes:
        key = (q.flight_number, q.depart_at)
        if key not in best or q.price < best[key].price:
            best[key] = q
    return list(best.values())


def _to_int(amount: str | None) -> int | None:
    try:
        return round(float(amount))
    except (TypeError, ValueError):
        return None


def _airline(offer: dict) -> str:
    owner = offer.get("owner") or {}
    return str(owner.get("name") or owner.get("iata_code") or "")


def _first_segment(offer: dict) -> dict:
    """The first segment of the first slice — the departing leg we show in the digest."""
    slices = offer.get("slices") or []
    if not slices:
        return {}
    segments = slices[0].get("segments") or []
    return segments[0] if segments else {}


def _flight_number(offer: dict) -> str:
    seg = _first_segment(offer)
    carrier = seg.get("marketing_carrier") or {}
    code = carrier.get("iata_code") or ""
    number = seg.get("marketing_carrier_flight_number") or ""
    return f"{code}{number}".strip()


def _depart_at(offer: dict) -> str:
    return str(_first_segment(offer).get("departing_at") or "")


def _google_flights(origin: str, destination: str, depart: date) -> str:
    """Duffel offers are booked programmatically, not via a public URL — so we hand the user a
    Google Flights search for the same route+date as a practical 'go book it' link."""
    q = quote_plus(f"Flights from {origin.upper()} to {destination.upper()} on {depart.isoformat()}")
    return f"https://www.google.com/travel/flights?q={q}"
