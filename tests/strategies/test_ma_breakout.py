"""Tests for MABreakoutStrategy (突破均線)."""
import pytest
from strategies.ma_breakout import MABreakoutStrategy


@pytest.fixture
def strat():
    return MABreakoutStrategy()


def test_bullish_score_high(strat, price_df_bullish):
    score = strat.score(price_df_bullish)
    assert score > 50, f"Bullish input should score >50, got {score}"


def test_bearish_score_lower_than_bullish(strat, price_df_bullish, price_df_bearish):
    bull = strat.score(price_df_bullish)
    bear = strat.score(price_df_bearish)
    assert bull > bear, f"Bullish ({bull}) should outscore bearish ({bear})"


def test_empty_df_returns_zero(strat):
    import pandas as pd
    score = strat.score(pd.DataFrame())
    assert score == 0.0


def test_score_in_range(strat, price_df_bullish, price_df_bearish, price_df_flat):
    for df in [price_df_bullish, price_df_bearish, price_df_flat]:
        s = strat.score(df)
        assert 0 <= s <= 100, f"Score {s} out of range [0,100]"


def test_details_has_signal_key(strat, price_df_bullish):
    d = strat.details(price_df_bullish)
    assert "signal" in d, "details() must contain 'signal' key"
    assert isinstance(d["signal"], str)


def test_variance_flat_vs_bullish(strat, price_df_flat, price_df_bullish):
    """Catch 'stuck constant score' regression: two inputs must differ."""
    s_flat = strat.score(price_df_flat)
    s_bull = strat.score(price_df_bullish)
    assert s_flat != s_bull, (
        f"MABreakout returned identical score ({s_flat}) for flat and bullish — "
        "possible stuck-constant bug"
    )
