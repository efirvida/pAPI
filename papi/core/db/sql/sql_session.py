from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from loguru import logger
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from papi.core.settings import get_config

# Module-level logger
log = logger.bind(module="database")


@asynccontextmanager
async def get_sql_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Asynchronous context manager for database sessions with production-grade features.

    Features:
    - Connection pooling with configurable size
    - Automatic transaction management
    - Error handling with rollback safety
    - Connection recycling
    - Timeout configurations
    - Comprehensive logging

    Usage:
        async with get_sql_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

    Raises:
        RuntimeError: For configuration errors
        SQLAlchemyError: For database operation errors

    Yields:
        AsyncSession: Database session instance
    """
    config = get_config()
    sql_alchemy_cfg = config.database.get_backend("sqlalchemy").get_defined_fields()

    # Validate configuration
    if not sql_uri:
        log.critical("Database SQL_URI not configured")
        raise RuntimeError("Database configuration missing: SQL_URI not set")

    # Create engine with production-ready settings
    engine = create_async_engine(**sql_alchemy_cfg)

    # Configure session factory
    session_factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
    )

    # Session management
    session = session_factory()
    try:
        log.debug("Database session opened")
        yield session
        await session.commit()
        log.debug("Transaction committed successfully")
    except SQLAlchemyError as e:
        log.error(f"Database operation failed: {str(e)}")
        await session.rollback()
        log.warning("Transaction rolled back due to error")
        raise
    except Exception as e:
        log.critical(f"Unexpected error in session: {str(e)}")
        await session.rollback()
        raise RuntimeError("Database session aborted") from e
    finally:
        await session.close()
        log.debug("Database session closed")


async def sql_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency generator for FastAPI route handlers with session management.

    Designed for use with FastAPI dependency injection system:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(sql_session)):
            ...

    Features:
    - Proper session lifecycle management
    - Automatic commit/rollback
    - Error handling
    - Resource cleanup

    Yields:
        AsyncSession: Database session instance
    """
    async with get_sql_session() as session:
        try:
            yield session
        finally:
            # Ensures session closure even if middleware catches exceptions
            if session.is_active:
                await session.close()
                log.debug("Route session closed in dependency")
