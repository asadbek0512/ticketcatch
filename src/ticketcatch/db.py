from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, asc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import settings
from .models import Preference, PriceQuote, Watch

_db_path = Path(settings.db_path)
_db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(f"sqlite+aiosqlite:///{_db_path}", echo=False)
_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Columns added after the first release. create_all() only creates missing *tables*, so an
# existing pricequote table needs them bolted on by hand.
_ADDED_COLUMNS = {"stops": "INTEGER", "duration_min": "INTEGER", "bags": "INTEGER"}


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        rows = await conn.exec_driver_sql("PRAGMA table_info(pricequote)")
        existing = {r[1] for r in rows.fetchall()}
        for name, sql_type in _ADDED_COLUMNS.items():
            if name not in existing:
                await conn.exec_driver_sql(f"ALTER TABLE pricequote ADD COLUMN {name} {sql_type}")


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with _session_maker() as session:
        yield session


async def get_preference(session: AsyncSession, user_id: str) -> Preference:
    """The user's current menu selection, created with defaults the first time they open it."""
    rows = await session.exec(select(Preference).where(Preference.user_id == user_id))
    pref = rows.first()
    if pref is None:
        pref = Preference(user_id=user_id)
        session.add(pref)
        await session.commit()
        await session.refresh(pref)
    return pref


async def active_watches(session: AsyncSession) -> list[Watch]:
    rows = await session.exec(select(Watch).where(Watch.active == True))  # noqa: E712
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
