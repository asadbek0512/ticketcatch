"""The inline menu: pick where from, where to, which day — then search, watch or change settings.

Callback data is a short `verb:arg` string because Telegram caps it at 64 bytes, and every screen
is rebuilt from the user's stored Preference rather than from message state, so a menu still works
after a bot restart or when the user scrolls back to an old message.
"""

from datetime import date, timedelta

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import airports, money, schedule
from .i18n import LANG_NAMES, day_label, t
from .models import Preference, Watch

AIRPORT_COLUMNS = 3
REGION_COLUMNS = 2
DATE_CHOICES = 14  # days offered as buttons, starting tomorrow
RETURN_CHOICES = 14  # return dates offered, counted from the outbound day
DATE_COLUMNS = 2
CURRENCY_COLUMNS = 3
MARKET_COLUMNS = 2
NOTIFY_COLUMNS = 2  # '09:00 · 21:00' is wide — two per row still fits a narrow phone
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


# Departure cities for the first screen. This bot searches 129 airports on every continent, and the
# first screen has to look like that — an opening menu of fixed routes out of one country tells
# everyone else the bot is not for them. These six are hubs on different continents, so whoever
# opens the bot sees at least one city they might actually leave from.
START_ORIGINS: tuple[str, ...] = ("TAS", "ICN", "SVO", "IST", "DXB", "ALA")

# Where people actually go from each of those hubs. Only ever shown after the traveller has told us
# where they are, so nobody is offered a corridor that has nothing to do with them; the "other city"
# button next to them opens the full 129 either way.
ROUTES_FROM: dict[str, tuple[str, ...]] = {
    "TAS": ("ICN", "SVO", "IST", "DXB", "ALA", "JFK"),
    "ICN": ("TAS", "SKD", "NMA", "FEG", "BHK", "UGC"),
    "SVO": ("TAS", "SKD", "NMA", "IST", "DXB", "ALA"),
    "IST": ("TAS", "SKD", "ICN", "DXB", "SVO", "JFK"),
    "DXB": ("TAS", "SKD", "ICN", "IST", "DEL", "SVO"),
    "ALA": ("TAS", "IST", "DXB", "ICN", "SVO", "NQZ"),
}
ROUTE_COLUMNS = 2
RECENT_ROUTES = 2  # how many of the traveller's own routes get a one-tap button


def _short_city(code: str) -> str:
    """"Seul Incheon" → "Seul". Two of these plus an arrow have to fit on half a phone screen, and
    a label Telegram truncates mid-word is worse than a slightly less precise one — the airport code
    is still what gets searched."""
    return airports.city(code).split()[0]


def _route_button(origin: str, destination: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=f"{_short_city(origin)} → {_short_city(destination)}",
        callback_data=f"route:{origin}:{destination}",
    )


