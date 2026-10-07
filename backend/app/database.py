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
engine_kwargs = {
    "echo": False,
    "future": True,
}
if "sqlite" in db_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(
    db_url,
    **engine_kwargs
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


async def init_db(target_engine=None) -> None:
    """
    Creates database tables if they do not exist and performs idempotent schema migrations
    to ensure all model columns exist across PostgreSQL and SQLite.
    """
    active_engine = target_engine or engine
    async with active_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Idempotent column migrations for existing tables
        migrations = [
            ("cities", "latitude", "DOUBLE PRECISION", "FLOAT"),
            ("cities", "longitude", "DOUBLE PRECISION", "FLOAT"),
            ("events", "latitude", "DOUBLE PRECISION", "FLOAT"),
            ("events", "longitude", "DOUBLE PRECISION", "FLOAT"),
            ("events", "rejection_reason", "TEXT", "TEXT"),
            ("events", "organization_id", "VARCHAR(36)", "VARCHAR(36)"),
            ("events", "allow_event_contact", "BOOLEAN DEFAULT FALSE", "BOOLEAN DEFAULT 0"),
            ("events", "source_type", "VARCHAR(30) DEFAULT 'user'", "VARCHAR(30) DEFAULT 'user'"),
            ("events", "source_name", "VARCHAR(100)", "VARCHAR(100)"),
            ("events", "external_id", "VARCHAR(255)", "VARCHAR(255)"),
            ("events", "source_url", "VARCHAR(1024)", "VARCHAR(1024)"),
            ("events", "last_synced_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
            ("users", "avatar_url", "VARCHAR(1024)", "TEXT"),
            ("users", "default_city_id", "VARCHAR(50)", "TEXT"),
            ("broadcasts", "attribution_token", "VARCHAR(32)", "VARCHAR(32)"),
            ("broadcast_recipients", "opened_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
            ("broadcast_recipients", "attributed_interest_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
            ("broadcast_recipients", "attributed_rsvp_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
            ("payment_orders", "customer_email", "VARCHAR(255)", "VARCHAR(255)"),
            ("payment_orders", "service_name", "VARCHAR(255) DEFAULT 'Ivently Pro — доступ на 30 дней'", "VARCHAR(255) DEFAULT 'Ivently Pro — доступ на 30 дней'"),
            ("payment_orders", "confirmation_url", "VARCHAR(1024)", "VARCHAR(1024)"),
            ("payment_orders", "paid_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
            ("payment_orders", "expires_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
            ("payment_orders", "receipt_status", "VARCHAR(30) DEFAULT 'pending'", "VARCHAR(30) DEFAULT 'pending'"),
            ("payment_orders", "receipt_url", "VARCHAR(1024)", "VARCHAR(1024)"),
            ("payment_orders", "receipt_issued_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
            ("payment_orders", "pro_extended_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
            ("payment_orders", "success_notified_at", "TIMESTAMP WITH TIME ZONE", "TIMESTAMP"),
            ("payment_orders", "metadata_json", "TEXT", "TEXT"),
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
                    if existing_cols and col not in existing_cols:
                        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {sqlite_type};"))
                        logger.info(f"Added column {col} to SQLite table {table}")
                except Exception as e:
                    logger.warning(f"SQLite column migration note ({table}.{col}): {e}")

        # Idempotent index creation
        indexes = [
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_broadcasts_attribution_token ON broadcasts (attribution_token);",
            "CREATE INDEX IF NOT EXISTS idx_broadcast_recipients_attr ON broadcast_recipients (user_id, broadcast_id, opened_at);",
            "CREATE INDEX IF NOT EXISTS idx_organization_plans_org_status ON organization_plans (organization_id, status);",
            "CREATE INDEX IF NOT EXISTS idx_events_source_external ON events (source_name, external_id);",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_orders_provider_payment_id ON payment_orders (provider, provider_payment_id);",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_orders_idempotency_key ON payment_orders (idempotency_key);",
            "CREATE INDEX IF NOT EXISTS idx_payment_orders_org_status ON payment_orders (organization_id, status);",
            "CREATE INDEX IF NOT EXISTS idx_payment_transactions_order_created ON payment_transactions (payment_order_id, created_at);",
            "CREATE INDEX IF NOT EXISTS idx_payment_webhook_logs_event_provider ON payment_webhook_logs (event_id, provider);",
        ]
        for idx_sql in indexes:
            try:
                await conn.execute(text(idx_sql))
            except Exception as e:
                logger.warning(f"Index migration note ({idx_sql}): {e}")

    logger.info("Database tables and migrations initialized successfully.")


async def close_db() -> None:
    """Closes database connections on application shutdown."""
    await engine.dispose()
    logger.info("Database connections closed.")
