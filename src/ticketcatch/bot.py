import logging
from datetime import date, datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, CallbackQuery, Message

from . import airports, history, menu, money
from .config import settings
from .db import (
    counts,
    get_preference,
    get_session,
    init_db,
    last_board,
    last_cheapest,
    price_history,
    user_watches,
)
from .i18n import ago_label, day_label, normalize, t
from .models import Preference, PriceQuote, Watch, route_key, utcnow
from .notifier import format_board, format_rows
from .ratelimit import Cooldown
from .search import day_prices, fetch_offers
from .sources import SearchOpts

log = logging.getLogger("ticketcatch")

_DATE_FMT = "%Y-%m-%d"
_RESULT_LIMIT = 8
_MAX_WATCHES = 10  # a watch costs a search twice a day; this is generosity, not a wall
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


def _when(pref: Preference, long: bool = False) -> str:
    """How this trip's dates read: one date, or both when there is a return leg."""
    out = f"{day_label(pref.depart_date, pref.lang)} · {pref.depart_date}" if long else (
        pref.depart_date.isoformat()
    )
    if not pref.return_date:
        return out
    back = (
        f"{day_label(pref.return_date, pref.lang)} · {pref.return_date}"
        if long
        else pref.return_date.isoformat()
    )
    return f"{out} → {back}"


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
    elif field == "ret":
        await _edit(
            callback.message,
            t(pref.lang, "pick_return"),
            menu.return_date_keyboard(pref.depart_date, pref.return_date, pref.lang),
        )
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
        if pref.return_date and pref.return_date <= day:
            pref.return_date = None  # the old return is now before departure — drop it, don't guess
        return None

    if field == "ret":
        if not value:  # the "remove return" button — back to a one-way search
            pref.return_date = None
            return None
        try:
            day = datetime.strptime(value, _DATE_FMT).date()
        except ValueError:
            return "bad_date"
        if day <= pref.depart_date:
            return "err_return_before"
        if day > date.today() + timedelta(days=_MAX_LEAD_DAYS):
            return "too_far"
        pref.return_date = day
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
    parts = callback.data.split(":", 2)
    field, value = parts[1], parts[2] if len(parts) > 2 else ""
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
    prompt = t(pref.lang, "type_date" if field in ("depart", "ret") else "type_airport")
    await _edit(callback.message, prompt)
    await callback.answer()


async def _on_typed(message: Message, state: FSMContext) -> None:
    """Free text for the field being edited: a date, an IATA code, or a city name to search for."""
    field = (await state.get_data()).get("field")
    raw = (message.text or "").strip()
    pref = await _pref(message)

    if field and field.startswith("thr:"):
        # Typed thresholds arrive as "750 000" or "750,000" as often as "750000" — people write
        # money the way they read it, and rejecting that would be pedantry, not validation.
        digits = raw.replace(" ", "").replace(",", "").replace(".", "").replace(" ", "")
        if not digits.isdigit() or int(digits) <= 0:
            await message.answer(t(pref.lang, "thr_bad"))
            return
        watch = await _store_threshold(int(field.split(":")[1]), pref.user_id, int(digits))
        await state.clear()
        if watch is None:
            await message.answer(t(pref.lang, "watch_unknown"))
            return
        await message.answer(
            t(pref.lang, "thr_set", price=money.format_price(watch.threshold_price, watch.currency)),
            reply_markup=menu.watch_keyboard(watch, pref.lang),
        )
        return

    if field in ("depart", "ret"):
        error = _apply(pref, field, raw)
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
            return_at=o.return_at,
            return_stops=o.return_stops,
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

    route, when = _route(pref), _when(pref)
    await _edit(callback.message, t(pref.lang, "searching", route=route, date=when))

    try:
        offers = await fetch_offers(
            pref.origin,
            pref.destination,
            pref.depart_date,
            _opts(pref),
            ret=pref.return_date,
        )
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
    board = format_board(_live_rows(offers), route, _when(pref, long=True), pref.lang)
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
        strip = await day_prices(
            pref.origin, pref.destination, pref.depart_date, _opts(pref), ret=pref.return_date
        )
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
            and w.return_date == pref.return_date
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
                return_date=pref.return_date,
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
        t(pref.lang, "watch_added", route=_route(pref), date=_when(pref))
    )


