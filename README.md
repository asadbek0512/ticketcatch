# TicketCatch

Telegram bot that watches flight prices across multiple sources and sends the cheapest options
with links **twice a day**, flagging price drops and threshold alerts.

Built on the jobcatch architecture (SQLite + httpx + Telegram + a source registry), but instead of
"is this posting new?" the core question is **"did the price drop?"**.

## Status

Live. Runs on the OCI server under pm2 (`ticketcatch-bot` + `ticketcatch-poll`), reboot-safe.
The digest is a real booking board: every airline flying the route that day, cheapest first,
with departure time, duration, stop count and flight number.

Not tied to one route or one country any more: ~140 airports worldwide, three interface languages
(uz/ru/en), a per-user currency and market, and one-way or round-trip search. Started as ICN ⇄ TAS
in Korean won; that is now just the default.

Four sources are polled and merged: **Kiwi.com** (bookable fares priced for the user's market,
per-itinerary booking link, baggage allowance — the primary source), **Google Flights** (covers
carriers Kiwi lacks), **Trip.com** (OTA board, read with a headless browser — it has no API and
blocks plain HTTP), and **Aviasales** (cached fares, but often the cheapest quote on a flight the
others also list). Duffel stays unregistered: its free tier is test-mode and returns invented
airlines and fares. Skyscanner and Aviata.kz are not reachable — both serve a bot challenge even
in a real browser.

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
python -m ticketcatch loop       # continuous — checks every POLL_INTERVAL_SECONDS (12h)
uv run pytest tests -q           # parser / i18n / airport / dedupe tests
```

In production the bot and the loop run as two processes (e.g. pm2 on the OCI server).

## Commands

| Command | What it does |
|---|---|
| `/start` | Welcome card → the search panel |
| `/qidir` | The panel: from / to / date / return / search / watch |
| `/list` | Active watches — tap one to open its history, alert and pause |
| `/sozlama` | Language, currency, market |
| `/help` | How it works, in the user's language |
| `/stats` | Owner-only: users, watches, quotes, searches |

## Architecture

| File | Role |
|---|---|
| `bot.py` | Aiogram — commands, callbacks, free-text airport search |
| `menu.py` | Inline menu — panel, pickers, return dates, calendar strip, watch screens, settings |
| `history.py` | A watch's stored prices → sparkline + "book now or wait" (pure, no I/O) |
| `i18n.py` | uz/ru/en tables, months, weekdays, country names; `t(lang, key, **kw)` |
| `airports.py` | ~140 airports in 8 regions; ranked fuzzy `search()` |
| `money.py` | Markets (point of sale) vs currencies, price formatting |
| `browser.py` | One shared Chromium for the whole process, gated by a semaphore |
| `search.py` | `fetch_offers` (parallel + cached), `day_prices` (cheapest-day strip), `dedupe` |
| `ratelimit.py` | `Cooldown` — per-user search throttle |
| `sources/__init__.py` | `Quote`, `SearchOpts` (currency + market), `fetch_json`, airline directory |
| `sources/kiwi.py` | Kiwi.com GraphQL search → bookable itineraries (primary source) |
| `sources/googleflights.py` | Google Flights search → every itinerary that day (cross-check) |
| `sources/tripcom.py` | Trip.com result board, scraped through the shared browser |
| `sources/aviasales.py` | Travelpayouts cached fares — cheap quotes, may already be sold |
| `registry.py` | `SOURCES` map — every registered source is merged and deduped |
| `models.py` | `Watch`, `PriceQuote`, `Preference` (per-user settings), `SearchCache` |
| `ops/` | `deploy.sh` (pull + restart), `healthcheck.sh` (watchdog), `backup.sh` |
| `db.py` | async SQLite, column migrations, cache read/write, stats |
| `poller.py` | group by route+market → fetch in parallel → compare → notify → persist |
| `notifier.py` | Telegram digest card, price-drop badge, send pacing and 429 retries |

**Round trips are priced as a pair, not as two tickets.** Adding a return date changes the query,
not just the display: Kiwi switches GraphQL root field, Trip.com flips `triptype`, Google searches
both legs. So a round trip is a different product from the same outbound flown one way — it gets
its own cache entry, its own `route_key`, and its own watch. Kiwi describes the return leg;
Google and Trip.com price the pair against the outbound they list and leave `return_at` empty,
which is why the board can show the same outbound from two sources without merging them.

**A watch is a screen, not a row.** Tapping it in `/list` opens price history, the threshold alert
and pause. The history costs nothing — the poller already captured every one of those prices, so
the card is a database read, and `price_history` collapses each capture batch to its cheapest quote
because the graph tracks "what could I have paid", not every quote we saw. The sparkline is scaled
to that route's own range, and the verdict (book / wait / no movement) is the part users act on.
Threshold buttons are derived from the observed cheapest, since "alert me under 500,000" is
meaningless until you know whether the route sells for 300,000 or 3,000,000.

**Looking costs nothing; searching costs a minute.** The poller prices every watch twice a day and
stores the whole board, so `/list` and the watch screen are database reads: `last_cheapest` puts a
price and its age next to every row, `last_board` reprints the newest capture in full. Making a tap
wait ~60s for four websites to re-confirm a number already on disk would be a worse answer, not a
fresher one — every stored price is stamped with how old it is (`ago_label`), and 🔍 runs a live
search for people who want one. The digest, the on-demand board and the stored board all render
through `notifier.format_rows`, so the same prices read identically however you arrived at them.

**Pause is its own column.** `active=False` means deleted; `paused=True` keeps the watch and its
history but takes it out of `active_watches()`. Reusing one flag for both would mean stopping the
messages for a week destroys the price history that makes "↓ cheaper" possible.

### Three things worth knowing

**Market is not currency.** `market` is the country the ticket is bought from and changes the
fare itself; `currency` only changes how that fare is written. A watch copies both at creation
time and never re-reads them, because "↓ 40,000 KRW cheaper" only means something if every
capture of that watch was priced the same way.

**Airline codes are resolved after the gather, not during it.** Trip.com can only read a two-letter
code off the carrier logo; the code→name directory is filled by Google and Kiwi. Sources now run
concurrently, so there is no ordering guarantee — `search._named()` does the lookup once every
source has reported. Move it back inside a parser and Trip.com quotes start reading `OZ` again.

## Adding a source

1. Write `sources/aviata.py` with `SOURCE = "aviata"` and
   ```python
   async def fetch(origin, destination, depart, opts: SearchOpts | None = None,
                   ret: date | None = None) -> list[Quote]
   ```
   Read prices with `opts.currency` / `opts.market`, never from `settings`. If it cannot price a
   round trip, raise `SourceError` when `ret` is set — the board drops it and keeps the others.
2. If it needs a browser, use `async with browser.new_page() as page` — never launch your own.
3. Register it in `registry.py`. The poller picks it up automatically and merges its offers.

## Configuration

Beyond `TELEGRAM_BOT_TOKEN`, the knobs that matter (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `DEFAULT_LANG` | `uz` | Interface language before the user picks one |
| `CURRENCY` / `MARKET` | `krw` / `kr` | Default point of sale |
| `BROWSER_CONCURRENCY` | `3` | Simultaneous browser pages (RAM ceiling) |
| `ROUTE_CONCURRENCY` | `4` | Routes polled at once |
| `CACHE_TTL_SECONDS` | `1800` | How long a searched route+day stays cached |
| `SEARCH_COOLDOWN_SECONDS` | `60` | Per-user gap between manual searches |

The cache lives in the database, not in memory, so the bot and the poller — separate pm2
processes — share it.

## Deploy (OCI server)

**Push to `main` and it deploys itself.** The server is a checkout of this repo (read-only deploy
key) and a cron job runs `ops/deploy.sh` every minute: it fetches, and if the remote moved it
resets, re-syncs dependencies and restarts both pm2 processes. `data/` and `.env` are gitignored,
so the live database and secrets survive every deploy.

GitHub Actions is billing-locked on this account, so the workflow in `.github/workflows` sits
dormant and deployment pulls from the server instead. Nothing changes when billing is fixed —
the workflow only runs tests.

```bash
ssh freeserver 'bash ~/ticketcatch/ops/deploy.sh'   # deploy now instead of waiting a minute
ssh freeserver 'tail ~/ticketcatch/data/deploy.log' # what the cron did
```

The server needs Python 3.11 (uv installs it; the system python is 3.10). New columns are added
by `db.init_db()` on startup — no manual migration step.

### Watchdog and backups

| Script | Cron | What it does |
|---|---|---|
| `ops/healthcheck.sh` | every 15 min | pm2 status + "has the poller written a price in 10h?" → Telegram alert to `TELEGRAM_OWNER_ID`, once per failure, plus a recovery message |
| `ops/backup.sh` | 03:30 daily | `sqlite3 .backup` (safe on a live DB) → gzip into `~/backups/ticketcatch`, 14 days kept |

The health check exists because pm2 only sees crashes. A process that is *online* but wedged — a
stuck browser, a dead long-poll — looks perfectly healthy to it and to nobody else.
