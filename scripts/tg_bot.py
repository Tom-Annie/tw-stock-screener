"""
Telegram Bot 互動腳本
監聽使用者指令，回傳分析報表

指令:
  /scan          — 執行完整掃描 TOP 10 + CSV
  /stock 2330    — 分析單一個股 8 策略
  /top [N]       — 查看最近一次分析的 TOP N (預設 10)
  /status        — API 剩餘額度
  /help          — 顯示指令列表

用法:
  python scripts/tg_bot.py          # 前景執行（Ctrl+C 停止）
  python scripts/tg_bot.py --once   # 只檢查一次新訊息就結束（排程用）
"""
import os
import sys
import time
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

# 切換到專案根目錄
_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.chdir(_project_root)
sys.path.insert(0, _project_root)

# 讀 secrets
_secrets_path = Path(_project_root) / ".streamlit" / "secrets.toml"
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

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
OFFSET_FILE = Path.home() / ".tw-stock-screener" / "tg_bot_offset.json"

if not BOT_TOKEN or not CHAT_ID:
    print("ERROR: TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 未設定")
    sys.exit(1)


# ── Telegram 工具 ─────────────────────────────────────────

def send_message(text, parse_mode="HTML"):
    try:
        resp = requests.post(f"{API_BASE}/sendMessage", json={
            "chat_id": CHAT_ID, "text": text, "parse_mode": parse_mode,
        }, timeout=15)
        return resp.status_code == 200
    except Exception as e:
        print(f"  send_message error: {e}")
        return False


def send_document(file_path, caption=""):
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(f"{API_BASE}/sendDocument",
                data={"chat_id": CHAT_ID, "caption": caption},
                files={"document": (os.path.basename(file_path), f, "text/csv")},
                timeout=30)
        return resp.status_code == 200
    except Exception as e:
        print(f"  send_document error: {e}")
        return False


def get_updates(offset=None):
    params = {"timeout": 30, "allowed_updates": ["message"]}
    if offset:
        params["offset"] = offset
    try:
        resp = requests.get(f"{API_BASE}/getUpdates", params=params, timeout=35)
        if resp.status_code == 200:
            return resp.json().get("result", [])
    except Exception:
        pass
    return []


def load_offset():
    if OFFSET_FILE.exists():
        try:
            return json.loads(OFFSET_FILE.read_text()).get("offset", 0)
        except Exception:
            pass
    return 0


def save_offset(offset):
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(json.dumps({"offset": offset}))


# ── 指令處理 ─────────────────────────────────────────

def cmd_help():
    send_message(
        "<b>📋 可用指令</b>\n\n"
        "/scan — 執行完整掃描 (TOP 10 + CSV)\n"
        "/stock 2330 — 分析單一個股\n"
        "/top [N] — 查看最近分析的 TOP N\n"
        "/status — API 剩餘額度\n"
        "/help — 顯示此說明"
    )


def cmd_status():
    from data.fetcher import check_finmind_usage
    usage = check_finmind_usage()
    if usage:
        pct = usage["used"] / max(usage["limit"], 1) * 100
        icon = "🟢" if pct < 60 else ("🟡" if pct < 85 else "🔴")
        send_message(
            f"{icon} <b>API 狀態</b>\n\n"
            f"已使用: {usage['used']} / {usage['limit']}\n"
            f"剩餘: {usage['limit'] - usage['used']}\n"
            f"使用率: {pct:.1f}%"
        )
    else:
        send_message("⚠️ 無法查詢 API 狀態（未設定 FINMIND_TOKEN？）")


