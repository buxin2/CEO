"""Lightweight schema updates for production DBs (create_all does not alter existing tables)."""

import logging

from sqlalchemy import inspect, text

from models import db

logger = logging.getLogger(__name__)


def _table_exists(engine, table_name):
    return table_name in inspect(engine).get_table_names()


def _column_exists(engine, table_name, column_name):
    if not _table_exists(engine, table_name):
        return False
    columns = [c["name"] for c in inspect(engine).get_columns(table_name)]
    return column_name in columns


def _is_postgres(engine):
    return engine.dialect.name == "postgresql"


def _add_column(engine, table, column, postgres_def, sqlite_def):
    if _column_exists(engine, table, column):
        return
    ddl = postgres_def if _is_postgres(engine) else sqlite_def
    logger.info("Applying schema migration: ALTER TABLE %s ADD %s", table, column)
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def _ensure_cloudinary_settings_table(engine):
    if _table_exists(engine, "cloudinary_settings"):
        return
    logger.info("Creating cloudinary_settings table")
    if _is_postgres(engine):
        ddl = (
            "CREATE TABLE cloudinary_settings ("
            "id SERIAL PRIMARY KEY, "
            "cloud_name VARCHAR(80) DEFAULT '', "
            "encrypted_api_key TEXT DEFAULT '', "
            "encrypted_api_secret TEXT DEFAULT '', "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    else:
        ddl = (
            "CREATE TABLE cloudinary_settings ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "cloud_name VARCHAR(80) DEFAULT '', "
            "encrypted_api_key TEXT DEFAULT '', "
            "encrypted_api_secret TEXT DEFAULT '', "
            "updated_at DATETIME"
            ")"
        )
    with engine.begin() as conn:
        conn.execute(text(ddl))


def run_schema_migrations():
    """Add columns introduced after initial production deploy."""
    engine = db.engine

    # News + timetable link (added with Daily Opportunity feature)
    _add_column(
        engine,
        "timetable_items",
        "link_opportunity_id",
        "link_opportunity_id INTEGER",
        "link_opportunity_id INTEGER",
    )

    # PostgreSQL: add FK only if both tables exist and constraint missing
    if _is_postgres(engine) and _table_exists(engine, "opportunity_items"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DO $$ BEGIN "
                    "IF NOT EXISTS ("
                    "  SELECT 1 FROM pg_constraint WHERE conname = 'fk_timetable_items_link_opportunity'"
                    ") THEN "
                    "ALTER TABLE timetable_items "
                    "ADD CONSTRAINT fk_timetable_items_link_opportunity "
                    "FOREIGN KEY (link_opportunity_id) REFERENCES opportunity_items(id); "
                    "END IF; END $$;"
                )
            )

    _add_column(
        engine,
        "mentor_settings",
        "timezone_country",
        "timezone_country VARCHAR(80) DEFAULT ''",
        "timezone_country VARCHAR(80) DEFAULT ''",
    )
    _add_column(
        engine,
        "mentor_settings",
        "timezone_city",
        "timezone_city VARCHAR(80) DEFAULT ''",
        "timezone_city VARCHAR(80) DEFAULT ''",
    )
    _add_column(
        engine,
        "mentor_settings",
        "timezone_id",
        "timezone_id VARCHAR(64) DEFAULT ''",
        "timezone_id VARCHAR(64) DEFAULT ''",
    )

    _add_column(
        engine,
        "group_messages",
        "image_url",
        "image_url VARCHAR(500)",
        "image_url VARCHAR(500)",
    )

    _ensure_cloudinary_settings_table(engine)

    # Communities — paid membership + products inventory
    _add_column(engine, "communities", "community_type", "community_type VARCHAR(20) DEFAULT 'free'", "community_type VARCHAR(20) DEFAULT 'free'")
    _add_column(engine, "communities", "price_cents", "price_cents INTEGER DEFAULT 0", "price_cents INTEGER DEFAULT 0")
    _add_column(engine, "communities", "currency", "currency VARCHAR(10) DEFAULT 'USD'", "currency VARCHAR(10) DEFAULT 'USD'")
    _add_column(engine, "communities", "billing_interval", "billing_interval VARCHAR(20) DEFAULT 'one_time'", "billing_interval VARCHAR(20) DEFAULT 'one_time'")

    _add_column(engine, "community_products", "price_cents", "price_cents INTEGER DEFAULT 0", "price_cents INTEGER DEFAULT 0")
    _add_column(engine, "community_products", "quantity_available", "quantity_available INTEGER DEFAULT 0", "quantity_available INTEGER DEFAULT 0")
    _add_column(engine, "community_products", "quantity_reserved", "quantity_reserved INTEGER DEFAULT 0", "quantity_reserved INTEGER DEFAULT 0")
    _add_column(engine, "community_products", "digital_delivery_url", "digital_delivery_url VARCHAR(500) DEFAULT ''", "digital_delivery_url VARCHAR(500) DEFAULT ''")
    _add_column(engine, "community_products", "digital_delivery_text", "digital_delivery_text TEXT DEFAULT ''", "digital_delivery_text TEXT DEFAULT ''")
    _add_column(engine, "community_products", "fee_percent", "fee_percent DOUBLE PRECISION DEFAULT 0", "fee_percent REAL DEFAULT 0")

    _add_column(engine, "community_memberships", "payment_id", "payment_id INTEGER", "payment_id INTEGER")

    db.session.commit()
    logger.info("Schema migrations complete.")
