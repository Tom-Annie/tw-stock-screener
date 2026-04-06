"""
綜合評分引擎
整合四大策略，產出最終排名
"""
import pandas as pd
import numpy as np
from typing import Dict

from config.settings import DEFAULT_WEIGHTS


def compute_composite_score(strategy_scores: Dict[str, float],
                            weights: Dict[str, float] = None) -> float:
    """
    計算加權綜合分數
    strategy_scores: {"ma_breakout": 75, "volume_price": 60, ...}
    weights: {"ma_breakout": 0.25, ...}
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0

    score = sum(
        strategy_scores.get(key, 0) * w
        for key, w in weights.items()
    )
    return round(score / total_weight, 1)


def rank_stocks(results: list, weights: Dict[str, float] = None) -> pd.DataFrame:
    """
    排名所有股票

    results: list of dict, 每個 dict 包含:
        stock_id, name, ma_breakout_score, volume_price_score,
        relative_strength_score, institutional_flow_score,
        以及各策略的 details

    回傳: 排名後的 DataFrame
    """
    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    strategy_keys = ["ma_breakout", "volume_price",
                     "relative_strength", "institutional_flow",
                     "enhanced_technical", "margin_analysis",
                     "us_market", "shareholder"]

    # 計算綜合分數
    def calc_composite(row):
        scores = {k: row.get(f"{k}_score", 0) for k in strategy_keys}
        return compute_composite_score(scores, weights)

    df["composite_score"] = df.apply(calc_composite, axis=1)

    # 等級標示
    df["grade"] = pd.cut(
        df["composite_score"],
        bins=[-1, 30, 50, 65, 80, 101],
        labels=["D", "C", "B", "A", "S"]
    )

    # 排名
    df = df.sort_values("composite_score", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)

    return df


def get_strategy_summary(df: pd.DataFrame) -> dict:
    """產生策略摘要統計"""
    if df.empty:
        return {}

    return {
        "total_stocks": len(df),
        "s_grade": len(df[df["grade"] == "S"]),
        "a_grade": len(df[df["grade"] == "A"]),
        "avg_composite": round(df["composite_score"].mean(), 1),
        "max_composite": round(df["composite_score"].max(), 1),
    }
