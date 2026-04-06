"""
策略三：相對強弱
RSI 指標 + 相對大盤強弱表現
"""
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy
from utils.indicators import rsi, relative_performance, price_change_pct
from config.settings import RSI_PERIOD, RSI_BULLISH_LOW, RSI_BULLISH_HIGH


class RelativeStrengthStrategy(BaseStrategy):
    name = "相對強弱"
    description = "RSI 動能指標 + 相對大盤超額報酬"

    def _analyze(self, price_df: pd.DataFrame, **kwargs):
        """一次計算 RSI 與相對強弱指標"""
        close = price_df["close"]
        rsi_values = rsi(close, RSI_PERIOD)
        current_rsi = rsi_values.iloc[-1]

        # RSI 趨勢
        rsi_change = 0
        if len(rsi_values) >= 6 and pd.notna(rsi_values.iloc[-6]):
            rsi_change = current_rsi - rsi_values.iloc[-6]

        # 相對大盤
        index_close = kwargs.get("index_close")
        rel_5 = rel_20 = 0.0
        if index_close is not None and len(index_close) >= 20:
            rel_5 = relative_performance(close, index_close, 5)
            rel_20 = relative_performance(close, index_close, 20)

        # 近期動能
        pct_5 = 0
        if len(close) >= 6:
            pct_5 = (close.iloc[-1] / close.iloc[-6] - 1) * 100

        # RSI 狀態
        if pd.isna(current_rsi):
            rsi_state = "無資料"
        elif current_rsi >= 80:
            rsi_state = "過熱"
        elif current_rsi >= 60:
            rsi_state = "強勢"
        elif current_rsi >= 50:
            rsi_state = "中性偏多"
        elif current_rsi >= 40:
            rsi_state = "中性偏空"
        else:
            rsi_state = "弱勢"

        return {
            "current_rsi": current_rsi,
            "rsi_change": rsi_change,
            "rsi_state": rsi_state,
            "rel_5": rel_5,
            "rel_20": rel_20,
            "pct_5": pct_5,
        }

    def score(self, price_df: pd.DataFrame, **kwargs) -> float:
        if price_df.empty or len(price_df) < RSI_PERIOD + 5:
            return 0.0

        ind = self._analyze(price_df, **kwargs)
        r = ind["current_rsi"]

        if pd.isna(r):
            return 0.0

        score = 0.0

        # 1. RSI 評分 (max 40) — 使用可設定的強勢區間
        rsi_low = RSI_BULLISH_LOW
        rsi_high = RSI_BULLISH_HIGH
        if rsi_low <= r <= rsi_high:
            score += 40  # 最佳區間
        elif (rsi_low - 5) <= r < rsi_low:
            score += 30  # 接近強勢區
        elif rsi_high < r <= (rsi_high + 10):
            score += 25  # 略微過熱但仍在趨勢中
        elif 40 <= r < (rsi_low - 5):
            score += 15  # 中性偏弱
        elif r > (rsi_high + 10):
            score += 10  # 過熱但仍給分（強勢股不過度懲罰）

        # 2. RSI 趨勢 (max 15)
        rc = ind["rsi_change"]
        if rc > 10:
            score += 15
        elif rc > 5:
            score += 10
        elif rc > 0:
            score += 5

        # 3. 相對大盤表現 (max 30)
        if ind["rel_5"] > 5:
            score += 10
        elif ind["rel_5"] > 2:
            score += 7
        elif ind["rel_5"] > 0:
            score += 3

        if ind["rel_20"] > 10:
            score += 20
        elif ind["rel_20"] > 5:
            score += 15
        elif ind["rel_20"] > 0:
            score += 8

        # 4. 近期漲幅動能 (max 15)
        p5 = ind["pct_5"]
        if 3 <= p5 <= 15:
            score += 15
        elif 1 <= p5 < 3:
            score += 10
        elif 0 < p5 < 1:
            score += 5

        return self._clamp(score)

    def details(self, price_df: pd.DataFrame, **kwargs) -> dict:
        if price_df.empty or len(price_df) < RSI_PERIOD + 1:
            return {"rsi": 0, "relative_5d": 0, "relative_20d": 0}

        ind = self._analyze(price_df, **kwargs)
        r = round(ind["current_rsi"], 1) if pd.notna(ind["current_rsi"]) else 0

        return {
            "rsi": r,
            "rsi_state": ind["rsi_state"],
            "relative_5d": round(ind["rel_5"], 2),
            "relative_20d": round(ind["rel_20"], 2),
            "signal": f"RSI {r}({ind['rsi_state']}) 勝大盤{ind['rel_20']:+.1f}%"
        }