def start_keyboard(lang: str, recent: tuple[tuple[str, str], ...] = ()) -> InlineKeyboardMarkup:
    """First screen: where are you flying from?

    Someone who has used the bot before gets their own routes on top, priced in one tap — that is
    the fastest this can be, and it is personal rather than guessed. Everyone else picks a departure
    city and then a destination, which is two taps to a real price and, unlike a fixed list of
    routes, works the same whether they are in Tashkent, Almaty or New York."""
    rows: list[list[InlineKeyboardButton]] = [
        [_route_button(origin, destination)]
        for origin, destination in recent[:RECENT_ROUTES]
        if airports.is_iata(origin) and airports.is_iata(destination)
    ]
    rows += _rows(
        [
            InlineKeyboardButton(
                text=f"{airports.flag(code)} {_short_city(code)}",
                callback_data=f"from:{code}",
            )
            for code in START_ORIGINS
        ],
        ROUTE_COLUMNS,
    )
    rows.append([InlineKeyboardButton(text=t(lang, "btn_other_route"), callback_data="panel")])
    rows.append(
        [
            InlineKeyboardButton(text=t(lang, "btn_settings"), callback_data="cfg"),
            InlineKeyboardButton(text=t(lang, "btn_help"), callback_data="help"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def depart_keyboard(lang: str) -> InlineKeyboardMarkup:
    """Third screen: the route is known, so ask the one thing that is genuinely theirs — the day.

    Same days as date_keyboard, but these buttons run the search instead of returning to the panel:
    at this point the traveller has already said everything the search needs."""
    start = date.today() + timedelta(days=1)
    buttons = [
        InlineKeyboardButton(
            text=day_label(start + timedelta(days=i), lang),
            callback_data=f"when:{(start + timedelta(days=i)).isoformat()}",
        )
        for i in range(DATE_CHOICES)
    ]
    rows = _rows(buttons, DATE_COLUMNS)
    rows.append(
        [
            InlineKeyboardButton(text=t(lang, "btn_other_date"), callback_data="manual:depart"),
            InlineKeyboardButton(text=t(lang, "btn_back_start"), callback_data="home"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def destination_keyboard(origin: str, lang: str) -> InlineKeyboardMarkup:
    """Second screen: having said where they are, where are they going?

    Tapping a city here does not fill in a form — it searches. The whole point of these two screens
    is that a stranger sees a real price before being asked to understand anything."""
    # Only the destination is named: the message above these buttons already says where the
    # traveller is leaving from, and repeating it on all six buttons costs the width that would
    # otherwise show the city.
    rows = _rows(
        [
            InlineKeyboardButton(
                text=f"{airports.flag(code)} {_short_city(code)}",
                callback_data=f"route:{origin}:{code}",
            )
            for code in ROUTES_FROM.get(origin, ())
        ],
        ROUTE_COLUMNS,
    )
    rows.append(
        [
            InlineKeyboardButton(text=t(lang, "btn_other_city"), callback_data=f"toany:{origin}"),
            InlineKeyboardButton(text=t(lang, "btn_back_start"), callback_data="home"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def result_keyboard(pref: Preference) -> InlineKeyboardMarkup:
    """What to do with a board you just searched for — including handing it to someone else, which
    is the moment a traveller is most likely to want to."""
    lang = pref.lang
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "btn_refresh"), callback_data="go"),
                InlineKeyboardButton(text=t(lang, "btn_watch"), callback_data="watch"),
            ],
            [
                InlineKeyboardButton(text=t(lang, "btn_cheapest_days"), callback_data="days"),
                share_button(pref.origin, pref.destination, pref.depart_date, lang),
            ],
            [InlineKeyboardButton(text=t(lang, "btn_panel"), callback_data="panel")],
        ]
    )


def watches_keyboard(watches: list[Watch], lang: str) -> InlineKeyboardMarkup:
    """One button per watch, opening it. The list used to delete on tap, which put the destructive
    action where the curious one belongs — and left history, alerts and pausing unreachable."""
    rows = [
        [
            InlineKeyboardButton(
                text=(
                    f"{'⏸' if w.paused else '🔔'} {w.origin}→{w.destination}"
                    f" · {w.depart_date.isoformat()}"
                    + (f" 🔁 {w.return_date.isoformat()}" if w.return_date else "")
                ),
                callback_data=f"w:{w.pk}",
            )
        ]
        for w in watches
    ]
    rows.append(_back(lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def share_button(origin: str, destination: str, depart: date, lang: str) -> InlineKeyboardButton:
    """Pass a route to a friend as a live query rather than a screenshot.

    switch_inline_query hands Telegram's own chat picker the text "ICN TAS 2026-09-25". Whoever
    receives it gets prices looked up at the moment they read the message, so a fare that has moved
    since is simply not quoted — which is the difference between a share that helps and a share
    that misleads a week later."""
    return InlineKeyboardButton(
        text=t(lang, "btn_share"),
        switch_inline_query=f"{origin} {destination} {depart.isoformat()}",
    )


def watch_keyboard(watch: Watch, lang: str) -> InlineKeyboardMarkup:
    """Everything you can do to one watch. Delete sits alone on the last row, away from the taps
    people make while browsing."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            # The stored prices are already on the card, so a live search is an explicit choice
            # here rather than the price of looking.
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_search_live"), callback_data=f"wgo:{watch.pk}"
                )
            ],
            [
                InlineKeyboardButton(text=t(lang, "btn_history"), callback_data=f"hist:{watch.pk}"),
                InlineKeyboardButton(text=t(lang, "btn_threshold"), callback_data=f"thr:{watch.pk}"),
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_resume" if watch.paused else "btn_pause"),
                    callback_data=f"pause:{watch.pk}",
                ),
                share_button(watch.origin, watch.destination, watch.depart_date, lang),
            ],
            [InlineKeyboardButton(text=t(lang, "btn_delete"), callback_data=f"del:{watch.pk}")],
            _back(lang, "mine"),
        ]
    )


def threshold_keyboard(
    pk: int, options: list[int], currency: str, has_current: bool, lang: str
) -> InlineKeyboardMarkup:
    """Alert prices offered as buttons. The numbers come from what the route has actually cost, so
    they are choices rather than a blank field the user has to guess at."""
    rows = [
        [
            InlineKeyboardButton(
                text=f"🔥 < {money.format_price(price, currency)}",
                callback_data=f"setthr:{pk}:{price}",
            )
        ]
        for price in options
    ]
    if has_current:
        rows.append(
            [InlineKeyboardButton(text=t(lang, "btn_thr_off"), callback_data=f"setthr:{pk}:0")]
        )
    rows.append(_back(lang, f"w:{pk}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def watch_result_keyboard(pk: int, lang: str) -> InlineKeyboardMarkup:
    """After a live search on a watch — back to the watch, not to the panel, because that is where
    the user came from and where their alert and history live."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_refresh"), callback_data=f"wgo:{pk}")],
            _back(lang, f"w:{pk}"),
        ]
    )


def history_keyboard(pk: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "btn_refresh"), callback_data=f"hist:{pk}")],
            _back(lang, f"w:{pk}"),
        ]
    )