async def _watch_list(pref: Preference) -> tuple[str, object]:
    async with get_session() as s:
        mine = await user_watches(s, pref.user_id)
    if not mine:
        return t(pref.lang, "watch_none"), menu.start_keyboard(pref.lang)

    lines = [t(pref.lang, "watch_list"), ""]
    async with get_session() as s:
        latest = {w.pk: await last_cheapest(s, _rkey(w), w.currency) for w in mine}
    for w in mine:
        threshold = (
            f" · 🔥 &lt; {money.format_price(w.threshold_price, w.currency)}"
            if w.threshold_price
            else ""
        )
        back = f" 🔁 {w.return_date.isoformat()}" if w.return_date else ""
        paused = " ⏸" if w.paused else ""
        lines.append(
            f"<b>{airports.city(w.origin)} → {airports.city(w.destination)}</b>{paused}\n"
            f"     {day_label(w.depart_date, pref.lang)} · {w.depart_date.isoformat()}{back}"
            f"{threshold}"
        )
        # The price the list is about, right in the list. Opening a watch to find out what it
        # currently costs is one tap too many for the question people actually have.
        best = latest.get(w.pk)
        lines.append(
            t(
                pref.lang,
                "list_price",
                price=money.format_price(best.price, best.currency),
                ago=_ago(best.captured_at, pref.lang),
            )
            if best
            else t(pref.lang, "list_no_price")
        )
    lines.extend(("", f"<i>{t(pref.lang, 'watch_open')}</i>"))
    return "\n".join(lines), menu.watches_keyboard(mine, pref.lang)


def _rkey(watch: Watch) -> str:
    return route_key(watch.origin, watch.destination, watch.depart_date, watch.return_date)


def _ago(captured_at: datetime, lang: str) -> str:
    """How old a stored price is. captured_at is written as UTC-aware but read back naive by
    SQLite, so both shapes have to work or the subtraction raises."""
    at = captured_at if captured_at.tzinfo else captured_at.replace(tzinfo=timezone.utc)
    return ago_label((utcnow() - at).total_seconds(), lang)


async def _owned(callback: CallbackQuery, pref: Preference) -> Watch | None:
    """The watch this callback refers to, but only if it belongs to whoever pressed the button.

    callback_data is client-supplied: nothing stops someone editing `w:7` into `w:8` and reading a
    stranger's route. Every watch screen goes through here."""
    pk = callback.data.split(":")[1]
    if not pk.isdigit():
        return None
    async with get_session() as s:
        watch = await s.get(Watch, int(pk))
    if watch is None or watch.user_id != pref.user_id or not watch.active:
        return None
    return watch


def _watch_label(watch: Watch, lang: str) -> tuple[str, str]:
    route = f"{airports.city(watch.origin)} → {airports.city(watch.destination)}"
    when = f"📅 {day_label(watch.depart_date, lang)} · {watch.depart_date.isoformat()}"
    if watch.return_date:
        when += f"\n🔁 {day_label(watch.return_date, lang)} · {watch.return_date.isoformat()}"
    return route, when


def _watch_card(watch: Watch, lang: str, board: list[PriceQuote] | None = None) -> str:
    """The watch, and — instantly — the prices the last check found.

    No searching happens here. The poller stores every board it fetches, so the answer to "what
    does this cost" is already on disk; making the user wait a minute for four websites to
    re-confirm a number we already have would be a worse answer, not a fresher one. The age is
    stated on the card, and 🔍 is one tap away when they want it live."""
    route, when = _watch_label(watch, lang)
    head = t(
        lang,
        "watch_detail",
        route=route,
        date=when,
        market=money.market_label(watch.market, lang),
        currency=watch.currency.upper(),
        status=t(lang, "status_paused" if watch.paused else "status_active"),
        threshold=(
            t(lang, "thr_line", price=money.format_price(watch.threshold_price, watch.currency))
            if watch.threshold_price
            else ""
        ),
    )
    if not board:
        return f"{head}\n\n{t(lang, 'no_prices_yet')}"
    rows = format_rows(board[:_RESULT_LIMIT], lang)
    return f"{head}\n{t(lang, 'checked_at', ago=_ago(board[0].captured_at, lang))}\n\n{rows}"


