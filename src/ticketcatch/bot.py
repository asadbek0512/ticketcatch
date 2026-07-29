import logging
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, CallbackQuery, Message

from . import airports, menu, money
from .config import settings
from .db import counts, get_preference, get_session, init_db, user_watches
from .i18n import day_label, normalize, t
from .models import Preference, PriceQuote, Watch, utcnow
from .notifier import format_board
from .ratelimit import Cooldown
from .search import day_prices, fetch_offers
from .sources import SearchOpts

log = logging.getLogger("ticketcatch")

_DATE_FMT = "%Y-%m-%d"
_RESULT_LIMIT = 8
_MAX_WATCHES = 10  # a watch costs a search three times a day; this is generosity, not a wall
_MAX_LEAD_DAYS = 335  # airlines sell ~11 months out — beyond that every source returns nothing

_searching = Cooldown(settings.search_cooldown_seconds)

# The ☰ button next to the input field. /qidir leads because everything else is reachable from it.
_COMMANDS = [
    BotCommand(command="qidir", description="🔍 Qidiruv paneli / Search"),
    BotCommand(command="list", description="📋 Kuzatuvlarim / My watches"),
    BotCommand(command="sozlama", description="⚙️ Til, valyuta / Settings"),
    BotCommand(command="help", description="❓ Yordam / Help"),
]


class Editing(StatesGroup):
    value = State()


# --- shared helpers ----------------------------------------------------------------------------


def _chat(event: Message | CallbackQuery) -> str:
    message = event if isinstance(event, Message) else event.message
    return str(message.chat.id)


async def _pref(event: Message | CallbackQuery) -> Preference:
    """Preference for whoever triggered this, seeded with their Telegram language when new."""
    hint = normalize(event.from_user.language_code if event.from_user else None)
    async with get_session() as s:
        return await get_preference(s, _chat(event), lang_hint=hint)


async def _save(pref: Preference) -> None:
    async with get_session() as s:
        s.add(pref)
        await s.commit()


async def _edit(message: Message, text: str, markup=None) -> None:
    """Edit in place, tolerating the two harmless failures: an unchanged body and a message too
    old for Telegram to edit. Neither is worth an error in the user's chat."""
    try:
        await message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        await message.answer(text, reply_markup=markup, disable_web_page_preview=True)


async def _show_panel(event: Message | CallbackQuery) -> None:
    pref = await _pref(event)
    text, markup = menu.panel_text(pref), menu.panel_keyboard(pref)
    if isinstance(event, CallbackQuery):
        await _edit(event.message, text, markup)
    else:
        await event.answer(text, reply_markup=markup)


def _route(pref: Preference) -> str:
    return f"{pref.origin} → {pref.destination}"


def _opts(pref: Preference) -> SearchOpts:
    return SearchOpts.of(currency=pref.currency, market=pref.market)


# --- commands ----------------------------------------------------------------------------------


async def _cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    pref = await _pref(message)
    await message.answer(t(pref.lang, "start"), reply_markup=menu.start_keyboard(pref.lang))


async def _cmd_help(message: Message) -> None:
    pref = await _pref(message)
    await message.answer(t(pref.lang, "help"), reply_markup=menu.start_keyboard(pref.lang))


async def _cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_panel(message)


async def _cmd_settings(message: Message, state: FSMContext) -> None:
    await state.clear()
    pref = await _pref(message)
    await message.answer(menu.settings_text(pref), reply_markup=menu.settings_keyboard(pref.lang))


async def _cmd_stats(message: Message) -> None:
    """Owner-only: how much the bot is actually being used."""
    if str(message.chat.id) != str(settings.telegram_owner_id):
        return
    pref = await _pref(message)
    async with get_session() as s:
        numbers = await counts(s)
    await message.answer(t(pref.lang, "stats", **numbers))


# --- panel navigation --------------------------------------------------------------------------


async def _cb_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _show_panel(callback)
    await callback.answer()


async def _cb_help(callback: CallbackQuery) -> None:
    pref = await _pref(callback)
    await _edit(callback.message, t(pref.lang, "help"), menu.panel_keyboard(pref))
    await callback.answer()