# --- settings ----------------------------------------------------------------------------------


def tz_label(name: str) -> str:
    """'Asia/Seoul' → 'Seoul'. The region prefix is filing, not information."""
    return name.split("/")[-1].replace("_", " ")


def settings_text(pref: Preference) -> str:
    return t(
        pref.lang,
        "settings_title",
        lang=LANG_NAMES.get(pref.lang, pref.lang),
        currency=money.currency_label(pref.currency),
        market=money.market_label(pref.market, pref.lang),
        times=schedule.slot_label(pref.notify_hour),
        tz=tz_label(pref.tz),
    )


def settings_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "btn_lang"), callback_data="cfg:lang"),
                InlineKeyboardButton(text=t(lang, "btn_currency"), callback_data="cfg:cur"),
            ],
            [
                InlineKeyboardButton(text=t(lang, "btn_market"), callback_data="cfg:mkt"),
                InlineKeyboardButton(text=t(lang, "btn_notify"), callback_data="cfg:time"),
            ],
            _back(lang),
        ]
    )


def notify_keyboard(pref: Preference) -> InlineKeyboardMarkup:
    """Morning hours, with the current one marked. Each button shows both slots, because that is
    what the choice actually buys: "09:00 · 21:00", not "9"."""
    buttons = [
        InlineKeyboardButton(
            text=("✅ " if h == pref.notify_hour else "") + schedule.slot_label(h),
            callback_data=f"setnotify:{h}",
        )
        for h in schedule.HOUR_CHOICES
    ]
    rows = _rows(buttons, NOTIFY_COLUMNS)
    rows.append([InlineKeyboardButton(text=t(pref.lang, "btn_tz"), callback_data="cfg:tz")])
    rows.append(_back(pref.lang, "cfg"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tz_keyboard(pref: Preference) -> InlineKeyboardMarkup:
    """The same country list as the market picker, but answering a different question: where the
    user *is*, not where they buy. Usually the same country, which is why market seeds it."""
    buttons = [
        InlineKeyboardButton(
            text=("✅ " if schedule.tz_for_market(m.code) == pref.tz else "")
            + f"{m.flag} {m.name(pref.lang)}",
            callback_data=f"settz:{m.code}",
        )
        for m in money.MARKETS
    ]
    rows = _rows(buttons, MARKET_COLUMNS)
    rows.append(_back(pref.lang, "cfg:time"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
