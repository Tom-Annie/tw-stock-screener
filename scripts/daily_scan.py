"""
每日自動掃描 + Telegram 推播
由 GitHub Actions 排程執行
"""
import os
import sys
from datetime import datetime, timedelta

# 加入專案根目錄到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 設定環境變數給 config.settings 讀取
os.environ["FINMIND_TOKEN"] = os.environ.get("FINMIND_TOKEN", "")

from utils.telegram_notify import send as _tg_send


def send_telegram(message: str) -> bool:
    """包一層好記 log（邏輯委派給 utils.telegram_notify.send）"""
    ok = _tg_send(message)
    print("Telegram sent OK" if ok else "Telegram send failed")
    return ok


def main():
    # step 用於追蹤目前執行到哪個步驟，失敗時回報給 Telegram
    step = "初始化"
    try:
        import pandas as pd
        from data.fetcher import (fetch_stock_list, fetch_stock_prices,
                                  fetch_stock_prices_batch,
                                  fetch_institutional_batch,
                                  fetch_margin_batch,
                                  fetch_us_stock, fetch_night_futures,
                                  fetch_day_futures, fetch_taiex)
        from strategies.ma_breakout import MABreakoutStrategy
        from strategies.volume_price import VolumePriceStrategy
        from strategies.relative_strength import RelativeStrengthStrategy
        from strategies.institutional_flow import InstitutionalFlowStrategy
        from strategies.enhanced_technical import EnhancedTechnicalStrategy
        from strategies.margin_analysis import MarginAnalysisStrategy
        from strategies.us_market import USMarketStrategy
        from strategies.shareholder import ShareholderStrategy
        from strategies.scorer import compute_composite_score
        from strategies.runner import score_stock
        from config.settings import DEFAULT_WEIGHTS, MIN_PRICE_ROWS
        import time

        # --- Daily scan weights ---
        # Override weights for strategies where we skip data fetching to save
        # API quota.  Setting weight=0 means these strategies don't distort
        # the composite score.  The denominator in compute_composite_score
        # uses sum(weights.values()), so zero-weight strategies are excluded
        # automatically.
        daily_weights = {
            **DEFAULT_WEIGHTS,
            "margin_analysis": 0,   # 融資融券 skipped to save API quota
            "shareholder": 0,       # TDCC 集保資料 too expensive for batch fetch
        }

        end_date = datetime.now()
        end_date_str = end_date.strftime("%Y-%m-%d")
        start_date = (end_date - timedelta(days=100)).strftime("%Y-%m-%d")

        print(f"[{datetime.now()}] 開始每日掃描...")

        # 1. 取得股票清單
        step = "取得股票清單"
        stock_list = fetch_stock_list()
        if stock_list.empty:
            send_telegram("⚠️ 每日掃描失敗：無法取得股票清單")
            return

        all_ids = stock_list["stock_id"].tolist()

        # 2. 篩選成交量前 200 大
        step = "篩選成交量前 200 大"
        print("篩選成交量前 200 大...")
        target_stocks = all_ids[:200]  # fallback
        try:
            recent_date = (end_date - timedelta(days=5)).strftime("%Y-%m-%d")
            recent_prices = fetch_stock_prices(start_date=recent_date, end_date=end_date_str)
            if not recent_prices.empty:
                latest = recent_prices.sort_values("date").groupby("stock_id").tail(1)
                latest = latest[latest["stock_id"].isin(all_ids)]
                top_vol = latest.nlargest(200, "volume")["stock_id"].tolist()
                target_stocks = top_vol
        except Exception as e:
            print(f"成交量篩選失敗: {e}")

        if len(target_stocks) > 200:
            target_stocks = target_stocks[:200]

        print(f"將分析 {len(target_stocks)} 檔")

        # 3. 下載價量資料（批次，yfinance 優先，自帶快取與 rate limit 管理）
        step = "下載價量資料"
        print("下載價量資料...")
        all_prices = fetch_stock_prices_batch(target_stocks, start_date, end_date_str)
        if all_prices.empty:
            send_telegram("⚠️ 每日掃描失敗：無法取得價量資料")
            return
        print(f"已下載 {all_prices['stock_id'].nunique()} 檔價量資料")

        # 4. 下載法人資料（批次）
        step = "下載法人資料"
        inst_start = (end_date - timedelta(days=30)).strftime("%Y-%m-%d")
        fetched_ids = all_prices["stock_id"].unique().tolist()

        all_institutional = pd.DataFrame()
        print("下載法人資料...")
        try:
            all_institutional = fetch_institutional_batch(
                fetched_ids, inst_start, end_date_str
            )
            print(f"法人資料 {all_institutional['stock_id'].nunique() if not all_institutional.empty else 0} 檔")
        except Exception as e:
            print(f"法人資料失敗: {e}")

        # 融資融券: 跳過以節省 API quota，weight 已設為 0
        all_margin = pd.DataFrame()
        print("跳過融資融券（節省 API quota，weight=0）")

        # TDCC 集保資料: 跳過以節省 API quota，weight 已設為 0
        all_tdcc = pd.DataFrame()
        print("跳過 TDCC 集保資料（節省 API quota，weight=0）")

        # 5. 美股/夜盤/大盤
        step = "下載美股/夜盤/大盤"
        us_start = (end_date - timedelta(days=40)).strftime("%Y-%m-%d")
        sox_df = tsm_df = night_df = day_futures_df = pd.DataFrame()
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

        if not all_prices.empty:
            tsmc = all_prices[all_prices["stock_id"] == "2330"]
            if not tsmc.empty:
                tsmc_close = tsmc.sort_values("date")["close"].iloc[-1]

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

        # 6. 計算策略分數（全部 8 個策略）
        step = "計算策略分數"
        print("計算策略分數...")
        strategies = {
            "ma_breakout": MABreakoutStrategy(),
            "volume_price": VolumePriceStrategy(),
            "relative_strength": RelativeStrengthStrategy(),
            "institutional_flow": InstitutionalFlowStrategy(),
            "enhanced_technical": EnhancedTechnicalStrategy(),
            "margin_analysis": MarginAnalysisStrategy(),
            "us_market": USMarketStrategy(),
            "shareholder": ShareholderStrategy(),          # 大戶籌碼
        }

        valid_stocks = stock_list[
            stock_list["stock_id"].isin(target_stocks) &
            stock_list["stock_id"].isin(all_prices["stock_id"].unique())
        ]

        context = {
            "taiex_close": taiex_close,
            "sox_df": sox_df, "tsm_df": tsm_df,
            "night_df": night_df, "day_futures_df": day_futures_df,
            "tsmc_close": tsmc_close,
        }

        results = []
        for idx, (_, stock) in enumerate(valid_stocks.iterrows()):
            sid = stock["stock_id"]
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
            if not all_tdcc.empty:
                per_stock["tdcc_df"] = all_tdcc[all_tdcc["stock_id"] == sid].copy()

            out = score_stock(price_df, strategies, context=context, per_stock=per_stock)
            scores = {k: v["score"] for k, v in out.items()}

            # Use daily_weights (margin_analysis=0, shareholder=0) so skipped
            # strategies don't distort the composite score
            composite = compute_composite_score(scores, weights=daily_weights)
            name = stock.get("name", sid)
            industry = stock.get("industry", "")
            close = price_df["close"].iloc[-1]

            results.append({
                "stock_id": sid,
                "name": name,
                "industry": industry,
                "close": round(close, 2),
                "composite": round(composite, 1),
                "scores": scores,
            })

        if not results:
            send_telegram("⚠️ 每日掃描完成但無有效結果")
            return

        # 7. 排名
        step = "排名與統計"
        results.sort(key=lambda x: x["composite"], reverse=True)

        # 8. 統計
        total = len(results)
        s_count = sum(1 for r in results if r["composite"] > 80)
        a_count = sum(1 for r in results if 65 < r["composite"] <= 80)
        avg_score = sum(r["composite"] for r in results) / total
        hot_pct = (s_count + a_count) / total * 100

        if hot_pct >= 40:
            temp = "🔴 過熱"
        elif hot_pct >= 25:
            temp = "🟠 偏熱"
        elif hot_pct >= 15:
            temp = "🟢 溫和"
        elif hot_pct >= 5:
            temp = "🔵 偏冷"
        else:
            temp = "⚪ 極冷"

        # 9. 組合訊息
        step = "組合訊息與推送"
        lines = [
            f"📊 <b>每日市場掃描</b>",
            f"🕐 {end_date_str}",
            f"🌡️ 市場溫度：<b>{temp}</b>（S+A 佔 {hot_pct:.0f}%）",
            f"📈 分析 {total} 檔 | 平均 {avg_score:.0f} 分",
            f"⭐ S級 {s_count} 檔 | A級 {a_count} 檔",
            "",
        ]

        # TOP 10
        top10 = results[:10]
        lines.append("<b>🏆 TOP 10：</b>")
        for i, r in enumerate(top10, 1):
            grade = "S" if r["composite"] > 80 else "A" if r["composite"] > 65 else "B"
            lines.append(
                f"{i}. <b>{r['stock_id']} {r['name']}</b>"
                f" | {r['close']} | {r['composite']}分({grade})"
            )

        # 高分新面孔提示
        lines.append("")
        lines.append('💡 <a href="https://tw-stock-screener-tom-annie.streamlit.app/">完整排名請到網頁版查看</a>')

        message = "\n".join(lines)
        send_telegram(message)
        print(f"[{datetime.now()}] 掃描完成，已推送 Telegram")

    except Exception as e:
        import traceback
        error_msg = (
            f"⚠️ 每日掃描失敗\n"
            f"步驟：{step}\n"
            f"錯誤：{type(e).__name__}: {e}\n"
            f"詳情：{traceback.format_exc()[-500:]}"
        )
        print(error_msg)
        send_telegram(error_msg)


if __name__ == "__main__":
    main()