async def _cb_swap(callback: CallbackQuery) -> None:
    """One tap for the way back — the return leg is the second thing every user wants."""
    pref = await _pref(callback)
    pref.origin, pref.destination = pref.destination, pref.origin
    await _save(pref)
    await _show_panel(callback)
    await callback.answer(t(pref.lang, "saved"))


async def _cb_pick(callback: CallbackQuery) -> None:
    """Open the option list for one field."""
    field = callback.data.split(":", 1)[1]
    pref = await _pref(callback)
    if field == "depart":
        await _edit(callback.message, t(pref.lang, "ask_date"), menu.date_keyboard(pref.lang))
    else:
        other = pref.destination if field == "origin" else pref.origin
        label = t(pref.lang, "ask_from" if field == "origin" else "ask_to")
        await _edit(callback.message, label, menu.airport_keyboard(field, other, pref.lang))
    await callback.answer()


async def _cb_region(callback: CallbackQuery) -> None:
    """`reg:origin` lists the regions, `reg:origin:eu` lists that region's airports."""
    parts = callback.data.split(":")
    field = parts[1]
    pref = await _pref(callback)
    if len(parts) == 2:
        await _edit(callback.message, t(pref.lang, "ask_region"), menu.region_keyboard(field, pref.lang))
    else:
        other = pref.destination if field == "origin" else pref.origin
        await _edit(
            callback.message,
            t(pref.lang, f"region_{parts[2]}"),
            menu.region_airports_keyboard(field, parts[2], other, pref.lang),
        )
    await callback.answer()


def _apply(pref: Preference, field: str, value: str) -> str | None:
    """Write one field, returning an error key if the value doesn't make sense."""
    if field == "depart":
        try:
            day = datetime.strptime(value, _DATE_FMT).date()
        except ValueError:
            return "bad_date"
        if day <= date.today():
            return "past_date"
        if day > date.today() + timedelta(days=_MAX_LEAD_DAYS):
            return "too_far"
        pref.depart_date = day
        return None

    code = value.upper()
    if field == "origin":
        if code == pref.destination:
            return "same_city"
        pref.origin = code
    else:
        if code == pref.origin:
            return "same_city"
        pref.destination = code
    return None


async def _cb_set(callback: CallbackQuery) -> None:
    _, field, value = callback.data.split(":", 2)
    pref = await _pref(callback)
    error = _apply(pref, field, value)
    if error:
        await callback.answer(t(pref.lang, error), show_alert=True)
        return
    await _save(pref)
    await _show_panel(callback)
    await callback.answer(t(pref.lang, "saved"))