async def _watch_screen(watch: Watch, lang: str) -> tuple[str, object]:
    async with get_session() as s:
        board = await last_board(s, _rkey(watch), watch.currency)
    return _watch_card(watch, lang, board), menu.watch_keyboard(watch, lang)


async def _cb_watch_open(callback: CallbackQuery, state: FSMContext) -> None:
    """One watch: last known prices right away, plus everything you can do to it."""
    await state.clear()  # leaving the threshold prompt by the back button must not keep listening
    pref = await _pref(callback)
    watch = await _owned(callback, pref)
    if watch is None:
        await callback.answer(t(pref.lang, "watch_unknown"), show_alert=True)
        return
    text, markup = await _watch_screen(watch, pref.lang)
    await _edit(callback.message, text, markup)
    await callback.answer()


async def _cb_history(callback: CallbackQuery) -> None:
    """What this watch has cost so far. Free: the poller already captured every one of these
    prices, so the answer is a database read, not four more searches."""
    pref = await _pref(callback)
    watch = await _owned(callback, pref)
    if watch is None:
        await callback.answer(t(pref.lang, "watch_unknown"), show_alert=True)
        return
    rkey = route_key(watch.origin, watch.destination, watch.depart_date, watch.return_date)
    async with get_session() as s:
        points = await price_history(s, rkey, watch.currency)
    route, _ = _watch_label(watch, pref.lang)
    card = history.format_history(
        points, watch.currency, pref.lang, route, _watch_when(watch)
    )
    await _edit(callback.message, card, menu.history_keyboard(watch.pk, pref.lang))
    await callback.answer()


def _watch_when(watch: Watch) -> str:
    out = watch.depart_date.isoformat()
    return f"{out} → {watch.return_date.isoformat()}" if watch.return_date else out


async def _cb_watch_search(callback: CallbackQuery) -> None:
    """A live search for this watch's own route, priced the way the watch is priced.

    The watch carries its own currency and market, so this must not borrow them from the panel:
    the point of opening a watch is to see that watch's numbers, not today's menu settings."""
    pref = await _pref(callback)
    watch = await _owned(callback, pref)
    if watch is None:
        await callback.answer(t(pref.lang, "watch_unknown"), show_alert=True)
        return

    chat_id = _chat(callback)
    waiting = _searching.remaining(chat_id)
    if waiting:
        await callback.answer(t(pref.lang, "cooldown", seconds=waiting), show_alert=True)
        return
    _searching.hit(chat_id)
    await callback.answer()

    route, _ = _watch_label(watch, pref.lang)
    when = _watch_when(watch)
    await _edit(callback.message, t(pref.lang, "searching", route=route, date=when))
    opts = SearchOpts.of(currency=watch.currency, market=watch.market)
    try:
        offers = await fetch_offers(
            watch.origin, watch.destination, watch.depart_date, opts, ret=watch.return_date
        )
    except Exception as e:
        log.exception("watch search failed for %s: %s", watch.pk, e)
        _searching.clear(chat_id)
        text, markup = await _watch_screen(watch, pref.lang)
        await _edit(callback.message, f"{t(pref.lang, 'search_failed')}\n\n{text}", markup)
        return

    if not offers:
        await _edit(
            callback.message,
            t(pref.lang, "search_empty", route=route, date=when),
            menu.watch_result_keyboard(watch.pk, pref.lang),
        )
        return
    board = format_board(_live_rows(offers), route, when, pref.lang)
    await _edit(callback.message, board, menu.watch_result_keyboard(watch.pk, pref.lang))


