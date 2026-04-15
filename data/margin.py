"""
融資融券資料擷取
"""
import time
import hashlib
import pandas as pd
import requests
from datetime import datetime, timedelta

from config.settings import CACHE_DIR, CACHE_TTL_FUTURES_HOURS
from data.cache import fetch_with_cache
from data.institutional import _get_trading_days, _strip_commas


def _fetch_margin_twse(stock_id: str, start_date: str,
                        end_date: str = None) -> pd.DataFrame:
    """
    從 TWSE 取得融資融券資料 (備援)
    每次回傳一天全市場，逐日下載再篩選
    """
    url = "https://www.twse.com.tw/exchangeReport/MI_MARGN"
    trading_days = _get_trading_days(start_date, end_date)
    result_rows = []

    for day in trading_days:
        date_str = day.strftime("%Y%m%d")

        # Check cache
        cache_key = f"twse_margin_{date_str}"
        hashed = hashlib.md5(cache_key.encode()).hexdigest()[:12]
        cache_file = CACHE_DIR / f"twse_margin_{hashed}.parquet"

        day_df = None
        if cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime < timedelta(hours=CACHE_TTL_FUTURES_HOURS):
                day_df = pd.read_parquet(cache_file)

        if day_df is None:
            try:
                resp = requests.get(url, params={
                    "response": "json", "date": date_str, "selectType": "ALL"
                }, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                time.sleep(0.5)
                continue

            if data.get("stat") != "OK":
                time.sleep(0.5)
                continue

            # MI_MARGN has "tables" array; the second table (index 1) has
            # per-stock margin data. First table is summary.
            tables = data.get("tables", [])
            if len(tables) < 2 or "data" not in tables[1]:
                time.sleep(0.5)
                continue

            rows = []
            for row in tables[1]["data"]:
                try:
                    sid = row[0].strip()
                    # Columns: 股票代號, 股票名稱,
                    #   融資買進, 融資賣出, 融資現金償還, 融資前日餘額, 融資今日餘額,
                    #   融資限額, 融券買進, 融券賣出, 融券現金償還, 融券前日餘額,
                    #   融券今日餘額, 融券限額, 資券互抵, 註記
                    margin_balance = int(_strip_commas(row[6]))
                    short_balance = int(_strip_commas(row[12]))
                    rows.append({
                        "date": day,
                        "stock_id": sid,
                        "margin_balance": margin_balance,
                        "short_balance": short_balance,
                    })
                except (ValueError, IndexError):
                    continue

            if rows:
                day_df = pd.DataFrame(rows)
                day_df.to_parquet(cache_file, index=False)
            else:
                time.sleep(0.5)
                continue

            time.sleep(0.5)

        # Filter for target stock
        match = day_df[day_df["stock_id"] == stock_id]
        if not match.empty:
            result_rows.append(match)

    if not result_rows:
        return pd.DataFrame()

    result = pd.concat(result_rows, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"])
    for col in ["margin_balance", "short_balance"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
    return result.sort_values("date").reset_index(drop=True)


def fetch_margin_data(stock_id: str, start_date: str,
                      end_date: str = None,
                      skip_fallback: bool = False) -> pd.DataFrame:
    """
    取得融資融券資料 (單檔)
    回傳欄位: date, stock_id, margin_balance, short_balance
    skip_fallback: True 時跳過慢速 TWSE 備援（批次模式用）
    """
    if not stock_id:
        return pd.DataFrame()

    params = {"data_id": stock_id, "start_date": start_date}
    if end_date:
        params["end_date"] = end_date

    try:
        df = fetch_with_cache("TaiwanStockMarginPurchaseShortSale", params)
    except Exception:
        df = pd.DataFrame()

    if df.empty:
        if skip_fallback:
            return pd.DataFrame()
        # Fallback: TWSE
        return _fetch_margin_twse(stock_id, start_date, end_date)

    df["date"] = pd.to_datetime(df["date"])

    # FinMind 真實欄位：
    #   MarginPurchaseTodayBalance (融資餘額，策略用)
    #   MarginPurchaseLimit (融資上限，每檔固定 — 別誤用)
    #   ShortSaleTodayBalance (融券餘額)
    # 先比對精確欄名，避免 "Limit" 被當成 balance
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if cl == "marginpurchasetodaybalance" or cl == "marginpurchasebalance":
            col_map[c] = "margin_balance"
        elif cl == "shortsaletodaybalance" or cl == "shortsalebalance":
            col_map[c] = "short_balance"
        elif cl == "marginpurchasebuy":
            col_map[c] = "margin_buy"
        elif cl == "marginpurchasesell":
            col_map[c] = "margin_sell"
        elif cl == "shortsalebuy":
            col_map[c] = "short_buy"
        elif cl == "shortsalesell":
            col_map[c] = "short_sell"

    if col_map:
        df = df.rename(columns=col_map)

    for col in ["margin_balance", "short_balance", "margin_buy",
                "margin_sell", "short_buy", "short_sell"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    keep = ["date", "stock_id", "margin_balance", "short_balance",
            "margin_buy", "margin_sell", "short_buy", "short_sell"]
    available = [c for c in keep if c in df.columns]
    return df[available].sort_values("date").reset_index(drop=True)


def fetch_margin_batch(stock_ids: list, start_date: str,
                       end_date: str = None,
                       progress_callback=None) -> pd.DataFrame:
    """分批抓取多檔股票的融資融券資料，快取命中時跳過 sleep"""
    all_dfs = []
    api_calls_since_sleep = 0
    for i, sid in enumerate(stock_ids):
        if progress_callback and i % 30 == 0:
            progress_callback(i, len(stock_ids),
                              f"下載融資融券... ({i}/{len(stock_ids)})")
        try:
            df = fetch_margin_data(sid, start_date, end_date, skip_fallback=True)
            if not df.empty:
                all_dfs.append(df)
                api_calls_since_sleep += 1
        except Exception:
            continue

        if api_calls_since_sleep >= 30:
            time.sleep(0.3)
            api_calls_since_sleep = 0

    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)


__all__ = [
    "_fetch_margin_twse",
    "fetch_margin_data",
    "fetch_margin_batch",
]
