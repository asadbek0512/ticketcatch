import httpx

from datetime import date

from . import Quote, SearchOpts, SourceError, learn_airline

SOURCE = "kiwi"
# Kiwi.com's public search API — the one the website itself calls. Unlike a cached-fare feed it
# returns bookable itineraries: a real price for a real seat, a per-itinerary booking URL, and
# the baggage that price includes. It also carries small carriers the big engines miss (Qanot Sharq).
API = "https://api.skypicker.com/umbrella/v2/graphql"
BOOKING_HOST = "https://www.kiwi.com"
TIMEOUT = 60
LIMIT = 60  # the whole board for a day; the poller keeps only the cheapest TOP_N
STATION = "Station:airport:{}"

_SEGMENTS = """
sectorSegments {
  segment {
    code
    source { localTime station { code } }
    carrier { code name }
  }
}
"""

QUERY = (
    """
query($search: SearchOnewayInput, $filter: ItinerariesFilterInput, $options: ItinerariesOptionsInput) {
  onewayItineraries(search: $search, filter: $filter, options: $options) {
    __typename
    ... on Itineraries {
      itineraries {
        id
        duration
        price { amount }
        bagsInfo { includedCheckedBags }
        bookingOptions { edges { node { bookingUrl } } }
        ... on ItineraryOneWay { sector { %s } }
      }
    }
  }
}
"""
    % _SEGMENTS
)

# Round trips are a different root field with a different input type — the two legs are priced
# together, so this is not two one-way searches added up and is usually cheaper than that.
RETURN_QUERY = (
    """
query($search: SearchReturnInput, $filter: ItinerariesFilterInput, $options: ItinerariesOptionsInput) {
  returnItineraries(search: $search, filter: $filter, options: $options) {
    __typename
    ... on Itineraries {
      itineraries {
        id
        duration
        price { amount }
        bagsInfo { includedCheckedBags }
        bookingOptions { edges { node { bookingUrl } } }
        ... on ItineraryReturn {
          outbound { %s }
          inbound { %s }
        }
      }
    }
  }
}
"""
    % (_SEGMENTS, _SEGMENTS)
)


def _day(day: date) -> dict[str, str]:
    return {"start": f"{day.isoformat()}T00:00:00", "end": f"{day.isoformat()}T23:59:59"}


async def fetch(
    origin: str,
    destination: str,
    depart: date,
    opts: SearchOpts | None = None,
    ret: date | None = None,
) -> list[Quote]:
    """Every bookable itinerary for that route and day, priced for the buyer's market.

    With `ret` the two legs are priced as one round trip, which is a different — and normally
    cheaper — fare than the two one-way tickets added together."""
    opts = opts or SearchOpts.of()
    itinerary: dict[str, object] = {
        "source": {"ids": [STATION.format(origin.upper())]},
        "destination": {"ids": [STATION.format(destination.upper())]},
        "outboundDepartureDate": _day(depart),
    }
    if ret:
        itinerary["inboundDepartureDate"] = _day(ret)

    payload = {
        "query": RETURN_QUERY if ret else QUERY,
        "variables": {
            "search": {
                "itinerary": itinerary,
                "passengers": {"adults": 1, "children": 0, "infants": 0},
                "cabinClass": {"cabinClass": "ECONOMY", "applyMixedClasses": False},
            },
            "filter": {"limit": LIMIT},
            # partnerMarket decides the point of sale — fares differ by country, so this must be
            # the market the ticket is actually bought from, not wherever the server happens to run.
            "options": {
                "currency": opts.currency,
                "locale": "en",
                "partner": "skypicker",
                "partnerMarket": opts.market,
                "sortBy": "PRICE",
                "sortOrder": "ASCENDING",
            },
        },
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(API, json=payload, headers={"user-agent": "ticketcatch/1.0"})
    if resp.status_code != 200:
        raise SourceError(f"kiwi: HTTP {resp.status_code} — {resp.text[:200]}")

    body = resp.json()
    if body.get("errors"):
        raise SourceError(f"kiwi: {str(body['errors'])[:200]}")

    root = "returnItineraries" if ret else "onewayItineraries"
    result = (body.get("data") or {}).get(root) or {}
    if result.get("__typename") != "Itineraries":
        raise SourceError(f"kiwi: unexpected response {result.get('__typename')}")

    quotes = [q for it in result.get("itineraries") or [] if (q := _to_quote(it, opts))]
    if not quotes:
        raise SourceError(f"kiwi: 0 offers for {origin}-{destination} {depart.isoformat()}")
    return quotes


def _to_quote(itinerary: dict, opts: SearchOpts) -> Quote | None:
    price = (itinerary.get("price") or {}).get("amount")
    if price is None:
        return None

    # One-way puts the legs under `sector`; a round trip splits them into `outbound` + `inbound`.
    outbound = itinerary.get("sector") or itinerary.get("outbound") or {}
    segments = _legs(outbound)
    back = _legs(itinerary.get("inbound") or {})
    first = segments[0] if segments else {}
    carrier = first.get("carrier") or {}
    learn_airline(carrier.get("code"), carrier.get("name"))
    duration_sec = itinerary.get("duration")

    return Quote(
        source=SOURCE,
        price=round(float(price)),
        currency=opts.currency,
        airline=str(carrier.get("name") or carrier.get("code") or ""),
        flight_number=f"{carrier.get('code') or ''}{first.get('code') or ''}",
        depart_at=_stamp((first.get("source") or {}).get("localTime")),
        deep_link=_booking_url(itinerary),
        stops=max(len(segments) - 1, 0),
        duration_min=round(duration_sec / 60) if duration_sec else None,
        bags=(itinerary.get("bagsInfo") or {}).get("includedCheckedBags"),
        return_at=_stamp((back[0].get("source") or {}).get("localTime")) if back else "",
        return_stops=max(len(back) - 1, 0) if back else None,
    )


def _legs(sector: dict) -> list[dict]:
    return [s.get("segment") or {} for s in sector.get("sectorSegments") or []]


def _booking_url(itinerary: dict) -> str:
    """bookingUrl is host-relative and carries the token that pins this exact fare."""
    edges = (itinerary.get("bookingOptions") or {}).get("edges") or []
    path = (edges[0].get("node") or {}).get("bookingUrl") if edges else None
    return f"{BOOKING_HOST}{path}" if path else BOOKING_HOST


def _stamp(raw: str | None) -> str:
    """'2026-08-15T16:35:00' -> '2026-08-15 16:35' (local time at the departure airport)."""
    if not raw:
        return ""
    day, _, rest = raw.partition("T")
    return f"{day} {rest[:5]}".strip() if rest else day
