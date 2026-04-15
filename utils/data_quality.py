"""
資料品質自動檢測

每日掃描結束時呼叫 check_scan_quality(ranked)，回傳異常清單。
異常的定義：
- 「卡常數」：某策略分數全部一樣（通常意味著資料抓取壞掉，像之前融資融券=10 的 bug）
- 「低變異」：某策略 std 過低，但不全相同
- NaN/缺值比例過高
- 分數超出 0-100 範圍

呼叫端（daily_scan / app）可依此決定是否推 TG 警報。
"""
from typing import List
import pandas as pd
import numpy as np


# 8 個策略分數欄位
SCORE_COLS = [
    "ma_breakout_score", "volume_price_score", "relative_strength_score",
    "institutional_flow_score", "enhanced_technical_score",
    "margin_analysis_score", "us_market_score", "shareholder_score",
]


def check_scan_quality(ranked: pd.DataFrame,
                       min_rows: int = 20) -> List[str]:
    """
    檢測掃描結果的資料品質異常。

    Parameters
    ----------
    ranked : pd.DataFrame
        掃描完成的排名 DataFrame，需含 SCORE_COLS
    min_rows : int
        低於此列數直接回傳「樣本過少」

    Returns
    -------
    list[str]
        異常訊息列表（空列表代表資料健康）
    """
    issues = []

    if ranked is None or ranked.empty:
        return ["掃描結果為空 DataFrame"]

    if len(ranked) < min_rows:
        issues.append(f"樣本過少：僅 {len(ranked)} 檔（門檻 {min_rows}）")

    for col in SCORE_COLS:
        if col not in ranked.columns:
            issues.append(f"缺欄位：{col}")
            continue

        s = ranked[col].dropna()
        if s.empty:
            issues.append(f"{col}：全部 NaN（資料抓取可能失敗）")
            continue

        nan_ratio = 1 - len(s) / len(ranked)
        if nan_ratio > 0.3:
            issues.append(f"{col}：NaN 比例 {nan_ratio:.0%}")

        # 分數卡常數：nunique==1 幾乎一定是 bug（像之前 margin=10、shareholder=50）
        # 例外：shareholder 權重=0 時允許全 50（中性分），但其他策略不應該
        if s.nunique() == 1:
            const_val = s.iloc[0]
            if col == "shareholder_score" and const_val in (0, 50):
                pass  # 集保資料已知受限，中性分可接受
            else:
                issues.append(f"{col}：所有股票同分 {const_val}（策略可能壞掉）")
            continue

        # 低變異：std < 2 且範圍 < 10，意味所有股票擠在一小段
        std = s.std()
        rng = s.max() - s.min()
        if std < 2 and rng < 10 and col != "shareholder_score":
            issues.append(f"{col}：變異過低 std={std:.1f} range={rng:.1f}")

        # 超出合理範圍
        if s.min() < -0.1 or s.max() > 100.1:
            issues.append(f"{col}：分數越界 [{s.min():.1f}, {s.max():.1f}]")

    return issues


def format_issues_for_tg(issues: List[str], date_str: str = "") -> str:
    """把異常列表格式化為 TG HTML 訊息（空則回傳空字串）"""
    if not issues:
        return ""
    header = f"⚠️ <b>資料品質異常</b>"
    if date_str:
        header += f" — {date_str}"
    lines = [header, ""]
    lines.extend(f"• {msg}" for msg in issues)
    lines.append("")
    lines.append("請檢查資料源與策略計算邏輯。")
    return "\n".join(lines)
