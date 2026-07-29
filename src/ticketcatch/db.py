import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, fields
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, asc, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import settings
from .models import Preference, PriceQuote, SearchCache, Watch, utcnow
from .sources import Quote

_db_path = Path(settings.db_path)
_db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(f"sqlite+aiosqlite:///{_db_path}", echo=False)
_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

CACHE_SWEEP_FACTOR = 4  # rows older than this many TTLs are dead weight, not a fallback

# Columns added after a table already shipped. create_all() only creates missing *tables*, so
# live databases need these bolted on by hand — quoted defaults because SQLite writes them into
# every existing row.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "pricequote": {
        "stops": "INTEGER",
        "duration_min": "INTEGER",
        "bags": "INTEGER",
        "return_at": "TEXT DEFAULT ''",
        "return_stops": "INTEGER",
    },
    "watch": {
        "currency": f"TEXT DEFAULT '{settings.currency.lower()}'",
        "market": f"TEXT DEFAULT '{settings.market.lower()}'",
        "lang": f"TEXT DEFAULT '{settings.default_lang}'",
        "return_date": "DATE",
        "paused": "BOOLEAN DEFAULT 0",
    },
    "preference": {
        "lang": f"TEXT DEFAULT '{settings.default_lang}'",
        "currency": f"TEXT DEFAULT '{settings.currency.lower()}'",
        "market": f"TEXT DEFAULT '{settings.market.lower()}'",
        "searches": "INTEGER DEFAULT 0",
        "return_date": "DATE",
    },
}


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        for table, columns in _ADDED_COLUMNS.items():
            rows = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
            existing = {r[1] for r in rows.fetchall()}
            if not existing:  # create_all just made it — already has every column
                continue
            for name, sql_type in columns.items():
                if name not in existing:
                    await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}")


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with _session_maker() as session:
        yield session


async def get_preference(
    session: AsyncSession, user_id: str, lang_hint: str | None = None
) -> Preference:
    """The user's current menu selection, created with defaults the first time they open it.

    lang_hint is Telegram's client language, used only at creation: a new user should see their
    own language immediately, but someone who later picked a language in Settings keeps it."""
    rows = await session.exec(select(Preference).where(Preference.user_id == user_id))
    pref = rows.first()
    if pref is None:
        pref = Preference(user_id=user_id)
        if lang_hint:
            pref.lang = lang_hint
        session.add(pref)
        await session.commit()
        await session.refresh(pref)
    return pref


_QUOTE_FIELDS = {f.name for f in fields(Quote)}


async def cached_offers(session: AsyncSession, key: str, max_age: int) -> list[Quote] | None:
    """The newest still-fresh search for this key, or None. max_age <= 0 disables the cache."""
    if max_age <= 0:
        return None
    cutoff = utcnow() - timedelta(seconds=max_age)
    rows = await session.exec(
        select(SearchCache)
        .where(SearchCache.cache_key == key, SearchCache.created_at >= cutoff)
        .order_by(desc(SearchCache.created_at))
        .limit(1)
    )
    row = rows.first()
    if row is None:
        return None
    try:
        raw = json.loads(row.payload)
    except ValueError:
        return None
    # Tolerate rows written by an older build: unknown keys are dropped, missing ones default.
    return [Quote(**{k: v for k, v in item.items() if k in _QUOTE_FIELDS}) for item in raw]


async def store_offers(session: AsyncSession, key: str, offers: list[Quote]) -> None:
    """Replace this key's cached result and sweep long-expired rows so the table stays small."""
    stale = utcnow() - timedelta(seconds=settings.cache_ttl_seconds * CACHE_SWEEP_FACTOR)
    await session.execute(delete(SearchCache).where(SearchCache.cache_key == key))
    await session.execute(delete(SearchCache).where(SearchCache.created_at < stale))
    session.add(SearchCache(cache_key=key, payload=json.dumps([asdict(o) for o in offers])))
    await session.commit()


