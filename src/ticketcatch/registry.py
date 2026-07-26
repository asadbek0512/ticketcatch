from collections.abc import Awaitable, Callable
from datetime import date

from .sources import Quote, aviasales, googleflights

# source name -> async fetch(origin, destination, depart_date) -> list[Quote]
# The poller merges every registered source, so the digest shows the union of their offers.
# duffel is deliberately absent: its free tier is test-mode only and invents fake airlines
# and fares, which would put made-up prices at the top of the digest.
SOURCES: dict[str, Callable[[str, str, date], Awaitable[list[Quote]]]] = {
    googleflights.SOURCE: googleflights.fetch,  # live airline-by-airline board, real fares
    aviasales.SOURCE: aviasales.fetch,  # cached cheapest + affiliate booking link
}
