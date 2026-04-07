"""
每日本地分析腳本
掃描 50 檔熱門科技股，儲存結果到歷史記錄
可搭配 Windows 工作排程器或手動執行
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 切換到專案根目錄（排程器不一定會設 working directory）
_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.chdir(_project_root)
sys.path.insert(0, _project_root)

# 嘗試從 .streamlit/secrets.toml 讀取 token
_secrets_path = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"
if _secrets_path.exists():
    try:
        with open(_secrets_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and val and key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass

if os.environ.get("FINMIND_TOKEN"):
    import config.settings as cfg
    cfg.FINMIND_TOKEN = os.environ["FINMIND_TOKEN"]


# 科技業產業清單
TECH_INDUSTRIES = [
    "半導體業", "光電業", "電子零組件業", "電器電纜",
    "電腦及週邊設備業", "電子通路業", "通信網路業",
    "資訊服務業", "數位雲端",
]

PHASE_B_LIMIT = 50


def main():
    import pandas as pd
    from data.fetcher import (
        fetch_stock_list, fetch_stock_prices,
        fetch_stock_prices_batch,
        fetch_institutional_batch, fetch_margin_batch,
        fetch_us_stock, fetch_night_futures,
        fetch_day_futures, fetch_tdcc_holders, fetch_taiex,
    )
    from strategies.ma_breakout import MABreakoutStrategy
    from strategies.volume_price import VolumePriceStrategy
    from strategies.relative_strength import RelativeStrengthStrategy
    from strategies.institutional_flow import InstitutionalFlowStrategy
    from strategies.enhanced_technical import EnhancedTechnicalStrategy
    from strategies.margin_analysis import MarginAnalysisStrategy
    from strategies.us_market import USMarketStrategy
    from strategies.shareholder import ShareholderStrategy
    from strategies.scorer import rank_stocks
    from config.settings import DEFAULT_WEIGHTS, CACHE_DIR
    import time

    end_date = datetime.now()
    end_date_str = end_date.strftime("%Y-%m-%d")
    start_date = (end_date - timedelta(days=100)).strftime("%Y-%m-%d")

    print(f"[{datetime.now()}] 開始每日本地分析 — {end_date_str}")

    # Step 1: 股票清單 + 科技業篩選
    print("  載入股票清單...")
    stock_list = fetch_stock_list()
    if stock_list.empty:
        print("  ERROR: 無法取得股票清單")
        return

    if "industry" in stock_list.columns:
        stock_list = stock_list[stock_list["industry"].isin(TECH_INDUSTRIES)].copy()
    print(f"  科技業共 {len(stock_list)} 檔")

    # Step 2: 成交量篩選 TOP N
    target_stocks = stock_list["stock_id"].tolist()
    if len(target_stocks) > PHASE_B_LIMIT:
        print(f"  篩選成交量前 {PHASE_B_LIMIT} 大...")
        try:
            recent_date = (end_date - timedelta(days=5)).strftime("%Y-%m-%d")
            recent_prices = fetch_stock_prices(start_date=recent_date, end_date=end_date_str)
            if not recent_prices.empty:
                latest = recent_prices.sort_values("date").groupby("stock_id").tail(1)
                latest = latest[latest["stock_id"].isin(target_stocks)]
                top_vol = latest.nlargest(PHASE_B_LIMIT, "volume")["stock_id"].tolist()
                target_stocks = top_vol
        except Exception:
            pass
        if len(target_stocks) > PHASE_B_LIMIT:
            target_stocks = target_stocks[:PHASE_B_LIMIT]

    print(f"  將分析 {len(target_stocks)} 檔")

    # Step 3: 價量資料
    print("  下載價量資料...")
    all_prices = fetch_stock_prices_batch(target_stocks, start_date, end_date_str)
    if all_prices.empty:
        print("  ERROR: 無法取得價量資料")
        return

    # Step 4: 美股/大盤
    print("  下載美股/大盤資料...")
    us_start = (end_date - timedelta(days=40)).strftime("%Y-%m-%d")
    sox_df = pd.DataFrame()
    tsm_df = pd.DataFrame()
    night_df = pd.DataFrame()
    day_futures_df = pd.DataFrame()
    tsmc_close = 0.0
    taiex_close = None

    try:
        sox_df = fetch_us_stock("^SOX", us_start, end_date_str)
    except Exception:
        pass
    try:
        tsm_df = fetch_us_stock("TSM", us_start, end_date_str)
    except Exception:
        pass
    try:
        night_df = fetch_night_futures(us_start, end_date_str)
    except Exception:
        pass
    try:
        day_futures_df = fetch_day_futures(us_start, end_date_str)
    except Exception:
        pass

    tsmc_prices = all_prices[all_prices["stock_id"] == "2330"]
    if not tsmc_prices.empty:
        tsmc_close = tsmc_prices.sort_values("date")["close"].iloc[-1]

    try:
        taiex_df = fetch_taiex(start_date, end_date_str)
        if not taiex_df.empty:
            taiex_df = taiex_df.sort_values("date")
            if "close" in taiex_df.columns:
                taiex_close = taiex_df["close"]
            elif "price" in taiex_df.columns:
                taiex_close = taiex_df["price"]
    except Exception:
        pass

    # Step 5: 法人 + 融資
    print("  下載法人/融資資料...")
    inst_start = (end_date - timedelta(days=30)).strftime("%Y-%m-%d")
    all_institutional = pd.DataFrame()
    all_margin = pd.DataFrame()
    try:
        all_institutional = fetch_institutional_batch(target_stocks, inst_start, end_date_str)
    except Exception as e:
        print(f"  WARNING: 法人資料失敗 - {e}")
    try:
        all_margin = fetch_margin_batch(target_stocks, inst_start, end_date_str)
    except Exception as e:
        print(f"  WARNING: 融資資料失敗 - {e}")

    # Step 6: 八大策略計算
    print("  計算策略分數...")
    ma_strategy = MABreakoutStrategy()
    vp_strategy = VolumePriceStrategy()
    rs_strategy = RelativeStrengthStrategy()
    inst_strategy = InstitutionalFlowStrategy()
    et_strategy = EnhancedTechnicalStrategy()
    margin_strategy = MarginAnalysisStrategy()
    us_strategy = USMarketStrategy()
    sh_strategy = ShareholderStrategy()

    valid_stocks = stock_list[
        stock_list["stock_id"].isin(target_stocks) &
        stock_list["stock_id"].isin(all_prices["stock_id"].unique())
    ]

    results = []
    total = len(valid_stocks)
    for idx, (_, stock) in enumerate(valid_stocks.iterrows()):
        sid = stock["stock_id"]
        if idx % 10 == 0:
            print(f"  分析中... ({idx}/{total}) {sid}")

        price_df = all_prices[all_prices["stock_id"] == sid].copy()
        if len(price_df) < 60:
            continue
        price_df = price_df.sort_values("date").reset_index(drop=True)

        def _safe_score(fn, **kw):
            try:
                return fn(price_df, **kw)
            except Exception:
                return 0

        def _safe_detail(fn, **kw):
            try:
                return fn(price_df, **kw)
            except Exception:
                return {"signal": ""}

        rs_kwargs = {}
        if taiex_close is not None and len(taiex_close) >= 20:
            rs_kwargs["index_close"] = taiex_close

        inst_df = all_institutional[all_institutional["stock_id"] == sid].copy() if not all_institutional.empty else pd.DataFrame()
        margin_df = all_margin[all_margin["stock_id"] == sid].copy() if not all_margin.empty else pd.DataFrame()

        try:
            tdcc_df = fetch_tdcc_holders(sid)
        except Exception:
            tdcc_df = pd.DataFrame()
        if idx % 10 == 9:
            time.sleep(0.5)

        ma_score = _safe_score(ma_strategy.score)
        vp_score = _safe_score(vp_strategy.score)
        rs_score = _safe_score(rs_strategy.score, **rs_kwargs)
        inst_score = _safe_score(inst_strategy.score, institutional_df=inst_df)
        et_score = _safe_score(et_strategy.score)
        margin_score = _safe_score(margin_strategy.score, margin_df=margin_df)
        us_score = _safe_score(us_strategy.score, sox_df=sox_df, tsm_df=tsm_df,
                               tsmc_close=tsmc_close, night_df=night_df,
                               day_futures_df=day_futures_df)
        sh_score = _safe_score(sh_strategy.score, tdcc_df=tdcc_df)

        results.append({
            "stock_id": sid,
            "name": stock.get("name", sid),
            "industry": stock.get("industry", ""),
            "close": round(price_df["close"].iloc[-1], 2),
            "volume": int(price_df["volume"].iloc[-1]),
            "ma_breakout_score": round(ma_score, 1),
            "volume_price_score": round(vp_score, 1),
            "relative_strength_score": round(rs_score, 1),
            "institutional_flow_score": round(inst_score, 1),
            "enhanced_technical_score": round(et_score, 1),
            "margin_analysis_score": round(margin_score, 1),
            "us_market_score": round(us_score, 1),
            "shareholder_score": round(sh_score, 1),
            "ma_signal": _safe_detail(ma_strategy.details).get("signal", ""),
            "vp_signal": _safe_detail(vp_strategy.details).get("signal", ""),
            "rs_signal": _safe_detail(rs_strategy.details, **rs_kwargs).get("signal", ""),
            "inst_signal": _safe_detail(inst_strategy.details, institutional_df=inst_df).get("signal", ""),
            "et_signal": _safe_detail(et_strategy.details).get("signal", ""),
            "margin_signal": _safe_detail(margin_strategy.details, margin_df=margin_df).get("signal", ""),
            "us_signal": _safe_detail(us_strategy.details, sox_df=sox_df, tsm_df=tsm_df,
                                      tsmc_close=tsmc_close, night_df=night_df,
                                      day_futures_df=day_futures_df).get("signal", ""),
            "sh_signal": _safe_detail(sh_strategy.details, tdcc_df=tdcc_df).get("signal", ""),
        })

    if not results:
        print("  ERROR: 沒有分析結果")
        return

    # Step 7: 排名
    ranked = rank_stocks(results, DEFAULT_WEIGHTS)
    print(f"  排名完成：{len(ranked)} 檔")

    # Step 8: 存歷史
    history_dir = CACHE_DIR.parent / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / f"{end_date_str}.parquet"
    ranked.to_parquet(history_file, index=False)
    print(f"  已儲存到 {history_file}")

    # Step 9: 顯示 TOP 10
    print(f"\n{'='*60}")
    print(f"  TOP 10 科技股 — {end_date_str}")
    print(f"{'='*60}")
    for _, row in ranked.head(10).iterrows():
        print(f"  #{int(row['rank']):>3}  {row['stock_id']}  {row['name']:<8}"
              f"  分數: {row['composite_score']:.1f}  等級: {row['grade']}")
    print(f"{'='*60}")

    # Step 10: 簡易歷史比對
    hist_files = sorted(history_dir.glob("*.parquet"), reverse=True)
    if len(hist_files) >= 2:
        prev_file = hist_files[1]  # 昨天
        try:
            prev = pd.read_parquet(prev_file)
            today_top = set(ranked.head(20)["stock_id"])
            prev_top = set(prev.head(20)["stock_id"])
            new_entries = today_top - prev_top
            if new_entries:
                print(f"\n  🆕 新進 TOP 20: {', '.join(new_entries)}")
            exits = prev_top - today_top
            if exits:
                print(f"  📤 退出 TOP 20: {', '.join(exits)}")
        except Exception:
            pass

    print(f"\n[{datetime.now()}] 分析完成！")


if __name__ == "__main__":
    main()
