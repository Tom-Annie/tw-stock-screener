"""
Tests for USMarketStrategy (美股連動).

Note: _get_usd_twd() may call yfinance. We force the cached rate to avoid
network calls in tests.
"""
import pandas as pd
import numpy as np
import pytest
from strategies.us_market import USMarketStrategy


@pytest.fixture(autouse=True)
def patch_usd_twd():
    """Force a fixed USD/TWD rate so tests don't hit the network."""
    USMarketStrategy._cached_usd_twd = 31.5
    yield
    USMarketStrategy._cached_usd_twd = None


@pytest.fixture
def strat():
    return USMarketStrategy()


def test_bullish_us_scores_high(strat, price_df_bullish, sox_df, tsm_df, night_df, day_futures_df):
    score = strat.score(
        price_df_bullish,
        sox_df=sox_df,
        tsm_df=tsm_df,
        tsmc_close=850.0,
        night_df=night_df,
        day_futures_df=day_futures_df,
    )
    assert score > 30, f"Bullish US market input should score >30, got {score}"


def test_bearish_sox_scores_lower(strat, price_df_bullish,
                                   sox_df, sox_df_bearish, tsm_df, night_df, day_futures_df):
    bull_score = strat.score(
        price_df_bullish,
        sox_df=sox_df,
        tsm_df=tsm_df,
        tsmc_close=850.0,
        night_df=night_df,
        day_futures_df=day_futures_df,
    )
    bear_score = strat.score(
        price_df_bullish,
        sox_df=sox_df_bearish,
        tsm_df=tsm_df,
        tsmc_close=850.0,
        night_df=night_df,
        day_futures_df=day_futures_df,
    )
    assert bull_score >= bear_score, (
        f"Bullish SOX ({bull_score}) should score >= bearish SOX ({bear_score})"
    )


def test_empty_kwargs_doesnt_crash(strat, price_df_bullish):
    """All optional kwargs missing → should not crash, returns default."""
    score = strat.score(
        price_df_bullish,
        sox_df=pd.DataFrame(),
        tsm_df=pd.DataFrame(),
        tsmc_close=0.0,
        night_df=pd.DataFrame(),
        day_futures_df=pd.DataFrame(),
    )
    # Night gap missing → returns 15 (neutral); sox+tsm both 0 → score ≥ 0
    assert score >= 0


def test_score_in_range(strat, price_df_bullish, sox_df, tsm_df, night_df, day_futures_df):
    s = strat.score(
        price_df_bullish,
        sox_df=sox_df,
        tsm_df=tsm_df,
        tsmc_close=850.0,
        night_df=night_df,
        day_futures_df=day_futures_df,
    )
    assert 0 <= s <= 100


def test_details_has_signal_key(strat, price_df_bullish, sox_df, tsm_df, night_df, day_futures_df):
    d = strat.details(
        price_df_bullish,
        sox_df=sox_df,
        tsm_df=tsm_df,
        tsmc_close=850.0,
        night_df=night_df,
        day_futures_df=day_futures_df,
    )
    assert "signal" in d
    assert isinstance(d["signal"], str)


def test_variance_bull_vs_bear_sox(strat, price_df_bullish,
                                    sox_df, sox_df_bearish, tsm_df, night_df, day_futures_df):
    """Variance check: bullish vs bearish SOX must produce different scores."""
    s_bull = strat.score(price_df_bullish, sox_df=sox_df, tsm_df=tsm_df,
                          tsmc_close=850.0, night_df=night_df, day_futures_df=day_futures_df)
    s_bear = strat.score(price_df_bullish, sox_df=sox_df_bearish, tsm_df=tsm_df,
                          tsmc_close=850.0, night_df=night_df, day_futures_df=day_futures_df)
    assert s_bull != s_bear, (
        f"USMarket returned same score ({s_bull}) for bullish and bearish SOX — "
        "possible stuck-constant bug"
    )
