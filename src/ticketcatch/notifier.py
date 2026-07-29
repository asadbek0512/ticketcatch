import asyncio
import html
import logging
import time

import httpx

from .config import settings
from .i18n import t
from .models import PriceQuote, Watch
from .money import format_price

API = "https://api.telegram.org/bot{token}/{method}"
log = logging.getLogger("ticketcatch")

# Telegram's documented ceilings: ~30 messages/second overall and ~1/second into one chat. Going
# over earns a 429 with a retry_after, and a poll fanning out to hundreds of watchers would hit it
# immediately — so the sender paces itself instead of learning by getting throttled.
GLOBAL_INTERVAL = 1 / 25
CHAT_INTERVAL = 1.05
SEND_RETRIES = 3

_send_lock = asyncio.Lock()
_last_global = 0.0
_last_to_chat: dict[str, float] = {}


def _e(s: str) -> str:
    return html.escape(s or "")


def _money(q: PriceQuote) -> str:
    return format_price(q.price, q.currency)


def _stops(q: PriceQuote, lang: str) -> str:
    """Nonstop vs connecting is the first thing worth seeing after the price, so it gets a badge
    on the headline rather than a word buried in the detail line."""
    if q.stops is None:
        return t(lang, "stops_unknown")
    return t(lang, "nonstop") if q.stops == 0 else t(lang, "transfers", count=q.stops)


def _duration(q: PriceQuote) -> str:
    """'7h 40m' — left in the universal aviation shorthand rather than translated."""
    if not q.duration_min:
        return ""
    hours, minutes = divmod(q.duration_min, 60)
    return f"{hours}h {minutes:02d}m" if minutes else f"{hours}h"


def _bags(q: PriceQuote, lang: str) -> str:
    """Whether the fare already covers a checked bag — the usual reason a price 'changes' later."""
    if q.bags is None:
        return ""
    return t(lang, "bags", count=q.bags) if q.bags else t(lang, "bags_none")


# Which site quoted this fare — the whole point is comparing them. "~" marks a cached quote:
# a price someone saw earlier, which may already be sold out.
_SOURCE_LABEL = {
    "kiwi": "Kiwi",
    "google": "Google",
    "aviasales": "~Aviasales",
    "tripcom": "Trip.com",
}


def _source(q: PriceQuote) -> str:
    return _SOURCE_LABEL.get(q.source, q.source)


def _line(index: int, q: PriceQuote, lang: str) -> str:
    """One booking-board row: price first (that's what's being compared), then who and how."""
    price = _money(q)
    if q.deep_link:
        price = f'<a href="{_e(q.deep_link)}">{price}</a>'
    back = t(lang, "results_return", date=q.return_at) if q.return_at else ""
    detail = " · ".join(
        x
        for x in (q.depart_at, back, _duration(q), _bags(q, lang), q.flight_number, _source(q))
        if x
    )
    who = _e(q.airline) or "—"
    head = f"{index}. <b>{price}</b> — {who}  {_stops(q, lang)}"
    return f"{head}\n     <i>{_e(detail)}</i>" if detail else head


def format_rows(quotes: list[PriceQuote], lang: str) -> str:
    """The numbered price rows plus the "a quote is not a booking" line. Shared by the on-demand
    board, the scheduled digest and the stored board a watch shows instantly — the same prices
    should read identically however the user arrived at them."""
    body = [_line(i, q, lang) for i, q in enumerate(quotes, start=1)]
    return "\n".join((*body, "", t(lang, "results_foot")))


def format_board(quotes: list[PriceQuote], route: str, date_label: str, lang: str) -> str:
    """The on-demand answer: header, rows, and the reminder that a quote isn't a booking."""
    head = t(lang, "results_head", route=_e(route), date=date_label)
    return f"{head}\n\n{format_rows(quotes, lang)}"


def format_digest(watch: Watch, cheapest: list[PriceQuote], previous: PriceQuote | None) -> str:
    """The scheduled card: route header, price-change badge, cheapest options with links."""
    lang = watch.lang
    route = f"{watch.origin} → {watch.destination}"
    when = watch.depart_date.isoformat()
    if watch.return_date:
        when = f"{when} → {watch.return_date.isoformat()}"
    lines = [t(lang, "digest_head", route=_e(route), date=when)]

    best = cheapest[0]
    if previous is not None and previous.price != best.price:
        delta = best.price - previous.price
        amount = format_price(abs(delta), best.currency)
        lines.append(t(lang, "cheaper" if delta < 0 else "pricier", amount=amount))

    if watch.threshold_price is not None and best.price <= watch.threshold_price:
        lines.append(
            t(lang, "alert", threshold=format_price(watch.threshold_price, best.currency))
        )

    lines.append("")
    lines.extend(_line(i, q, lang) for i, q in enumerate(cheapest, start=1))
    # The digest arrives unprompted, hours after the prices were read — it needs the "this is a
    # quote, not a booking" line more than the on-demand board does, not less.
    lines.extend(("", t(lang, "results_foot")))
    return "\n".join(lines)


async def _pace(chat_id: str) -> None:
    """Hold the caller until this chat and the process as a whole are inside Telegram's limits."""
    global _last_global
    async with _send_lock:
        now = time.monotonic()
        wait = max(
            _last_global + GLOBAL_INTERVAL - now,
            _last_to_chat.get(chat_id, now - CHAT_INTERVAL) + CHAT_INTERVAL - now,
        )
        if wait > 0:
            await asyncio.sleep(wait)
        stamp = time.monotonic()
        _last_global, _last_to_chat[chat_id] = stamp, stamp


async def send_text(chat_id: str, text: str, preview: bool = False) -> bool:
    if settings.dry_run:
        log.info("DRY_RUN would send to %s:\n%s\n", chat_id, text)
        return True
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    url = API.format(token=settings.telegram_bot_token, method="sendMessage")
    body = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": not preview,
    }

    for attempt in range(SEND_RETRIES):
        await _pace(chat_id)
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(url, json=body)
        except httpx.HTTPError as e:  # a dropped connection is worth one more try
            log.warning("sendMessage transport error (%s/%s): %s", attempt + 1, SEND_RETRIES, e)
            continue
        if resp.status_code == 200:
            return True
        if resp.status_code == 429:
            after = (resp.json().get("parameters") or {}).get("retry_after", 1)
            log.warning("telegram rate limit, waiting %ss", after)
            await asyncio.sleep(float(after))
            continue
        # 403 = the user blocked the bot; retrying will never help.
        log.error("sendMessage failed %s: %s", resp.status_code, resp.text[:200])
        return False
    return False
