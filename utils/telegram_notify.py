"""
Telegram Bot 推播通知
需在 Streamlit Secrets 設定：
  TELEGRAM_BOT_TOKEN = "你的bot token"
  TELEGRAM_CHAT_ID = "你的chat id"
"""
import requests
import streamlit as st

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _get_config() -> tuple:
    try:
        token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
        return token, chat_id
    except Exception:
        return "", ""


def is_available() -> bool:
    token, chat_id = _get_config()
    return bool(token and chat_id)


def send(message: str) -> bool:
    """發送 Telegram 通知"""
    token, chat_id = _get_config()
    if not token or not chat_id:
        return False

    try:
        resp = requests.post(
            TELEGRAM_API.format(token=token),
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def format_portfolio_alert(results: list) -> str:
    """將庫存分析結果格式化為通知訊息"""
    if not results:
        return ""

    dt = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"📊 <b>庫存分析通知</b>", f"🕐 {dt}", ""]

    # 需要行動的股票
    action_stocks = []
    for r in results:
        if "error" in r:
            continue
        action = r.get("action", {})
        color = action.get("color", "")
        if color in ("red", "blue"):
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

    # 總覽
    valid = [r for r in results if "error" not in r and r.get("avg_cost", 0) > 0]
    if valid:
        total_cost = sum(r["avg_cost"] * r["shares"] for r in valid)
        total_value = sum(r["current_price"] * r["shares"] for r in valid)
        total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0
        lines.append(f"📈 總損益：<b>{total_pnl_pct:+.1f}%</b>")

    return "\n".join(lines)
