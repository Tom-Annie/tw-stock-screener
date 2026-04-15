"""
Shared pytest fixtures for tw-stock-screener test suite.
All DataFrames use the real schema from data/prices.py::_normalize_price_df.
"""
import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_df(n: int, start_price: float, trend: float,
                   base_volume: int = 100_000, vol_trend: float = 0.0,
                   stock_id: str = "9999") -> pd.DataFrame:
    """
    Build a synthetic price_df with the schema:
      date, stock_id, open, high, low, close, volume
    trend > 0 → uptrend, trend < 0 → downtrend, trend == 0 → flat
    vol_trend: additive multiplier per day to volume (positive = growing vol)
    """
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    prices = [start_price + i * trend for i in range(n)]
    # add tiny noise so MA logic doesn't collapse
    rng = np.random.default_rng(42)
    noise = rng.normal(0, start_price * 0.002, n)
    closes = np.array(prices) + noise
    closes = np.maximum(closes, 1.0)

    opens = closes * rng.uniform(0.995, 1.005, n)
    highs = closes * rng.uniform(1.001, 1.015, n)
    lows = closes * rng.uniform(0.985, 0.999, n)

    volumes = np.array([
        max(1000, int(base_volume + i * vol_trend + rng.integers(-5000, 5000)))
        for i in range(n)
    ])

    return pd.DataFrame({
        "date": dates,
        "stock_id": stock_id,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


# ---------------------------------------------------------------------------
# price_df fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def price_df_bullish():
    """60-day uptrend with increasing volume — clear bull market."""
    return _make_price_df(n=70, start_price=100.0, trend=0.6,
                          base_volume=200_000, vol_trend=2000)


@pytest.fixture
def price_df_bearish():
    """60-day downtrend with decreasing volume."""
    return _make_price_df(n=70, start_price=150.0, trend=-0.6,
                          base_volume=200_000, vol_trend=-500)


@pytest.fixture
def price_df_flat():
    """60-day sideways (flat) market."""
    return _make_price_df(n=70, start_price=100.0, trend=0.0,
                          base_volume=100_000, vol_trend=0)


# ---------------------------------------------------------------------------
# institutional_df fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def institutional_df_buying():
    """20 rows of strong foreign + trust net buying."""
    n = 20
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(7)
    return pd.DataFrame({
        "date": dates,
        "foreign_net": rng.integers(800, 2000, n),
        "trust_net": rng.integers(300, 800, n),
        "dealer_net": rng.integers(100, 400, n),
    })


@pytest.fixture
def institutional_df_selling():
    """20 rows of consistent net selling."""
    n = 20
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(13)
    return pd.DataFrame({
        "date": dates,
        "foreign_net": rng.integers(-2000, -200, n),
        "trust_net": rng.integers(-500, -50, n),
        "dealer_net": rng.integers(-300, -10, n),
    })


# ---------------------------------------------------------------------------
# margin_df fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def margin_df_squeeze():
    """
    軋空訊號: margin_balance decreasing (good — chip settling),
    short_balance increasing (shorts piling in), high short/margin ratio.
    """
    n = 20
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    # Decreasing margin: 50000 → 30000
    margin_balance = np.linspace(50000, 30000, n).astype(int)
    # Increasing short: 5000 → 15000
    short_balance = np.linspace(5000, 15000, n).astype(int)
    return pd.DataFrame({
        "date": dates,
        "margin_balance": margin_balance,
        "short_balance": short_balance,
    })


@pytest.fixture
def margin_df_retail_chase():
    """
    散戶追高訊號: margin_balance increasing rapidly, short_balance low.
    """
    n = 20
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    margin_balance = np.linspace(20000, 60000, n).astype(int)
    short_balance = np.linspace(1000, 1200, n).astype(int)
    return pd.DataFrame({
        "date": dates,
        "margin_balance": margin_balance,
        "short_balance": short_balance,
    })


# ---------------------------------------------------------------------------
# index / market fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def taiex_close():
    """60-value bullish TAIEX close series."""
    rng = np.random.default_rng(99)
    vals = 18000 + np.cumsum(rng.normal(30, 60, 60))
    return pd.Series(vals)


@pytest.fixture
def taiex_close_bearish():
    """60-value bearish TAIEX close series."""
    rng = np.random.default_rng(88)
    vals = 20000 + np.cumsum(rng.normal(-40, 60, 60))
    return pd.Series(vals)


# ---------------------------------------------------------------------------
# US market fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sox_df():
    """SOX index: 30 rows, bullish."""
    n = 30
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(1)
    closes = 4000 + np.cumsum(rng.normal(10, 20, n))
    return pd.DataFrame({"date": dates, "close": closes})


@pytest.fixture
def sox_df_bearish():
    """SOX index: 30 rows, bearish."""
    n = 30
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(2)
    closes = 4500 + np.cumsum(rng.normal(-12, 20, n))
    return pd.DataFrame({"date": dates, "close": closes})


@pytest.fixture
def tsm_df():
    """TSM ADR: 10 rows, bullish. close ~170 USD (≈ 870 TWD/5 = 174 TWD per share)."""
    n = 10
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    rng = np.random.default_rng(3)
    closes = 165 + np.cumsum(rng.normal(0.5, 0.5, n))
    return pd.DataFrame({"date": dates, "close": closes})


@pytest.fixture
def night_df():
    """Night futures: 5 rows, higher than day (bullish gap)."""
    n = 5
    dates = pd.date_range("2024-01-08", periods=n, freq="B")
    return pd.DataFrame({"date": dates, "close": [20200, 20350, 20400, 20500, 20600]})


@pytest.fixture
def day_futures_df():
    """Day futures: 5 rows — lower than night (so night gap is positive)."""
    n = 5
    dates = pd.date_range("2024-01-08", periods=n, freq="B")
    return pd.DataFrame({"date": dates, "close": [20000, 20100, 20150, 20200, 20300]})


# ---------------------------------------------------------------------------
# shareholder (TDCC) fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def tdcc_df_bullish():
    """
    Two periods of TDCC data.
    Big holders (400+ shares) increase from 55% → 58% (bullish).
    Small holders decrease from 20% → 17% (bullish).
    """
    rows = []
    for date_str, big_pct, small_pct in [("2024-01-01", 55.0, 20.0),
                                           ("2024-01-08", 58.0, 17.0)]:
        rows.append({"date": date_str, "holding_range": "400-600", "holders": 100, "shares": 500000, "pct": big_pct})
        rows.append({"date": date_str, "holding_range": "1-999", "holders": 5000, "shares": 100000, "pct": small_pct})
        rows.append({"date": date_str, "holding_range": "其他", "holders": 2000, "shares": 200000, "pct": 100 - big_pct - small_pct})
    return pd.DataFrame(rows)


@pytest.fixture
def tdcc_df_bearish():
    """
    Two periods: big holders shrink 60% → 55%, small holders grow 15% → 20%.
    """
    rows = []
    for date_str, big_pct, small_pct in [("2024-01-01", 60.0, 15.0),
                                           ("2024-01-08", 55.0, 20.0)]:
        rows.append({"date": date_str, "holding_range": "400-600", "holders": 100, "shares": 500000, "pct": big_pct})
        rows.append({"date": date_str, "holding_range": "1-999", "holders": 5000, "shares": 100000, "pct": small_pct})
        rows.append({"date": date_str, "holding_range": "其他", "holders": 2000, "shares": 200000, "pct": 100 - big_pct - small_pct})
    return pd.DataFrame(rows)