async def active_watches(session: AsyncSession) -> list[Watch]:
    """What the poller should price now. A paused watch still exists and still owns its history —
    it just costs nothing and sends nothing until the user resumes it."""
    rows = await session.exec(
        select(Watch).where(Watch.active == True, Watch.paused == False)  # noqa: E712
    )
    return list(rows.all())


async def user_watches(session: AsyncSession, user_id: str) -> list[Watch]:
    rows = await session.exec(
        select(Watch)
        .where(Watch.user_id == user_id, Watch.active == True)  # noqa: E712
        .order_by(asc(Watch.depart_date))
    )
    return list(rows.all())


async def counts(session: AsyncSession) -> dict[str, int]:
    """Headline numbers for /stats and the health check."""
    users = await session.exec(select(func.count()).select_from(Preference))
    watches = await session.exec(
        select(func.count()).select_from(Watch).where(Watch.active == True)  # noqa: E712
    )
    quotes = await session.exec(select(func.count()).select_from(PriceQuote))
    searches = await session.exec(select(func.coalesce(func.sum(Preference.searches), 0)))
    return {
        "users": users.first() or 0,
        "watches": watches.first() or 0,
        "quotes": quotes.first() or 0,
        "searches": searches.first() or 0,
    }


async def price_history(
    session: AsyncSession, route_key: str, currency: str, limit: int = 30
) -> list[tuple[datetime, int]]:
    """The cheapest price at each capture, oldest first — "is this route getting dearer?".

    One row per batch, not per quote: the poller stamps every row of a cycle with the same
    captured_at, so grouping by it turns the quote table back into the sequence of moments we
    looked. Only `currency` batches count, for the same reason last_cheapest filters on it — a
    KRW price next to a USD one is a graph of the settings screen, not of the fare.

    The newest `limit` batches are read and then reversed, so a long-lived watch shows its recent
    trend rather than its first month."""
    rows = await session.exec(
        select(PriceQuote.captured_at, func.min(PriceQuote.price))
        .where(PriceQuote.route_key == route_key, PriceQuote.currency == currency)
        .group_by(PriceQuote.captured_at)
        .order_by(desc(PriceQuote.captured_at))
        .limit(limit)
    )
    return [(at, int(price)) for at, price in reversed(list(rows.all()))]


async def last_board(
    session: AsyncSession, route_key: str, currency: str
) -> list[PriceQuote]:
    """The whole newest capture, cheapest first — what the last poll actually found.

    This is what makes a watch answer instantly. The prices the user was sent this morning are
    already in the table, so opening a watch is a read, not a minute of scraping: waiting for four
    websites to re-confirm a number we already have is a worse answer, not a fresher one. The
    captured_at on the rows tells them how old it is, and 🔍 is there when they want it live."""
    latest = await session.exec(
        select(func.max(PriceQuote.captured_at)).where(
            PriceQuote.route_key == route_key, PriceQuote.currency == currency
        )
    )
    latest_at = latest.first()
    if latest_at is None:
        return []
    rows = await session.exec(
        select(PriceQuote)
        .where(
            PriceQuote.route_key == route_key,
            PriceQuote.captured_at == latest_at,
            PriceQuote.currency == currency,
        )
        .order_by(asc(PriceQuote.price))
    )
    return list(rows.all())


async def last_cheapest(session: AsyncSession, route_key: str, currency: str) -> PriceQuote | None:
    """The cheapest quote from the most recent capture batch — the baseline we compare against.
    A batch shares one captured_at (set in the poller), so we find the latest batch timestamp,
    then return its lowest-price row. Only batches priced in `currency` count: comparing 333 USD
    against 450000 KRW would report a fake price jump the day the currency setting changes."""
    latest = await session.exec(
        select(func.max(PriceQuote.captured_at)).where(
            PriceQuote.route_key == route_key, PriceQuote.currency == currency
        )
    )
    latest_at = latest.first()
    if latest_at is None:
        return None
    rows = await session.exec(
        select(PriceQuote)
        .where(
            PriceQuote.route_key == route_key,
            PriceQuote.captured_at == latest_at,
            PriceQuote.currency == currency,
        )
        .order_by(asc(PriceQuote.price))
        .limit(1)
    )
    return rows.first()
