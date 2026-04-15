"""Tests for EnhancedTechnicalStrategy (技術綜合)."""
import pandas as pd
import numpy as np
import pytest
from strategies.enhanced_technical import EnhancedTechnicalStrategy


@pytest.fixture
def strat():
    return EnhancedTechnicalStrategy()


def _make_kd_golden_cross(n=60):
    """
    Construct a price series that forces a KD golden cross near the end:
    - first 50 days: gradual decline (K < D, low range)
    - last 10 days: sharp recovery (K crosses above D)
    """
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    # decline then recover
    closes = (np.concatenate([
        np.linspace(120, 90, 50),
        np.linspace(90, 110, 10),
    ]) + np.random.default_rng(55).normal(0, 0.3, n))
    closes = np.maximum(closes, 1.0)
    opens = closes * 0.999
    highs = closes * 1.008
    lows = closes * 0.992
    volumes = np.full(n, 200_000)
    return pd.DataFrame({
        "date": dates, "stock_id": "9999",
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": volumes,
    })


def test_bullish_scores_reasonable(strat, price_df_bullish):
    score = strat.score(price_df_bullish)
    assert score >= 0, "Score should be non-negative"
    assert score <= 100, "Score should not exceed 100"


def test_bearish_scores_lower(strat, price_df_bullish, price_df_bearish):
    bull = strat.score(price_df_bullish)
    bear = strat.score(price_df_bearish)
    assert bull >= bear, f"Bullish ({bull}) should score >= bearish ({bear})"


def test_empty_df_returns_zero(strat):
    assert strat.score(pd.DataFrame()) == 0.0


def test_short_df_returns_zero(strat):
    """DataFrame with < 30 rows → 0."""
    import pandas as pd
    dates = pd.date_range("2024-01-01", periods=10, freq="B")
    df = pd.DataFrame({
        "date": dates, "stock_id": "9999",
        "open": [100]*10, "high": [101]*10, "low": [99]*10,
        "close": [100]*10, "volume": [100000]*10,
    })
    assert strat.score(df) == 0.0


def test_details_has_signal_key(strat, price_df_bullish):
    d = strat.details(price_df_bullish)
    assert "signal" in d
    assert isinstance(d["signal"], str)


def test_variance_bull_vs_bear(strat, price_df_bullish, price_df_bearish):
    """Variance check: different market conditions must produce different scores."""
    s_bull = strat.score(price_df_bullish)
    s_bear = strat.score(price_df_bearish)
    assert s_bull != s_bear, (
        f"EnhancedTechnical returned same score ({s_bull}) for bull and bear — "
        "possible stuck-constant bug"
    )
