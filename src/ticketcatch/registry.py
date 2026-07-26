from collections.abc import Awaitable, Callable
from datetime import date

from .sources import Quote, aviasales, googleflights, kiwi, tripcom

# source name -> async fetch(origin, destination, depart_date) -> list[Quote]
# The poller merges every registered source, so the digest shows the union of their offers.
# duffel stays unregistered: its free tier is test-mode and invents airlines and fares.
SOURCES: dict[str, Callable[[str, str, date], Awaitable[list[Quote]]]] = {
    kiwi.SOURCE: kiwi.fetch,  # bookable fares + per-itinerary booking link, priced for our market
    googleflights.SOURCE: googleflights.fetch,  # cross-check, covers carriers Kiwi lacks
    aviasales.SOURCE: aviasales.fetch,  # cached, but often undercuts the rest on the same flight
    tripcom.SOURCE: tripcom.fetch,  # OTA board, browser-driven; slowest source, so it runs last
}
