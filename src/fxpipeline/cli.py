"""Command-line interface for the FX pipeline.

Usage:
    python -m fxpipeline run --start 2024-01-01 --end 2024-03-01 \
        --base USD --symbols EUR,GBP,HNL,MXN

The CLI is a thin wrapper: it parses arguments, configures logging, builds the
:class:`Settings`/:class:`RunRequest`, and delegates to
:func:`fxpipeline.pipeline.run`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

from .config import RunRequest, Settings
from .logging_conf import configure_logging, get_logger
from .pipeline import run as run_pipeline

logger = get_logger("cli")


def _valid_date(value: str) -> str:
    """Validate that ``value`` is an ISO ``YYYY-MM-DD`` date string."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid date '{value}', expected YYYY-MM-DD"
        ) from exc
    return value


def _parse_symbols(value: str) -> tuple[str, ...]:
    """Parse a comma-separated symbols string into an upper-cased tuple."""
    symbols = tuple(s.strip().upper() for s in value.split(",") if s.strip())
    if not symbols:
        raise argparse.ArgumentTypeError("at least one symbol is required")
    return symbols


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with the ``run`` subcommand."""
    parser = argparse.ArgumentParser(
        prog="fxpipeline",
        description="Extract, transform, and load FX rates from Frankfurter.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run the ELT pipeline for a date range.")
    run_p.add_argument(
        "--start",
        type=_valid_date,
        required=True,
        help="Inclusive start date (YYYY-MM-DD).",
    )
    run_p.add_argument(
        "--end",
        type=_valid_date,
        default=date.today().isoformat(),
        help="Inclusive end date (YYYY-MM-DD). Defaults to today.",
    )
    run_p.add_argument(
        "--base",
        default=None,
        help="Base currency (defaults to configured FX_BASE_CURRENCY).",
    )
    run_p.add_argument(
        "--symbols",
        type=_parse_symbols,
        default=None,
        help="Comma-separated target currencies (e.g. EUR,GBP,HNL,MXN).",
    )
    run_p.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    run_p.set_defaults(func=_cmd_run)
    return parser


def _cmd_run(args: argparse.Namespace) -> int:
    """Handle the ``run`` subcommand."""
    configure_logging(args.log_level)
    settings = Settings.from_env()
    request = RunRequest(
        start=args.start,
        end=args.end,
        base=args.base,
        symbols=args.symbols,
    )
    result = run_pipeline(settings, request)
    logger.info(
        "done rows_loaded=%d range=%s..%s base=%s",
        result.rows_loaded,
        result.start,
        result.end,
        result.base,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
