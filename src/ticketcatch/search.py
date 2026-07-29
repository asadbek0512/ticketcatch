import logging
from datetime import date

from .registry import SOURCES
from .sources import Quote

log = logging.getLogger("ticketcatch")


async def fetch_offers(origin: str, destination: str, depart: date) -> list[Quote]:
    """Every registered source for one route+date, merged, deduped, cheapest first.

    Shared by the scheduled poller and the menu's on-demand search so both answer with the same
    board. A failing source is logged and skipped — one dead source never blanks a route."""
    merged: list[Quote] = []
    for name, fetch in SOURCES.items():
        try:
            merged.extend(await fetch(origin, destination, depart))
        except Exception as e:  # fail loud per-source, keep the others alive
            log.error("source failed [%s] %s-%s: %s", name, origin, destination, e)
    return dedupe(merged)


def dedupe(offers: list[Quote]) -> list[Quote]:
    """Sources overlap — the same physical flight can come back from several of them. Keep the
    cheapest quote per flight so the digest reads like a booking board, not a log.

    Identity is (departure time, stops) rather than the flight number: sources disagree on the
    number (codeshares) or omit it entirely, but on one route and day two itineraries almost never
    leave at the same minute with the same number of stops. That is what makes the comparison work
    — the same seat quoted by three sites collapses to the cheapest of the three."""
    best: dict[tuple, Quote] = {}
    for o in offers:
        key = (o.depart_at, o.stops) if o.depart_at else (o.flight_number or o.airline, None)
        if key not in best or o.price < best[key].price:
            best[key] = o
    return sorted(best.values(), key=lambda o: o.price)
