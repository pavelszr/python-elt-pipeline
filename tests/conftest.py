"""Shared pytest fixtures for the fxpipeline test suite."""

from __future__ import annotations

from typing import Any

import pytest

from fxpipeline.config import Settings


@pytest.fixture()
def settings() -> Settings:
    """Return deterministic settings pointing at an in-memory warehouse."""
    return Settings(
        api_base_url="https://api.frankfurter.app",
        base_currency="USD",
        symbols=("EUR", "HNL"),
        db_path=":memory:",
        table_name="fx_rates",
        ma_windows=(2, 3),
        request_timeout=5.0,
        max_retries=2,
        backoff_factor=0.0,
    )


@pytest.fixture()
def sample_payload() -> dict[str, Any]:
    """A small, fixed Frankfurter-shaped payload covering three days."""
    return {
        "amount": 1.0,
        "base": "USD",
        "start_date": "2024-01-01",
        "end_date": "2024-01-03",
        "rates": {
            "2024-01-01": {"EUR": 0.90, "HNL": 24.0},
            "2024-01-02": {"EUR": 0.99, "HNL": 24.6},
            "2024-01-03": {"EUR": 0.90, "HNL": 25.0},
        },
    }
