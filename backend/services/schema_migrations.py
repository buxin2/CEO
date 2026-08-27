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


def _ensure_store_customer_notices_table(engine):
    if _table_exists(engine, "store_customer_notices"):
        return
    logger.info("Creating store_customer_notices table")
    if _is_postgres(engine):
        ddl = (
            "CREATE TABLE store_customer_notices ("
            "id SERIAL PRIMARY KEY, "
            "store_customer_id INTEGER NOT NULL, "
            "title VARCHAR(255) DEFAULT '', "
            "body TEXT DEFAULT '', "
            "kind VARCHAR(40) DEFAULT 'message', "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "read_at TIMESTAMP"
            ")"
        )
    else:
        ddl = (
            "CREATE TABLE store_customer_notices ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "store_customer_id INTEGER NOT NULL, "
            "title VARCHAR(255) DEFAULT '', "
            "body TEXT DEFAULT '', "
            "kind VARCHAR(40) DEFAULT 'message', "
            "created_at DATETIME, "
            "read_at DATETIME"
            ")"
        )
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _ensure_payment_settings_table(engine):
    if _table_exists(engine, "payment_settings"):
        return
    logger.info("Creating payment_settings table")
    if _is_postgres(engine):
        ddl = (
            "CREATE TABLE payment_settings ("
            "id SERIAL PRIMARY KEY, "
            "mode VARCHAR(10) DEFAULT 'live', "
            "brand_name VARCHAR(120) DEFAULT 'Store', "
            "enc_paypal_client_id TEXT DEFAULT '', "
            "enc_paypal_secret TEXT DEFAULT '', "
            "enc_paypal_sandbox_client_id TEXT DEFAULT '', "
            "enc_paypal_sandbox_secret TEXT DEFAULT '', "
            "enc_modem_public_key TEXT DEFAULT '', "
            "enc_modem_secret TEXT DEFAULT '', "
            "enc_modem_webhook_secret TEXT DEFAULT '', "
            "enc_modem_test_secret TEXT DEFAULT '', "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
    else:
        ddl = (
            "CREATE TABLE payment_settings ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "mode VARCHAR(10) DEFAULT 'live', "
            "brand_name VARCHAR(120) DEFAULT 'Store', "
            "enc_paypal_client_id TEXT DEFAULT '', "
            "enc_paypal_secret TEXT DEFAULT '', "
            "enc_paypal_sandbox_client_id TEXT DEFAULT '', "
            "enc_paypal_sandbox_secret TEXT DEFAULT '', "
            "enc_modem_public_key TEXT DEFAULT '', "
            "enc_modem_secret TEXT DEFAULT '', "
            "enc_modem_webhook_secret TEXT DEFAULT '', "
            "enc_modem_test_secret TEXT DEFAULT '', "
            "updated_at DATETIME"
            ")"
        )
    with engine.begin() as conn:
        conn.execute(text(ddl))


def _migrate_store_customer_google(engine):
    if not _table_exists(engine, "store_customers"):
        return
    _add_column(engine, "store_customers", "google_sub", "google_sub VARCHAR(64)", "google_sub VARCHAR(64)")
    _add_column(
        engine,
        "store_customers",
        "has_password",
        "has_password BOOLEAN DEFAULT TRUE",
        "has_password BOOLEAN DEFAULT 1",
    )
    if _is_postgres(engine):
        try:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE store_customers ALTER COLUMN phone DROP NOT NULL"))
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_store_customers_google_sub "
                    "ON store_customers (google_sub)"
                ))
        except Exception as exc:
            logger.info("store_customers google migration note: %s", exc)


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
    _ensure_payment_settings_table(engine)

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
    _add_column(
        engine,
        "communities",
        "image_url",
        "image_url VARCHAR(500) DEFAULT ''",
        "image_url VARCHAR(500) DEFAULT ''",
    )
    _add_column(
        engine,
        "community_memberships",
        "paid_until",
        "paid_until TIMESTAMP",
        "paid_until DATETIME",
    )

    _add_column(engine, "coupons", "store_product_id", "store_product_id INTEGER", "store_product_id INTEGER")

    for col, pg, sq in (
        ("origin_name", "origin_name VARCHAR(120) DEFAULT 'Store'", "origin_name VARCHAR(120) DEFAULT 'Store'"),
        ("origin_street", "origin_street VARCHAR(255) DEFAULT ''", "origin_street VARCHAR(255) DEFAULT ''"),
        ("origin_city", "origin_city VARCHAR(120) DEFAULT 'Greater Noida'", "origin_city VARCHAR(120) DEFAULT 'Greater Noida'"),
        ("origin_state", "origin_state VARCHAR(80) DEFAULT 'UP'", "origin_state VARCHAR(80) DEFAULT 'UP'"),
        ("origin_zip", "origin_zip VARCHAR(20) DEFAULT '201310'", "origin_zip VARCHAR(20) DEFAULT '201310'"),
        ("origin_country", "origin_country VARCHAR(8) DEFAULT 'IN'", "origin_country VARCHAR(8) DEFAULT 'IN'"),
        ("origin_phone", "origin_phone VARCHAR(32) DEFAULT ''", "origin_phone VARCHAR(32) DEFAULT ''"),
        ("origin_email", "origin_email VARCHAR(255) DEFAULT ''", "origin_email VARCHAR(255) DEFAULT ''"),
        ("default_weight_kg", "default_weight_kg DOUBLE PRECISION DEFAULT 0.6", "default_weight_kg REAL DEFAULT 0.6"),
        ("default_length_cm", "default_length_cm DOUBLE PRECISION DEFAULT 20", "default_length_cm REAL DEFAULT 20"),
        ("default_width_cm", "default_width_cm DOUBLE PRECISION DEFAULT 15", "default_width_cm REAL DEFAULT 15"),
        ("default_height_cm", "default_height_cm DOUBLE PRECISION DEFAULT 8", "default_height_cm REAL DEFAULT 8"),
        ("customs_signer", "customs_signer VARCHAR(120) DEFAULT ''", "customs_signer VARCHAR(120) DEFAULT ''"),
    ):
        _add_column(engine, "store_settings", col, pg, sq)

    _add_column(engine, "store_products", "weight_kg", "weight_kg DOUBLE PRECISION", "weight_kg REAL")
    _add_column(engine, "store_products", "length_cm", "length_cm DOUBLE PRECISION", "length_cm REAL")
    _add_column(engine, "store_products", "width_cm", "width_cm DOUBLE PRECISION", "width_cm REAL")
    _add_column(engine, "store_products", "height_cm", "height_cm DOUBLE PRECISION", "height_cm REAL")

    for col, pg, sq in (
        ("shipping_carrier", "shipping_carrier VARCHAR(120) DEFAULT ''", "shipping_carrier VARCHAR(120) DEFAULT ''"),
        ("shipping_service", "shipping_service VARCHAR(160) DEFAULT ''", "shipping_service VARCHAR(160) DEFAULT ''"),
        ("shipping_currency", "shipping_currency VARCHAR(10) DEFAULT ''", "shipping_currency VARCHAR(10) DEFAULT ''"),
        ("shipping_estimated_days", "shipping_estimated_days INTEGER", "shipping_estimated_days INTEGER"),
        ("shippo_rate_id", "shippo_rate_id VARCHAR(80) DEFAULT ''", "shippo_rate_id VARCHAR(80) DEFAULT ''"),
        ("shippo_shipment_id", "shippo_shipment_id VARCHAR(80) DEFAULT ''", "shippo_shipment_id VARCHAR(80) DEFAULT ''"),
        ("shipment_weight_kg", "shipment_weight_kg DOUBLE PRECISION", "shipment_weight_kg REAL"),
        ("shipment_length_cm", "shipment_length_cm DOUBLE PRECISION", "shipment_length_cm REAL"),
        ("shipment_width_cm", "shipment_width_cm DOUBLE PRECISION", "shipment_width_cm REAL"),
        ("shipment_height_cm", "shipment_height_cm DOUBLE PRECISION", "shipment_height_cm REAL"),
        ("shipping_zone", "shipping_zone VARCHAR(120) DEFAULT ''", "shipping_zone VARCHAR(120) DEFAULT ''"),
    ):
        _add_column(engine, "store_orders", col, pg, sq)

    _add_column(
        engine,
        "store_orders",
        "store_customer_id",
        "store_customer_id INTEGER",
        "store_customer_id INTEGER",
    )

    _ensure_store_customer_notices_table(engine)
    _migrate_store_customer_google(engine)

    db.session.commit()
    logger.info("Schema migrations complete.")
