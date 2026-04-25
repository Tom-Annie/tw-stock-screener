"""
台股交易日曆 — 判定「最近一筆已收盤、資料齊備」的交易日。

判定規則(由內到外):
  1. 平日 14:30 後才算當天資料齊(法人公告 ~14:30)
  2. 週末退到週五
  3. 國定假日跳過(查 config/tw_holidays.json)
  4. 颱風假 → 用 latest_trading_day_verified() 反查 ^TWII 修正
"""
from __future__ import annotations

import json
import functools
from datetime import datetime, timedelta, date
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    TPE = ZoneInfo("Asia/Taipei")
except Exception:
    TPE = None  # 若 Python <3.9 或缺 tzdata,回退用 naive

HOLIDAYS_FILE = Path(__file__).resolve().parent.parent / "config" / "tw_holidays.json"

DATA_READY_HOUR = 14
DATA_READY_MINUTE = 30


@functools.lru_cache(maxsize=8)
def _load_holidays(year: int) -> frozenset[str]:
    if not HOLIDAYS_FILE.exists():
        return frozenset()
    try:
        data = json.loads(HOLIDAYS_FILE.read_text(encoding="utf-8"))
        return frozenset(data.get(str(year), []))
    except Exception:
        return frozenset()


def _now_tpe() -> datetime:
    if TPE is not None:
        return datetime.now(TPE)
    return datetime.now()


def latest_trading_day(now: datetime | None = None) -> date:
    """
    回傳最近一筆「已收盤且資料齊備」的台股交易日(純本地計算,不打網路)。
    """
    now = now or _now_tpe()
    d = now.date()

    if (now.hour, now.minute) < (DATA_READY_HOUR, DATA_READY_MINUTE):
        d -= timedelta(days=1)

    holidays = _load_holidays(d.year)
    while d.weekday() >= 5 or d.isoformat() in holidays:
        d -= timedelta(days=1)
        if d.year not in (now.year, now.year - 1):
            holidays = _load_holidays(d.year)

    return d


def is_trading_now(now: datetime | None = None) -> bool:
    """是否處於台股盤中時段(09:00-13:30,排除週末/假日)"""
    now = now or _now_tpe()
    if now.weekday() >= 5:
        return False
    if now.date().isoformat() in _load_holidays(now.year):
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 <= minutes <= 13 * 60 + 30


@functools.lru_cache(maxsize=1)
def _verified_cache():
    return {"date": None, "fetched_at": None}


def latest_trading_day_verified(ttl_minutes: int = 60) -> date:
    """
    用 yfinance ^TWII 最新一筆日期當答案(連颱風假都正確)。
    結果快取 ttl_minutes 分鐘,避免每次呼叫都打網路。
    """
    cache = _verified_cache()
    now = _now_tpe()
    if (cache["date"] and cache["fetched_at"]
            and (now - cache["fetched_at"]).total_seconds() < ttl_minutes * 60):
        return cache["date"]

    try:
        import yfinance as yf
        df = yf.Ticker("^TWII").history(period="10d", auto_adjust=False)
        if not df.empty:
            d = df.index[-1].date()
            cache["date"] = d
            cache["fetched_at"] = now
            return d
    except Exception:
        pass

    return latest_trading_day(now)


__all__ = [
    "latest_trading_day",
    "latest_trading_day_verified",
    "is_trading_now",
]
