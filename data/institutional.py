"""
法人籌碼資料擷取 — 三大法人買賣超
"""
import time
import hashlib
import pandas as pd
import requests
from datetime import datetime, timedelta

from config.settings import CACHE_DIR, CACHE_TTL_FUTURES_HOURS
from data.cache import fetch_with_cache


def _get_trading_days(start_date: str, end_date: str = None) -> list:
    """
    產生 start_date 到 end_date 之間的營業日列表 (排除週末)
    回傳 list of datetime
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
    days = []
    current = start_dt
    while current <= end_dt:
        if current.weekday() < 5:  # Mon-Fri
            days.append(current)
        current += timedelta(days=1)
    return days


def _strip_commas(val) -> str:
    """移除數字字串中的逗號"""
    return str(val).replace(",", "").strip()


def _parse_institutional_df(df: pd.DataFrame) -> pd.DataFrame:
    """解析 FinMind 法人買賣超原始資料（向量化版本，比 iterrows 快 10-50x）"""
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["buy"] = pd.to_numeric(df.get("buy", 0), errors="coerce").fillna(0)
    df["sell"] = pd.to_numeric(df.get("sell", 0), errors="coerce").fillna(0)
    df["net"] = df["buy"] - df["sell"]

    # 把 name 映射成 category（外資/投信/自營）
    name_str = df["name"].astype(str)
    cat = pd.Series("", index=df.index)
    cat[name_str.str.contains("外資|Foreign", na=False)] = "foreign"
    cat[name_str.str.contains("投信|Trust", na=False)] = "trust"
    cat[name_str.str.contains("自營|Dealer", na=False)] = "dealer"
    df["_cat"] = cat
    df = df[df["_cat"] != ""]
    if df.empty:
        return pd.DataFrame()

    # 外資 / 投信：需 buy, sell, net 三欄
    fgn = df[df["_cat"] == "foreign"].groupby(
        ["date", "stock_id"], as_index=False)[["buy", "sell", "net"]].sum()
    fgn = fgn.rename(columns={"buy": "foreign_buy", "sell": "foreign_sell",
                              "net": "foreign_net"})
    trt = df[df["_cat"] == "trust"].groupby(
        ["date", "stock_id"], as_index=False)[["buy", "sell", "net"]].sum()
    trt = trt.rename(columns={"buy": "trust_buy", "sell": "trust_sell",
                              "net": "trust_net"})
    # 自營可能有多子類（自營商-自行、-避險），需加總淨額
    dlr = df[df["_cat"] == "dealer"].groupby(
        ["date", "stock_id"], as_index=False)["net"].sum()
    dlr = dlr.rename(columns={"net": "dealer_net"})

    # 以「date, stock_id」完整 outer join
    keys = pd.concat([fgn[["date", "stock_id"]],
                      trt[["date", "stock_id"]],
                      dlr[["date", "stock_id"]]]).drop_duplicates()
    result = keys.merge(fgn, on=["date", "stock_id"], how="left") \
                 .merge(trt, on=["date", "stock_id"], how="left") \
                 .merge(dlr, on=["date", "stock_id"], how="left")

    fill_cols = ["foreign_buy", "foreign_sell", "foreign_net",
                 "trust_buy", "trust_sell", "trust_net", "dealer_net"]
    for col in fill_cols:
        if col not in result.columns:
            result[col] = 0
    result[fill_cols] = result[fill_cols].fillna(0)
    result["total_net"] = result["foreign_net"] + result["trust_net"] + result["dealer_net"]

    return result.sort_values(["stock_id", "date"]).reset_index(drop=True)


def _fetch_institutional_twse(stock_id: str, start_date: str,
                               end_date: str = None) -> pd.DataFrame:
    """
    從 TWSE 取得三大法人買賣超資料 (備援)
    TWSE API 每次回傳一天的全市場資料，需逐日下載再篩選
    """
    url = "https://www.twse.com.tw/fund/T86"
    trading_days = _get_trading_days(start_date, end_date)
    result_rows = []

    for day in trading_days:
        date_str = day.strftime("%Y%m%d")

        # Check cache for this day
        cache_key = f"twse_inst_{date_str}"
        hashed = hashlib.md5(cache_key.encode()).hexdigest()[:12]
        cache_file = CACHE_DIR / f"twse_inst_{hashed}.parquet"

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

            if data.get("stat") != "OK" or "data" not in data:
                time.sleep(0.5)
                continue

            # Parse all rows for caching
            rows = []
            for row in data["data"]:
                try:
                    sid = row[0].strip()
                    rows.append({
                        "date": day,
                        "stock_id": sid,
                        "foreign_net": int(_strip_commas(row[4])),
                        "trust_net": int(_strip_commas(row[10])),
                        "dealer_net": int(_strip_commas(row[11])),
                        "total_net": int(_strip_commas(row[18])),
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
    # Convert shares to 張 (1張=1000股) — TWSE reports in shares
    for col in ["foreign_net", "trust_net", "dealer_net", "total_net"]:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
    return result.sort_values("date").reset_index(drop=True)


def fetch_institutional_investors(stock_id: str = None, start_date: str = None,
                                  end_date: str = None) -> pd.DataFrame:
    """
    取得三大法人買賣超資料 (單檔)
    回傳欄位: date, stock_id, foreign_net, trust_net, dealer_net, total_net
    """
    if not stock_id:
        return pd.DataFrame()

    params = {"data_id": stock_id, "start_date": start_date}
    if end_date:
        params["end_date"] = end_date

    try:
        df = fetch_with_cache("TaiwanStockInstitutionalInvestorsBuySell", params)
        if not df.empty:
            return _parse_institutional_df(df)
    except Exception:
        pass

    # Fallback: TWSE
    return _fetch_institutional_twse(stock_id, start_date, end_date)


def fetch_institutional_batch(stock_ids: list, start_date: str,
                              end_date: str = None,
                              progress_callback=None) -> pd.DataFrame:
    """
    分批抓取多檔股票的法人買賣超資料，快取命中時跳過 sleep
    """
    all_dfs = []
    api_calls_since_sleep = 0
    for i, sid in enumerate(stock_ids):
        if progress_callback and i % 30 == 0:
            progress_callback(i, len(stock_ids),
                              f"下載法人籌碼... ({i}/{len(stock_ids)})")
        try:
            # 先檢查快取
            params = {"data_id": sid, "start_date": start_date}
            if end_date:
                params["end_date"] = end_date
            raw = fetch_with_cache("TaiwanStockInstitutionalInvestorsBuySell", params)
            if not raw.empty:
                all_dfs.append(_parse_institutional_df(raw))
                if not raw.attrs.get("cache_hit"):
                    api_calls_since_sleep += 1
        except Exception:
            continue

        # 每 30 次 API 呼叫才 sleep
        if api_calls_since_sleep >= 30:
            time.sleep(0.3)
            api_calls_since_sleep = 0

    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)


__all__ = [
    "_get_trading_days",
    "_strip_commas",
    "_parse_institutional_df",
    "_fetch_institutional_twse",
    "fetch_institutional_investors",
    "fetch_institutional_batch",
]
