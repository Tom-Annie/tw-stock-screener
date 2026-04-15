"""
技術指標計算模組
"""
import pandas as pd
import numpy as np


def moving_average(series: pd.Series, period: int) -> pd.Series:
    """簡單移動平均線"""
    return series.rolling(window=period, min_periods=period).mean()


def exponential_moving_average(series: pd.Series, period: int) -> pd.Series:
    """指數移動平均線"""
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI (相對強弱指標)
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    # avg_loss == 0 時（純上漲）RSI 應為 100 而非 NaN；此 NaN 會讓
    # RelativeStrengthStrategy 對強勢股悄悄打 0 分
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.where(avg_loss != 0, 100.0)
    return out


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """量比 = 當日成交量 / N日平均量"""
    avg_vol = volume.rolling(window=period, min_periods=period).mean()
    return volume / avg_vol.replace(0, np.nan)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD 指標"""
    ema_fast = exponential_moving_average(series, fast)
    ema_slow = exponential_moving_average(series, slow)
    dif = ema_fast - ema_slow
    dem = exponential_moving_average(dif, signal)
    histogram = dif - dem
    return dif, dem, histogram


def relative_performance(stock_close: pd.Series, index_close: pd.Series,
                         period: int = 20) -> float:
    """
    計算個股相對大盤的超額報酬率
    stock_close 和 index_close 需要同長度、對齊日期
    """
    if len(stock_close) < period or len(index_close) < period:
        return 0.0

    stock_ret = (stock_close.iloc[-1] / stock_close.iloc[-period] - 1) * 100
    index_ret = (index_close.iloc[-1] / index_close.iloc[-period] - 1) * 100
    return stock_ret - index_ret


def price_change_pct(series: pd.Series, period: int = 1) -> pd.Series:
    """N日漲跌幅 (%)"""
    return series.pct_change(periods=period) * 100


# ===== 進階指標 =====

def stochastic_kd(high: pd.Series, low: pd.Series, close: pd.Series,
                  k_period: int = 9, d_period: int = 3):
    """KD 隨機指標"""
    lowest = low.rolling(window=k_period, min_periods=k_period).min()
    highest = high.rolling(window=k_period, min_periods=k_period).max()
    rsv = (close - lowest) / (highest - lowest).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / d_period, adjust=False).mean()
    d = k.ewm(alpha=1 / d_period, adjust=False).mean()
    return k, d


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0):
    """布林通道"""
    ma = series.rolling(window=period, min_periods=period).mean()
    std = series.rolling(window=period, min_periods=period).std()
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    # %B = (價格 - 下軌) / (上軌 - 下軌)
    pct_b = (series - lower) / (upper - lower).replace(0, np.nan)
    return upper, ma, lower, pct_b


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """OBV 能量潮"""
    direction = np.sign(close.diff())
    direction.iloc[0] = 0
    return (volume * direction).cumsum()


def bias(close: pd.Series, period: int = 20) -> pd.Series:
    """乖離率 BIAS (%)"""
    ma = close.rolling(window=period, min_periods=period).mean()
    return ((close - ma) / ma.replace(0, np.nan)) * 100


def obv_trend(close: pd.Series, volume: pd.Series, period: int = 20) -> float:
    """OBV 趨勢斜率 (正=量能流入, 負=量能流出)"""
    obv_values = obv(close, volume)
    if len(obv_values) < period:
        return 0.0
    recent = obv_values.iloc[-period:]
    x = np.arange(len(recent))
    if recent.std() == 0:
        return 0.0
    slope = np.polyfit(x, recent.values, 1)[0]
    return slope


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series,
               period: int = 14) -> pd.Series:
    """威廉指標 %R"""
    highest = high.rolling(window=period, min_periods=period).max()
    lowest = low.rolling(window=period, min_periods=period).min()
    return -100 * (highest - close) / (highest - lowest).replace(0, np.nan)


def atr(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14) -> pd.Series:
    """平均真實範圍 ATR"""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()


def max_drawdown(close: pd.Series) -> tuple:
    """
    最大回撤 (Maximum Drawdown)
    回傳 (mdd_pct, drawdown_series)
      mdd_pct: 最大回撤百分比 (負值，例如 -15.3)
      drawdown_series: 每日回撤百分比序列（用於繪圖）
    """
    if close.empty or len(close) < 2:
        return 0.0, pd.Series(dtype=float)
    cummax = close.cummax()
    drawdown = (close - cummax) / cummax * 100
    mdd_pct = drawdown.min()
    return round(float(mdd_pct), 2), drawdown


def volatility_risk(high: pd.Series, low: pd.Series, close: pd.Series) -> dict:
    """
    波動率風險指標
    回傳 dict: atr_pct (ATR 佔股價%), risk_level (低/中/高/極高), atr_trend (擴張/收斂/穩定)
    """
    if len(close) < 20:
        return {"atr_pct": 0, "risk_level": "無資料", "atr_trend": "無資料"}

    atr_s = atr(high, low, close, 14)
    current_atr = atr_s.iloc[-1]
    current_close = close.iloc[-1]

    if pd.isna(current_atr) or current_close <= 0:
        return {"atr_pct": 0, "risk_level": "無資料", "atr_trend": "無資料"}

    atr_pct = round(current_atr / current_close * 100, 2)

    # 風險等級
    if atr_pct > 5:
        risk_level = "極高"
    elif atr_pct > 3:
        risk_level = "高"
    elif atr_pct > 1.5:
        risk_level = "中"
    else:
        risk_level = "低"

    # ATR 趨勢（近 5 日 vs 近 20 日）
    atr_trend = "穩定"
    if len(atr_s.dropna()) >= 20:
        atr_5 = atr_s.iloc[-5:].mean()
        atr_20 = atr_s.iloc[-20:].mean()
        if pd.notna(atr_5) and pd.notna(atr_20) and atr_20 > 0:
            ratio = atr_5 / atr_20
            if ratio > 1.3:
                atr_trend = "擴張"  # 波動加大
            elif ratio < 0.7:
                atr_trend = "收斂"  # 波動縮小

    return {"atr_pct": atr_pct, "risk_level": risk_level, "atr_trend": atr_trend}