async def _cb_manual(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    pref = await _pref(callback)
    await state.set_state(Editing.value)
    await state.update_data(field=field)
    prompt = t(pref.lang, "type_date" if field == "depart" else "type_airport")
    await _edit(callback.message, prompt)
    await callback.answer()


async def _on_typed(message: Message, state: FSMContext) -> None:
    """Free text for the field being edited: a date, an IATA code, or a city name to search for."""
    field = (await state.get_data()).get("field")
    raw = (message.text or "").strip()
    pref = await _pref(message)

    if field == "depart":
        error = _apply(pref, "depart", raw)
        if error:
            await message.answer(t(pref.lang, error))
            return
    elif airports.is_iata(raw) and airports.get(raw) is None:
        # An unlisted but valid-looking code is taken at face value — our directory is curated,
        # not exhaustive, and refusing DAC because we never listed it would be a bug, not a guard.
        error = _apply(pref, field, raw)
        if error:
            await message.answer(t(pref.lang, error))
            return
    else:
        found = airports.search(raw)
        if not found:
            await message.answer(t(pref.lang, "no_airports", query=raw))
            return
        if len(found) > 1:
            await message.answer(
                t(pref.lang, "found_airports", query=raw),
                reply_markup=menu.results_keyboard(field, found, pref.lang),
            )
            await state.clear()
            return
        error = _apply(pref, field, found[0].code)
        if error:
            await message.answer(t(pref.lang, error))
            return

    await _save(pref)
    await state.clear()
    await _show_panel(message)


# --- search ------------------------------------------------------------------------------------


def _live_rows(offers: list) -> list[PriceQuote]:
    """Wrap live offers in the same rows the digest renders. route_key is empty and nothing is
    committed — this is an on-demand answer, not price history."""
    return [
        PriceQuote(
            route_key="",
            source=o.source,
            price=o.price,
            currency=o.currency,
            airline=o.airline,
            flight_number=o.flight_number,
            depart_at=o.depart_at,
            deep_link=o.deep_link,
            stops=o.stops,
            duration_min=o.duration_min,
            bags=o.bags,
            captured_at=utcnow(),
        )
        for o in offers[:_RESULT_LIMIT]
    ]


async def _cb_search(callback: CallbackQuery) -> None:
    """Ask every source right now. Trip.com drives a real browser, so this takes about a minute —
    a wait message is edited into the result so the chat stays quiet."""
    pref = await _pref(callback)
    chat_id = _chat(callback)

    waiting = _searching.remaining(chat_id)
    if waiting:
        await callback.answer(t(pref.lang, "cooldown", seconds=waiting), show_alert=True)
        return
    _searching.hit(chat_id)
    await callback.answer()

    route, when = _route(pref), pref.depart_date.isoformat()
    await _edit(callback.message, t(pref.lang, "searching", route=route, date=when))

    try:
        offers = await fetch_offers(pref.origin, pref.destination, pref.depart_date, _opts(pref))
    except Exception as e:
        log.exception("live search failed for %s: %s", chat_id, e)
        _searching.clear(chat_id)  # our fault, not theirs — don't make them wait it out
        await _edit(callback.message, t(pref.lang, "search_failed"), menu.result_keyboard(pref.lang))
        return

    if not offers:
        await _edit(
            callback.message,
            t(pref.lang, "search_empty", route=route, date=when),
            menu.result_keyboard(pref.lang),
        )
        return

    pref.searches += 1
    await _save(pref)
    board = format_board(
        _live_rows(offers), route, f"{day_label(pref.depart_date, pref.lang)} · {when}", pref.lang
    )
    await _edit(callback.message, board, menu.result_keyboard(pref.lang))


async def _cb_days(callback: CallbackQuery) -> None:
    """Price the days around the chosen one, so "fly a day later, pay less" is visible at a glance."""
    pref = await _pref(callback)
    chat_id = _chat(callback)

    waiting = _searching.remaining(chat_id)
    if waiting:
        await callback.answer(t(pref.lang, "cooldown", seconds=waiting), show_alert=True)
        return
    _searching.hit(chat_id)
    await callback.answer()

    route = _route(pref)
    await _edit(callback.message, t(pref.lang, "searching", route=route, date=t(pref.lang, "btn_cheapest_days")))
    try:
        strip = await day_prices(pref.origin, pref.destination, pref.depart_date, _opts(pref))
    except Exception as e:
        log.exception("calendar failed for %s: %s", chat_id, e)
        _searching.clear(chat_id)
        await _edit(callback.message, t(pref.lang, "search_failed"), menu.result_keyboard(pref.lang))
        return

    header = f"{t(pref.lang, 'btn_cheapest_days')}\n<b>{route}</b>"
    await _edit(callback.message, header, menu.days_keyboard(strip, pref.currency, pref.lang))


# --- watches -----------------------------------------------------------------------------------


async def _cb_watch(callback: CallbackQuery) -> None:
    pref = await _pref(callback)
    async with get_session() as s:
        mine = await user_watches(s, pref.user_id)
        if len(mine) >= _MAX_WATCHES:
            await callback.answer(t(pref.lang, "watch_limit", limit=_MAX_WATCHES), show_alert=True)
            return
        if any(
            w.origin == pref.origin
            and w.destination == pref.destination
            and w.depart_date == pref.depart_date
            for w in mine
        ):
            await callback.answer(t(pref.lang, "watch_exists"), show_alert=True)
            return
        s.add(
            Watch(
                user_id=pref.user_id,
                origin=pref.origin,
                destination=pref.destination,
                depart_date=pref.depart_date,
                # Frozen at creation: the digest compares this watch's own price history, which
                # only holds together if every capture is priced the same way.
                currency=pref.currency,
                market=pref.market,
                lang=pref.lang,
            )
        )
        await s.commit()

    await callback.answer(t(pref.lang, "saved"))
    await callback.message.answer(
        t(pref.lang, "watch_added", route=_route(pref), date=pref.depart_date.isoformat())
    )


async def _watch_list(pref: Preference) -> tuple[str, object]:
    async with get_session() as s:
        mine = await user_watches(s, pref.user_id)
    if not mine:
        return t(pref.lang, "watch_none"), menu.start_keyboard(pref.lang)

    lines = [t(pref.lang, "watch_list"), ""]
    for w in mine:
        threshold = (
            f" · 🔥 &lt; {money.format_price(w.threshold_price, w.currency)}"
            if w.threshold_price
            else ""
        )
        lines.append(
            f"<b>{airports.city(w.origin)} → {airports.city(w.destination)}</b>\n"
            f"     {day_label(w.depart_date, pref.lang)} · {w.depart_date.isoformat()}"
            f" · {w.currency.upper()}{threshold}"
        )
    return "\n".join(lines), menu.watches_keyboard(mine, pref.lang)


async def _cmd_list(message: Message) -> None:
    pref = await _pref(message)
    text, markup = await _watch_list(pref)
    await message.answer(text, reply_markup=markup)


async def _cb_mine(callback: CallbackQuery) -> None:
    pref = await _pref(callback)
    text, markup = await _watch_list(pref)
    await _edit(callback.message, text, markup)
    await callback.answer()


async def _deactivate(pk: int, user_id: str) -> bool:
    async with get_session() as s:
        watch = await s.get(Watch, pk)
        if watch is None or watch.user_id != user_id:
            return False
        watch.active = False
        s.add(watch)
        await s.commit()
    return True


async def _cb_delete(callback: CallbackQuery) -> None:
    pref = await _pref(callback)
    ok = await _deactivate(int(callback.data.split(":", 1)[1]), pref.user_id)
    await callback.answer(t(pref.lang, "watch_removed" if ok else "watch_unknown"))
    text, markup = await _watch_list(pref)
    await _edit(callback.message, text, markup)


async def _cmd_remove(message: Message, command: CommandObject) -> None:
    pref = await _pref(message)
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer(t(pref.lang, "remove_format"))
        return
    ok = await _deactivate(int(arg), pref.user_id)
    await message.answer(t(pref.lang, "watch_removed" if ok else "watch_unknown"))


async def _cmd_add(message: Message, command: CommandObject) -> None:
    """The typing shortcut for people who already know the codes: /add ICN TAS 2026-08-15 [price]."""
    pref = await _pref(message)
    parts = (command.args or "").split()
    if len(parts) < 3:
        await message.answer(t(pref.lang, "add_format"))
        return

    origin, destination, raw_date = parts[0].upper(), parts[1].upper(), parts[2]
    staged = Preference(user_id=pref.user_id, origin=origin, destination=destination)
    error = _apply(staged, "depart", raw_date)
    if error:
        await message.answer(t(pref.lang, error))
        return
    if origin == destination:
        await message.answer(t(pref.lang, "same_city"))
        return

    threshold = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
    async with get_session() as s:
        if len(await user_watches(s, pref.user_id)) >= _MAX_WATCHES:
            await message.answer(t(pref.lang, "watch_limit", limit=_MAX_WATCHES))
            return
        s.add(
            Watch(
                user_id=pref.user_id,
                origin=origin,
                destination=destination,
                depart_date=staged.depart_date,
                threshold_price=threshold,
                currency=pref.currency,
                market=pref.market,
                lang=pref.lang,
            )
        )
        await s.commit()

    extra = f" · 🔥 &lt; {money.format_price(threshold, pref.currency)}" if threshold else ""
    await message.answer(
        t(
            pref.lang,
            "add_ok",
            route=f"{origin} → {destination}",
            date=staged.depart_date.isoformat(),
            extra=extra,
        )
    )


# --- settings ----------------------------------------------------------------------------------


async def _cb_settings(callback: CallbackQuery) -> None:
    """`cfg` is the settings screen; `cfg:lang` / `cfg:cur` / `cfg:mkt` are its three lists."""
    pref = await _pref(callback)
    section = callback.data.split(":", 1)[1] if ":" in callback.data else ""
    screens = {
        "": (menu.settings_text(pref), menu.settings_keyboard(pref.lang)),
        "lang": (t(pref.lang, "ask_lang"), menu.lang_keyboard(pref.lang)),
        "cur": (t(pref.lang, "ask_currency"), menu.currency_keyboard(pref.lang)),
        "mkt": (t(pref.lang, "ask_market"), menu.market_keyboard(pref.lang)),
    }
    text, markup = screens.get(section, screens[""])
    await _edit(callback.message, text, markup)
    await callback.answer()


async def _cb_set_lang(callback: CallbackQuery) -> None:
    pref = await _pref(callback)
    pref.lang = normalize(callback.data.split(":", 1)[1])
    await _save(pref)
    await _edit(callback.message, menu.settings_text(pref), menu.settings_keyboard(pref.lang))
    await callback.answer(t(pref.lang, "saved"))


async def _cb_set_currency(callback: CallbackQuery) -> None:
    pref = await _pref(callback)
    pref.currency = callback.data.split(":", 1)[1].lower()
    await _save(pref)
    await _edit(callback.message, menu.settings_text(pref), menu.settings_keyboard(pref.lang))
    await callback.answer(t(pref.lang, "saved"))


async def _cb_set_market(callback: CallbackQuery) -> None:
    """Changing the country also moves the currency: nobody picks 'Uzbekistan' and means 'in won'.
    They can still override it afterwards in the currency list."""
    pref = await _pref(callback)
    pref.market = callback.data.split(":", 1)[1].lower()
    pref.currency = money.currency_for(pref.market)
    await _save(pref)
    await _edit(callback.message, menu.settings_text(pref), menu.settings_keyboard(pref.lang))
    await callback.answer(
        t(
            pref.lang,
            "market_note",
            market=money.market_label(pref.market, pref.lang),
            currency=pref.currency.upper(),
        )
    )


# --- wiring ------------------------------------------------------------------------------------


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.register(_cmd_start, Command("start"))
    dp.message.register(_cmd_help, Command("help"))
    dp.message.register(_cmd_menu, Command("qidir", "menu", "search"))
    dp.message.register(_cmd_settings, Command("sozlama", "settings"))
    dp.message.register(_cmd_stats, Command("stats"))
    dp.message.register(_cmd_add, Command("add"))
    dp.message.register(_cmd_list, Command("list"))
    dp.message.register(_cmd_remove, Command("remove"))
    dp.message.register(_on_typed, Editing.value)

    dp.callback_query.register(_cb_panel, F.data == "panel")
    dp.callback_query.register(_cb_help, F.data == "help")
    dp.callback_query.register(_cb_swap, F.data == "swap")
    dp.callback_query.register(_cb_search, F.data == "go")
    dp.callback_query.register(_cb_days, F.data == "days")
    dp.callback_query.register(_cb_watch, F.data == "watch")
    dp.callback_query.register(_cb_mine, F.data == "mine")
    dp.callback_query.register(_cb_settings, F.data == "cfg")
    dp.callback_query.register(_cb_settings, F.data.startswith("cfg:"))
    dp.callback_query.register(_cb_set_lang, F.data.startswith("setlang:"))
    dp.callback_query.register(_cb_set_currency, F.data.startswith("setcur:"))
    dp.callback_query.register(_cb_set_market, F.data.startswith("setmkt:"))
    dp.callback_query.register(_cb_delete, F.data.startswith("del:"))
    dp.callback_query.register(_cb_pick, F.data.startswith("pick:"))
    dp.callback_query.register(_cb_region, F.data.startswith("reg:"))
    dp.callback_query.register(_cb_set, F.data.startswith("set:"))
    dp.callback_query.register(_cb_manual, F.data.startswith("manual:"))
    return dp


async def run_bot() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    await init_db()
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await bot.set_my_commands(_COMMANDS)  # populates the ☰ menu next to the input field
    dp = build_dispatcher()
    log.info("bot polling started")
    try:
        await dp.start_polling(bot)
    finally:
        from .browser import shutdown

        await shutdown()
