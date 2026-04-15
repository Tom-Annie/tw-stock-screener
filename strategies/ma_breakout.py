"""
策略一：突破均線
偵測股價突破關鍵均線 (5/10/20/60日)，並評估突破力道
"""
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy
from utils.indicators import moving_average
from config.settings import MA_PERIODS


class MABreakoutStrategy(BaseStrategy):
    name = "突破均線"
    description = "偵測股價站上多條均線，近期突破者加分"

    def _analyze(self, price_df: pd.DataFrame):
        """一次計算所有均線指標，供 score() 和 details() 共用"""
        close = price_df["close"]
        latest_close = close.iloc[-1]

        # 預先計算所有均線
        ma_series = {}
        ma_values = {}
        for period in MA_PERIODS:
            ma = moving_average(close, period)
            ma_series[period] = ma
            if pd.notna(ma.iloc[-1]):
                ma_values[period] = ma.iloc[-1]

        # 站上幾條均線
        above_ma = []
        for period, val in ma_values.items():
            if latest_close > val:
                above_ma.append(period)

        # 近3日是否剛突破
        breakout = []
        for period in MA_PERIODS:
            ma = ma_series[period]
            if period not in ma_values or len(ma) < 4:
                continue
            recently_below = any(
                close.iloc[-(i + 1)] <= ma.iloc[-(i + 1)]
                for i in range(1, min(4, len(close)))
                if pd.notna(ma.iloc[-(i + 1)])
            )
            if latest_close > ma_values[period] and recently_below:
                breakout.append(period)

        # 多頭排列
        sorted_periods = sorted(ma_values.keys())
        bullish = (len(sorted_periods) >= 3 and
                   all(ma_values[sorted_periods[i]] > ma_values[sorted_periods[i + 1]]
                       for i in range(len(sorted_periods) - 1)))

        return above_ma, breakout, bullish, ma_values

    def score(self, price_df: pd.DataFrame, **kwargs) -> float:
        if price_df.empty or len(price_df) < max(MA_PERIODS):
            return 0.0

        above_ma, breakout, bullish, _ = self._analyze(price_df)

        score = len(above_ma) * 15       # max 60
        score += len(breakout) * 8       # max 32
        if bullish:
            score += 8

        return self._clamp(score)

    def details(self, price_df: pd.DataFrame, **kwargs) -> dict:
        if price_df.empty or len(price_df) < max(MA_PERIODS):
            return {"above_ma": [], "breakout": [], "bullish_alignment": False,
                    "signal": "資料不足"}

        above_ma, breakout, bullish, ma_values = self._analyze(price_df)

        above_labels = [f"MA{p}" for p in above_ma]
        breakout_labels = [f"MA{p}" for p in breakout]

        return {
            "above_ma": above_labels,
            "breakout": breakout_labels,
            "bullish_alignment": bullish,
            "ma_values": {f"MA{k}": round(v, 2) for k, v in ma_values.items()},
            "signal": "突破" + "+".join(breakout_labels) if breakout_labels else
                      f"站上{len(above_labels)}條均線" if above_labels else "均線下方"
        }
