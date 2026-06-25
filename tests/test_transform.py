"""Unit tests for the pure pandas transform functions."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import pytest

from fxpipeline.transform import (
    add_daily_pct_change,
    add_moving_averages,
    build_dataset,
    to_long_frame,
)


def test_to_long_frame_shape_and_sorting(sample_payload: dict[str, Any]) -> None:
    frame = to_long_frame(sample_payload)

    # 3 days x 2 currencies = 6 rows.
    assert len(frame) == 6
    assert list(frame.columns) == ["date", "base_currency", "currency", "rate"]
    assert set(frame["currency"]) == {"EUR", "HNL"}
    assert (frame["base_currency"] == "USD").all()

    # Sorted by currency then date.
    eur = frame[frame["currency"] == "EUR"].reset_index(drop=True)
    assert list(eur["date"]) == [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]
    assert eur["rate"].tolist() == [0.90, 0.99, 0.90]


def test_to_long_frame_empty_payload() -> None:
    frame = to_long_frame({"base": "USD", "rates": {}})
    assert frame.empty
    assert list(frame.columns) == ["date", "base_currency", "currency", "rate"]


def test_add_daily_pct_change_values(sample_payload: dict[str, Any]) -> None:
    frame = add_daily_pct_change(to_long_frame(sample_payload))

    eur = frame[frame["currency"] == "EUR"].reset_index(drop=True)
    # First observation is NaN.
    assert math.isnan(eur.loc[0, "pct_change"])
    # 0.90 -> 0.99 is +10%.
    assert eur.loc[1, "pct_change"] == pytest.approx(10.0)
    # 0.99 -> 0.90 is approx -9.0909%.
    assert eur.loc[2, "pct_change"] == pytest.approx(-9.090909, rel=1e-4)


def test_pct_change_is_per_currency(sample_payload: dict[str, Any]) -> None:
    frame = add_daily_pct_change(to_long_frame(sample_payload))
    # The first row of EACH currency group must be NaN (no cross-currency leak).
    # Use .nth(0) to grab the positional first row (groupby.first skips NaN).
    firsts = frame.groupby("currency", sort=False)["pct_change"].nth(0)
    assert all(math.isnan(v) for v in firsts)


def test_add_moving_averages_window_values(
    sample_payload: dict[str, Any],
) -> None:
    frame = add_moving_averages(to_long_frame(sample_payload), windows=(2,))
    eur = frame[frame["currency"] == "EUR"].reset_index(drop=True)

    assert "ma_2" in frame.columns
    # min_periods=1: first value equals the rate itself.
    assert eur.loc[0, "ma_2"] == pytest.approx(0.90)
    # Second value is mean(0.90, 0.99).
    assert eur.loc[1, "ma_2"] == pytest.approx((0.90 + 0.99) / 2)
    # Third value is mean(0.99, 0.90).
    assert eur.loc[2, "ma_2"] == pytest.approx((0.99 + 0.90) / 2)


def test_build_dataset_columns(sample_payload: dict[str, Any]) -> None:
    frame = build_dataset(sample_payload, ma_windows=(2, 3))
    for col in [
        "date",
        "base_currency",
        "currency",
        "rate",
        "pct_change",
        "ma_2",
        "ma_3",
    ]:
        assert col in frame.columns
    assert len(frame) == 6


def test_build_dataset_empty() -> None:
    frame = build_dataset({"base": "USD", "rates": {}}, ma_windows=(7, 30))
    assert frame.empty
    assert "pct_change" in frame.columns
    assert "ma_7" in frame.columns
    assert "ma_30" in frame.columns


def test_transforms_do_not_mutate_input(sample_payload: dict[str, Any]) -> None:
    long_frame = to_long_frame(sample_payload)
    snapshot = long_frame.copy(deep=True)
    _ = add_daily_pct_change(long_frame)
    _ = add_moving_averages(long_frame, windows=(2, 3))
    pd.testing.assert_frame_equal(long_frame, snapshot)
