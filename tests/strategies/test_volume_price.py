"""Tests for VolumePriceStrategy (量價齊揚)."""
import pandas as pd
import numpy as np
import pytest
from strategies.volume_price import VolumePriceStrategy


@pytest.fixture
def strat():
    return VolumePriceStrategy()


def _make_strong_vol_price(n=60):
    """
    Price up strongly + recent volume surging above 1.5x 20-day avg.
    Strategy VOLUME_SURGE_RATIO = 1.5. Design:
    - first 50 days: base volume 50k, gradual price grind
    - last 10 days: 5x volume spike (250k) + sharp price jump
    This ensures vol_ratio > 1.5 and pct > 1% at the last bar.
    """
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    closes = np.concatenate([np.linspace(100, 105, 50), np.linspace(105, 115, 10)])
    volumes = np.concatenate([np.full(50, 50_000), np.full(10, 250_000)]).astype(int)
    opens = closes * 0.998
    highs = closes * 1.012
    lows = closes * 0.990
    return pd.DataFrame({
        "date": dates, "stock_id": "9999",
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": volumes,
    })


def test_strong_vol_price_scores_high(strat):
    df = _make_strong_vol_price()
    score = strat.score(df)
    assert score > 50, f"Strong volume+price input should score >50, got {score}"


def test_bearish_scores_lower(strat, price_df_bullish, price_df_bearish):
    bull = strat.score(price_df_bullish)
    bear = strat.score(price_df_bearish)
    assert bull >= bear, f"Bullish ({bull}) should score >= bearish ({bear})"


def test_empty_df_returns_zero(strat):
    assert strat.score(pd.DataFrame()) == 0.0


def test_score_in_range(strat, price_df_bullish, price_df_bearish, price_df_flat):
    for df in [price_df_bullish, price_df_bearish, price_df_flat]:
        s = strat.score(df)
        assert 0 <= s <= 100


def test_details_has_signal_key(strat, price_df_bullish):
    d = strat.details(price_df_bullish)
    assert "signal" in d
    assert isinstance(d["signal"], str)


def test_variance_flat_vs_strong(strat, price_df_flat):
    """Variance check: strong vol-price vs flat must produce different scores."""
    strong = _make_strong_vol_price()
    s_strong = strat.score(strong)
    s_flat = strat.score(price_df_flat)
    assert s_strong != s_flat, (
        f"VolumePrice returned same score ({s_strong}) for strong and flat — "
        "possible stuck-constant bug"
    )
