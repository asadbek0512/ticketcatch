import logging
from datetime import date, datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, CallbackQuery, Message
from sqlmodel import select

from . import menu
from .config import settings
from .db import get_preference, get_session, init_db
from .models import Preference, PriceQuote, Watch, utcnow
from .notifier import format_digest
from .search import fetch_offers

log = logging.getLogger("ticketcatch")

_DATE_FMT = "%Y-%m-%d"
_IATA_LENGTH = 3
_RESULT_LIMIT = 8
_HELP = (
    "✈️ <b>TicketCatch</b> — eng arzon biletni siz uchun kuzatadi.\n\n"
    "4 ta saytdan (Kiwi, Trip.com, Google Flights, Aviasales) narxlarni solishtiraman va "
    "eng arzonini ko'rsataman. Kuzatuvga qo'shsangiz, kuniga 3 marta yangilab turaman va "
    "narx tushsa xabar beraman.\n\n"
    "<b>/qidir</b> — yo'nalish va sanani tanlab qidirish\n"
    "<b>/list</b> — kuzatuvlaringiz\n"
    "<b>/remove 3</b> — kuzatuvni o'chirish\n\n"
    "Tez yo'l: <code>/add ICN TAS 2026-08-15</code>"
)
# The ☰ button next to the input field. /qidir leads, since everything else starts there.
_COMMANDS = [
    BotCommand(command="qidir", description="🔍 Yo'nalish tanlab qidirish"),
    BotCommand(command="list", description="📋 Kuzatuvlarim"),
    BotCommand(command="remove", description="🗑 Kuzatuvni o'chirish"),
    BotCommand(command="help", description="❓ Yordam"),
]


class Editing(StatesGroup):
    """Waiting for a typed airport code or date after '✏️ o'zim yozaman'."""

    value = State()


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw, _DATE_FMT).date()


def _apply(pref: Preference, field: str, value: str) -> None:
    if field == "depart":
        pref.depart_date = _parse_date(value)
    elif field == "origin":
        pref.origin = value.upper()
    else:
        pref.destination = value.upper()


async def _show_panel(message: Message, user_id: str, edit: bool = False) -> None:
    async with get_session() as s:
        pref = await get_preference(s, user_id)
    text, markup = menu.panel_text(pref), menu.panel_keyboard(pref)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


async def _cmd_start(message: Message) -> None:
    await message.answer(_HELP)


async def _cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _show_panel(message, str(message.chat.id))


async def _cb_panel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _show_panel(callback.message, str(callback.message.chat.id), edit=True)
    await callback.answer()


async def _cb_pick(callback: CallbackQuery) -> None:
    """Open the option list for one field."""
    field = callback.data.split(":", 1)[1]
    async with get_session() as s:
        pref = await get_preference(s, str(callback.message.chat.id))
    if field == "depart":
        await callback.message.edit_text("📅 Qaysi kun?", reply_markup=menu.date_keyboard())
    else:
        other = pref.destination if field == "origin" else pref.origin
        label = "📍 Qayerdan uchasiz?" if field == "origin" else "🎯 Qayerga uchasiz?"
        await callback.message.edit_text(label, reply_markup=menu.airport_keyboard(field, other))
    await callback.answer()


async def _cb_set(callback: CallbackQuery) -> None:
    _, field, value = callback.data.split(":", 2)
    async with get_session() as s:
        pref = await get_preference(s, str(callback.message.chat.id))
        _apply(pref, field, value)
        s.add(pref)
        await s.commit()
    await _show_panel(callback.message, str(callback.message.chat.id), edit=True)
    await callback.answer("✅ O'zgartirildi")


