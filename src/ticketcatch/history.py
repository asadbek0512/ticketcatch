"""Turning a watch's stored prices into an answer to "should I buy now or wait?".

Pure formatting: it takes the (moment, cheapest price) sequence the database already holds and
renders a sparkline plus a verdict. No I/O, so the judgement is testable without a database — and
the judgement is the point. A list of numbers tells the user nothing they can act on.
"""

from datetime import datetime

from .i18n import MONTHS, t
from .money import format_price

BARS = "▁▂▃▄▅▆▇█"
SPARK_POINTS = 24  # bars that still fit one Telegram line on a narrow phone

# How close to the window's extremes a price has to be before we call it cheap or dear. Prices
# wobble by a few percent between captures, so "exactly the minimum" would almost never fire and
# would make the verdict useless on the day it matters most.
NEAR_LOW = 1.03
NEAR_HIGH = 0.97
FLAT_SPREAD = 0.02  # below this much difference between min and max there is no trend to report


def sparkline(prices: list[int]) -> str:
    """A bar per capture, scaled to this window. Relative, not absolute: the question is "is it
    high or low *for this route*", and a 400-dollar flight and a 40-dollar one both deserve a
    readable graph."""
    if not prices:
        return ""
    window = prices[-SPARK_POINTS:]
    low, high = min(window), max(window)
    if high == low:
        return BARS[0] * len(window)  # a flat line, not a random one
    span = high - low
    return "".join(BARS[round((p - low) / span * (len(BARS) - 1))] for p in window)


def verdict(prices: list[int], lang: str) -> str:
    """Cheap now, dear now, or neither — the sentence the user actually reads."""
    low, high, now = min(prices), max(prices), prices[-1]
    if high - low <= low * FLAT_SPREAD:
        return t(lang, "hist_flat")
    if now <= low * NEAR_LOW:
        return t(lang, "hist_low")
    if now >= high * NEAR_HIGH:
        return t(lang, "hist_high", percent=round((now - low) / low * 100))
    return t(lang, "hist_mid", percent=round((now - low) / low * 100))


def _stamp(at: datetime, lang: str) -> str:
    return f"{at.day} {MONTHS.get(lang, MONTHS['uz'])[at.month - 1]}"


def format_history(
    points: list[tuple[datetime, int]], currency: str, lang: str, route: str, when: str
) -> str:
    """The price-history card. Needs at least two captures to say anything: one point is a price,
    not a history, and drawing a single bar would imply a trend we haven't observed."""
    header = f"{t(lang, 'hist_title')}\n<b>{route}</b> · {when}"
    if len(points) < 2:
        return f"{header}\n\n{t(lang, 'hist_thin')}"

    prices = [p for _, p in points]
    low, high, now = min(prices), max(prices), prices[-1]
    first_at, last_at = points[0][0], points[-1][0]
    return "\n".join(
        (
            header,
            "",
            f"<code>{sparkline(prices)}</code>",
            f"<i>{_stamp(first_at, lang)} → {_stamp(last_at, lang)} · {len(points)}×</i>",
            "",
            t(lang, "hist_now", price=format_price(now, currency)),
            t(
                lang,
                "hist_range",
                low=format_price(low, currency),
                high=format_price(high, currency),
            ),
            "",
            verdict(prices, lang),
        )
    )


def suggestions(points: list[tuple[datetime, int]]) -> list[int]:
    """Threshold prices worth offering as buttons: a few steps under what the route costs today.

    Derived from the observed cheapest rather than fixed round numbers, because "alert me under
    500,000" means nothing until you know whether the route sells for 300,000 or 3,000,000."""
    if not points:
        return []
    low = min(p for _, p in points)
    steps = [round(low * (1 - cut) / 1000) * 1000 for cut in (0.05, 0.10, 0.15)]
    return [s for s in dict.fromkeys(steps) if s > 0]
