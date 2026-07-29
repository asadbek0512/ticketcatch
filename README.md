# TicketCatch

Telegram bot that watches flight prices (ICN ⇄ TAS to start) across multiple sources and sends
the cheapest options with links **three times a day**, flagging price drops and threshold alerts.

Built on the jobcatch architecture (SQLite + httpx + Telegram + a source registry), but instead of
"is this posting new?" the core question is **"did the price drop?"**.

## Status

Live. Runs on the OCI server under pm2 (`ticketcatch-bot` + `ticketcatch-poll`), reboot-safe.
The digest is a real booking board: every airline flying the route that day, cheapest first,
with departure time, duration, stop count and flight number.

Four sources are polled and merged: **Kiwi.com** (bookable fares priced for `MARKET`, per-itinerary
booking link, baggage allowance — the primary source), **Google Flights** (covers carriers Kiwi
lacks), **Trip.com** (OTA board, read with a headless browser — it has no API and blocks plain
HTTP), and **Aviasales** (cached fares, but often the cheapest quote on a flight the others also
list). Duffel stays unregistered: its free tier is test-mode and returns invented airlines and
fares. Skyscanner and Aviata.kz are not reachable — both serve a bot challenge even in a real
browser.

The same flight quoted by several sites collapses to the cheapest of them, so the board answers
"who sells this seat for the least".

## Setup

```bash
cd "$HOME"                       # macOS: avoid EPERM uv_cwd when the repo is under ~/Desktop
uv sync                          # or: pip install -e .
uv run playwright install chromium   # once — the Trip.com source drives a real browser
cp .env.example .env             # fill TELEGRAM_BOT_TOKEN (sources need no key)
```

## Run

```bash
python -m ticketcatch bot        # run the Telegram bot (user adds watches)
python -m ticketcatch poll       # one price-check cycle (DRY_RUN logs, doesn't send)
python -m ticketcatch loop       # continuous — checks every POLL_INTERVAL_SECONDS (8h)
```

In production the bot and the loop run as two processes (e.g. pm2 on the OCI server).

## Architecture

| File | Role |
|---|---|
| `menu.py` | Inline menu — route/date pickers, panel and result keyboards |
| `search.py` | `fetch_offers` — every source merged and deduped; shared by poller and menu |
| `sources/__init__.py` | `fetch_json` helper, `Quote` dataclass, `SourceError` |
| `sources/kiwi.py` | Kiwi.com GraphQL search → bookable itineraries (primary source) |
| `sources/googleflights.py` | Google Flights search → every itinerary that day (cross-check) |
| `sources/tripcom.py` | Trip.com result board, scraped with headless Playwright |
| `sources/aviasales.py` | Travelpayouts cached fares — cheap quotes, may already be sold |
| `registry.py` | `SOURCES` map — every registered source is merged and deduped |
| `models.py` | `Watch` (user request) + `PriceQuote` (price history) |
| `db.py` | async SQLite, `active_watches`, `last_cheapest` |
| `poller.py` | group by route → fetch → dedupe (cheapest per flight) → compare → notify → persist |
| `notifier.py` | Telegram digest card (price-drop badge, threshold alert) |
| `bot.py` | Aiogram — `/qidir` menu, on-demand search, `/add`, `/list`, `/remove` |

## Adding a source

1. Write `sources/aviata.py` with `SOURCE = "aviata"` and
   `async def fetch(origin, destination, depart) -> list[Quote]`.
2. Register it in `registry.py`. The poller picks it up automatically and merges its offers.

## Deploy (OCI server)

```bash
# data/ must stay excluded — it holds the live watches and price history, which a local
# copy would silently overwrite (the DB is data/ticketcatch.sqlite, not *.db).
rsync -az --delete --exclude .venv --exclude .git --exclude __pycache__ --exclude data ./ freeserver:~/ticketcatch/
ssh freeserver 'cd ~/ticketcatch && ~/.local/bin/uv sync --python 3.11 && pm2 restart ticketcatch-bot ticketcatch-poll'
```

The server needs Python 3.11 (uv installs it; the system python is 3.10).
