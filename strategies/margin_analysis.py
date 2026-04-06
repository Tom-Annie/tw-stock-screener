"""
策略六：融資融券籌碼分析
融資減少+股價持穩=籌碼沉澱(好)
融資暴增+股價暴漲=散戶追高(危險)
"""
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy


class MarginAnalysisStrategy(BaseStrategy):
    name = "融資融券"
    description = "融資融券變化分析，偵測籌碼沉澱與散戶追高"

    def _analyze(self, margin_df: pd.DataFrame):
        """一次計算融資融券指標"""
        margin_df = margin_df.sort_values("date").tail(20)

        margin_change = None
        short_change = None
        short_margin_ratio = None

        # 融資變化
        if "margin_balance" in margin_df.columns and len(margin_df) >= 10:
            mb = margin_df["margin_balance"]
            recent_5 = mb.iloc[-5:].mean()
            older_5 = mb.iloc[-10:-5].mean()
            if older_5 > 0:
                margin_change = (recent_5 - older_5) / older_5 * 100

        # 融券變化
        if "short_balance" in margin_df.columns and len(margin_df) >= 5:
            sb = margin_df["short_balance"]
            short_recent = sb.iloc[-5:].mean()
            short_older = sb.iloc[-10:-5].mean() if len(sb) >= 10 else sb.iloc[:5].mean()
            if short_older > 0:
                short_change = (short_recent - short_older) / short_older * 100

        # 券資比
        if ("margin_balance" in margin_df.columns and
                "short_balance" in margin_df.columns):
            latest_margin = margin_df["margin_balance"].iloc[-1]
            latest_short = margin_df["short_balance"].iloc[-1]
            if latest_margin > 0:
                short_margin_ratio = latest_short / latest_margin * 100

        return margin_change, short_change, short_margin_ratio

    def score(self, price_df: pd.DataFrame, **kwargs) -> float:
        margin_df = kwargs.get("margin_df")
        if margin_df is None or margin_df.empty or len(margin_df) < 5:
            return 50.0  # 無資料給中性分

        margin_change, short_change, ratio = self._analyze(margin_df)
        score = 0.0

        # 1. 融資變化 (max 40)
        if margin_change is not None:
            if margin_change < -5:
                score += 40
            elif margin_change < -2:
                score += 30
            elif margin_change < 0:
                score += 20
            elif margin_change < 3:
                score += 10
            elif margin_change > 10:
                score -= 10

        # 2. 融券變化 (max 30)
        if short_change is not None:
            if short_change > 10:
                score += 20
            elif short_change > 5:
                score += 15
            elif short_change < -10:
                score += 10

        # 3. 券資比 (max 30)
        if ratio is not None:
            if ratio > 30:
                score += 30
            elif ratio > 20:
                score += 20
            elif ratio > 10:
                score += 10

        return self._clamp(score)

    def details(self, price_df: pd.DataFrame, **kwargs) -> dict:
        margin_df = kwargs.get("margin_df")
        if margin_df is None or margin_df.empty:
            return {"signal": "無融資融券資料"}

        margin_change, short_change, ratio = self._analyze(margin_df)
        signals = []

        if margin_change is not None:
            if margin_change < -2:
                signals.append(f"融資減{abs(margin_change):.1f}%")
            elif margin_change > 5:
                signals.append(f"融資增{margin_change:.1f}%")

        if ratio is not None and ratio > 20:
            signals.append(f"券資比{ratio:.1f}%")

        return {
            "signal": " ".join(signals) if signals else "籌碼中性"
        }
