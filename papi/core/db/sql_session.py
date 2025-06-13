from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from papi.core.settings import get_config


@asynccontextmanager
async def get_sql_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Asynchronous context manager that yields an SQLAlchemy asynchronous session.

    This function creates a SQLAlchemy async engine and session factory using
    the SQL URI specified in the application settings. It ensures that the session
    is properly committed or rolled back depending on whether an exception occurs.

    Raises:
        RuntimeError: If the SQL URI is not configured in `config.yaml`.
        SQLAlchemyError: If an exception occurs during the session.

    Yields:
        AsyncSession: An instance of SQLAlchemy asynchronous session.

    Example:
        ```python
        async with get_sql_session() as session:
            result = await session.execute(select(MyModel))
            data = result.scalars().all()
        ```
    """
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
    """
    Async generator dependency for frameworks like FastAPI that require dependency injection.

    Yields:
        AsyncSession: A SQLAlchemy async session from the context manager.

    Example (FastAPI):
        ```python
        from fastapi import Depends, APIRouter
        from sqlalchemy.ext.asyncio import AsyncSession

        router = APIRouter()


        @router.get("/items")
        async def list_items(session: AsyncSession = Depends(sql_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()
        ```
    """
    async with get_sql_session() as session:
        yield session
