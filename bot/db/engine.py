from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot import config
from bot.db.models import Base

engine = create_async_engine(f"sqlite+aiosqlite:///{config.DB_PATH}")
session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
