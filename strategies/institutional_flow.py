"""
策略四：法人籌碼
追蹤外資、投信、自營商買賣超動向
"""
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy
from config.settings import INSTITUTIONAL_LOOKBACK


class InstitutionalFlowStrategy(BaseStrategy):
    name = "法人籌碼"
    description = "三大法人買賣超分析，投信權重最高"

    def score(self, price_df: pd.DataFrame, **kwargs) -> float:
        """
        kwargs:
            institutional_df: pd.DataFrame - 法人買賣超資料
                欄位: date, foreign_net, trust_net, dealer_net, total_net
        """
        inst_df = kwargs.get("institutional_df")
        if inst_df is None or inst_df.empty:
            return 50.0  # 無資料給中性分，避免不公平懲罰

        # 取最近 N 天
        inst_df = inst_df.sort_values("date").tail(INSTITUTIONAL_LOOKBACK)
        if len(inst_df) < 3:
            return 50.0

        score = 0.0

        # 1. 投信買賣超 (max 30)
        trust_sub = 0.0
        trust_net_sum = inst_df["trust_net"].sum()
        trust_consecutive = self._consecutive_buy_days(inst_df["trust_net"])

        if trust_net_sum > 0:
            trust_sub += min(15, trust_consecutive * 3)
            # 量級加分（連續天數+量級共 max 30）
            trust_avg = inst_df["trust_net"].mean()
            if trust_avg > 500:
                trust_sub += 15
            elif trust_avg > 200:
                trust_sub += 10
            elif trust_avg > 0:
                trust_sub += 5
        score += min(trust_sub, 30)

        # 2. 外資買賣超 (max 25)
        foreign_sub = 0.0
        foreign_net_sum = inst_df["foreign_net"].sum()
        foreign_consecutive = self._consecutive_buy_days(inst_df["foreign_net"])

        if foreign_net_sum > 0:
            foreign_sub += min(12, foreign_consecutive * 3)
            foreign_avg = inst_df["foreign_net"].mean()
            if foreign_avg > 1000:
                foreign_sub += 13
            elif foreign_avg > 500:
                foreign_sub += 8
            elif foreign_avg > 0:
                foreign_sub += 4
        score += min(foreign_sub, 25)

        # 3. 自營商買賣超 (max 15)
        dealer_net_sum = inst_df["dealer_net"].sum()
        if dealer_net_sum > 0:
            score += 10
            dealer_consecutive = self._consecutive_buy_days(inst_df["dealer_net"])
            score += min(5, dealer_consecutive)

        # 4. 三大法人同步買超加分 (max 30)
        latest = inst_df.iloc[-1]
        buyers = sum([
            latest.get("foreign_net", 0) > 0,
            latest.get("trust_net", 0) > 0,
            latest.get("dealer_net", 0) > 0
        ])

        if buyers == 3:
            score += 20
        elif buyers == 2:
            score += 10

        # 總分上限保護: 30 + 25 + 15 + 20 = 90, 不會輕易滿分
        return self._clamp(score)

    def _consecutive_buy_days(self, net_series: pd.Series) -> int:
        """計算最近連續買超天數"""
        count = 0
        for val in reversed(net_series.values):
            if val > 0:
                count += 1
            else:
                break
        return count

    def details(self, price_df: pd.DataFrame, **kwargs) -> dict:
        inst_df = kwargs.get("institutional_df")
        if inst_df is None or inst_df.empty:
            return {"foreign_net": 0, "trust_net": 0, "dealer_net": 0,
                    "consecutive_days": 0, "signal": "無資料"}

        inst_df = inst_df.sort_values("date").tail(INSTITUTIONAL_LOOKBACK)

        # 近期累計
        foreign_sum = int(inst_df["foreign_net"].sum())
        trust_sum = int(inst_df["trust_net"].sum())
        dealer_sum = int(inst_df["dealer_net"].sum())
        total_sum = foreign_sum + trust_sum + dealer_sum

        # 連續買超
        trust_streak = self._consecutive_buy_days(inst_df["trust_net"])
        foreign_streak = self._consecutive_buy_days(inst_df["foreign_net"])

        # 訊號文字
        parts = []
        if trust_sum > 0:
            parts.append(f"投信買{trust_sum:,}張")
        if foreign_sum > 0:
            parts.append(f"外資買{foreign_sum:,}張")
        if trust_streak > 2:
            parts.append(f"投信連{trust_streak}日")

        latest = inst_df.iloc[-1]
        all_buy = (latest.get("foreign_net", 0) > 0 and
                   latest.get("trust_net", 0) > 0 and
                   latest.get("dealer_net", 0) > 0)
        if all_buy:
            parts.append("三大法人同步買超")

        return {
            "foreign_net_total": foreign_sum,
            "trust_net_total": trust_sum,
            "dealer_net_total": dealer_sum,
            "total_net": total_sum,
            "trust_consecutive": trust_streak,
            "foreign_consecutive": foreign_streak,
            "signal": " ".join(parts) if parts else "法人偏空"
        }
