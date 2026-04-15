"""
FinMind API 基礎 — 直接呼叫 FinMind REST API
"""
import pandas as pd
import requests

from config.settings import FINMIND_TOKEN


FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"


def _fetch_finmind(dataset: str, params: dict) -> pd.DataFrame:
    """呼叫 FinMind API"""
    payload = {"dataset": dataset, **params}
    if FINMIND_TOKEN:
        payload["token"] = FINMIND_TOKEN

    resp = requests.get(FINMIND_API_URL, params=payload, timeout=120)
    if resp.status_code == 402:
        raise RuntimeError("FinMind API 免費額度已用完（每小時 600 次），請稍後再試")
    if resp.status_code == 429:
        raise RuntimeError("FinMind API 請求過於頻繁，請稍後再試")
    if not resp.ok:
        raise RuntimeError(f"FinMind API 錯誤 (HTTP {resp.status_code})")
    data = resp.json()

    if data.get("status") != 200:
        msg = data.get("msg", "Unknown error")
        raise RuntimeError(f"FinMind API error: {msg}")

    df = pd.DataFrame(data.get("data", []))
    return df


def check_finmind_usage() -> dict | None:
    """查詢 FinMind API 剩餘額度，回傳 {'used': int, 'limit': int} 或 None"""
    if not FINMIND_TOKEN:
        return None
    try:
        resp = requests.get(
            "https://api.web.finmindtrade.com/v2/user_info",
            headers={"Authorization": f"Bearer {FINMIND_TOKEN}"},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            return {
                "used": data.get("user_count", 0),
                "limit": data.get("api_request_limit", 600),
            }
    except Exception:
        pass
    return None


__all__ = ["FINMIND_API_URL", "_fetch_finmind", "check_finmind_usage"]