def cmd_top(n=10):
    from config.settings import CACHE_DIR
    history_dir = CACHE_DIR.parent / "history"
    hist_files = sorted(history_dir.glob("*.parquet"), reverse=True)
    if not hist_files:
        send_message("⚠️ 尚無歷史分析資料，請先執行 /scan")
        return

    import pandas as pd
    latest = hist_files[0]
    date_str = latest.stem
    df = pd.read_parquet(latest)

    grade_emoji = {"S": "🔥", "A": "⭐", "B": "🟢", "C": "🟡", "D": "⚪"}
    lines = [f"📊 <b>TOP {n} — {date_str}</b>", ""]
    for _, row in df.head(n).iterrows():
        g = str(row.get("grade", ""))
        emoji = grade_emoji.get(g, "")
        lines.append(
            f"#{int(row['rank']):>2}  <b>{row['stock_id']} {row.get('name', '')}</b>"
            f"  {row['composite_score']:.1f}分 {emoji}{g}"
        )
    lines.append("")
    lines.append(f"資料日期: {date_str}")
    send_message("\n".join(lines))


def cmd_stock(stock_id):
    import pandas as pd
    from data.fetcher import (
        fetch_stock_prices_batch, fetch_stock_list,
        fetch_us_stock, fetch_taiex,
    )
    from strategies.ma_breakout import MABreakoutStrategy
    from strategies.volume_price import VolumePriceStrategy
    from strategies.relative_strength import RelativeStrengthStrategy
    from strategies.institutional_flow import InstitutionalFlowStrategy
    from strategies.enhanced_technical import EnhancedTechnicalStrategy
    from strategies.margin_analysis import MarginAnalysisStrategy
    from strategies.us_market import USMarketStrategy
    from strategies.shareholder import ShareholderStrategy

    send_message(f"⏳ 分析 {stock_id} 中...")

    end_date = datetime.now()
    end_str = end_date.strftime("%Y-%m-%d")
    start_str = (end_date - timedelta(days=100)).strftime("%Y-%m-%d")

    # 名稱
    stock_name = stock_id
    try:
        sl = fetch_stock_list()
        match = sl[sl["stock_id"] == stock_id]
        if not match.empty:
            stock_name = f"{stock_id} {match.iloc[0].get('name', '')}"
    except Exception:
        pass

    # 價量
    prices = fetch_stock_prices_batch([stock_id], start_str, end_str)
    if prices.empty or len(prices) < 60:
        send_message(f"❌ {stock_name}: 資料不足（需 60 天以上）")
        return

    pdf = prices[prices["stock_id"] == stock_id].sort_values("date").reset_index(drop=True)

    # 大盤
    taiex_close = None
    try:
        taiex_df = fetch_taiex(start_str, end_str)
        if not taiex_df.empty:
            taiex_df = taiex_df.sort_values("date")
            taiex_close = taiex_df.get("close", taiex_df.get("price"))
    except Exception:
        pass

    # 美股
    us_start = (end_date - timedelta(days=40)).strftime("%Y-%m-%d")
    sox_df = tsm_df = pd.DataFrame()
    try:
        sox_df = fetch_us_stock("^SOX", us_start, end_str)
    except Exception:
        pass
    try:
        tsm_df = fetch_us_stock("TSM", us_start, end_str)
    except Exception:
        pass

    tsmc_close = pdf["close"].iloc[-1] if stock_id == "2330" else 0

    # 8 策略
    strategies = [
        ("均線突破", MABreakoutStrategy(), {}),
        ("量價齊揚", VolumePriceStrategy(), {}),
        ("相對強弱", RelativeStrengthStrategy(),
         {"index_close": taiex_close} if taiex_close is not None and len(taiex_close) >= 20 else {}),
        ("法人籌碼", InstitutionalFlowStrategy(), {"institutional_df": pd.DataFrame()}),
        ("進階技術", EnhancedTechnicalStrategy(), {}),
        ("融資融券", MarginAnalysisStrategy(), {"margin_df": pd.DataFrame()}),
        ("美股連動", USMarketStrategy(), {"sox_df": sox_df, "tsm_df": tsm_df,
                                          "tsmc_close": tsmc_close, "night_df": pd.DataFrame(),
                                          "day_futures_df": pd.DataFrame()}),
        ("大戶籌碼", ShareholderStrategy(), {"tdcc_df": pd.DataFrame()}),
    ]

    lines = [f"📈 <b>{stock_name} 分析報告</b>", ""]
    lines.append(f"收盤價: {pdf['close'].iloc[-1]:.2f}")
    vol = pdf['volume'].iloc[-1]
    if pd.notna(vol):
        lines.append(f"成交量: {int(vol):,}")
    lines.append("")

    total_score = 0
    total_weight = 0
    from config.settings import DEFAULT_WEIGHTS
    weight_keys = ["ma_breakout", "volume_price", "relative_strength",
                   "institutional_flow", "enhanced_technical", "margin_analysis",
                   "us_market", "shareholder"]

    for i, (name, strategy, kwargs) in enumerate(strategies):
        try:
            score = strategy.score(pdf, **kwargs)
            detail = strategy.details(pdf, **kwargs)
            signal = detail.get("signal", "")
        except Exception:
            score = 0
            signal = "計算錯誤"

        icon = "🟢" if score >= 65 else ("🟡" if score >= 40 else "🔴")
        lines.append(f"{icon} <b>{name}</b>: {score:.0f}分  {signal}")

        w = DEFAULT_WEIGHTS.get(weight_keys[i], 0)
        total_score += score * w
        total_weight += w

    composite = round(total_score / max(total_weight, 0.01), 1)
    if composite >= 80:
        grade = "S 🔥"
    elif composite >= 65:
        grade = "A ⭐"
    elif composite >= 50:
        grade = "B 🟢"
    elif composite >= 30:
        grade = "C 🟡"
    else:
        grade = "D ⚪"

    lines.insert(3, f"<b>綜合: {composite}分 ({grade})</b>")
    lines.append("")
    lines.append(f'💡 <a href="https://tw-stock-screener-tom-annie.streamlit.app/">網頁版詳細分析</a>')

    send_message("\n".join(lines))


