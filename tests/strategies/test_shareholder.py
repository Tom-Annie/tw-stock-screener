"""
Tests for ShareholderStrategy (大戶籌碼).

Note: FinMind集保資料受限 — weight is 0 in production, but the strategy
logic itself must still work correctly. These tests check for the
historical 'always returns 50' regression.
"""
import pandas as pd
import pytest
from strategies.shareholder import ShareholderStrategy


@pytest.fixture
def strat():
    return ShareholderStrategy()


def test_bullish_tdcc_scores_high(strat, price_df_bullish, tdcc_df_bullish):
    score = strat.score(price_df_bullish, tdcc_df=tdcc_df_bullish)
    assert score > 50, (
        f"Big-holder increasing should score >50, got {score}. "
        "If score==50 always, the 'stuck at 50' regression is back."
    )


def test_bearish_tdcc_scores_lower(strat, price_df_bullish,
                                    tdcc_df_bullish, tdcc_df_bearish):
    bull_score = strat.score(price_df_bullish, tdcc_df=tdcc_df_bullish)
    bear_score = strat.score(price_df_bullish, tdcc_df=tdcc_df_bearish)
    assert bull_score > bear_score, (
        f"Bullish TDCC ({bull_score}) should outscore bearish ({bear_score})"
    )


def test_no_tdcc_df_returns_neutral(strat, price_df_bullish):
    """Missing tdcc_df → neutral 50."""
    score = strat.score(price_df_bullish)
    assert score == 50.0


def test_score_in_range(strat, price_df_bullish, tdcc_df_bullish, tdcc_df_bearish):
    for df in [tdcc_df_bullish, tdcc_df_bearish]:
        s = strat.score(price_df_bullish, tdcc_df=df)
        assert 0 <= s <= 100, f"Score {s} out of [0, 100]"


def test_details_has_signal_key(strat, price_df_bullish, tdcc_df_bullish):
    d = strat.details(price_df_bullish, tdcc_df=tdcc_df_bullish)
    assert "signal" in d
    assert isinstance(d["signal"], str)


def test_variance_bull_vs_bear(strat, price_df_bullish,
                                tdcc_df_bullish, tdcc_df_bearish):
    """
    CRITICAL variance check: bullish vs bearish chip concentration must differ.
    This catches the historical 'always returns 50' ShareholderStrategy bug.
    """
    s_bull = strat.score(price_df_bullish, tdcc_df=tdcc_df_bullish)
    s_bear = strat.score(price_df_bullish, tdcc_df=tdcc_df_bearish)
    assert s_bull != s_bear, (
        f"ShareholderStrategy returned IDENTICAL score ({s_bull}) for bullish "
        "and bearish TDCC inputs. This is the 'stuck at 50' regression!"
    )


def test_single_period_uses_absolute_value(strat, price_df_bullish):
    """When only one TDCC period is available, strategy uses absolute big-holder %."""
    single_period = pd.DataFrame([
        {"date": "2024-01-01", "holding_range": "400-600",
         "holders": 50, "shares": 500000, "pct": 75.0},
        {"date": "2024-01-01", "holding_range": "1-999",
         "holders": 3000, "shares": 80000, "pct": 10.0},
        {"date": "2024-01-01", "holding_range": "其他",
         "holders": 1000, "shares": 120000, "pct": 15.0},
    ])
    score = strat.score(price_df_bullish, tdcc_df=single_period)
    # big_pct=75 → score += 60 → clamped 60
    assert score >= 50, f"75% big holders should score >=50, got {score}"
