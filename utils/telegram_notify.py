"""
Telegram Bot 推播通知 — 統一給 app.py / scripts / GitHub Actions 使用

讀取順序：Streamlit secrets → 環境變數。
這樣同一個 send() 無論在 Streamlit Cloud、WSL、GitHub Actions 都能用。

設定：
- Streamlit: .streamlit/secrets.toml 設 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
- Scripts  : export TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
"""
import os
import requests

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _get_config() -> tuple:
    """先試 Streamlit secrets，再 fallback 環境變數"""
    token = chat_id = ""
    try:
        import streamlit as st
        token = st.secrets.get("TELEGRAM_BOT_TOKEN", "") or ""
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "") or ""
    except Exception:
        pass
    if not token:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not chat_id:
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    return token, chat_id


def is_available() -> bool:
    token, chat_id = _get_config()
    return bool(token and chat_id)


def send(message: str, parse_mode: str = "HTML",
         disable_web_page_preview: bool = True) -> bool:
    """發送 Telegram 訊息；回傳是否成功"""
    token, chat_id = _get_config()
    if not token or not chat_id:
        return False

    try:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json={
                "chat_id": chat_id, "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            },
            timeout=15,
        )
        return resp.status_code == 200
    except Exception:
        return False


def send_document(file_path: str, caption: str = "",
                  filename: str = None, mime: str = "text/csv") -> bool:
    """發送檔案附件（例如 CSV）"""
    token, chat_id = _get_config()
    if not token or not chat_id:
        return False
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": chat_id, "caption": caption},
                files={"document": (filename or file_path, f, mime)},
                timeout=30,
            )
        return resp.status_code == 200
    except Exception:
        return False


def format_portfolio_alert(results: list) -> str:
    """將庫存分析結果格式化為通知訊息"""
    if not results:
        return ""

    from datetime import datetime
    dt = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"📊 <b>庫存分析通知</b>", f"🕐 {dt}", ""]

    action_stocks = []
    for r in results:
        if "error" in r:
            continue
        action = r.get("action", {})
        if action.get("color") in ("red", "blue"):
            action_stocks.append(r)

    if not action_stocks:
        lines.append("✅ 所有持股狀態正常，無需特別操作。")
    else:
        lines.append(f"⚠️ <b>{len(action_stocks)} 檔需要注意：</b>")
        lines.append("")
        for r in action_stocks:
            act = r["action"]
            icon = "🔴" if act["color"] == "red" else "🔵"
            lines.append(
                f"{icon} <b>{r['stock_id']} {r.get('name', '')}</b>"
                f" | {act['action']}"
                f" | 損益 {r['pnl_pct']:+.1f}%"
                f" | 分數 {r['composite']}"
            )
            lines.append(f"   → {act['reason']}")
            lines.append("")

    valid = [r for r in results if "error" not in r and r.get("avg_cost", 0) > 0]
    if valid:
        total_cost = sum(r["avg_cost"] * r["shares"] for r in valid)
        total_value = sum(r["current_price"] * r["shares"] for r in valid)
        total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0
        lines.append(f"📈 總損益：<b>{total_pnl_pct:+.1f}%</b>")

    return "\n".join(lines)
