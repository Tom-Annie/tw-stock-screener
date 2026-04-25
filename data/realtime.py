"""
即時報價層 — TWSE MIS API(15-20 秒延遲,完全免費,無需 token)

API 端點:
  https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_2330.tw|otc_3105.tw

回傳欄位(節錄):
  c   股票代碼     n   名稱      z   最新成交價    o   開盤
  h   最高         l   最低      y   昨收         v   累積成交量
  tv  最新一筆成交量    t  成交時間  pz  最新一筆成交價
  a/b 五檔賣/買價(_  分隔)        f/g  五檔賣/買量
  ex  市場別:tse=上市  otc=上櫃
"""
from __future__ import annotations

import time
import requests
import pandas as pd
from typing import Iterable

MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0",
    "Referer": "https://mis.twse.com.tw/stock/fibest.jsp",
    "Accept": "*/*",
}


def _safe_float(v, default=0.0) -> float:
    try:
        if v is None or v == "" or v == "-":
            return default
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return default


def _safe_int(v, default=0) -> int:
    try:
        if v is None or v == "" or v == "-":
            return default
        return int(float(str(v).replace(",", "")))
    except (ValueError, TypeError):
        return default


def _build_channels(stock_ids: Iterable[str]) -> str:
    """先試 tse(上市),抓不到的下次再用 otc(上櫃)。
    這裡為了一次到位,把每檔同時送 tse 與 otc,API 只回有資料的那筆。"""
    chs = []
    for sid in stock_ids:
        sid = str(sid).strip()
        if not sid:
            continue
        chs.append(f"tse_{sid}.tw")
        chs.append(f"otc_{sid}.tw")
    return "|".join(chs)


def fetch_mis_quote(stock_ids: list[str], timeout: int = 6) -> pd.DataFrame:
    """
    取即時報價(批次)。
    回傳欄位:
      stock_id, name, market, price, open, high, low, yesterday_close,
      volume, change, change_pct, time, bid_price, ask_price, bid_vol, ask_vol
    """
    if not stock_ids:
        return pd.DataFrame()

    ex_ch = _build_channels(stock_ids)
    params = {"ex_ch": ex_ch, "json": "1", "delay": "0", "_": int(time.time() * 1000)}

    try:
        r = requests.get(MIS_URL, params=params, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return pd.DataFrame()

    msg = payload.get("msgArray", []) or []
    rows = []
    seen = set()  # (stock_id) 去重 — 同檔同時打 tse+otc 只取有報價的那筆
    for x in msg:
        sid = x.get("c", "")
        if not sid or sid in seen:
            continue
        price = _safe_float(x.get("z"))
        last_price = _safe_float(x.get("pz"))
        if price <= 0:
            price = last_price
        y_close = _safe_float(x.get("y"))
        if price <= 0 and y_close > 0:
            price = y_close

        bids = (x.get("b") or "").rstrip("_").split("_")
        asks = (x.get("a") or "").rstrip("_").split("_")
        bid_vols = (x.get("g") or "").rstrip("_").split("_")
        ask_vols = (x.get("f") or "").rstrip("_").split("_")

        change = price - y_close if y_close > 0 else 0.0
        change_pct = (change / y_close * 100) if y_close > 0 else 0.0

        rows.append({
            "stock_id": sid,
            "name": x.get("n", ""),
            "market": "上市" if x.get("ex") == "tse" else "上櫃",
            "price": price,
            "open": _safe_float(x.get("o")),
            "high": _safe_float(x.get("h")),
            "low": _safe_float(x.get("l")),
            "yesterday_close": y_close,
            "volume": _safe_int(x.get("v")),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "time": x.get("t", ""),
            "bid_price": _safe_float(bids[0] if bids else 0),
            "ask_price": _safe_float(asks[0] if asks else 0),
            "bid_vol": _safe_int(bid_vols[0] if bid_vols else 0),
            "ask_vol": _safe_int(ask_vols[0] if ask_vols else 0),
        })
        seen.add(sid)

    return pd.DataFrame(rows)


def fetch_mis_index(index_codes: list[str] | None = None) -> pd.DataFrame:
    """
    取大盤即時指數。預設抓加權(TSE)與櫃買(OTC)。
    index_codes 範例: ['t00', 'o00'] (t00=加權, o00=櫃買)
    """
    codes = index_codes or ["t00", "o00"]
    # 加權用 tse_ 前綴,櫃買用 otc_ 前綴
    parts = []
    for c in codes:
        prefix = "otc" if c.startswith("o") else "tse"
        parts.append(f"{prefix}_{c}.tw")
    ex_ch = "|".join(parts)
    params = {"ex_ch": ex_ch, "json": "1", "delay": "0", "_": int(time.time() * 1000)}

    try:
        r = requests.get(MIS_URL, params=params, headers=HEADERS, timeout=6)
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return pd.DataFrame()

    rows = []
    for x in payload.get("msgArray", []) or []:
        price = _safe_float(x.get("z")) or _safe_float(x.get("pz"))
        y = _safe_float(x.get("y"))
        change = price - y if y > 0 else 0.0
        pct = (change / y * 100) if y > 0 else 0.0
        rows.append({
            "code": x.get("c", ""),
            "name": x.get("n", ""),
            "price": price,
            "yesterday_close": y,
            "change": round(change, 2),
            "change_pct": round(pct, 2),
            "time": x.get("t", ""),
        })
    return pd.DataFrame(rows)


__all__ = ["fetch_mis_quote", "fetch_mis_index"]
