"""The inline menu: pick where from, where to, which day — then search, watch or change settings.

Callback data is a short `verb:arg` string because Telegram caps it at 64 bytes, and every screen
is rebuilt from the user's stored Preference rather than from message state, so a menu still works
after a bot restart or when the user scrolls back to an old message.
"""

from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import airports, money
from .i18n import LANG_NAMES, day_label, t
from .models import Preference, Watch

AIRPORT_COLUMNS = 3
REGION_COLUMNS = 2
DATE_CHOICES = 14  # days offered as buttons, starting tomorrow
RETURN_CHOICES = 14  # return dates offered, counted from the outbound day
DATE_COLUMNS = 2
CURRENCY_COLUMNS = 3
MARKET_COLUMNS = 2
FIELDS = ("origin", "destination", "depart")


def _rows(buttons: list[InlineKeyboardButton], columns: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + columns] for i in range(0, len(buttons), columns)]


def _back(lang: str, to: str = "panel") -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=to)]


# --- panel -------------------------------------------------------------------------------------


def panel_text(pref: Preference) -> str:
    lang = pref.lang
    return "\n".join(
        (
            t(lang, "panel_title"),
            "",
            f"<b>{airports.label(pref.origin)} → {airports.label(pref.destination)}</b>",
            t(lang, "panel_date", date=f"{day_label(pref.depart_date, lang)} · {pref.depart_date}"),
            (
                t(lang, "panel_return", date=f"{day_label(pref.return_date, lang)} · {pref.return_date}")
                if pref.return_date
                else t(lang, "panel_oneway")
            ),
            t(
                lang,
                "panel_money",
                market=money.market_label(pref.market, lang),
                currency=pref.currency.upper(),
            ),
            "",
            t(lang, "panel_hint"),
        )
    )


def panel_keyboard(pref: Preference) -> InlineKeyboardMarkup:
    lang = pref.lang
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"📍 {pref.origin}", callback_data="pick:origin"),
                InlineKeyboardButton(text=t(lang, "btn_swap"), callback_data="swap"),
                InlineKeyboardButton(text=f"🎯 {pref.destination}", callback_data="pick:destination"),
            ],
            [
                InlineKeyboardButton(
                    text=f"📅 {day_label(pref.depart_date, lang)}", callback_data="pick:depart"
                ),
                InlineKeyboardButton(
                    text=(
                        f"🔁 {day_label(pref.return_date, lang)}"
                        if pref.return_date
                        else t(lang, "btn_roundtrip")
                    ),
                    callback_data="pick:ret",
                ),
            ],
            [InlineKeyboardButton(text=t(lang, "btn_search"), callback_data="go")],
            [
                InlineKeyboardButton(text=t(lang, "btn_cheapest_days"), callback_data="days"),
                InlineKeyboardButton(text=t(lang, "btn_watch"), callback_data="watch"),
            ],
            [
                InlineKeyboardButton(text=t(lang, "btn_watches"), callback_data="mine"),
                InlineKeyboardButton(text=t(lang, "btn_settings"), callback_data="cfg"),
                InlineKeyboardButton(text=t(lang, "btn_help"), callback_data="help"),
            ],
        ]
    )


