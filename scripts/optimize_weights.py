"""
權重最佳化：隨機搜尋 + 未來 N 日報酬

原理：
- 載入 history/*.parquet（每日掃描結果，含 8 策略分數 + close）
- 對每份歷史，以候選權重重新計算綜合分 → 取 TOP-N 股
- 用未來 N 日實際收盤計算報酬率（需調 data/prices）
- 用平均 forward return 當 fitness，找最佳權重組合

用法:
    python3 scripts/optimize_weights.py --trials 2000 --top 10 --forward 5

需要至少 20 個歷史檔才會有統計意義（少於此會印警告但仍跑完）。
"""
import argparse
import os
import sys
from pathlib import Path
from datetime import timedelta

# 確保能 import 專案模組
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

import numpy as np
import pandas as pd


STRATEGY_KEYS = [
    "ma_breakout", "volume_price", "relative_strength", "institutional_flow",
    "enhanced_technical", "margin_analysis", "us_market", "shareholder",
]
SCORE_COLS = [f"{k}_score" for k in STRATEGY_KEYS]


def _random_weights(rng: np.random.Generator) -> dict:
    """Dirichlet 隨機採樣 — 保證和=1、非負，避免手工做正規化"""
    w = rng.dirichlet(np.ones(len(STRATEGY_KEYS)))
    return dict(zip(STRATEGY_KEYS, w.tolist()))


def _composite(df: pd.DataFrame, weights: dict) -> pd.Series:
    """依權重計算綜合分數（向量化）"""
    total = sum(weights.values())
    if total == 0:
        return pd.Series(0, index=df.index)
    s = sum(df[f"{k}_score"].fillna(0) * w for k, w in weights.items())
    return s / total


def _load_history(history_dir: Path) -> list:
    """回傳 [(date_str, DataFrame), ...] 依日期排序"""
    files = sorted(history_dir.glob("*.parquet"))
    out = []
    for f in files:
        date_str = f.stem  # YYYY-MM-DD
        try:
            df = pd.read_parquet(f)
        except Exception as e:
            print(f"  跳過 {f.name}: {e}")
            continue
        if not all(c in df.columns for c in SCORE_COLS + ["stock_id", "close"]):
            print(f"  {f.name} 欄位不完整，跳過")
            continue
        out.append((date_str, df))
    return out


def _fetch_forward_return(stock_ids: list, base_date: str,
                          forward_days: int) -> dict:
    """取得從 base_date 起 forward_days 個交易日後的報酬率 {sid: pct}"""
    from data.fetcher import fetch_stock_prices_batch
    base = pd.Timestamp(base_date)
    end = (base + timedelta(days=forward_days * 2 + 10)).strftime("%Y-%m-%d")
    try:
        prices = fetch_stock_prices_batch(stock_ids, base_date, end)
    except Exception as e:
        print(f"  forward return 抓取失敗: {e}")
        return {}
    if prices.empty:
        return {}

    prices = prices.sort_values(["stock_id", "date"])
    returns = {}
    for sid, g in prices.groupby("stock_id"):
        closes = g["close"].reset_index(drop=True)
        if len(closes) < forward_days + 1:
            continue
        base_close = closes.iloc[0]
        fwd_close = closes.iloc[forward_days]
        if pd.notna(base_close) and base_close > 0:
            returns[sid] = float(fwd_close / base_close - 1)
    return returns


def evaluate_weights(weights: dict, snapshots: list,
                     forward_returns_cache: dict, top_n: int) -> float:
    """
    對所有歷史日計算「以此權重排名 → TOP-N 平均 forward return」
    snapshots: [(date_str, df), ...]
    forward_returns_cache: {date_str: {sid: pct_return}}
    """
    perf = []
    for date_str, df in snapshots:
        returns = forward_returns_cache.get(date_str, {})
        if not returns:
            continue
        df = df.copy()
        df["_composite"] = _composite(df, weights)
        top = df.nlargest(top_n, "_composite")
        top_returns = [returns[sid] for sid in top["stock_id"] if sid in returns]
        if top_returns:
            perf.append(np.mean(top_returns))
    return float(np.mean(perf)) if perf else 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--top", type=int, default=10, help="TOP-N 數量")
    parser.add_argument("--forward", type=int, default=5, help="未來幾個交易日")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    from config.settings import CACHE_DIR
    history_dir = CACHE_DIR.parent / "history"

    snapshots = _load_history(history_dir)
    if not snapshots:
        print(f"❌ {history_dir} 沒有可用的歷史檔")
        return
    print(f"載入 {len(snapshots)} 個歷史快照：{snapshots[0][0]} ~ {snapshots[-1][0]}")
    if len(snapshots) < 20:
        print(f"⚠️ 只有 {len(snapshots)} 個歷史檔（建議至少 20），結果統計意義有限")

    # 每日的 forward return 要到未來才有，最末一天不能算
    usable = snapshots[:-1] if len(snapshots) > 1 else snapshots

    # 先預抓所有日期的 forward returns（全股票，一次性）
    print(f"預抓 forward returns（forward={args.forward} 日）...")
    fr_cache = {}
    for date_str, df in usable:
        all_ids = df["stock_id"].astype(str).tolist()
        fr_cache[date_str] = _fetch_forward_return(
            all_ids, date_str, args.forward
        )
        print(f"  {date_str}: {len(fr_cache[date_str])} 檔有 forward return")

    # 隨機搜尋
    rng = np.random.default_rng(args.seed)
    best = {"score": -1e9, "weights": None}
    from config.settings import DEFAULT_WEIGHTS

    baseline = evaluate_weights(DEFAULT_WEIGHTS, usable, fr_cache, args.top)
    print(f"\n基準（DEFAULT_WEIGHTS）TOP-{args.top} 平均 {args.forward}日報酬: "
          f"{baseline*100:+.2f}%")

    print(f"\n開始隨機搜尋 {args.trials} 組權重...")
    for i in range(args.trials):
        w = _random_weights(rng)
        score = evaluate_weights(w, usable, fr_cache, args.top)
        if score > best["score"]:
            best["score"] = score
            best["weights"] = w
            if (i + 1) % 100 == 0 or i < 5:
                print(f"  trial {i+1:5d}: {score*100:+.2f}% (新最佳)")

    print(f"\n{'='*60}")
    print(f"最佳權重（TOP-{args.top} 平均 {args.forward}日報酬 "
          f"{best['score']*100:+.2f}%）:")
    print(f"{'='*60}")
    for k in STRATEGY_KEYS:
        w = best["weights"][k]
        base_w = DEFAULT_WEIGHTS.get(k, 0)
        delta = w - base_w
        print(f"  {k:<22} {w:.3f}  (baseline {base_w:.2f}, Δ {delta:+.3f})")

    print(f"\n相較基準改善: {(best['score']-baseline)*100:+.2f} 百分點")


if __name__ == "__main__":
    main()
