"""
LINE Notify 推播通知
需在 Streamlit Secrets 設定 LINE_NOTIFY_TOKEN
取得方式：https://notify-bot.line.me/my/ → 發行存取權杖
"""
import requests
import streamlit as st

LINE_NOTIFY_API = "https://notify-api.line.me/api/notify"


def _get_token() -> str:
    try:
        return st.secrets.get("LINE_NOTIFY_TOKEN", "")
    except Exception:
        return ""


def is_available() -> bool:
    return bool(_get_token())


def send(message: str) -> bool:
    """發送 LINE 通知，回傳是否成功"""
    token = _get_token()
    if not token:
        return False

    try:
        resp = requests.post(
            LINE_NOTIFY_API,
            headers={"Authorization": f"Bearer {token}"},
            data={"message": message},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:
        return False


def format_portfolio_alert(results: list) -> str:
    """將庫存分析結果格式化為通知訊息"""
    if not results:
        return ""

    lines = ["\n📊 庫存分析通知"]
    lines.append(f"時間：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # 需要行動的股票
    action_stocks = []
    for r in results:
        if "error" in r:
            continue
        action = r.get("action", {})
        act_name = action.get("action", "")
        color = action.get("color", "")

        # 只通知需要行動的（紅色和藍色）
        if color in ("red", "blue"):
            action_stocks.append(r)

    if not action_stocks:
        lines.append("所有持股狀態正常，無需特別操作。")
    else:
        lines.append(f"⚠️ {len(action_stocks)} 檔需要注意：")
        lines.append("")
        for r in action_stocks:
            act = r["action"]
            icon = "🔴" if act["color"] == "red" else "🔵"
            lines.append(
                f"{icon} {r['stock_id']} {r.get('name', '')}"
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
        lines.append(f"📈 總損益：{total_pnl_pct:+.1f}%")

    return "\n".join(lines)
