"""Unit tests for environment-based configuration."""

from __future__ import annotations

import pytest

from fxpipeline.config import RunRequest, Settings


def test_defaults_when_no_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure a clean environment for the FX_ namespace.
    for var in (
        "FX_API_BASE_URL",
        "FX_BASE_CURRENCY",
        "FX_SYMBOLS",
        "FX_DB_PATH",
        "FX_TABLE_NAME",
        "FX_MA_WINDOWS",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings.from_env()
    assert settings.base_currency == "USD"
    assert "HNL" in settings.symbols
    assert settings.api_base_url == "https://api.frankfurter.app"
    assert settings.ma_windows == (7, 30)


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FX_BASE_CURRENCY", "eur")
    monkeypatch.setenv("FX_SYMBOLS", "usd, gbp ,hnl")
    monkeypatch.setenv("FX_MA_WINDOWS", "5,10")
    monkeypatch.setenv("FX_API_BASE_URL", "https://example.test/")
    monkeypatch.setenv("FX_MAX_RETRIES", "7")

    settings = Settings.from_env()
    assert settings.base_currency == "EUR"
    assert settings.symbols == ("USD", "GBP", "HNL")
    assert settings.ma_windows == (5, 10)
    # Trailing slash is stripped.
    assert settings.api_base_url == "https://example.test"
    assert settings.max_retries == 7


def test_run_request_resolution() -> None:
    settings = Settings(base_currency="USD", symbols=("EUR", "HNL"))

    default_req = RunRequest(start="2024-01-01", end="2024-01-31")
    assert default_req.resolved_base(settings) == "USD"
    assert default_req.resolved_symbols(settings) == ("EUR", "HNL")

    override_req = RunRequest(
        start="2024-01-01", end="2024-01-31", base="gbp", symbols=("MXN",)
    )
    assert override_req.resolved_base(settings) == "GBP"
    assert override_req.resolved_symbols(settings) == ("MXN",)
