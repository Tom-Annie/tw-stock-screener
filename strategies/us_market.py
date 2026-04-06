"""
策略七：美股與夜盤連動
費半趨勢 + 台積電ADR折溢價 + 夜盤價差
用於判斷隔日台股整體氛圍，作為個股選股的加減分
"""
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy


class USMarketStrategy(BaseStrategy):
    name = "美股連動"
    description = "費半趨勢、台積電ADR折溢價、夜盤價差綜合判斷"

    # 匯率快取 (同一次分析只查一次)
    _cached_usd_twd = None

    @classmethod
    def _get_usd_twd(cls) -> float:
        """取得即時 USD/TWD 匯率，失敗時用 31.5"""
        if cls._cached_usd_twd is not None:
            return cls._cached_usd_twd
        try:
            import yfinance as yf
            data = yf.download("TWD=X", period="5d", progress=False)
            if not data.empty:
                # 處理 MultiIndex columns
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = [c[-1] if isinstance(c, tuple) else c
                                    for c in data.columns]
                # 嘗試不同的欄位名
                close_col = None
                for c in data.columns:
                    if str(c).lower() in ("close", "adj close", "adjclose"):
                        close_col = c
                        break
                if close_col is not None:
                    rate = float(data[close_col].dropna().iloc[-1])
                    if 25 < rate < 40:
                        cls._cached_usd_twd = rate
                        return rate
        except Exception:
            pass
        cls._cached_usd_twd = 31.5
        return 31.5

    def score(self, price_df: pd.DataFrame, **kwargs) -> float:
        """
        kwargs:
            sox_df: pd.DataFrame - 費半指數日K (date, close)
            tsm_df: pd.DataFrame - 台積電ADR日K (date, close)
            tsmc_close: float - 台積電台股最新收盤價
            night_df: pd.DataFrame - 夜盤資料 (date, close)
            day_futures_df: pd.DataFrame - 日盤資料 (date, close)
        """
        sox_df = kwargs.get("sox_df")
        tsm_df = kwargs.get("tsm_df")
        tsmc_close = kwargs.get("tsmc_close")
        night_df = kwargs.get("night_df")
        day_futures_df = kwargs.get("day_futures_df")

        score = 0.0

        # 1. 費半指數趨勢 (max 35)
        score += self._sox_score(sox_df)

        # 2. 台積電 ADR 折溢價 (max 35)
        score += self._tsm_premium_score(tsm_df, tsmc_close)

        # 3. 夜盤價差 (max 30)
        score += self._night_gap_score(night_df, day_futures_df)

        return self._clamp(score)

    def _sox_score(self, sox_df: pd.DataFrame) -> float:
        """費半指數趨勢評分"""
        if sox_df is None or sox_df.empty or len(sox_df) < 10:
            return 0.0

        sox_df = sox_df.sort_values("date").tail(30)
        close = sox_df["close"]
        score = 0.0

        # 5日漲跌幅
        if len(close) >= 5:
            ret_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100
            if ret_5d > 3:
                score += 15
            elif ret_5d > 1:
                score += 10
            elif ret_5d > 0:
                score += 5
            elif ret_5d < -3:
                score -= 5

        # 前一日漲跌
        if len(close) >= 2:
            ret_1d = (close.iloc[-1] / close.iloc[-2] - 1) * 100
            if ret_1d > 1:
                score += 10
            elif ret_1d > 0:
                score += 5
            elif ret_1d < -2:
                score -= 5

        # 站上10日均線
        if len(close) >= 10:
            ma10 = close.rolling(10).mean().iloc[-1]
            if pd.notna(ma10) and close.iloc[-1] > ma10:
                score += 10

        return max(score, 0)

    def _tsm_premium_score(self, tsm_df: pd.DataFrame,
                           tsmc_close: float) -> float:
        """台積電ADR折溢價評分"""
        if tsm_df is None or tsm_df.empty or not tsmc_close:
            return 0.0

        tsm_df = tsm_df.sort_values("date")
        adr_close = tsm_df["close"].iloc[-1]
        if pd.isna(adr_close) or adr_close <= 0:
            return 0.0

        # ADR 換算台幣 (1 ADR = 5 股台積電)
        usd_twd = self._get_usd_twd()
        adr_tw_price = adr_close * usd_twd / 5

        # 溢價率 = (ADR換算價 - 台股價) / 台股價 * 100
        premium_pct = (adr_tw_price - tsmc_close) / tsmc_close * 100

        score = 0.0

        # ADR 溢價 = 國際投資人看好 = 隔天台股偏多
        if premium_pct > 2:
            score += 25
        elif premium_pct > 1:
            score += 20
        elif premium_pct > 0.3:
            score += 15
        elif premium_pct > 0:
            score += 10
        # ADR 折價 = 國際投資人偏空
        elif premium_pct < -2:
            score -= 5
        elif premium_pct < -1:
            score += 0

        # ADR 自身趨勢
        if len(tsm_df) >= 5:
            ret = (tsm_df["close"].iloc[-1] / tsm_df["close"].iloc[-5] - 1) * 100
            if ret > 2:
                score += 10
            elif ret > 0:
                score += 5

        return max(score, 0)

    def _night_gap_score(self, night_df: pd.DataFrame,
                         day_df: pd.DataFrame) -> float:
        """夜盤價差評分"""
        if (night_df is None or night_df.empty or
                day_df is None or day_df.empty):
            return 0.0

        night_df = night_df.sort_values("date")
        day_df = day_df.sort_values("date")

        # 取最近一天日盤收盤和夜盤收盤
        day_close = day_df["close"].iloc[-1]
        night_close = night_df["close"].iloc[-1]

        if pd.isna(day_close) or pd.isna(night_close) or day_close <= 0:
            return 0.0

        # 夜盤漲跌幅 = (夜盤收盤 - 日盤收盤) / 日盤收盤
        gap_pct = (night_close - day_close) / day_close * 100

        score = 0.0

        # 夜盤上漲 = 隔天偏多
        if gap_pct > 1:
            score += 20
        elif gap_pct > 0.5:
            score += 15
        elif gap_pct > 0:
            score += 10
        # 夜盤下跌
        elif gap_pct < -1:
            score -= 5
        elif gap_pct < -0.5:
            score += 0

        # 夜盤連續方向 (最近3天)
        if len(night_df) >= 3 and len(day_df) >= 3:
            recent_gaps = []
            for i in range(-3, 0):
                if abs(i) <= len(night_df) and abs(i) <= len(day_df):
                    nc = night_df["close"].iloc[i]
                    dc = day_df["close"].iloc[i]
                    if pd.notna(nc) and pd.notna(dc) and dc > 0:
                        recent_gaps.append((nc - dc) / dc * 100)

            if recent_gaps and all(g > 0 for g in recent_gaps):
                score += 10  # 連續3天夜盤上漲
            elif recent_gaps and all(g < 0 for g in recent_gaps):
                score -= 5  # 連續3天夜盤下跌

        return max(score, 0)

    def details(self, price_df: pd.DataFrame, **kwargs) -> dict:
        sox_df = kwargs.get("sox_df")
        tsm_df = kwargs.get("tsm_df")
        tsmc_close = kwargs.get("tsmc_close")
        night_df = kwargs.get("night_df")
        day_futures_df = kwargs.get("day_futures_df")

        signals = []

        # 費半
        if sox_df is not None and not sox_df.empty and len(sox_df) >= 2:
            sox_df = sox_df.sort_values("date")
            ret = (sox_df["close"].iloc[-1] / sox_df["close"].iloc[-2] - 1) * 100
            if ret > 0:
                signals.append(f"費半+{ret:.1f}%")
            else:
                signals.append(f"費半{ret:.1f}%")

        # ADR 折溢價
        if (tsm_df is not None and not tsm_df.empty and tsmc_close):
            adr_close = tsm_df.sort_values("date")["close"].iloc[-1]
            if pd.notna(adr_close) and adr_close > 0:
                adr_tw = adr_close * self._get_usd_twd() / 5
                prem = (adr_tw - tsmc_close) / tsmc_close * 100
                if prem > 0:
                    signals.append(f"ADR溢價{prem:.1f}%")
                else:
                    signals.append(f"ADR折價{abs(prem):.1f}%")

        # 夜盤
        if (night_df is not None and not night_df.empty and
                day_futures_df is not None and not day_futures_df.empty):
            nc = night_df.sort_values("date")["close"].iloc[-1]
            dc = day_futures_df.sort_values("date")["close"].iloc[-1]
            if pd.notna(nc) and pd.notna(dc) and dc > 0:
                gap = (nc - dc) / dc * 100
                if gap > 0:
                    signals.append(f"夜盤+{gap:.2f}%")
                else:
                    signals.append(f"夜盤{gap:.2f}%")

        return {
            "signal": " ".join(signals) if signals else "無美股/夜盤資料"
        }
