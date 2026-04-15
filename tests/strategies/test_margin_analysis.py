"""
Tests for MarginAnalysisStrategy (融資融券).

CRITICAL: This strategy had a known bug where it always returned 10 due to
a column mapping error. These tests are specifically designed to catch any
regression where the score becomes stuck at a constant value.
"""
import pandas as pd
import numpy as np
import pytest
from strategies.margin_analysis import MarginAnalysisStrategy


@pytest.fixture
def strat():
    return MarginAnalysisStrategy()


def test_squeeze_signal_scores_high(strat, price_df_bullish, margin_df_squeeze):
    """
    軋空: margin decreasing + short increasing → should score high (chips settling).
    """
    score = strat.score(price_df_bullish, margin_df=margin_df_squeeze)
    assert score > 50, (
        f"Short squeeze setup should score >50, got {score}. "
        "If score==10 or ==50, the column-mapping bug may have returned."
    )


def test_retail_chase_scores_lower(strat, price_df_bullish,
                                    margin_df_squeeze, margin_df_retail_chase):
    """
    Retail chasing (margin surging) should score lower than chips-settling.
    """
    squeeze_score = strat.score(price_df_bullish, margin_df=margin_df_squeeze)
    chase_score = strat.score(price_df_bullish, margin_df=margin_df_retail_chase)
    assert squeeze_score > chase_score, (
        f"Squeeze ({squeeze_score}) should outscore retail chase ({chase_score})"
    )


def test_no_margin_df_returns_neutral(strat, price_df_bullish):
    """Missing margin_df → neutral 50.0."""
    score = strat.score(price_df_bullish)
    assert score == 50.0


def test_score_in_range(strat, price_df_bullish, margin_df_squeeze, margin_df_retail_chase):
    for df in [margin_df_squeeze, margin_df_retail_chase]:
        s = strat.score(price_df_bullish, margin_df=df)
        assert 0 <= s <= 100, f"Score {s} out of [0,100]"


def test_details_has_signal_key(strat, price_df_bullish, margin_df_squeeze):
    d = strat.details(price_df_bullish, margin_df=margin_df_squeeze)
    assert "signal" in d
    assert isinstance(d["signal"], str)


def test_variance_squeeze_vs_chase(strat, price_df_bullish,
                                    margin_df_squeeze, margin_df_retail_chase):
    """
    CRITICAL variance check: squeeze vs retail-chase MUST produce different scores.
    This is the primary regression guard for the historical 'stuck at 10' bug.
    """
    s_squeeze = strat.score(price_df_bullish, margin_df=margin_df_squeeze)
    s_chase = strat.score(price_df_bullish, margin_df=margin_df_retail_chase)
    assert s_squeeze != s_chase, (
        f"MarginAnalysis returned IDENTICAL score ({s_squeeze}) for squeeze and "
        "retail-chase inputs. This is the 'stuck constant' regression!"
    )


def test_margin_balance_column_actually_used(strat, price_df_bullish):
    """
    Verify that the 'margin_balance' column drives the score.
    Two DataFrames identical except margin_balance must differ in score.
    """
    n = 20
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    base = {
        "date": dates,
        "short_balance": np.full(n, 5000),
    }
    # Low margin (decreasing → good chips settling → higher score)
    df_low_margin = pd.DataFrame({**base,
        "margin_balance": np.linspace(40000, 25000, n).astype(int)})
    # High margin (increasing → retail chasing → lower score)
    df_high_margin = pd.DataFrame({**base,
        "margin_balance": np.linspace(20000, 60000, n).astype(int)})

    s_low = strat.score(price_df_bullish, margin_df=df_low_margin)
    s_high = strat.score(price_df_bullish, margin_df=df_high_margin)

    assert s_low != s_high, (
        f"margin_balance column appears NOT to be influencing the score — "
        f"both inputs returned {s_low}. Column mapping bug suspected."
    )
    assert s_low > s_high, (
        f"Decreasing margin ({s_low}) should outscore increasing margin ({s_high})"
    )
