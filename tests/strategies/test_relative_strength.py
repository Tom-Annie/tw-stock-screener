"""Tests for RelativeStrengthStrategy (相對強弱)."""
import pandas as pd
import numpy as np
import pytest
from strategies.relative_strength import RelativeStrengthStrategy


@pytest.fixture
def strat():
    return RelativeStrengthStrategy()


def _rsi_safe_df(start=100.0, trend=0.4, n=70, seed=7):
    """
    Build a price_df with enough noise that RSI avg_loss > 0.
    A purely monotone series causes RSI NaN because avg_loss == 0.
    std=1.5 ensures ~30% of days are red.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    closes = start + np.cumsum(rng.normal(trend, 1.5, n))
    closes = np.maximum(closes, 1.0)
    opens = closes * rng.uniform(0.995, 1.005, n)
    highs = closes * rng.uniform(1.001, 1.01, n)
    lows = closes * rng.uniform(0.99, 0.999, n)
    return pd.DataFrame({
        "date": dates, "stock_id": "9999",
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": rng.integers(100_000, 400_000, n),
    })


@pytest.fixture
def rsi_bullish():
    return _rsi_safe_df(start=100.0, trend=0.5, seed=7)


@pytest.fixture
def rsi_bearish():
    return _rsi_safe_df(start=150.0, trend=-0.5, seed=8)


def test_bullish_with_index_scores_high(strat, rsi_bullish, taiex_close):
    score = strat.score(rsi_bullish, index_close=taiex_close)
    assert score > 30, f"Bullish + strong index should score >30, got {score}"


def test_bearish_lower_than_bullish(strat, rsi_bullish, rsi_bearish, taiex_close):
    bull = strat.score(rsi_bullish, index_close=taiex_close)
    bear = strat.score(rsi_bearish, index_close=taiex_close)
    assert bull > bear, f"Bullish ({bull}) should outscore bearish ({bear})"


def test_no_index_close_doesnt_crash(strat, rsi_bullish):
    """Missing index_close kwarg — strategy must not crash."""
    score = strat.score(rsi_bullish)
    assert 0 <= score <= 100


def test_empty_df_returns_zero(strat, taiex_close):
    assert strat.score(pd.DataFrame(), index_close=taiex_close) == 0.0


def test_details_has_signal_key(strat, rsi_bullish, taiex_close):
    d = strat.details(rsi_bullish, index_close=taiex_close)
    assert "signal" in d
    assert isinstance(d["signal"], str)


def test_variance_bull_vs_bear(strat, rsi_bullish, rsi_bearish, taiex_close):
    """Variance check: bullish vs bearish must produce different scores."""
    s_bull = strat.score(rsi_bullish, index_close=taiex_close)
    s_bear = strat.score(rsi_bearish, index_close=taiex_close)
    assert s_bull != s_bear, (
        f"RelativeStrength returned identical score ({s_bull}) for bull and bear — "
        "possible stuck-constant bug"
    )
