"""
策略八：大戶籌碼集中度
分析集保中心股權分散表，偵測大戶持股變化
大戶增加+散戶減少=籌碼集中(好)
散戶增加+大戶減少=籌碼發散(危險)
"""
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy


class ShareholderStrategy(BaseStrategy):
    name = "大戶籌碼"
    description = "集保股權分散表分析，偵測大戶持股集中度變化"

    # 大戶門檻: 持股 400張以上 (level 12~17 通常是大戶)
    BIG_LEVELS = {"400-600", "600-800", "800-1,000", "1,000以上",
                  "400張以上", "600張以上", "800張以上", "1,000張以上",
                  "400-599", "600-799", "800-999"}

    # 散戶門檻: 持股 10張以下
    SMALL_LEVELS = {"1-999", "1,000-5,000", "5,001-10,000",
                    "1以下", "1-5", "5-10", "1張以下", "1-5張", "5-10張"}

    def score(self, price_df: pd.DataFrame, **kwargs) -> float:
        """
        kwargs:
            tdcc_df: pd.DataFrame - 集保股權分散表
                欄位: date, holding_range, holders, shares, pct
        """
        tdcc_df = kwargs.get("tdcc_df")
        if tdcc_df is None or tdcc_df.empty:
            return 50.0  # 無資料給中性分

        score = 0.0
        dates = sorted(tdcc_df["date"].unique())

        if len(dates) < 2:
            # 只有一期資料，看絕對值
            latest = tdcc_df[tdcc_df["date"] == dates[-1]]
            big_pct = self._big_holder_pct(latest)
            if big_pct > 70:
                score += 60
            elif big_pct > 50:
                score += 45
            elif big_pct > 30:
                score += 30
            else:
                score += 15
            return self._clamp(score)

        # 取最近兩期比較
        latest = tdcc_df[tdcc_df["date"] == dates[-1]]
        prev = tdcc_df[tdcc_df["date"] == dates[-2]]

        latest_big = self._big_holder_pct(latest)
        prev_big = self._big_holder_pct(prev)
        latest_small = self._small_holder_pct(latest)
        prev_small = self._small_holder_pct(prev)

        # 1. 大戶持股比例 (max 40)
        if latest_big > 70:
            score += 40
        elif latest_big > 50:
            score += 30
        elif latest_big > 30:
            score += 20
        else:
            score += 10

        # 2. 大戶持股變化 (max 30)
        big_change = latest_big - prev_big
        if big_change > 2:
            score += 30  # 大戶大幅增加
        elif big_change > 0.5:
            score += 20  # 大戶小幅增加
        elif big_change > -0.5:
            score += 10  # 持平
        elif big_change < -2:
            score -= 10  # 大戶大幅減少 = 危險

        # 3. 散戶持股變化 (max 30)
        small_change = latest_small - prev_small
        if small_change < -2:
            score += 30  # 散戶大幅減少 = 好
        elif small_change < -0.5:
            score += 20
        elif small_change < 0.5:
            score += 10
        elif small_change > 2:
            score -= 10  # 散戶大幅增加 = 危險

        return self._clamp(score)

    def _big_holder_pct(self, df: pd.DataFrame) -> float:
        """計算大戶持股比例（持股 400 張以上）"""
        if "pct" not in df.columns or "holding_range" not in df.columns:
            return 0.0

        def _is_big(x: str) -> bool:
            x = str(x)
            # 明確的大戶分級
            for k in ["400-", "600-", "800-", "1,000以上", "1000以上",
                       "400張", "600張", "800張", "1,000張以上"]:
                if k in x:
                    return True
            return False

        big = df[df["holding_range"].apply(_is_big)]
        return big["pct"].sum()

    def _small_holder_pct(self, df: pd.DataFrame) -> float:
        """計算散戶持股比例（持股 10 張以下）"""
        if "pct" not in df.columns or "holding_range" not in df.columns:
            return 0.0
        small = df[df["holding_range"].astype(str).apply(
            lambda x: (any(k in x for k in ["1-", "1,000-5", "5,001", "以下"])
                        and "1,000以上" not in x and "1,000張以上" not in x)
        )]
        return small["pct"].sum()

    def details(self, price_df: pd.DataFrame, **kwargs) -> dict:
        tdcc_df = kwargs.get("tdcc_df")
        if tdcc_df is None or tdcc_df.empty:
            return {"signal": "無集保資料"}

        dates = sorted(tdcc_df["date"].unique())
        signals = []

        latest = tdcc_df[tdcc_df["date"] == dates[-1]]
        big_pct = self._big_holder_pct(latest)
        signals.append(f"大戶{big_pct:.1f}%")

        if len(dates) >= 2:
            prev = tdcc_df[tdcc_df["date"] == dates[-2]]
            prev_big = self._big_holder_pct(prev)
            change = big_pct - prev_big
            if change > 0.5:
                signals.append(f"增{change:+.1f}%")
            elif change < -0.5:
                signals.append(f"減{change:+.1f}%")

        return {
            "signal": " ".join(signals) if signals else "籌碼中性",
            "big_holder_pct": round(big_pct, 1),
        }
