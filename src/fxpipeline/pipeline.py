"""Orchestration: wire extract -> transform -> load into one run.

This module is the seam between the pure layers and the CLI. It contains no
argument parsing and no logging configuration so it can be driven from tests or
another program just as easily as from the command line.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import RunRequest, Settings
from .extract import fetch_time_series
from .load import load_frame
from .logging_conf import get_logger
from .transform import build_dataset

logger = get_logger("pipeline")


@dataclass(frozen=True, slots=True)
class RunResult:
    """Summary of a completed pipeline run.

    Attributes:
        rows_loaded: Number of rows written to the warehouse.
        start: Inclusive start date of the run.
        end: Inclusive end date of the run.
        base: Effective base currency.
        symbols: Effective target currencies.
    """

    rows_loaded: int
    start: str
    end: str
    base: str
    symbols: tuple[str, ...]


def run(settings: Settings, request: RunRequest) -> RunResult:
    """Execute a full extract -> transform -> load cycle.

    Args:
        settings: Runtime settings (API, warehouse, retries, MA windows).
        request: The date range and optional base/symbols overrides.

    Returns:
        A :class:`RunResult` describing what was loaded.
    """
    base = request.resolved_base(settings)
    symbols = request.resolved_symbols(settings)

    logger.info(
        "run start=%s end=%s base=%s symbols=%s",
        request.start,
        request.end,
        base,
        ",".join(symbols),
    )

    payload = fetch_time_series(settings, request.start, request.end, base, symbols)
    dataset = build_dataset(payload, settings.ma_windows)
    rows = load_frame(settings, dataset)

    logger.info("run complete rows_loaded=%d", rows)
    return RunResult(
        rows_loaded=rows,
        start=request.start,
        end=request.end,
        base=base,
        symbols=symbols,
    )
