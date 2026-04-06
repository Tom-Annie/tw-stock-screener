"""
策略二：量價齊揚
偵測價漲量增的共振訊號
"""
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy
from utils.indicators import volume_ratio, price_change_pct
from config.settings import VOLUME_MA_PERIOD, VOLUME_SURGE_RATIO


class VolumePriceStrategy(BaseStrategy):
    name = "量價齊揚"
    description = "價漲量增，成交量突破均量配合股價上漲"

    def _analyze(self, price_df: pd.DataFrame):
        """一次計算量價指標"""
        close = price_df["close"]
        volume = price_df["volume"]

        vratio = volume_ratio(volume, VOLUME_MA_PERIOD)
        pct = price_change_pct(close)

        today_vratio = vratio.iloc[-1] if pd.notna(vratio.iloc[-1]) else 0
        today_pct = pct.iloc[-1] if pd.notna(pct.iloc[-1]) else 0

        # 連續量價齊揚天數
        streak = 0
        for i in range(1, min(11, len(close))):
            idx = -i
            if (pd.notna(pct.iloc[idx]) and pct.iloc[idx] > 0 and
                    pd.notna(vratio.iloc[idx]) and vratio.iloc[idx] > 1.0):
                streak += 1
            else:
                break

        # 量能趨勢
        vol_trend = 0
        if len(volume) >= VOLUME_MA_PERIOD:
            vol_5 = volume.iloc[-5:].mean()
            vol_20 = volume.iloc[-VOLUME_MA_PERIOD:].mean()
            if vol_20 > 0:
                vol_trend = vol_5 / vol_20

        return today_vratio, today_pct, streak, vol_trend

    def score(self, price_df: pd.DataFrame, **kwargs) -> float:
        if price_df.empty or len(price_df) < VOLUME_MA_PERIOD + 5:
            return 0.0

        today_vratio, today_pct, streak, vol_trend = self._analyze(price_df)

        if pd.isna(today_vratio):
            return 0.0

        score = 0.0

        # 1. 量能評分 (max 30)
        if today_vratio >= 3.0:
            score += 30
        elif today_vratio >= 2.0:
            score += 25
        elif today_vratio >= VOLUME_SURGE_RATIO:
            score += 20
        elif today_vratio >= 1.2:
            score += 10

        # 2. 價格配合評分 (max 30)
        if today_pct > 5:
            score += 30
        elif today_pct > 3:
            score += 25
        elif today_pct > 1:
            score += 20
        elif today_pct > 0.3:
            score += 10  # 至少漲 0.3% 才有意義
        # 0~0.3% 不給分，避免平盤也得分

        # 3. 連續量價齊揚天數 (max 25)
        score += min(streak * 5, 25)

        # 4. 量能趨勢 (max 15)
        if vol_trend >= 2.0:
            score += 15
        elif vol_trend >= 1.5:
            score += 10
        elif vol_trend >= 1.2:
            score += 5

        return self._clamp(score)

    def details(self, price_df: pd.DataFrame, **kwargs) -> dict:
        if price_df.empty or len(price_df) < VOLUME_MA_PERIOD + 1:
            return {"volume_ratio": 0, "price_change": 0, "streak": 0}

        today_vratio, today_pct, streak, _ = self._analyze(price_df)
        today_vratio = round(today_vratio, 2) if not pd.isna(today_vratio) else 0
        today_pct = round(today_pct, 2) if not pd.isna(today_pct) else 0

        signal_parts = []
        if today_vratio >= VOLUME_SURGE_RATIO:
            signal_parts.append(f"量增{today_vratio:.1f}倍")
        if today_pct > 0:
            signal_parts.append(f"漲{today_pct:.1f}%")
        if streak > 1:
            signal_parts.append(f"連{streak}日")

        return {
            "volume_ratio": today_vratio,
            "price_change_pct": today_pct,
            "streak": streak,
            "signal": " ".join(signal_parts) if signal_parts else "無明顯訊號"
        }
