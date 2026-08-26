from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from lightningfish_finance.ground_truth import get_finance_ground_truth


def _multiindex_price_df(ticker: str, closes: list[float]) -> pd.DataFrame:
    """Matches what a real yf.download() call returns: Close under a
    MultiIndex (Price, Ticker) even for a single ticker. Found the hard way
    when get_finance_ground_truth crashed with AttributeError: 'DataFrame'
    object has no attribute 'tolist' against a real, current yfinance."""
    index = pd.date_range("2026-04-30", periods=len(closes), freq="h")
    columns = pd.MultiIndex.from_product(
        [["Close", "High", "Low", "Open", "Volume"], [ticker]], names=["Price", "Ticker"]
    )
    df = pd.DataFrame(index=index, columns=columns, dtype=float)
    df[("Close", ticker)] = closes
    return df


def test_handles_multiindex_columns_from_real_yfinance():
    df = _multiindex_price_df("AAPL", [100.0, 101.0, 105.0])
    with patch("lightningfish_finance.ground_truth.yf.download", return_value=df):
        truth = get_finance_ground_truth("AAPL", "2026-04-30")
    assert truth.data["price_series"] == [100.0, 101.0, 105.0]
    assert truth.data["price_change_pct"] == (105.0 - 100.0) / 100.0


def test_negative_price_move():
    df = _multiindex_price_df("SMCI", [50.0, 40.0])
    with patch("lightningfish_finance.ground_truth.yf.download", return_value=df):
        truth = get_finance_ground_truth("SMCI", "2024-10-31")
    assert truth.data["price_change_pct"] < 0


def test_fewer_than_two_price_points_gives_zero_change():
    df = _multiindex_price_df("AAPL", [100.0])
    with patch("lightningfish_finance.ground_truth.yf.download", return_value=df):
        truth = get_finance_ground_truth("AAPL", "2026-04-30")
    assert truth.data["price_change_pct"] == 0.0


def test_empty_price_series_gives_zero_change():
    df = _multiindex_price_df("AAPL", [])
    with patch("lightningfish_finance.ground_truth.yf.download", return_value=df):
        truth = get_finance_ground_truth("AAPL", "2026-04-30")
    assert truth.data["price_series"] == []
    assert truth.data["price_change_pct"] == 0.0
