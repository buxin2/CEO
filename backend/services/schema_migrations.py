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

    db.session.commit()
    logger.info("Schema migrations complete.")