def cmd_scan():
    """執行完整掃描（調用 daily_local.main）"""
    send_message("⏳ 開始掃描 50 檔熱門科技股，約需 2-3 分鐘...")

    try:
        # 直接調用 daily_local 的 main
        from scripts.daily_local import main as daily_main
        daily_main()

        # 讀取剛存的結果
        import pandas as pd
        from config.settings import CACHE_DIR
        history_dir = CACHE_DIR.parent / "history"
        hist_files = sorted(history_dir.glob("*.parquet"), reverse=True)
        if hist_files:
            send_message("✅ 掃描完成！結果已儲存並推播。")
        else:
            send_message("⚠️ 掃描完成但無結果檔案")
    except Exception as e:
        send_message(f"❌ 掃描失敗: {e}")


# ── 訊息路由 ─────────────────────────────────────────

def handle_message(text):
    text = text.strip()
    if not text.startswith("/"):
        return

    parts = text.split()
    cmd = parts[0].lower().split("@")[0]  # 去掉 @botname
    args = parts[1:]

    if cmd == "/help" or cmd == "/start":
        cmd_help()
    elif cmd == "/status":
        cmd_status()
    elif cmd == "/top":
        n = 10
        if args:
            try:
                n = int(args[0])
            except ValueError:
                pass
        cmd_top(min(n, 50))
    elif cmd == "/stock":
        if not args:
            send_message("⚠️ 用法: /stock 2330")
            return
        cmd_stock(args[0])
    elif cmd == "/scan":
        cmd_scan()
    else:
        send_message(f"❓ 未知指令: {cmd}\n輸入 /help 查看可用指令")


# ── 主迴圈 ─────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="只檢查一次就結束")
    args = parser.parse_args()

    print(f"[{datetime.now()}] TG Bot 啟動 (chat_id={CHAT_ID})")
    if args.once:
        print("  模式: 單次檢查")

    offset = load_offset()

    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                save_offset(offset)

                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                text = msg.get("text", "")

                # 只回應指定的 chat
                if chat_id != CHAT_ID:
                    continue

                if text:
                    print(f"  收到: {text}")
                    handle_message(text)

        except KeyboardInterrupt:
            print("\n  Bot 停止")
            break
        except Exception as e:
            print(f"  Error: {e}")
            time.sleep(5)

        if args.once:
            break

        # 短暫休息避免 API 過度呼叫
        time.sleep(1)


if __name__ == "__main__":
    main()
