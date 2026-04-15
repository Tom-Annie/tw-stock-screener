"""Tests for InstitutionalFlowStrategy (法人籌碼)."""
import pandas as pd
import pytest
from strategies.institutional_flow import InstitutionalFlowStrategy


@pytest.fixture
def strat():
    return InstitutionalFlowStrategy()


def test_buying_scores_high(strat, price_df_bullish, institutional_df_buying):
    score = strat.score(price_df_bullish, institutional_df=institutional_df_buying)
    assert score > 60, f"Strong institutional buying should score >60, got {score}"


def test_selling_scores_lower(strat, price_df_bullish,
                               institutional_df_buying, institutional_df_selling):
    buy_score = strat.score(price_df_bullish, institutional_df=institutional_df_buying)
    sell_score = strat.score(price_df_bullish, institutional_df=institutional_df_selling)
    assert buy_score > sell_score, (
        f"Buying ({buy_score}) should outscore selling ({sell_score})"
    )


def test_no_inst_df_returns_neutral(strat, price_df_bullish):
    """Missing institutional_df → neutral 50."""
    score = strat.score(price_df_bullish)
    assert score == 50.0


def test_score_in_range(strat, price_df_bullish, institutional_df_buying,
                        institutional_df_selling):
    for inst in [institutional_df_buying, institutional_df_selling]:
        s = strat.score(price_df_bullish, institutional_df=inst)
        assert 0 <= s <= 100


def test_details_has_signal_key(strat, price_df_bullish, institutional_df_buying):
    d = strat.details(price_df_bullish, institutional_df=institutional_df_buying)
    assert "signal" in d
    assert isinstance(d["signal"], str)


def test_variance_buy_vs_sell(strat, price_df_bullish,
                               institutional_df_buying, institutional_df_selling):
    """Variance check: buying vs selling must produce different scores."""
    s_buy = strat.score(price_df_bullish, institutional_df=institutional_df_buying)
    s_sell = strat.score(price_df_bullish, institutional_df=institutional_df_selling)
    assert s_buy != s_sell, (
        f"InstitutionalFlow returned same score ({s_buy}) for buy/sell — "
        "possible stuck-constant bug"
    )
