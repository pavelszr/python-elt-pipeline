"""Transformation layer: pure pandas functions over the raw API payload.

Every function here is deterministic and side-effect free, taking and returning
DataFrames so they can be unit-tested with small fixed inputs.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Canonical column order for the tidy/long output.
LONG_COLUMNS: list[str] = [
    "date",
    "base_currency",
    "currency",
    "rate",
    "pct_change",
]


def to_long_frame(payload: dict[str, Any]) -> pd.DataFrame:
    """Convert a Frankfurter time-series payload into a tidy/long DataFrame.

    The raw payload nests rates as ``{date: {symbol: rate}}``. This flattens it
    into one row per (date, currency) pair.

    Args:
        payload: Decoded Frankfurter response containing ``base`` and ``rates``.

    Returns:
        A DataFrame with columns ``[date, base_currency, currency, rate]`` sorted
        by ``(currency, date)``. Empty payloads yield an empty, correctly typed
        frame.
    """
    base = str(payload.get("base", "")).upper()
    rates: dict[str, dict[str, float]] = payload.get("rates", {})

    records: list[dict[str, Any]] = []
    for date_str, symbol_map in rates.items():
        for symbol, rate in symbol_map.items():
            records.append(
                {
                    "date": date_str,
                    "base_currency": base,
                    "currency": str(symbol).upper(),
                    "rate": float(rate),
                }
            )

    frame = pd.DataFrame.from_records(
        records, columns=["date", "base_currency", "currency", "rate"]
    )
    if frame.empty:
        frame = frame.astype(
            {
                "date": "datetime64[ns]",
                "base_currency": "object",
                "currency": "object",
                "rate": "float64",
            }
        )
        return frame

    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values(["currency", "date"]).reset_index(drop=True)
    return frame


def add_daily_pct_change(frame: pd.DataFrame) -> pd.DataFrame:
    """Add a per-currency daily percentage-change column.

    Args:
        frame: A long frame as produced by :func:`to_long_frame`.

    Returns:
        A copy of ``frame`` with a ``pct_change`` column (percentage points;
        the first observation per currency is ``NaN``).
    """
    if frame.empty:
        out = frame.copy()
        out["pct_change"] = pd.Series(dtype="float64")
        return out

    out = frame.sort_values(["currency", "date"]).copy()
    out["pct_change"] = out.groupby("currency", sort=False)["rate"].pct_change() * 100.0
    return out.reset_index(drop=True)


def add_moving_averages(frame: pd.DataFrame, windows: tuple[int, ...]) -> pd.DataFrame:
    """Add per-currency simple moving averages of the rate.

    Args:
        frame: A long frame sorted (or sortable) by ``(currency, date)``.
        windows: Window sizes in days, e.g. ``(7, 30)``. Each yields a
            ``ma_<n>`` column.

    Returns:
        A copy of ``frame`` with one ``ma_<n>`` column per requested window.
        Windows use ``min_periods=1`` so early rows still get a value.
    """
    out = frame.sort_values(["currency", "date"]).copy()

    for window in windows:
        col = f"ma_{window}"
        if out.empty:
            out[col] = pd.Series(dtype="float64")
            continue
        out[col] = out.groupby("currency", sort=False)["rate"].transform(
            lambda s, w=window: s.rolling(window=w, min_periods=1).mean()
        )

    return out.reset_index(drop=True)


def build_dataset(payload: dict[str, Any], ma_windows: tuple[int, ...]) -> pd.DataFrame:
    """Run the full transform: long format + pct change + moving averages.

    Args:
        payload: Raw Frankfurter time-series payload.
        ma_windows: Moving-average window sizes to compute.

    Returns:
        The fully enriched long DataFrame ready to load.
    """
    long_frame = to_long_frame(payload)
    with_change = add_daily_pct_change(long_frame)
    enriched = add_moving_averages(with_change, ma_windows)
    return enriched
