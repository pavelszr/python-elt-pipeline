"""Unit tests for the argparse CLI."""

from __future__ import annotations

import argparse

import pytest

from fxpipeline import cli
from fxpipeline.config import RunRequest, Settings
from fxpipeline.pipeline import RunResult


def test_valid_date_accepts_iso() -> None:
    assert cli._valid_date("2024-01-01") == "2024-01-01"


def test_valid_date_rejects_bad() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._valid_date("01/01/2024")


def test_parse_symbols_upper_and_split() -> None:
    assert cli._parse_symbols("eur, gbp ,hnl") == ("EUR", "GBP", "HNL")


def test_parse_symbols_empty_rejected() -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        cli._parse_symbols(" , ")


def test_main_run_invokes_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(settings: Settings, request: RunRequest) -> RunResult:
        captured["settings"] = settings
        captured["request"] = request
        return RunResult(
            rows_loaded=12,
            start=request.start,
            end=request.end,
            base=request.resolved_base(settings),
            symbols=request.resolved_symbols(settings),
        )

    monkeypatch.setattr(cli, "run_pipeline", fake_run)

    code = cli.main(
        [
            "run",
            "--start",
            "2024-01-01",
            "--end",
            "2024-03-01",
            "--base",
            "USD",
            "--symbols",
            "EUR,HNL",
        ]
    )

    assert code == 0
    request = captured["request"]
    assert isinstance(request, RunRequest)
    assert request.start == "2024-01-01"
    assert request.end == "2024-03-01"
    assert request.base == "USD"
    assert request.symbols == ("EUR", "HNL")


def test_main_requires_subcommand() -> None:
    with pytest.raises(SystemExit):
        cli.main([])
