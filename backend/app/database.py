import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event, text
from app.config import settings

logger = logging.getLogger("evently.database")

Base = declarative_base()

# Configure engine with SQLite WAL and foreign keys if SQLite, or asyncpg for PostgreSQL
db_url = settings.async_database_url
connect_args = {}
if "sqlite" in db_url:
    connect_args = {"check_same_thread": False}

engine = create_async_engine(
    db_url,
    echo=False,
    connect_args=connect_args,
    future=True
)


# Enforce SQLite foreign keys and WAL mode on connect
@event.listens_for(engine.sync_engine, "connect")
def configure_sqlite_pragmas(dbapi_connection, connection_record):
    if "sqlite" in db_url:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Creates database tables if they do not exist and performs idempotent schema migrations
    to ensure all model columns exist across PostgreSQL and SQLite.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Idempotent column migrations for existing tables
        migrations = [
            ("cities", "latitude", "DOUBLE PRECISION", "FLOAT"),
            ("cities", "longitude", "DOUBLE PRECISION", "FLOAT"),
            ("events", "latitude", "DOUBLE PRECISION", "FLOAT"),
            ("events", "longitude", "DOUBLE PRECISION", "FLOAT"),
            ("events", "rejection_reason", "TEXT", "TEXT"),
            ("events", "organization_id", "VARCHAR(36)", "VARCHAR(36)"),
            ("users", "avatar_url", "VARCHAR(1024)", "TEXT"),
            ("users", "default_city_id", "VARCHAR(50)", "TEXT"),
        ]

        dialect_name = conn.dialect.name
        if "postgres" in dialect_name:
            for table, col, pg_type, _ in migrations:
                try:
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {pg_type};"))
                except Exception as e:
                    logger.warning(f"PostgreSQL column migration note ({table}.{col}): {e}")
        elif "sqlite" in dialect_name:
            for table, col, _, sqlite_type in migrations:
                try:
                    res = await conn.execute(text(f"PRAGMA table_info({table});"))
                    existing_cols = [row[1] for row in res.fetchall()]
                    if col not in existing_cols:
                        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {sqlite_type};"))
                        logger.info(f"Added column {col} to SQLite table {table}")
                except Exception as e:
                    logger.warning(f"SQLite column migration note ({table}.{col}): {e}")

    logger.info("Database tables and migrations initialized successfully.")


async def close_db() -> None:
    """Closes database connections on application shutdown."""
    await engine.dispose()
    logger.info("Database connections closed.")
