"""Integration-style test for the orchestration layer with a mocked extract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pytest

from fxpipeline import pipeline
from fxpipeline.config import RunRequest, Settings


def test_run_end_to_end_with_mocked_extract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    sample_payload: dict[str, Any],
) -> None:
    db_file = tmp_path / "wh.duckdb"
    settings = Settings(
        symbols=("EUR", "HNL"),
        db_path=str(db_file),
        table_name="fx_rates",
        ma_windows=(2, 3),
    )

    captured: dict[str, Any] = {}

    def fake_fetch(
        _settings: Settings,
        start: str,
        end: str,
        base: str,
        symbols: tuple[str, ...],
    ) -> dict[str, Any]:
        captured.update({"start": start, "end": end, "base": base, "symbols": symbols})
        return sample_payload

    monkeypatch.setattr(pipeline, "fetch_time_series", fake_fetch)

    request = RunRequest(start="2024-01-01", end="2024-01-03")
    result = pipeline.run(settings, request)

    assert result.rows_loaded == 6
    assert captured["base"] == "USD"
    assert captured["symbols"] == ("EUR", "HNL")

    # Re-run must remain idempotent through the full pipeline.
    result2 = pipeline.run(settings, request)
    assert result2.rows_loaded == 6

    conn = duckdb.connect(str(db_file))
    try:
        count = conn.execute("SELECT COUNT(*) FROM fx_rates").fetchone()[0]
    finally:
        conn.close()
    assert count == 6
