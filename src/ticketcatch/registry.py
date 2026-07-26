from collections.abc import Awaitable, Callable
from datetime import date

from .sources import Quote, googleflights, kiwi

# source name -> async fetch(origin, destination, depart_date) -> list[Quote]
# The poller merges every registered source, so the digest shows the union of their offers.
# Only sources that quote a live, bookable fare are registered:
#   - duffel: free tier is test-mode, invents fake airlines and fares.
#   - aviasales: returns one *cached* fare that may already be gone by the time we send it.
SOURCES: dict[str, Callable[[str, str, date], Awaitable[list[Quote]]]] = {
    kiwi.SOURCE: kiwi.fetch,  # bookable fares + per-itinerary booking link, priced for our market
    googleflights.SOURCE: googleflights.fetch,  # cross-check, covers carriers Kiwi lacks
}
