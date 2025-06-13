import asyncio

from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError


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

        if dialect == "postgresql":
            admin_url = url.set(database="postgres")
        elif dialect in ("mysql", "mariadb"):
            admin_url = url.set(database=None)
        else:
            raise RuntimeError(f"Unsupported SQL dialect: {dialect}")

        admin_url = admin_url.render_as_string(hide_password=False)
        engine = create_engine(
            admin_url, isolation_level="AUTOCOMMIT" if dialect == "postgresql" else None
        )

        with engine.connect() as conn:
            if dialect == "postgresql":
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": database_name},
                ).scalar()
            elif dialect in ("mysql", "mariadb"):
                with conn.execution_options(isolation_level="AUTOCOMMIT"):
                    result = conn.execute(text("SHOW DATABASES"))
                    exists = database_name in [row[0] for row in result]

            if exists:
                logger.info(f"Database '{database_name}' already exists.")
                return

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


async def create_database_if_not_exists(db_url: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, create_database_if_not_exists_sync, db_url)
