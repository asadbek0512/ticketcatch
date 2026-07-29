"""The inline menu: pick where from, where to, which day — then search or start watching."""

from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .models import Preference

# Airports offered as buttons. One shared list for both ends so a return leg (TAS → ICN) is just
# as easy to pick as the outbound. Anything not listed goes through "type it myself".
AIRPORTS: list[tuple[str, str]] = [
    ("ICN", "Seul ICN"),
    ("GMP", "Seul GMP"),
    ("PUS", "Busan"),
    ("TAS", "Toshkent"),
    ("SKD", "Samarqand"),
    ("NMA", "Namangan"),
    ("BHK", "Buxoro"),
    ("UGC", "Urganch"),
    ("FEG", "Farg'ona"),
    ("IST", "Istanbul"),
    ("ALA", "Olmaota"),
    ("DME", "Moskva"),
]
AIRPORT_COLUMNS = 3
DATE_CHOICES = 14  # days offered as buttons, starting tomorrow
DATE_COLUMNS = 2

_MONTHS = ("yan", "fev", "mar", "apr", "may", "iyn", "iyl", "avg", "sen", "okt", "noy", "dek")
_WEEKDAYS = ("Du", "Se", "Ch", "Pa", "Ju", "Sha", "Yak")

FIELDS = ("origin", "destination", "depart")


def city(code: str) -> str:
    for iata, name in AIRPORTS:
        if iata == code.upper():
            return name
    return code.upper()


def day_label(day: date) -> str:
    return f"{day.day} {_MONTHS[day.month - 1]} ({_WEEKDAYS[day.weekday()]})"


def panel_text(pref: Preference) -> str:
    return (
        f"<b>✈️ {pref.origin} → {pref.destination}</b>\n"
        f"{city(pref.origin)} — {city(pref.destination)}\n"
        f"📅 {day_label(pref.depart_date)} · <code>{pref.depart_date.isoformat()}</code>\n\n"
        "O'zgartirmoqchi bo'lgan qismni bosing:"
    )


def panel_keyboard(pref: Preference) -> InlineKeyboardMarkup:
    """Every button shows its current value, so the panel doubles as the summary."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"📍 {pref.origin}", callback_data="pick:origin"),
                InlineKeyboardButton(text=f"🎯 {pref.destination}", callback_data="pick:destination"),
            ],
            [
                InlineKeyboardButton(
                    text=f"📅 {day_label(pref.depart_date)}", callback_data="pick:depart"
                )
            ],
            [InlineKeyboardButton(text="🔍 Hozir qidirish", callback_data="go")],
            [InlineKeyboardButton(text="🔔 Kuzatuvga qo'shish", callback_data="watch")],
        ]
    )


def airport_keyboard(field: str, exclude: str) -> InlineKeyboardMarkup:
    """The other end of the route is left out — a flight from a city to itself isn't a choice."""
    buttons = [
        InlineKeyboardButton(text=f"{name}\n{code}", callback_data=f"set:{field}:{code}")
        for code, name in AIRPORTS
        if code != exclude.upper()
    ]
    rows = [
        buttons[i : i + AIRPORT_COLUMNS] for i in range(0, len(buttons), AIRPORT_COLUMNS)
    ]
    rows.append([InlineKeyboardButton(text="✏️ O'zim yozaman", callback_data=f"manual:{field}")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def date_keyboard() -> InlineKeyboardMarkup:
    """Tomorrow onward — today's flights are past the point of watching a price."""
    start = date.today() + timedelta(days=1)
    days = [start + timedelta(days=i) for i in range(DATE_CHOICES)]
    buttons = [
        InlineKeyboardButton(text=day_label(d), callback_data=f"set:depart:{d.isoformat()}")
        for d in days
    ]
    rows = [buttons[i : i + DATE_COLUMNS] for i in range(0, len(buttons), DATE_COLUMNS)]
    rows.append([InlineKeyboardButton(text="✏️ Boshqa sana", callback_data="manual:depart")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Qayta qidirish", callback_data="go")],
            [InlineKeyboardButton(text="🔔 Kuzatuvga qo'shish", callback_data="watch")],
            [InlineKeyboardButton(text="⬅️ Menyu", callback_data="panel")],
        ]
    )
