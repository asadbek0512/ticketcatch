import logging
from datetime import date, datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlmodel import select

from .config import settings
from .db import get_session, init_db
from .models import Watch

log = logging.getLogger("ticketcatch")

_DATE_FMT = "%Y-%m-%d"
_HELP = (
    "✈️ <b>TicketCatch</b> — eng arzon biletni siz uchun kuzatadi.\n\n"
    "Har kuni 2 marta tanlagan yo'nalishingiz bo'yicha eng arzon biletlarni link bilan "
    "yuboraman, narx arzonlashsa xabar beraman.\n\n"
    "<b>Buyruqlar:</b>\n"
    "<code>/add ICN TAS 2026-08-15</code> — kuzatuv qo'shish\n"
    "<code>/add ICN TAS 2026-08-15 450</code> — narx 450$ dan tushsa ALERT\n"
    "<code>/list</code> — kuzatuvlaringiz\n"
    "<code>/remove 3</code> — kuzatuvni o'chirish (raqami /list dan)\n"
)


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw, _DATE_FMT).date()


async def _cmd_start(message: Message) -> None:
    await message.answer(_HELP)


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
    extra = f" · ALERT < {threshold}$" if threshold else ""
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
        await message.answer("Kuzatuvingiz yo'q. <code>/add ICN TAS 2026-08-15</code> bilan qo'shing.")
        return
    lines = ["<b>Kuzatuvlaringiz:</b>"]
    for w in watches:
        thr = f" · <{w.threshold_price}$" if w.threshold_price else ""
        lines.append(f"<code>{w.pk}</code> · {w.origin} → {w.destination} · {w.depart_date.isoformat()}{thr}")
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
    dp = Dispatcher()
    dp.message.register(_cmd_start, Command("start", "help"))
    dp.message.register(_cmd_add, Command("add"))
    dp.message.register(_cmd_list, Command("list"))
    dp.message.register(_cmd_remove, Command("remove"))
    return dp


async def run_bot() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    await init_db()
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()
    log.info("bot polling started")
    await dp.start_polling(bot)
