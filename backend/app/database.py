from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, DeclarativeBase
from app.config import settings

engine_kwargs = {
    "echo": False,
    "future": True,
    "pool_pre_ping": True,
}

if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs.update(
        {
            "pool_size": 5,
            "max_overflow": 0,
            "pool_recycle": 1800,
            "pool_timeout": 30,
        }
    )

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
