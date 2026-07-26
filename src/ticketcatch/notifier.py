import html
import logging

import httpx

from .config import settings
from .models import PriceQuote, Watch

API = "https://api.telegram.org/bot{token}/{method}"
log = logging.getLogger("ticketcatch")


def _e(s: str) -> str:
    return html.escape(s or "")


# Currencies with no minor unit run into six digits, so they need thousands separators to stay
# readable at a glance; USD-sized numbers don't.
_GROUPED = {"krw", "uzs", "jpy", "vnd", "idr"}


def _money(q: PriceQuote) -> str:
    amount = f"{q.price:,}" if q.currency.lower() in _GROUPED else str(q.price)
    return f"{amount} {q.currency.upper()}"


def _stops(q: PriceQuote) -> str:
    if q.stops is None:
        return ""
    return "to'g'ridan-to'g'ri" if q.stops == 0 else f"{q.stops} transfer"


def _duration(q: PriceQuote) -> str:
    if not q.duration_min:
        return ""
    hours, minutes = divmod(q.duration_min, 60)
    return f"{hours}s {minutes:02d}d" if minutes else f"{hours}s"


def _bags(q: PriceQuote) -> str:
    """Whether the fare already covers a checked bag — the usual reason a price 'changes' later."""
    if q.bags is None:
        return ""
    return f"🧳 {q.bags} ta" if q.bags else "🧳 yo'q"


def _line(index: int, q: PriceQuote) -> str:
    """One booking-board row: price first (that's what's being compared), then who and how."""
    price = _money(q)
    if q.deep_link:
        price = f'<a href="{_e(q.deep_link)}">{price}</a>'
    detail = " · ".join(
        x for x in (q.depart_at, _duration(q), _stops(q), _bags(q), q.flight_number) if x
    )
    who = _e(q.airline) or "—"
    return f"{index}. <b>{price}</b> — {who}\n     <i>{_e(detail)}</i>" if detail else (
        f"{index}. <b>{price}</b> — {who}"
    )


def format_digest(watch: Watch, cheapest: list[PriceQuote], previous: PriceQuote | None) -> str:
    """Build the twice-daily card: route header, price-change badge, top-N cheapest with links."""
    route = f"{watch.origin} → {watch.destination}"
    header = f"<b>✈️ {_e(route)} · {watch.depart_date.isoformat()}</b>"
    lines = [header]

    best = cheapest[0]
    if previous is not None and previous.price != best.price:
        delta = best.price - previous.price
        if delta < 0:
            lines.append(f"↓ <b>{abs(delta)} {best.currency.upper()} arzonlashdi</b>")
        else:
            lines.append(f"↑ {delta} {best.currency.upper()} qimmatlashdi")

    if watch.threshold_price is not None and best.price <= watch.threshold_price:
        lines.append(f"🔥 <b>ALERT</b> — narx {watch.threshold_price} {best.currency.upper()} dan past!")

    lines.append("")
    lines.extend(_line(i, q) for i, q in enumerate(cheapest, start=1))
    return "\n".join(lines)


async def send_text(chat_id: str, text: str, preview: bool = False) -> bool:
    if settings.dry_run:
        log.info("DRY_RUN would send to %s:\n%s\n", chat_id, text)
        return True
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    url = API.format(token=settings.telegram_bot_token, method="sendMessage")
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": not preview,
            },
        )
    if resp.status_code != 200:
        log.error("sendMessage failed %s: %s", resp.status_code, resp.text[:200])
        return False
    return True
