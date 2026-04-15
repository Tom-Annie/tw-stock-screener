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


def _send_telegram_report(ranked, date_str, new_entries, exits, history_dir):
    """推播 TOP 10 文字訊息 + CSV 附件到 Telegram"""
    from utils.telegram_notify import is_available, send, send_document

    if not is_available():
        print("  跳過 TG 推播（未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID）")
        return

    # 組文字訊息
    lines = [f"📊 <b>每日科技股分析 — {date_str}</b>", ""]
    grade_emoji = {"S": "🔥", "A": "⭐", "B": "🟢", "C": "🟡", "D": "⚪"}
    for _, row in ranked.head(10).iterrows():
        g = str(row.get("grade", ""))
        emoji = grade_emoji.get(g, "")
        lines.append(
            f"#{int(row['rank']):>2}  <b>{row['stock_id']} {row['name']}</b>"
            f"  {row['composite_score']:.1f}分 {emoji}{g}"
        )
    lines.append("")

    if new_entries:
        lines.append(f"🆕 新進 TOP 20: {', '.join(new_entries)}")
    if exits:
        lines.append(f"📤 退出 TOP 20: {', '.join(exits)}")

    lines.append("")
    lines.append(f"共分析 {len(ranked)} 檔 | S:{len(ranked[ranked['grade']=='S'])} "
                 f"A:{len(ranked[ranked['grade']=='A'])} "
                 f"B:{len(ranked[ranked['grade']=='B'])}")
    lines.append("")
    lines.append('💡 <a href="https://tw-stock-screener-tom-annie.streamlit.app/">完整排名請到網頁版查看</a>')

    print("  TG 訊息已推播" if send("\n".join(lines)) else "  TG 訊息失敗")

    # 寫 CSV 並發附件
    try:
        csv_path = history_dir / f"{date_str}.csv"
        export_cols = ["rank", "stock_id", "name", "industry", "close", "volume",
                       "composite_score", "grade",
                       "ma_breakout_score", "volume_price_score",
                       "relative_strength_score", "institutional_flow_score",
                       "enhanced_technical_score", "margin_analysis_score",
                       "us_market_score", "shareholder_score"]
        avail = [c for c in export_cols if c in ranked.columns]
        ranked[avail].to_csv(csv_path, index=False, encoding="utf-8-sig")

        ok = send_document(
            str(csv_path), caption=f"📎 完整分析結果 {date_str}",
            filename=f"台股科技_{date_str}.csv",
        )
        print("  TG CSV 已傳送" if ok else "  TG CSV 失敗")
        csv_path.unlink(missing_ok=True)
    except Exception as e:
        print(f"  TG CSV 異常: {e}")


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
    from strategies.runner import score_stock
    from config.settings import DEFAULT_WEIGHTS, CACHE_DIR, MIN_PRICE_ROWS
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

    from utils.parallel_fetch import parallel_fetch
    _fetched = parallel_fetch({
        "sox":   (fetch_us_stock,      ("^SOX", us_start, end_date_str)),
        "tsm":   (fetch_us_stock,      ("TSM",  us_start, end_date_str)),
        "night": (fetch_night_futures, (us_start, end_date_str)),
        "day":   (fetch_day_futures,   (us_start, end_date_str)),
        "taiex": (fetch_taiex,         (start_date, end_date_str)),
    })
    sox_df = _fetched["sox"]
    tsm_df = _fetched["tsm"]
    night_df = _fetched["night"]
    day_futures_df = _fetched["day"]

    tsmc_prices = all_prices[all_prices["stock_id"] == "2330"]
    if not tsmc_prices.empty:
        tsmc_close = tsmc_prices.sort_values("date")["close"].iloc[-1]

    taiex_df = _fetched["taiex"]
    if not taiex_df.empty:
        taiex_df = taiex_df.sort_values("date")
        if "close" in taiex_df.columns:
            taiex_close = taiex_df["close"]
        elif "price" in taiex_df.columns:
            taiex_close = taiex_df["price"]

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
    strategies = {
        "ma_breakout": MABreakoutStrategy(),
        "volume_price": VolumePriceStrategy(),
        "relative_strength": RelativeStrengthStrategy(),
        "institutional_flow": InstitutionalFlowStrategy(),
        "enhanced_technical": EnhancedTechnicalStrategy(),
        "margin_analysis": MarginAnalysisStrategy(),
        "us_market": USMarketStrategy(),
        "shareholder": ShareholderStrategy(),
    }
    context = {
        "taiex_close": taiex_close,
        "sox_df": sox_df, "tsm_df": tsm_df,
        "night_df": night_df, "day_futures_df": day_futures_df,
        "tsmc_close": tsmc_close,
    }

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
        if len(price_df) < MIN_PRICE_ROWS:
            continue
        price_df = price_df.sort_values("date").reset_index(drop=True)

        per_stock = {}
        if not all_institutional.empty:
            per_stock["institutional_df"] = all_institutional[
                all_institutional["stock_id"] == sid
            ].copy()
        if not all_margin.empty:
            per_stock["margin_df"] = all_margin[all_margin["stock_id"] == sid].copy()

        try:
            per_stock["tdcc_df"] = fetch_tdcc_holders(sid)
        except Exception:
            per_stock["tdcc_df"] = pd.DataFrame()
        if idx % 10 == 9:
            time.sleep(0.5)

        out = score_stock(price_df, strategies, context=context,
                          per_stock=per_stock, include_details=True)

        results.append({
            "stock_id": sid,
            "name": stock.get("name", sid),
            "industry": stock.get("industry", ""),
            "close": round(price_df["close"].iloc[-1], 2),
            "volume": int(price_df["volume"].iloc[-1]) if pd.notna(price_df["volume"].iloc[-1]) else 0,
            "ma_breakout_score": round(out["ma_breakout"]["score"], 1),
            "volume_price_score": round(out["volume_price"]["score"], 1),
            "relative_strength_score": round(out["relative_strength"]["score"], 1),
            "institutional_flow_score": round(out["institutional_flow"]["score"], 1),
            "enhanced_technical_score": round(out["enhanced_technical"]["score"], 1),
            "margin_analysis_score": round(out["margin_analysis"]["score"], 1),
            "us_market_score": round(out["us_market"]["score"], 1),
            "shareholder_score": round(out["shareholder"]["score"], 1),
            "ma_signal": out["ma_breakout"]["detail"].get("signal", ""),
            "vp_signal": out["volume_price"]["detail"].get("signal", ""),
            "rs_signal": out["relative_strength"]["detail"].get("signal", ""),
            "inst_signal": out["institutional_flow"]["detail"].get("signal", ""),
            "et_signal": out["enhanced_technical"]["detail"].get("signal", ""),
            "margin_signal": out["margin_analysis"]["detail"].get("signal", ""),
            "us_signal": out["us_market"]["detail"].get("signal", ""),
            "sh_signal": out["shareholder"]["detail"].get("signal", ""),
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

    # 資料品質檢測（卡常數/NaN/低變異 → 印 log + TG 警報）
    try:
        from utils.data_quality import check_scan_quality, format_issues_for_tg
        from utils.telegram_notify import send as _tg_send
        _qc_issues = check_scan_quality(ranked)
        if _qc_issues:
            print(f"  ⚠️ 資料品質異常 {len(_qc_issues)} 項:")
            for msg in _qc_issues:
                print(f"    - {msg}")
            _tg_msg = format_issues_for_tg(_qc_issues, end_date_str)
            if _tg_msg:
                _tg_send(_tg_msg)
    except Exception as e:
        print(f"  資料品質檢測失敗: {e}")

    # Step 9: 顯示 TOP 10
    print(f"\n{'='*60}")
    print(f"  TOP 10 科技股 — {end_date_str}")
    print(f"{'='*60}")
    for _, row in ranked.head(10).iterrows():
        print(f"  #{int(row['rank']):>3}  {row['stock_id']}  {row['name']:<8}"
              f"  分數: {row['composite_score']:.1f}  等級: {row['grade']}")
    print(f"{'='*60}")

    # Step 10: 簡易歷史比對
    new_entries = set()
    exits = set()
    hist_files = sorted(history_dir.glob("*.parquet"), reverse=True)
    if len(hist_files) >= 2:
        prev_file = hist_files[1]  # 昨天
        try:
            prev = pd.read_parquet(prev_file)
            today_top = set(ranked.head(20)["stock_id"])
            prev_top = set(prev.head(20)["stock_id"])
            new_entries = today_top - prev_top
            exits = prev_top - today_top
            if new_entries:
                print(f"\n  🆕 新進 TOP 20: {', '.join(new_entries)}")
            if exits:
                print(f"  📤 退出 TOP 20: {', '.join(exits)}")
        except Exception:
            pass

    # Step 11: TG 推播 + CSV 附件
    _send_telegram_report(ranked, end_date_str, new_entries, exits, history_dir)

    print(f"\n[{datetime.now()}] 分析完成！")


if __name__ == "__main__":
    main()
