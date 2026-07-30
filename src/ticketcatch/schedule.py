"""When a watch is due for its next digest.

The poller used to fire every POLL_INTERVAL_SECONDS counted from whenever the process happened to
start, which means the delivery time drifted with every restart and could land at 4am. A price
digest is only useful at an hour the reader is awake, so the schedule is expressed the way a person
states it — "morning and evening, my time" — and the loop just ticks often enough to notice.

Pure: no I/O, no database, no clock of its own. Everything takes `now` so it can be tested.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# The evening digest is the morning one half a day later. One setting instead of two, because
# "when do you want to hear from me" is one question, and 12h apart is what twice a day means.
SLOT_GAP_HOURS = 12

# Two sends must not fall in the same slot. The tick is finer than an hour, so the local hour
# matches several times in a row; this is what makes only the first of them count. It sits below
# SLOT_GAP_HOURS so a slot is never skipped when a tick runs a little late.
MIN_GAP_HOURS = 10

DEFAULT_HOUR = 9
DEFAULT_TZ = "Asia/Seoul"

# The country a ticket is bought from is also, almost always, the country the buyer is sitting in —
# so the market picks the time zone and the user only corrects it if they are the exception.
MARKET_TZ: dict[str, str] = {
    "kr": "Asia/Seoul",
    "uz": "Asia/Tashkent",
    "us": "America/New_York",
    "ru": "Europe/Moscow",
    "kz": "Asia/Almaty",
    "tr": "Europe/Istanbul",
    "ae": "Asia/Dubai",
    "de": "Europe/Berlin",
    "gb": "Europe/London",
    "jp": "Asia/Tokyo",
}

# Offered in the picker. Morning only: the evening slot follows from it.
HOUR_CHOICES: tuple[int, ...] = (6, 7, 8, 9, 10, 11, 12, 13)


def tz_for_market(code: str) -> str:
    return MARKET_TZ.get(code.lower(), DEFAULT_TZ)


def zone(name: str) -> ZoneInfo | timezone:
    """The named zone, or UTC if this machine has no tz database. A missing tzdata should cost an
    hour of accuracy, never a crashed poll cycle."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return timezone.utc


def local_time(now: datetime, tz_name: str) -> datetime:
    return now.astimezone(zone(tz_name))


def slots(hour: int) -> tuple[int, int]:
    """The two local hours a user hears from us. 21 → (21, 9): the day rolls over."""
    first = hour % 24
    return first, (first + SLOT_GAP_HOURS) % 24


def slot_label(hour: int) -> str:
    """'09:00 · 21:00' — how the setting reads back, in any language."""
    return " · ".join(f"{h:02d}:00" for h in slots(hour))


def is_due(
    now: datetime, tz_name: str, hour: int, last_sent_at: datetime | None = None
) -> bool:
    """Should this watch be priced and sent on this tick?

    A watch that has never been sent is due at once — someone who just added a route should not
    wait until tomorrow morning to see whether it was worth adding."""
    if last_sent_at is None:
        return True
    if local_time(now, tz_name).hour not in slots(hour):
        return False
    since = last_sent_at if last_sent_at.tzinfo else last_sent_at.replace(tzinfo=timezone.utc)
    return now - since >= timedelta(hours=MIN_GAP_HOURS)
