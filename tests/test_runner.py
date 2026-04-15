"""
Tests for strategies/runner.py::score_stock().
Verifies orchestration, error isolation, and output schema.
"""
import pandas as pd
import numpy as np
import pytest

from strategies.runner import score_stock
from strategies.ma_breakout import MABreakoutStrategy
from strategies.volume_price import VolumePriceStrategy
from strategies.relative_strength import RelativeStrengthStrategy
from strategies.institutional_flow import InstitutionalFlowStrategy
from strategies.enhanced_technical import EnhancedTechnicalStrategy
from strategies.margin_analysis import MarginAnalysisStrategy
from strategies.us_market import USMarketStrategy
from strategies.shareholder import ShareholderStrategy


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

ALL_STRATEGY_KEYS = [
    "ma_breakout", "volume_price", "relative_strength", "institutional_flow",
    "enhanced_technical", "margin_analysis", "us_market", "shareholder",
]


@pytest.fixture(autouse=True)
def patch_usd_twd():
    """Avoid network call in USMarketStrategy during runner tests."""
    USMarketStrategy._cached_usd_twd = 31.5
    yield
    USMarketStrategy._cached_usd_twd = None


@pytest.fixture
def all_strategies():
    return {
        "ma_breakout": MABreakoutStrategy(),
        "volume_price": VolumePriceStrategy(),
        "relative_strength": RelativeStrengthStrategy(),
        "institutional_flow": InstitutionalFlowStrategy(),
        "enhanced_technical": EnhancedTechnicalStrategy(),
        "margin_analysis": MarginAnalysisStrategy(),
        "us_market": USMarketStrategy(),
        "shareholder": ShareholderStrategy(),
    }


@pytest.fixture
def price_df():
    n = 70
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(42)
    closes = 100 + np.cumsum(rng.normal(0.5, 1, n))
    return pd.DataFrame({
        "date": dates,
        "stock_id": "2330",
        "open": closes * 0.999,
        "high": closes * 1.01,
        "low": closes * 0.99,
        "close": closes,
        "volume": rng.integers(100_000, 500_000, n),
    })


@pytest.fixture
def minimal_context(taiex_close, sox_df, tsm_df, night_df, day_futures_df):
    return {
        "taiex_close": taiex_close,
        "sox_df": sox_df,
        "tsm_df": tsm_df,
        "tsmc_close": 850.0,
        "night_df": night_df,
        "day_futures_df": day_futures_df,
    }


@pytest.fixture
def minimal_per_stock(institutional_df_buying, margin_df_squeeze, tdcc_df_bullish):
    return {
        "institutional_df": institutional_df_buying,
        "margin_df": margin_df_squeeze,
        "tdcc_df": tdcc_df_bullish,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_returns_all_8_keys(all_strategies, price_df, minimal_context, minimal_per_stock):
    result = score_stock(price_df, all_strategies,
                         context=minimal_context, per_stock=minimal_per_stock)
    for key in ALL_STRATEGY_KEYS:
        assert key in result, f"Missing key '{key}' in score_stock output"


def test_each_entry_has_required_fields(all_strategies, price_df, minimal_context, minimal_per_stock):
    result = score_stock(price_df, all_strategies,
                         context=minimal_context, per_stock=minimal_per_stock)
    for key, entry in result.items():
        assert "score" in entry, f"{key}: missing 'score'"
        assert "detail" in entry, f"{key}: missing 'detail'"
        assert "error" in entry, f"{key}: missing 'error'"


def test_scores_are_numeric_and_in_range(all_strategies, price_df, minimal_context, minimal_per_stock):
    result = score_stock(price_df, all_strategies,
                         context=minimal_context, per_stock=minimal_per_stock)
    for key, entry in result.items():
        score = entry["score"]
        assert isinstance(score, (int, float)), f"{key}: score is not numeric ({type(score)})"
        assert 0 <= score <= 100, f"{key}: score {score} out of [0, 100]"


def test_include_details_false_makes_detail_none(all_strategies, price_df,
                                                  minimal_context, minimal_per_stock):
    result = score_stock(price_df, all_strategies,
                         context=minimal_context, per_stock=minimal_per_stock,
                         include_details=False)
    for key, entry in result.items():
        assert entry["detail"] is None, f"{key}: detail should be None when include_details=False"


def test_include_details_true_returns_dicts(all_strategies, price_df,
                                             minimal_context, minimal_per_stock):
    result = score_stock(price_df, all_strategies,
                         context=minimal_context, per_stock=minimal_per_stock,
                         include_details=True)
    for key, entry in result.items():
        if entry["error"] is None:
            assert isinstance(entry["detail"], dict), (
                f"{key}: detail should be dict when include_details=True, got {type(entry['detail'])}"
            )


def test_error_strategy_doesnt_poison_others(price_df, minimal_context, minimal_per_stock):
    """A strategy that always raises must not affect other strategies' scores."""

    class BrokenStrategy:
        name = "broken"

        def score(self, price_df, **kwargs):
            raise RuntimeError("intentional test error")

        def details(self, price_df, **kwargs):
            raise RuntimeError("intentional test error")

    strategies = {
        "ma_breakout": MABreakoutStrategy(),
        "broken": BrokenStrategy(),
        "volume_price": VolumePriceStrategy(),
    }

    result = score_stock(price_df, strategies,
                         context=minimal_context, per_stock=minimal_per_stock)

    # Broken strategy reports error with score=0
    assert result["broken"]["error"] is not None
    assert result["broken"]["score"] == 0

    # Other strategies still work
    assert result["ma_breakout"]["error"] is None
    assert result["volume_price"]["error"] is None


def test_empty_context_and_per_stock_doesnt_crash(all_strategies, price_df):
    """score_stock must not crash when context/per_stock are omitted."""
    result = score_stock(price_df, all_strategies)
    assert len(result) == 8
    for key, entry in result.items():
        assert "score" in entry


def test_empty_price_df_doesnt_crash(all_strategies, minimal_context, minimal_per_stock):
    """score_stock with empty price_df should handle gracefully (no crash)."""
    result = score_stock(pd.DataFrame(), all_strategies,
                         context=minimal_context, per_stock=minimal_per_stock)
    assert len(result) == 8
    for key, entry in result.items():
        assert "score" in entry