async def _cb_pause(callback: CallbackQuery) -> None:
    """Stop the messages without losing the price history that makes them meaningful."""
    pref = await _pref(callback)
    watch = await _owned(callback, pref)
    if watch is None:
        await callback.answer(t(pref.lang, "watch_unknown"), show_alert=True)
        return
    watch.paused = not watch.paused
    async with get_session() as s:
        s.add(watch)
        await s.commit()
    await callback.answer(t(pref.lang, "watch_resumed" if not watch.paused else "watch_paused"))
    text, markup = await _watch_screen(watch, pref.lang)
    await _edit(callback.message, text, markup)


async def _cb_threshold(callback: CallbackQuery, state: FSMContext) -> None:
    """Offer alert prices derived from what the route has actually cost, or let them type one."""
    pref = await _pref(callback)
    watch = await _owned(callback, pref)
    if watch is None:
        await callback.answer(t(pref.lang, "watch_unknown"), show_alert=True)
        return
    rkey = route_key(watch.origin, watch.destination, watch.depart_date, watch.return_date)
    async with get_session() as s:
        points = await price_history(s, rkey, watch.currency)

    await state.set_state(Editing.value)
    await state.update_data(field=f"thr:{watch.pk}")
    await _edit(
        callback.message,
        t(pref.lang, "thr_ask"),
        menu.threshold_keyboard(
            watch.pk,
            history.suggestions(points),
            watch.currency,
            watch.threshold_price is not None,
            pref.lang,
        ),
    )
    await callback.answer()


async def _store_threshold(pk: int, user_id: str, price: int | None) -> Watch | None:
    async with get_session() as s:
        watch = await s.get(Watch, pk)
        if watch is None or watch.user_id != user_id or not watch.active:
            return None
        watch.threshold_price = price
        s.add(watch)
        await s.commit()
    return watch


async def _cb_set_threshold(callback: CallbackQuery, state: FSMContext) -> None:
    """`setthr:<pk>:<price>` — price 0 is the "switch it off" button."""
    await state.clear()
    pref = await _pref(callback)
    _, raw_pk, raw_price = callback.data.split(":", 2)
    price = int(raw_price) if raw_price.isdigit() else 0
    watch = await _store_threshold(int(raw_pk), pref.user_id, price or None)
    if watch is None:
        await callback.answer(t(pref.lang, "watch_unknown"), show_alert=True)
        return
    await callback.answer(
        t(pref.lang, "thr_set", price=money.format_price(price, watch.currency))
        if price
        else t(pref.lang, "thr_cleared")
    )
    text, markup = await _watch_screen(watch, pref.lang)
    await _edit(callback.message, text, markup)


async def _cmd_list(message: Message) -> None:
    pref = await _pref(message)
    text, markup = await _watch_list(pref)
    await message.answer(text, reply_markup=markup)


async def _cb_mine(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
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
    """The typing shortcut for people who already know the codes.

    /add ICN TAS 2026-08-15 [2026-08-29] [price] — the fourth field is a return date if it parses
    as one and a threshold price otherwise, so the old one-way form keeps working unchanged."""
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

    rest = parts[3:]
    if rest and not rest[0].isdigit():
        error = _apply(staged, "ret", rest[0])
        if error:
            await message.answer(t(pref.lang, error))
            return
        rest = rest[1:]
    threshold = int(rest[0]) if rest and rest[0].isdigit() else None
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
                return_date=staged.return_date,
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
            date=_when(staged),
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
    dp.callback_query.register(_cb_watch_open, F.data.startswith("w:"))
    dp.callback_query.register(_cb_watch_search, F.data.startswith("wgo:"))
    dp.callback_query.register(_cb_history, F.data.startswith("hist:"))
    dp.callback_query.register(_cb_pause, F.data.startswith("pause:"))
    dp.callback_query.register(_cb_set_threshold, F.data.startswith("setthr:"))
    dp.callback_query.register(_cb_threshold, F.data.startswith("thr:"))
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
