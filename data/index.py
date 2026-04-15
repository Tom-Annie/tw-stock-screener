"""
指數相關資料擷取 — 加權指數、櫃買指數、市場漲跌家數
"""
import hashlib
import pandas as pd
import requests
from datetime import datetime, timedelta

from config.settings import (
    CACHE_DIR,
    CACHE_TTL_INDEX_HOURS,
    CACHE_TTL_INDEX_SHORT_HOURS,
    CACHE_TTL_BREADTH_HOURS,
)
from data.cache import fetch_with_cache


def _fetch_taiex_yfinance(start_date: str,
                           end_date: str = None) -> pd.DataFrame:
    """用 yfinance 抓加權指數 ^TWII (備援)"""
    cache_key = f"taiex_yf_{start_date}_{end_date or 'now'}"
    hashed = hashlib.md5(cache_key.encode()).hexdigest()[:12]
    cache_file = CACHE_DIR / f"taiex_yf_{hashed}.parquet"

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=CACHE_TTL_INDEX_HOURS):
            return pd.read_parquet(cache_file)

    try:
        import yfinance as yf
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        data = yf.download("^TWII", start=start_date, end=end,
                           progress=False, auto_adjust=False)
        if data.empty:
            return pd.DataFrame()

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data = data.reset_index()
        data = data.rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
            "Adj Close": "adj_close",
        })
        data["date"] = pd.to_datetime(data["date"])
        data["stock_id"] = "TAIEX"

        for col in ["open", "high", "low", "close"]:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")

        data = data.sort_values("date").reset_index(drop=True)
        if not data.empty:
            data.to_parquet(cache_file, index=False)
        return data
    except Exception:
        return pd.DataFrame()


def fetch_taiex(start_date: str, end_date: str = None) -> pd.DataFrame:
    """取得加權指數日K"""
    try:
        params = {"data_id": "TAIEX", "start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        df = fetch_with_cache("TaiwanStockTotalReturnIndex", params, ttl_hours=12)
        if df.empty:
            # fallback: 用發行量加權指數
            params2 = {"start_date": start_date}
            if end_date:
                params2["end_date"] = end_date
            df = fetch_with_cache("TaiwanVariousIndicators5Seconds", params2,
                                  ttl_hours=12)
        if not df.empty:
            return df
    except Exception:
        pass

    # Fallback: yfinance ^TWII
    return _fetch_taiex_yfinance(start_date, end_date)


def fetch_tpex_index(start_date: str, end_date: str = None) -> pd.DataFrame:
    """抓櫃買指數歷史（yfinance ^TWOII，失敗時回 FinMind 指標）"""
    cache_key = f"tpex_idx_{start_date}_{end_date or 'now'}"
    hashed = hashlib.md5(cache_key.encode()).hexdigest()[:12]
    cache_file = CACHE_DIR / f"tpex_idx_{hashed}.parquet"
    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=CACHE_TTL_INDEX_SHORT_HOURS):
            return pd.read_parquet(cache_file)

    try:
        import yfinance as yf
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        data = pd.DataFrame()
        for sym in ("^TWOII", "^TPEX"):
            data = yf.download(sym, start=start_date, end=end,
                               progress=False, auto_adjust=False)
            if not data.empty:
                break
        if data.empty:
            return pd.DataFrame()

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        data = data.reset_index().rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Volume": "volume",
        })
        data["date"] = pd.to_datetime(data["date"])
        for col in ["open", "high", "low", "close"]:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")
        data = data.sort_values("date").reset_index(drop=True)
        if not data.empty:
            data.to_parquet(cache_file, index=False)
        return data
    except Exception:
        return pd.DataFrame()


def fetch_market_breadth_twse(date_str: str = None) -> dict:
    """抓 TWSE 當日漲跌家數統計（免 token）

    回傳 {date, up, down, flat, limit_up, limit_down, volume, amount}
    date_str 格式 "YYYYMMDD"，省略則抓最近交易日。
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y%m%d")

    cache_file = CACHE_DIR / f"breadth_{date_str}.parquet"
    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=CACHE_TTL_BREADTH_HOURS):
            df = pd.read_parquet(cache_file)
            if not df.empty:
                return df.iloc[0].to_dict()

    try:
        url = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
        resp = requests.get(url, params={
            "date": date_str, "type": "MS", "response": "json"
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("stat") != "OK":
            return {}

        # TWSE MI_INDEX 表格 7「漲跌證券數合計」格式："6,400(271)"
        # 第二欄是總計(含權證)，第三欄才是股票類。取第三欄。
        import re as _re
        def _parse_paren(s: str):
            """解析 '6,400(271)' → (6400, 271)"""
            m = _re.match(r"([\d,]+)(?:\(([\d,]+)\))?", str(s).strip())
            if not m:
                return 0, 0
            main = int(m.group(1).replace(",", "")) if m.group(1) else 0
            paren = int(m.group(2).replace(",", "")) if m.group(2) else 0
            return main, paren

        up = down = flat = limit_up = limit_down = 0
        volume = amount = 0
        for tbl in data.get("tables", []):
            title = tbl.get("title", "") or ""
            rows = tbl.get("data", []) or []
            if "漲跌" in title:
                for row in rows:
                    if not row or len(row) < 3:
                        continue
                    label = str(row[0])
                    cell = row[2]  # 第 3 欄（index 2）= 股票類
                    if "上漲" in label:
                        up, limit_up = _parse_paren(cell)
                    elif "下跌" in label:
                        down, limit_down = _parse_paren(cell)
                    elif "持平" in label or "平盤" in label:
                        flat, _ = _parse_paren(cell)
            elif "大盤統計" in title:
                # 「1.一般股票」那列 → [label, 成交股數, 成交金額, 成交筆數]
                for row in rows:
                    if not row or len(row) < 3:
                        continue
                    if "一般股票" in str(row[0]):
                        # TWSE 欄位順序：[類別, 成交金額, 成交股數, 成交筆數]
                        try:
                            amount = int(str(row[1]).replace(",", ""))
                            volume = int(str(row[2]).replace(",", ""))
                        except (ValueError, IndexError):
                            pass
                        break

        result = {
            "date": date_str, "up": up, "down": down, "flat": flat,
            "limit_up": limit_up, "limit_down": limit_down,
            "volume": volume, "amount": amount,
        }
        pd.DataFrame([result]).to_parquet(cache_file, index=False)
        return result
    except Exception:
        return {}


__all__ = [
    "_fetch_taiex_yfinance",
    "fetch_taiex",
    "fetch_tpex_index",
    "fetch_market_breadth_twse",
]
