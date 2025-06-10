from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from papi.core.settings import get_config


@asynccontextmanager
async def get_sql_session() -> AsyncGenerator[AsyncSession, None]:
    settings = get_config()
    if not settings.database.sql_uri:
        raise RuntimeError("sql_uri is not configured in config.yaml.")

    engine = create_async_engine(settings.database.sql_uri, future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            raise


async def sql_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_sql_session() as session:
        yield session
