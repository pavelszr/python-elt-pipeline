"""Environment-based configuration for the FX pipeline.

Settings are resolved from environment variables (prefixed ``FX_``) with
sensible defaults, so the pipeline runs out of the box with zero configuration
while remaining fully overridable in CI or production.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

DEFAULT_BASE_CURRENCY = "USD"
DEFAULT_SYMBOLS: tuple[str, ...] = ("EUR", "GBP", "HNL", "MXN")
DEFAULT_API_BASE_URL = "https://api.frankfurter.app"
DEFAULT_DB_PATH = "warehouse.duckdb"
DEFAULT_TABLE_NAME = "fx_rates"
DEFAULT_MA_WINDOWS: tuple[int, ...] = (7, 30)


def _env(name: str, default: str) -> str:
    """Return the environment variable ``FX_<name>`` or ``default``."""
    return os.environ.get(f"FX_{name}", default)


def _env_int(name: str, default: int) -> int:
    """Return an integer environment variable ``FX_<name>`` or ``default``."""
    raw = os.environ.get(f"FX_{name}")
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    """Return a float environment variable ``FX_<name>`` or ``default``."""
    raw = os.environ.get(f"FX_{name}")
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _parse_csv(raw: str) -> tuple[str, ...]:
    """Parse a comma-separated string into an upper-cased tuple of tokens."""
    return tuple(token.strip().upper() for token in raw.split(",") if token.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable runtime configuration for the pipeline.

    Attributes:
        api_base_url: Base URL of the Frankfurter API.
        base_currency: Base (quote) currency for the rate series.
        symbols: Target currencies to extract against the base.
        db_path: Filesystem path to the DuckDB warehouse file.
        table_name: Destination table for loaded rates.
        ma_windows: Moving-average window sizes (in days) to compute.
        request_timeout: Per-request HTTP timeout, in seconds.
        max_retries: Maximum number of HTTP retry attempts.
        backoff_factor: Exponential backoff factor between retries.
    """

    api_base_url: str = DEFAULT_API_BASE_URL
    base_currency: str = DEFAULT_BASE_CURRENCY
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS
    db_path: str = DEFAULT_DB_PATH
    table_name: str = DEFAULT_TABLE_NAME
    ma_windows: tuple[int, ...] = DEFAULT_MA_WINDOWS
    request_timeout: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 0.5

    @classmethod
    def from_env(cls) -> Settings:
        """Build :class:`Settings` from environment variables with defaults."""
        symbols_raw = _env("SYMBOLS", ",".join(DEFAULT_SYMBOLS))
        ma_raw = _env("MA_WINDOWS", ",".join(str(w) for w in DEFAULT_MA_WINDOWS))
        return cls(
            api_base_url=_env("API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/"),
            base_currency=_env("BASE_CURRENCY", DEFAULT_BASE_CURRENCY).upper(),
            symbols=_parse_csv(symbols_raw),
            db_path=_env("DB_PATH", DEFAULT_DB_PATH),
            table_name=_env("TABLE_NAME", DEFAULT_TABLE_NAME),
            ma_windows=tuple(int(w) for w in _parse_csv(ma_raw)),
            request_timeout=_env_float("REQUEST_TIMEOUT", 30.0),
            max_retries=_env_int("MAX_RETRIES", 3),
            backoff_factor=_env_float("BACKOFF_FACTOR", 0.5),
        )


# Mutable convenience holder so callers can pass partial overrides without
# rebuilding the whole environment. Kept separate from the frozen Settings.
@dataclass(slots=True)
class RunRequest:
    """Parameters describing a single pipeline run.

    Attributes:
        start: Inclusive ISO start date (``YYYY-MM-DD``).
        end: Inclusive ISO end date (``YYYY-MM-DD``).
        base: Optional base-currency override for this run.
        symbols: Optional symbols override for this run.
    """

    start: str
    end: str
    base: str | None = None
    symbols: tuple[str, ...] | None = field(default=None)

    def resolved_base(self, settings: Settings) -> str:
        """Return the effective base currency for this run."""
        return (self.base or settings.base_currency).upper()

    def resolved_symbols(self, settings: Settings) -> tuple[str, ...]:
        """Return the effective symbols for this run."""
        return self.symbols if self.symbols else settings.symbols
