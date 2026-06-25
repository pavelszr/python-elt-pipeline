"""Load layer: idempotent upsert of FX rates into a DuckDB warehouse.

The destination table has a composite primary key of ``(date, base_currency,
currency)``. Loading deletes any overlapping keys first, then inserts the new
rows, so re-running an overlapping date range never produces duplicates
(incremental + idempotent).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import duckdb
import pandas as pd

from .config import Settings
from .logging_conf import get_logger

logger = get_logger("load")

# Columns persisted to the warehouse, in physical order.
_PERSIST_COLUMNS = ["date", "base_currency", "currency", "rate", "pct_change"]


@contextmanager
def connect(db_path: str) -> Iterator[duckdb.DuckDBPyConnection]:
    """Open a DuckDB connection as a context manager.

    Args:
        db_path: Path to the DuckDB file, or ``":memory:"`` for an in-memory db.

    Yields:
        An open DuckDB connection that is closed on exit.
    """
    conn = duckdb.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def ensure_table(conn: duckdb.DuckDBPyConnection, table: str) -> None:
    """Create the destination table if it does not already exist.

    Args:
        conn: An open DuckDB connection.
        table: Target table name.
    """
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            date DATE NOT NULL,
            base_currency VARCHAR NOT NULL,
            currency VARCHAR NOT NULL,
            rate DOUBLE NOT NULL,
            pct_change DOUBLE,
            ma_7 DOUBLE,
            ma_30 DOUBLE,
            loaded_at TIMESTAMP DEFAULT now(),
            PRIMARY KEY (date, base_currency, currency)
        )
        """
    )


def _ma_columns(frame: pd.DataFrame) -> list[str]:
    """Return moving-average columns present in the frame (e.g. ``ma_7``)."""
    return [c for c in frame.columns if c.startswith("ma_")]


def _ensure_ma_columns(
    conn: duckdb.DuckDBPyConnection, table: str, ma_cols: list[str]
) -> None:
    """Add any missing ``ma_<n>`` columns so dynamic windows still persist."""
    existing = {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            [table],
        ).fetchall()
    }
    for col in ma_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} DOUBLE")


def upsert_rates(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    frame: pd.DataFrame,
) -> int:
    """Idempotently upsert a long FX frame into ``table``.

    Overlapping primary keys are deleted before insertion, guaranteeing that a
    re-run over the same (or an overlapping) range leaves exactly one row per
    ``(date, base_currency, currency)``.

    Args:
        conn: An open DuckDB connection.
        table: Destination table name.
        frame: A long, enriched frame (see :func:`fxpipeline.transform`).

    Returns:
        The number of rows written.
    """
    ensure_table(conn, table)

    if frame.empty:
        logger.info("upsert skipped rows=0 table=%s", table)
        return 0

    ma_cols = _ma_columns(frame)
    _ensure_ma_columns(conn, table, ma_cols)

    columns = _PERSIST_COLUMNS + ma_cols
    staged = frame.loc[:, columns].copy()
    staged["date"] = pd.to_datetime(staged["date"]).dt.date

    # Register the DataFrame so DuckDB can read it as a relation.
    conn.register("staging_fx", staged)
    try:
        # Delete overlapping keys, then insert — the idempotency guarantee.
        conn.execute(
            f"""
            DELETE FROM {table} AS t
            USING staging_fx AS s
            WHERE t.date = s.date
              AND t.base_currency = s.base_currency
              AND t.currency = s.currency
            """
        )
        col_list = ", ".join(columns)
        conn.execute(
            f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM staging_fx"
        )
    finally:
        conn.unregister("staging_fx")

    rows = len(staged)
    logger.info("upsert ok rows=%d table=%s", rows, table)
    return rows


def load_frame(settings: Settings, frame: pd.DataFrame) -> int:
    """Open the configured warehouse and upsert ``frame`` into it.

    Args:
        settings: Runtime settings carrying ``db_path`` and ``table_name``.
        frame: The enriched long frame to persist.

    Returns:
        The number of rows written.
    """
    with connect(settings.db_path) as conn:
        return upsert_rates(conn, settings.table_name, frame)