def start_keyboard(lang: str) -> InlineKeyboardMarkup:
    """First screen: one obvious way in, plus the two things a new user asks for next."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_search"), callback_data="panel")],
            [
                InlineKeyboardButton(text=t(lang, "btn_settings"), callback_data="cfg"),
                InlineKeyboardButton(text=t(lang, "btn_help"), callback_data="help"),
            ],
        ]
    )


# --- airport pickers ---------------------------------------------------------------------------


def _airport_button(field: str, airport: airports.Airport) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"{airport.city}\n{airport.code}", callback_data=f"set:{field}:{airport.code}"
    )


def airport_keyboard(field: str, exclude: str, lang: str) -> InlineKeyboardMarkup:
    """The popular shortlist. The other end of the route is left out — you can't fly city→city."""
    buttons = [_airport_button(field, a) for a in airports.popular() if a.code != exclude.upper()]
    rows = _rows(buttons, AIRPORT_COLUMNS)
    rows.append(
        [
            InlineKeyboardButton(text=t(lang, "btn_more"), callback_data=f"reg:{field}"),
            InlineKeyboardButton(text=t(lang, "btn_type"), callback_data=f"manual:{field}"),
        ]
    )
    rows.append(_back(lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def region_keyboard(field: str, lang: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=t(lang, f"region_{region}"), callback_data=f"reg:{field}:{region}")
        for region in airports.REGIONS
    ]
    rows = _rows(buttons, REGION_COLUMNS)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_type"), callback_data=f"manual:{field}")])
    rows.append(_back(lang, f"pick:{field}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def region_airports_keyboard(
    field: str, region: str, exclude: str, lang: str
) -> InlineKeyboardMarkup:
    buttons = [
        _airport_button(field, a) for a in airports.in_region(region) if a.code != exclude.upper()
    ]
    rows = _rows(buttons, AIRPORT_COLUMNS)
    rows.append(_back(lang, f"reg:{field}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def results_keyboard(field: str, found: list[airports.Airport], lang: str) -> InlineKeyboardMarkup:
    """What free-text search found — one tap turns a typed city name into a chosen airport."""
    rows = _rows([_airport_button(field, a) for a in found], AIRPORT_COLUMNS)
    rows.append(_back(lang, f"pick:{field}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- date picker -------------------------------------------------------------------------------


def date_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Tomorrow onward — there is no point watching the price of a flight leaving today."""
    start = date.today() + timedelta(days=1)
    buttons = [
        InlineKeyboardButton(
            text=day_label(start + timedelta(days=i), lang),
            callback_data=f"set:depart:{(start + timedelta(days=i)).isoformat()}",
        )
        for i in range(DATE_CHOICES)
    ]
    rows = _rows(buttons, DATE_COLUMNS)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_other_date"), callback_data="manual:depart")])
    rows.append(_back(lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def days_keyboard(
    prices: list[tuple[date, int | None]], currency: str, lang: str
) -> InlineKeyboardMarkup:
    """A calendar strip with the price under each day, so a cheaper neighbouring date is one tap
    away instead of fourteen separate searches."""
    buttons = []
    for day, price in prices:
        tag = money.format_price(price, currency).rsplit(" ", 1)[0] if price else "—"
        buttons.append(
            InlineKeyboardButton(
                text=f"{day_label(day, lang)}\n{tag}",
                callback_data=f"set:depart:{day.isoformat()}",
            )
        )
    rows = _rows(buttons, DATE_COLUMNS)
    rows.append(_back(lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def return_date_keyboard(depart: date, current: date | None, lang: str) -> InlineKeyboardMarkup:
    """Return dates, offered as trip lengths from the outbound day.

    People book a return by how long they are staying — "a week", "two weeks" — not by scrolling a
    calendar to an absolute date, so the buttons are the days after departure rather than the days
    after today."""
    buttons = [
        InlineKeyboardButton(
            text=day_label(depart + timedelta(days=i), lang),
            callback_data=f"set:ret:{(depart + timedelta(days=i)).isoformat()}",
        )
        for i in range(1, RETURN_CHOICES + 1)
    ]
    rows = _rows(buttons, DATE_COLUMNS)
    rows.append(
        [InlineKeyboardButton(text=t(lang, "btn_other_date"), callback_data="manual:ret")]
    )
    if current:
        rows.append([InlineKeyboardButton(text=t(lang, "btn_clear_return"), callback_data="set:ret:")])
    rows.append(_back(lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- results -----------------------------------------------------------------------------------


def result_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "btn_refresh"), callback_data="go"),
                InlineKeyboardButton(text=t(lang, "btn_watch"), callback_data="watch"),
            ],
            [
                InlineKeyboardButton(text=t(lang, "btn_cheapest_days"), callback_data="days"),
                InlineKeyboardButton(text=t(lang, "btn_panel"), callback_data="panel"),
            ],
        ]
    )


def watches_keyboard(watches: list[Watch], lang: str) -> InlineKeyboardMarkup:
    """Each watch carries its own delete button — nobody should have to retype an id from a list."""
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"🗑 {w.origin}→{w.destination} · {w.depart_date.isoformat()}"
                    + (f" 🔁 {w.return_date.isoformat()}" if w.return_date else "")
                ),
                callback_data=f"del:{w.pk}",
            )
        ]
        for w in watches
    ]
    rows.append(_back(lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- settings ----------------------------------------------------------------------------------


def settings_text(pref: Preference) -> str:
    return t(
        pref.lang,
        "settings_title",
        lang=LANG_NAMES.get(pref.lang, pref.lang),
        currency=money.currency_label(pref.currency),
        market=money.market_label(pref.market, pref.lang),
    )


def settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "btn_lang"), callback_data="cfg:lang"),
                InlineKeyboardButton(text=t(lang, "btn_currency"), callback_data="cfg:cur"),
            ],
            [InlineKeyboardButton(text=t(lang, "btn_market"), callback_data="cfg:mkt")],
            _back(lang),
        ]
    )


def lang_keyboard(lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name, callback_data=f"setlang:{code}")]
        for code, name in LANG_NAMES.items()
    ]
    rows.append(_back(lang, "cfg"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def currency_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=label, callback_data=f"setcur:{code}")
        for code, label in money.CURRENCIES
    ]
    rows = _rows(buttons, CURRENCY_COLUMNS)
    rows.append(_back(lang, "cfg"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def market_keyboard(lang: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=f"{m.flag} {m.name(lang)}", callback_data=f"setmkt:{m.code}")
        for m in money.MARKETS
    ]
    rows = _rows(buttons, MARKET_COLUMNS)
    rows.append(_back(lang, "cfg"))
    return InlineKeyboardMarkup(inline_keyboard=rows)