async def _cb_manual(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    await state.set_state(Editing.value)
    await state.update_data(field=field)
    prompt = (
        "📅 Sanani yozing: <code>2026-08-15</code>"
        if field == "depart"
        else "✏️ Aeroport kodini yozing (3 harf): <code>DXB</code>"
    )
    await callback.message.edit_text(prompt)
    await callback.answer()


async def _on_typed(message: Message, state: FSMContext) -> None:
    """The typed half of '✏️ o'zim yozaman' — reject bad input without dropping out of the menu."""
    field = (await state.get_data()).get("field")
    raw = (message.text or "").strip()
    if field == "depart":
        try:
            value = _parse_date(raw)
        except ValueError:
            await message.answer("Sana noto'g'ri. Format: <code>2026-08-15</code>")
            return
        if value < date.today():
            await message.answer("Bu sana o'tib ketgan — kelajakdagi kunni yozing.")
            return
    elif len(raw) != _IATA_LENGTH or not raw.isalpha():
        await message.answer("Aeroport kodi 3 ta harf bo'lishi kerak, masalan <code>DXB</code>")
        return

    async with get_session() as s:
        pref = await get_preference(s, str(message.chat.id))
        _apply(pref, field, raw)
        s.add(pref)
        await s.commit()
    await state.clear()
    await _show_panel(message, str(message.chat.id))


def _live_rows(offers: list) -> list[PriceQuote]:
    """Wrap live offers in the same rows the digest renders. route_key is empty and nothing is
    committed — an on-demand search is an answer, not price history."""
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
    """Search every source right now. Trip.com drives a real browser, so this takes a minute or
    two — the wait message is edited into the result rather than leaving the chat silent."""
    await callback.answer()
    chat_id = str(callback.message.chat.id)
    async with get_session() as s:
        pref = await get_preference(s, chat_id)
    header = f"<b>{pref.origin} → {pref.destination}</b> · {pref.depart_date.isoformat()}"
    await callback.message.edit_text(
        f"⏳ {header}\n4 ta saytdan qidiryapman, 1–2 daqiqa ketadi…"
    )

    try:
        offers = await fetch_offers(pref.origin, pref.destination, pref.depart_date)
    except Exception as e:
        log.exception("live search failed for %s: %s", chat_id, e)
        await callback.message.edit_text(
            f"⚠️ {header}\nQidiruvda xatolik chiqdi. Birozdan keyin qayta urinib ko'ring.",
            reply_markup=menu.result_keyboard(),
        )
        return

    if not offers:
        await callback.message.edit_text(
            f"😕 {header}\nBu kunga hech narsa topilmadi. Sanani yoki yo'nalishni o'zgartiring.",
            reply_markup=menu.result_keyboard(),
        )
        return

    watch = Watch(
        user_id=chat_id,
        origin=pref.origin,
        destination=pref.destination,
        depart_date=pref.depart_date,
    )
    await callback.message.edit_text(
        format_digest(watch, _live_rows(offers), None),
        reply_markup=menu.result_keyboard(),
    )


async def _cb_watch(callback: CallbackQuery) -> None:
    chat_id = str(callback.message.chat.id)
    async with get_session() as s:
        pref = await get_preference(s, chat_id)
        duplicate = await s.exec(
            select(Watch).where(
                Watch.user_id == chat_id,
                Watch.origin == pref.origin,
                Watch.destination == pref.destination,
                Watch.depart_date == pref.depart_date,
                Watch.active == True,  # noqa: E712
            )
        )
        if duplicate.first() is not None:
            await callback.answer("Bu yo'nalish allaqachon kuzatuvda", show_alert=True)
            return
        s.add(
            Watch(
                user_id=chat_id,
                origin=pref.origin,
                destination=pref.destination,
                depart_date=pref.depart_date,
            )
        )
        await s.commit()
    await callback.answer("🔔 Kuzatuvga qo'shildi")
    await callback.message.answer(
        f"🔔 <b>{pref.origin} → {pref.destination}</b> · {pref.depart_date.isoformat()} "
        "kuzatuvga qo'shildi.\nKuniga 3 marta yangilab turaman."
    )


async def _cmd_add(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").split()
    if len(parts) < 3:
        await message.answer("Format: <code>/add ICN TAS 2026-08-15 [narx]</code>")
        return
    origin, destination, date_raw = parts[0], parts[1], parts[2]
    try:
        depart = _parse_date(date_raw)
    except ValueError:
        await message.answer("Sana noto'g'ri. Format: <code>YYYY-MM-DD</code> (masalan 2026-08-15)")
        return
    if depart < date.today():
        await message.answer("Sana o'tmishda — kelajakdagi kunni tanlang.")
        return
    threshold = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None

    watch = Watch(
        user_id=str(message.chat.id),
        origin=origin.upper(),
        destination=destination.upper(),
        depart_date=depart,
        threshold_price=threshold,
    )
    async with get_session() as s:
        s.add(watch)
        await s.commit()
    unit = settings.currency.upper()
    extra = f" · ALERT &lt; {threshold} {unit}" if threshold else ""
    await message.answer(
        f"✅ Kuzatuv qo'shildi: <b>{watch.origin} → {watch.destination}</b> · "
        f"{depart.isoformat()}{extra}\nBirinchi natijani keyingi tekshiruvda yuboraman."
    )


async def _cmd_list(message: Message) -> None:
    async with get_session() as s:
        rows = await s.exec(
            select(Watch).where(Watch.user_id == str(message.chat.id), Watch.active == True)  # noqa: E712
        )
        watches = list(rows.all())
    if not watches:
        await message.answer("Kuzatuvingiz yo'q. <b>/qidir</b> bilan yo'nalish tanlang.")
        return
    unit = settings.currency.upper()
    lines = ["<b>Kuzatuvlaringiz:</b>"]
    for w in watches:
        thr = f" · &lt;{w.threshold_price} {unit}" if w.threshold_price else ""
        lines.append(
            f"<code>{w.pk}</code> · {w.origin} → {w.destination} · {w.depart_date.isoformat()}{thr}"
        )
    await message.answer("\n".join(lines))


async def _cmd_remove(message: Message, command: CommandObject) -> None:
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await message.answer("Format: <code>/remove 3</code> (raqamni /list dan oling)")
        return
    async with get_session() as s:
        watch = await s.get(Watch, int(arg))
        if watch is None or watch.user_id != str(message.chat.id):
            await message.answer("Bunday kuzatuv topilmadi.")
            return
        watch.active = False
        s.add(watch)
        await s.commit()
    await message.answer("🗑 O'chirildi.")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.register(_cmd_start, Command("start", "help"))
    dp.message.register(_cmd_menu, Command("qidir", "menu", "search"))
    dp.message.register(_cmd_add, Command("add"))
    dp.message.register(_cmd_list, Command("list"))
    dp.message.register(_cmd_remove, Command("remove"))
    dp.message.register(_on_typed, Editing.value)

    dp.callback_query.register(_cb_panel, F.data == "panel")
    dp.callback_query.register(_cb_search, F.data == "go")
    dp.callback_query.register(_cb_watch, F.data == "watch")
    dp.callback_query.register(_cb_pick, F.data.startswith("pick:"))
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
    await dp.start_polling(bot)
