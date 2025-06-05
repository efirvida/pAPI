import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Optional, Union

from loguru import logger
from redis.asyncio import Redis, from_url
from sqlalchemy import Select, create_engine, text
from sqlalchemy.engine import Result
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from papi.core.settings import get_config

_redis: Optional[Redis] = None


async def get_redis_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(
            get_config().database.redis_uri,
            decode_responses=True,
        )
    return _redis


@asynccontextmanager
async def get_sql_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Asynchronous context manager for a SQLAlchemy database session.

    It handles the session lifecycle, including automatic commit on success
    and rollback on exceptions.

    Yields:
        AsyncSession: A SQLAlchemy async session object.

    Raises:
        SQLAlchemyError: If a database operation fails.
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
    Dependency for FastAPI route handlers to provide a database session.

    It uses the async context manager get_db_session() internally.
    """
    async with get_sql_session() as session:
        yield session


async def query_helper(statement: Any) -> Union[list[Any], int, Result]:
    """
    Executes a SQLAlchemy statement using an async session and returns the result.

    Supports SELECT, INSERT, UPDATE, and DELETE operations.

    Args:
        statement (Any): A SQLAlchemy statement, such as `select(User)` or `insert(User)`.

    Returns:
        Union[list[Any], int, Result]:
            - List of results for SELECT statements.
            - Scalar list if selecting a single column.
            - Affected row count for INSERT/UPDATE/DELETE.
            - Raw Result object for other cases.

    Raises:
        RuntimeError: If a SQLAlchemy error occurs.
    """
    async with get_db_session() as session:
        try:
            result: Result = await session.execute(statement)

            if (
                getattr(statement, "is_insert", False)
                or getattr(statement, "is_update", False)
                or getattr(statement, "is_delete", False)
            ):
                # DML operation: return number of affected rows
                return result.rowcount

            if isinstance(statement, Select):
                # Single-column SELECT: return scalar values
                if len(statement.selected_columns) == 1:
                    return result.scalars().all()
                # Multi-column SELECT: return row tuples
                return result.all()

            # Fallback: return raw result
            return result

        except SQLAlchemyError as e:
            raise RuntimeError(f"SQLAlchemy error during query execution: {e}") from e


async def create_database_if_not_exists(db_url: str) -> None:
    """
    Asynchronously ensures that a SQL database exists.

    This function runs in an async environment and uses a thread executor
    internally to avoid blocking the event loop. It handles PostgreSQL, MySQL,
    MariaDB, and SQLite.

    Args:
        db_url (str): SQLAlchemy database URI, e.g., 'postgresql://user:pass@localhost/dbname'

    Raises:
        RuntimeError: If the database creation fails or is unsupported.
    """

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, create_database_if_not_exists_sync, db_url)


def _sync_driver_url(db_url: str) -> str:
    url = make_url(db_url)
    if url.drivername == "postgresql+asyncpg":
        return url.set(drivername="postgresql+psycopg2").render_as_string(
            hide_password=False
        )
    if url.drivername == "mysql+aiomysql":
        return url.set(drivername="mysql+pymysql").render_as_string(hide_password=False)
    if url.drivername == "mariadb+aiomysql":
        return url.set(drivername="mariadb+pymysql").render_as_string(
            hide_password=False
        )
    return db_url


def create_database_if_not_exists_sync(db_url: str) -> None:
    """
    Synchronous helper that performs the actual database creation logic.
    Should be called only via `run_in_executor`.

    Args:
        db_url (str): SQLAlchemy database URI.

    Raises:
        RuntimeError: If creation fails or dialect is unsupported.
    """
    try:
        sync_url = _sync_driver_url(db_url)
        url = make_url(sync_url)
        dialect = url.get_backend_name()
        database_name = url.database

        if dialect == "sqlite":
            logger.info("SQLite database requires no manual creation.")
            return

        if not database_name:
            raise ValueError("Database name is missing in the URI.")

        # Build admin connection URL
        if dialect == "postgresql":
            admin_url = url.set(database="postgres")
        elif dialect in ("mysql", "mariadb"):
            admin_url = url.set(database=None)
        else:
            raise RuntimeError(f"Unsupported SQL dialect: {dialect}")

        # Create engine with autocommit isolation level for the whole connection
        admin_url = admin_url.render_as_string(hide_password=False)
        engine = create_engine(
            admin_url, isolation_level="AUTOCOMMIT" if dialect == "postgresql" else None
        )

        with engine.connect() as conn:
            # Check if DB exists
            if dialect == "postgresql":
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": database_name},
                ).scalar()
            elif dialect in ("mysql", "mariadb"):
                # For MySQL/MariaDB we need to execute in autocommit mode
                with conn.execution_options(isolation_level="AUTOCOMMIT"):
                    result = conn.execute(text("SHOW DATABASES"))
                    exists = database_name in [row[0] for row in result]
            else:
                raise RuntimeError(f"Dialect '{dialect}' not yet supported.")

            if exists:
                logger.info(f"Database '{database_name}' already exists.")
                return

            # Create DB
            logger.info(f"Creating database '{database_name}'...")
            if dialect == "postgresql":
                conn.execute(text(f'CREATE DATABASE "{database_name}"'))
            elif dialect in ("mysql", "mariadb"):
                with conn.execution_options(isolation_level="AUTOCOMMIT"):
                    conn.execute(text(f"CREATE DATABASE `{database_name}`"))

            logger.info(f"Database '{database_name}' created successfully.")

    except SQLAlchemyError as exc:
        logger.exception("Database creation failed due to SQL error.")
        raise RuntimeError(f"Database creation failed due to SQL error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error during database creation.")
        raise RuntimeError(f"Unexpected error during database creation: {exc}")
