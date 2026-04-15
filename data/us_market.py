"""
美股 / 期貨 / 匯率資料擷取
"""
import hashlib
import pandas as pd
from datetime import datetime, timedelta

from config.settings import CACHE_DIR, CACHE_TTL_PRICE_HOURS, CACHE_TTL_FUTURES_HOURS
from data.cache import fetch_with_cache


def _fetch_us_yfinance(ticker: str, start_date: str,
                       end_date: str = None) -> pd.DataFrame:
    """用 yfinance 抓美股資料"""
    try:
        import yfinance as yf
        end = end_date or datetime.now().strftime("%Y-%m-%d")
        data = yf.download(ticker, start=start_date, end=end,
                           progress=False, auto_adjust=False)
        if data.empty:
            return pd.DataFrame()

        # yfinance 回傳的 columns 可能是 MultiIndex
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data = data.reset_index()
        data = data.rename(columns={
            "Date": "date", "Open": "open", "High": "high",
            "Low": "low", "Close": "close", "Adj Close": "adj_close",
            "Volume": "volume"
        })
        data["stock_id"] = ticker
        data["date"] = pd.to_datetime(data["date"])

        for col in ["open", "high", "low", "close"]:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")

        return data.sort_values("date").reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def _fetch_us_finmind(ticker: str, start_date: str,
                      end_date: str = None) -> pd.DataFrame:
    """備援: 用 FinMind 抓美股資料"""
    params = {"data_id": ticker, "start_date": start_date}
    if end_date:
        params["end_date"] = end_date
    try:
        df = fetch_with_cache("USStockPrice", params, ttl_hours=18)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    col_map = {"Open": "open", "High": "high", "Low": "low",
               "Close": "close", "Adj_Close": "adj_close", "Volume": "volume"}
    df = df.rename(columns=col_map)
    for col in ["open", "high", "low", "close", "adj_close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


def fetch_us_stock(ticker: str, start_date: str,
                   end_date: str = None) -> pd.DataFrame:
    """
    取得美股日K資料 (優先 yfinance，備援 FinMind)
    ticker: 如 "TSM" (台積電ADR), "^SOX" (費半指數)
    回傳欄位: date, stock_id, open, high, low, close, volume
    """
    # 先檢查快取
    cache_key = f"us_{ticker}_{start_date}_{end_date or 'now'}"
    hashed = hashlib.md5(cache_key.encode()).hexdigest()[:12]
    cache_file = CACHE_DIR / f"us_stock_{hashed}.parquet"

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=CACHE_TTL_PRICE_HOURS):
            return pd.read_parquet(cache_file)

    # 優先用 yfinance (免費無限制)
    df = _fetch_us_yfinance(ticker, start_date, end_date)

    # 備援: FinMind
    if df.empty:
        df = _fetch_us_finmind(ticker, start_date, end_date)

    if not df.empty:
        df.to_parquet(cache_file, index=False)

    return df


def _get_usd_twd() -> float:
    """取得美元兌台幣匯率（快取 1 小時）"""
    cache_file = CACHE_DIR / "usd_twd.parquet"
    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=1):
            try:
                df = pd.read_parquet(cache_file)
                return float(df.iloc[0]["rate"])
            except Exception:
                pass
    try:
        import yfinance as yf
        data = yf.download("TWD=X", period="5d", progress=False)
        if not data.empty:
            rate = float(data["Close"].dropna().iloc[-1])
            pd.DataFrame([{"rate": rate}]).to_parquet(cache_file, index=False)
            return rate
    except Exception:
        pass
    return 30.5  # fallback


def fetch_night_futures(start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    取得台指期夜盤資料
    回傳欄位: date, open, high, low, close, volume, settlement_price, spread
    """
    params = {"data_id": "TX", "start_date": start_date}
    if end_date:
        params["end_date"] = end_date

    try:
        df = fetch_with_cache("TaiwanFuturesDaily", params, ttl_hours=18)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])

    # 只取夜盤 (after_market) 與近月合約
    if "trading_session" in df.columns:
        night = df[df["trading_session"] == "after_market"].copy()
    else:
        night = df.copy()

    # 取近月合約 (每個日期取最小的 contract_date)
    if "contract_date" in night.columns and not night.empty:
        night["contract_date"] = night["contract_date"].astype(str)
        idx = night.groupby("date")["contract_date"].idxmin()
        night = night.loc[idx]

    col_map = {"max": "high", "min": "low"}
    night = night.rename(columns=col_map)

    for col in ["open", "high", "low", "close", "settlement_price", "spread"]:
        if col in night.columns:
            night[col] = pd.to_numeric(night[col], errors="coerce")
    if "volume" in night.columns:
        night["volume"] = pd.to_numeric(night["volume"], errors="coerce")

    keep = ["date", "open", "high", "low", "close", "volume",
            "settlement_price", "spread"]
    available = [c for c in keep if c in night.columns]
    return night[available].sort_values("date").reset_index(drop=True)


def fetch_day_futures(start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    取得台指期日盤資料 (用於計算夜盤價差)
    """
    params = {"data_id": "TX", "start_date": start_date}
    if end_date:
        params["end_date"] = end_date

    try:
        df = fetch_with_cache("TaiwanFuturesDaily", params, ttl_hours=18)
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])

    if "trading_session" in df.columns:
        day = df[df["trading_session"] == "position"].copy()
    else:
        day = df.copy()

    if "contract_date" in day.columns and not day.empty:
        day["contract_date"] = day["contract_date"].astype(str)
        idx = day.groupby("date")["contract_date"].idxmin()
        day = day.loc[idx]

    col_map = {"max": "high", "min": "low"}
    day = day.rename(columns=col_map)

    for col in ["open", "high", "low", "close", "settlement_price"]:
        if col in day.columns:
            day[col] = pd.to_numeric(day[col], errors="coerce")

    keep = ["date", "open", "high", "low", "close", "volume", "settlement_price"]
    available = [c for c in keep if c in day.columns]
    return day[available].sort_values("date").reset_index(drop=True)


__all__ = [
    "_fetch_us_yfinance",
    "_fetch_us_finmind",
    "fetch_us_stock",
    "_get_usd_twd",
    "fetch_night_futures",
    "fetch_day_futures",
]
