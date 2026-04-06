"""
策略五：進階技術綜合
結合 KD、布林通道、OBV、MACD、乖離率的多重確認策略
只有多個指標同時給出訊號時才給高分，降低假訊號
"""
import pandas as pd
import numpy as np
from strategies.base import BaseStrategy
from utils.indicators import (
    stochastic_kd, bollinger_bands, obv, obv_trend,
    bias, macd, rsi, williams_r
)


class EnhancedTechnicalStrategy(BaseStrategy):
    name = "技術綜合"
    description = "KD/布林/OBV/MACD/乖離率 多重交叉驗證"

    def _analyze(self, price_df: pd.DataFrame):
        """一次計算所有技術指標"""
        close = price_df["close"]
        high = price_df["high"]
        low = price_df["low"]
        volume = price_df["volume"]

        k, d = stochastic_kd(high, low, close)
        _, _, _, pct_b = bollinger_bands(close)
        obv_sl = obv_trend(close, volume, 20)
        dif, dem, hist = macd(close)
        bias_20 = bias(close, 20)

        return {
            "k": k, "d": d,
            "pct_b": pct_b,
            "obv_slope": obv_sl,
            "dif": dif, "dem": dem,
            "bias_20": bias_20,
            "volume": volume,
        }

    def score(self, price_df: pd.DataFrame, **kwargs) -> float:
        if price_df.empty or len(price_df) < 30:
            return 0.0

        ind = self._analyze(price_df)
        score = 0.0

        # 1. KD 指標 (max 20) — 低檔交叉比高檔交叉更有價值
        k, d = ind["k"], ind["d"]
        if pd.notna(k.iloc[-1]) and pd.notna(d.iloc[-1]):
            k_val, d_val = k.iloc[-1], d.iloc[-1]
            is_golden = (len(k) >= 2 and pd.notna(k.iloc[-2]) and pd.notna(d.iloc[-2])
                         and k.iloc[-2] <= d.iloc[-2] and k_val > d_val)
            if is_golden:
                # 低檔黃金交叉（K < 40）更有意義
                if k_val < 40:
                    score += 20
                elif k_val < 60:
                    score += 15
                else:
                    score += 8  # 高檔交叉意義較低
            elif k_val > d_val:
                score += 10

        # 2. 布林通道 (max 20)
        pct_b = ind["pct_b"]
        if pd.notna(pct_b.iloc[-1]):
            b_val = pct_b.iloc[-1]
            if 0.5 <= b_val <= 0.9:
                score += 15
            elif 0.3 <= b_val < 0.5:
                score += 8
            elif 0.9 < b_val <= 1.1:
                score += 12  # 觸及上軌偏強
            if (len(pct_b) >= 3 and pd.notna(pct_b.iloc[-3])
                    and pct_b.iloc[-3] < 0.2 and b_val > 0.3):
                score += 5  # 從下軌回升

        # 3. OBV 能量潮 (max 20) — 用斜率正負及加速度判斷
        obv_slope = ind["obv_slope"]
        if obv_slope > 0:
            score += 12
            # 比較近期 OBV 斜率加速（用絕對斜率值與股價相比）
            close_val = price_df["close"].iloc[-1]
            if close_val > 0 and obv_slope > close_val * 100:
                score += 8  # OBV 斜率顯著（每天淨流入超過 100 手×股價）

        # 4. MACD (max 20) — 加入柱狀體擴張判斷
        dif, dem = ind["dif"], ind["dem"]
        if pd.notna(dif.iloc[-1]) and pd.notna(dem.iloc[-1]):
            hist_now = dif.iloc[-1] - dem.iloc[-1]
            if dif.iloc[-1] > dem.iloc[-1]:
                score += 10
            is_macd_golden = (len(dif) >= 2 and pd.notna(dif.iloc[-2]) and pd.notna(dem.iloc[-2])
                              and dif.iloc[-2] <= dem.iloc[-2] and dif.iloc[-1] > dem.iloc[-1])
            if is_macd_golden:
                score += 10
            elif len(dif) >= 2:
                hist_prev = dif.iloc[-2] - dem.iloc[-2]
                if pd.notna(hist_prev) and hist_now > hist_prev > 0:
                    score += 5  # 柱狀體擴張

        # 5. 乖離率保護 (max 20, 也可能扣分)
        bias_20 = ind["bias_20"]
        if pd.notna(bias_20.iloc[-1]):
            b = bias_20.iloc[-1]
            if 1 <= b <= 5:
                score += 15
            elif 0 < b < 1:
                score += 10
            elif 5 < b <= 10:
                score += 5
            elif b > 10:
                score -= 10  # 正乖離過大，追高風險
            elif -5 <= b < 0:
                score += 5   # 小幅負乖離，可能反彈
            elif b < -5:
                score += 0   # 大幅負乖離，趨勢偏弱不加分

        return self._clamp(score)

    def details(self, price_df: pd.DataFrame, **kwargs) -> dict:
        if price_df.empty or len(price_df) < 30:
            return {"signal": "資料不足"}

        ind = self._analyze(price_df)
        signals = []

        k, d = ind["k"], ind["d"]
        if pd.notna(k.iloc[-1]):
            k_val = round(k.iloc[-1], 1)
            if (len(k) >= 2 and pd.notna(k.iloc[-2]) and pd.notna(d.iloc[-2])
                    and k.iloc[-2] <= d.iloc[-2] and k.iloc[-1] > d.iloc[-1]):
                signals.append(f"KD黃金交叉({k_val})")
            elif k.iloc[-1] > d.iloc[-1]:
                signals.append(f"KD多方({k_val})")

        dif, dem = ind["dif"], ind["dem"]
        if pd.notna(dif.iloc[-1]) and pd.notna(dem.iloc[-1]):
            if (len(dif) >= 2 and pd.notna(dif.iloc[-2]) and pd.notna(dem.iloc[-2])
                    and dif.iloc[-2] <= dem.iloc[-2] and dif.iloc[-1] > dem.iloc[-1]):
                signals.append("MACD黃金交叉")
            elif dif.iloc[-1] > dem.iloc[-1]:
                signals.append("MACD多方")

        pct_b = ind["pct_b"]
        if pd.notna(pct_b.iloc[-1]):
            if pct_b.iloc[-1] > 0.9:
                signals.append("突破布林上軌")
            elif pct_b.iloc[-1] > 0.5:
                signals.append("布林強勢區")

        if ind["obv_slope"] > 0:
            signals.append("OBV流入")

        bias_20 = ind["bias_20"]
        if pd.notna(bias_20.iloc[-1]):
            b = round(bias_20.iloc[-1], 1)
            if b > 10:
                signals.append(f"乖離過大({b}%)")

        return {
            "signal": " ".join(signals) if signals else "無明顯訊號",
            "kd_k": round(k.iloc[-1], 1) if pd.notna(k.iloc[-1]) else 0,
            "bias_20": round(bias_20.iloc[-1], 1) if pd.notna(bias_20.iloc[-1]) else 0,
        }
