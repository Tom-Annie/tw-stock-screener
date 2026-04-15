"""
股票清單 / 名稱查詢 / TDCC 股權分散表
"""
import pandas as pd
import requests
from datetime import datetime, timedelta

from config.settings import CACHE_DIR, CACHE_TTL_STOCK_LIST_DAYS
from data.cache import fetch_with_cache
from data.finmind import _fetch_finmind


def _fetch_stock_list_twse() -> pd.DataFrame:
    """從 TWSE 取得上市股票清單 (備援)"""
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL"
    resp = requests.get(url, params={"response": "json"}, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("stat") != "OK" or "data" not in data:
        return pd.DataFrame()

    rows = []
    for row in data["data"]:
        try:
            sid = row[0].strip()
            name = row[1].strip()
            # Only keep 4-digit stock codes
            if len(sid) == 4 and sid.isdigit():
                rows.append({
                    "stock_id": sid,
                    "name": name,
                    "industry": "",
                })
        except (ValueError, IndexError):
            continue

    if not rows:
        return pd.DataFrame(columns=["stock_id", "name", "industry"])

    df = pd.DataFrame(rows)
    df = df.drop_duplicates(subset=["stock_id"], keep="first")
    return df


def lookup_stock_name(stock_id: str) -> str:
    """
    查詢股票名稱
    1. 先從快取的股票清單找
    2. 找不到就直接查 FinMind API
    3. 查到的結果補寫進快取
    """
    cache_file = CACHE_DIR / "stock_list.parquet"

    # 先從快取找
    if cache_file.exists():
        try:
            sl = pd.read_parquet(cache_file)
            match = sl[sl["stock_id"] == stock_id]
            if not match.empty and "name" in match.columns:
                name = match.iloc[0]["name"]
                if name:
                    return str(name)
        except Exception:
            pass

    # 快取裡沒有，查 FinMind API
    try:
        df = _fetch_finmind("TaiwanStockInfo", {})

        if not df.empty:
            df = df.rename(columns={
                "stock_id": "stock_id",
                "stock_name": "name",
                "industry_category": "industry"
            })

            # 找目標股票
            target = df[df["stock_id"] == stock_id]
            name = ""
            if not target.empty and "name" in target.columns:
                name = str(target.iloc[0]["name"])

            # 順便更新快取 (保留所有股票)
            keep = ["stock_id", "name", "industry"]
            available = [c for c in keep if c in df.columns]
            save_df = df[available].drop_duplicates(
                subset=["stock_id"], keep="first"
            )
            save_df.to_parquet(cache_file, index=False)

            return name
    except Exception:
        pass

    return ""


def fetch_stock_list() -> pd.DataFrame:
    """
    取得上市股票清單
    使用 TWSE OpenAPI
    """
    cache_file = CACHE_DIR / "stock_list.parquet"

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(days=CACHE_TTL_STOCK_LIST_DAYS):
            return pd.read_parquet(cache_file)

    try:
        # 使用 FinMind 的股票清單
        df = _fetch_finmind("TaiwanStockInfo", {})

        if not df.empty:
            # 只保留一般股票 (排除 ETF、權證等)
            if "type" in df.columns:
                df = df[df["type"].isin(["stock", "twse"])].copy()
            df = df.rename(columns={
                "stock_id": "stock_id",
                "stock_name": "name",
                "industry_category": "industry"
            })
            keep = ["stock_id", "name", "industry"]
            available = [c for c in keep if c in df.columns]
            df = df[available].copy()

            # 過濾: 只保留4碼數字的股票代碼 (排除權證等)
            df = df[df["stock_id"].str.match(r"^\d{4}$")].copy()
            # 去除重複
            df = df.drop_duplicates(subset=["stock_id"], keep="first")

            df.to_parquet(cache_file, index=False)
            return df.reset_index(drop=True)

    except Exception as e:
        print(f"Warning: Failed to fetch stock list from FinMind: {e}")

    # Fallback: TWSE API
    try:
        df = _fetch_stock_list_twse()
        if not df.empty:
            df.to_parquet(cache_file, index=False)
            return df.reset_index(drop=True)
    except Exception as e:
        print(f"Warning: Failed to fetch stock list from TWSE: {e}")

    # Fallback: 使用 twstock
    try:
        import twstock
        rows = []
        for code, info in twstock.codes.items():
            if (info.market == "上市" and
                    info.type == "股票" and
                    len(code) == 4 and code.isdigit()):
                rows.append({
                    "stock_id": code,
                    "name": info.name,
                    "industry": info.group
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            df.to_parquet(cache_file, index=False)
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["stock_id", "name", "industry"])


def fetch_tdcc_holders(stock_id: str) -> pd.DataFrame:
    """
    取得股權分散表 (透過 FinMind TaiwanStockHoldingSharesPer)
    回傳: date, stock_id, holding_range, holders, shares, pct
    """
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    params = {"data_id": stock_id, "start_date": start, "end_date": end}

    try:
        df = fetch_with_cache("TaiwanStockHoldingSharesPer", params,
                              ttl_hours=24)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])

    # 標準化欄位名
    col_map = {
        "HoldingSharesLevel": "holding_range",
        "people": "holders",
        "unit": "shares",
        "percent": "pct",
    }
    for old, new in col_map.items():
        if old in df.columns:
            df = df.rename(columns={old: new})

    for col in ["holders", "shares", "pct"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df.sort_values("date").reset_index(drop=True)


__all__ = [
    "_fetch_stock_list_twse",
    "lookup_stock_name",
    "fetch_stock_list",
    "fetch_tdcc_holders",
]
