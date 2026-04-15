"""
策略執行器 — 集中化「對單一股票跑 8 策略」的 kwargs 組裝與例外處理

呼叫端（app.py / scripts/daily_scan.py / scripts/daily_local.py）負責：
- 批次下載 price / institutional / margin / TDCC / 美股 / 大盤
- 進度條、log、結果 DataFrame 組裝

呼叫端不需自己重複 8 支策略的 kwargs 映射。
"""
from typing import Dict, Any, Optional
import pandas as pd


# 每支策略需要哪些 per-stock 或 context 欄位
_PER_STOCK_KW = {
    "institutional_flow": "institutional_df",
    "margin_analysis": "margin_df",
    "shareholder": "tdcc_df",
}


def _build_kwargs(key: str, context: dict, per_stock: dict) -> dict:
    """組出單一策略 score/details 所需的 kwargs"""
    kwargs = {}

    # per-stock 資料（法人/融資/集保）
    kw_name = _PER_STOCK_KW.get(key)
    if kw_name and per_stock.get(kw_name) is not None:
        df = per_stock[kw_name]
        if isinstance(df, pd.DataFrame) and not df.empty:
            kwargs[kw_name] = df

    # 大盤 index_close（relative_strength 專用）
    if key == "relative_strength":
        taiex_close = context.get("taiex_close")
        if taiex_close is not None and len(taiex_close) >= 20:
            kwargs["index_close"] = taiex_close

    # 美股 / 期貨 / TSMC（us_market 專用）
    if key == "us_market":
        kwargs.update(
            sox_df=context.get("sox_df", pd.DataFrame()),
            tsm_df=context.get("tsm_df", pd.DataFrame()),
            tsmc_close=context.get("tsmc_close", 0.0),
            night_df=context.get("night_df", pd.DataFrame()),
            day_futures_df=context.get("day_futures_df", pd.DataFrame()),
        )

    return kwargs


def score_stock(
    price_df: pd.DataFrame,
    strategies: Dict[str, Any],
    context: Optional[dict] = None,
    per_stock: Optional[dict] = None,
    include_details: bool = False,
) -> Dict[str, dict]:
    """
    對單一股票跑所有策略，回傳 {key: {"score": float, "detail": dict, "error": str|None}}

    strategies: {"ma_breakout": MABreakoutStrategy(), ...}
    context:    {"taiex_close": ..., "sox_df": ..., "tsm_df": ..., "night_df": ..., "day_futures_df": ..., "tsmc_close": ...}
    per_stock:  {"institutional_df": df, "margin_df": df, "tdcc_df": df}
    """
    context = context or {}
    per_stock = per_stock or {}
    out = {}
    for key, strat in strategies.items():
        kwargs = _build_kwargs(key, context, per_stock)
        try:
            score = strat.score(price_df, **kwargs)
            detail = strat.details(price_df, **kwargs) if include_details else None
            out[key] = {"score": score, "detail": detail, "error": None}
        except Exception as e:
            out[key] = {
                "score": 0,
                "detail": {"signal": "計算錯誤"} if include_details else None,
                "error": f"{type(e).__name__}: {e}",
            }
    return out
