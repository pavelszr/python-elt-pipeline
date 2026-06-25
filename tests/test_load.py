"""Unit tests for the load layer, focused on idempotency + incrementality."""

from __future__ import annotations

from typing import Any

import duckdb
import pytest

from fxpipeline.load import ensure_table, upsert_rates
from fxpipeline.transform import build_dataset


@pytest.fixture()
def conn() -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB connection, closed after the test."""
    connection = duckdb.connect(":memory:")
    yield connection
    connection.close()


def _row_count(conn: duckdb.DuckDBPyConnection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_ensure_table_is_idempotent(conn: duckdb.DuckDBPyConnection) -> None:
    ensure_table(conn, "fx_rates")
    ensure_table(conn, "fx_rates")  # second call must not error
    assert _row_count(conn, "fx_rates") == 0


def test_upsert_inserts_rows(
    conn: duckdb.DuckDBPyConnection, sample_payload: dict[str, Any]
) -> None:
    frame = build_dataset(sample_payload, ma_windows=(2, 3))
    written = upsert_rates(conn, "fx_rates", frame)

    assert written == 6
    assert _row_count(conn, "fx_rates") == 6


def test_upsert_is_idempotent_on_rerun(
    conn: duckdb.DuckDBPyConnection, sample_payload: dict[str, Any]
) -> None:
    frame = build_dataset(sample_payload, ma_windows=(2, 3))

    upsert_rates(conn, "fx_rates", frame)
    upsert_rates(conn, "fx_rates", frame)  # identical re-run

    # No duplicates: still exactly 6 rows.
    assert _row_count(conn, "fx_rates") == 6


def test_upsert_overlapping_range_no_duplicates(
    conn: duckdb.DuckDBPyConnection, sample_payload: dict[str, Any]
) -> None:
    first = build_dataset(sample_payload, ma_windows=(2, 3))
    upsert_rates(conn, "fx_rates", first)

    # An overlapping batch: day 3 repeats (updated rate) + a new day 4.
    overlapping = {
        "base": "USD",
        "rates": {
            "2024-01-03": {"EUR": 0.91, "HNL": 25.5},  # overlaps -> update
            "2024-01-04": {"EUR": 0.92, "HNL": 26.0},  # new
        },
    }
    second = build_dataset(overlapping, ma_windows=(2, 3))
    upsert_rates(conn, "fx_rates", second)

    # 3 original days + 1 new day = 4 distinct dates x 2 currencies = 8.
    assert _row_count(conn, "fx_rates") == 8

    # The overlapping day must reflect the UPDATED rate, not the original.
    updated = conn.execute(
        "SELECT rate FROM fx_rates WHERE date = DATE '2024-01-03' AND currency = 'EUR'"
    ).fetchone()[0]
    assert updated == pytest.approx(0.91)


def test_upsert_empty_frame_is_noop(
    conn: duckdb.DuckDBPyConnection, sample_payload: dict[str, Any]
) -> None:
    empty = build_dataset({"base": "USD", "rates": {}}, ma_windows=(2, 3))
    written = upsert_rates(conn, "fx_rates", empty)
    assert written == 0
    assert _row_count(conn, "fx_rates") == 0


def test_upsert_persists_pct_change_and_ma(
    conn: duckdb.DuckDBPyConnection, sample_payload: dict[str, Any]
) -> None:
    frame = build_dataset(sample_payload, ma_windows=(2, 3))
    upsert_rates(conn, "fx_rates", frame)

    cols = {
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'fx_rates'"
        ).fetchall()
    }
    assert {"pct_change", "ma_2", "ma_3"}.issubset(cols)
