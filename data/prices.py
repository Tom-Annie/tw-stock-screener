"""
價量相關資料擷取 — 個股日K、批次下載、TWSE/TPEx 備援
"""
import time
import hashlib
import pandas as pd
import requests
from datetime import datetime, timedelta

from config.settings import (
    CACHE_DIR,
    CACHE_TTL_PRICE_HOURS,
)
from data.cache import _cache_path, fetch_with_cache


def _parse_yf_single(data, ticker: str, stock_id: str) -> pd.DataFrame:
    """從 yfinance 下載結果中提取單檔股票資料（相容 0.2.x ~ 1.2.x）"""
    try:
        df = None
        if isinstance(data.columns, pd.MultiIndex):
            # MultiIndex: 找 ticker 在哪個 level
            for level in range(data.columns.nlevels):
                vals = set(data.columns.get_level_values(level))
                tk = ticker if ticker in vals else (ticker.upper() if ticker.upper() in vals else None)
                if tk:
                    try:
                        df = data.xs(tk, level=level, axis=1).copy()
                    except Exception:
                        continue
                    break
            if df is None:
                return pd.DataFrame()
        else:
            df = data.copy()

        # 確保 df 是 DataFrame
        if isinstance(df, pd.Series):
            df = df.to_frame()

        # reset index 把 Date 從 index 拉出來
        if isinstance(df.index, pd.DatetimeIndex) or df.index.name in ("Date", "date", "Datetime"):
            df = df.reset_index()

        # 展平所有欄位名為純字串
        flat_cols = []
        for c in df.columns:
            if isinstance(c, tuple):
                # 取 tuple 中有意義的部分（非空字串）
                parts = [str(x).strip() for x in c if x and str(x).strip()]
                flat_cols.append(parts[0] if parts else str(c))
            else:
                flat_cols.append(str(c).strip())
        df.columns = flat_cols

        # 標準化欄位名（不區分大小寫），每個目標只取首次匹配
        _target_map = {
            "date": ["date", "datetime"],
            "open": ["open"],
            "high": ["high"],
            "low": ["low"],
            "close": ["close", "adj close", "adjclose"],
            "volume": ["volume"],
        }
        col_rename = {}
        found = set()
        for c in df.columns:
            cl = c.lower().strip()
            for target, aliases in _target_map.items():
                if target not in found and cl in aliases:
                    col_rename[c] = target
                    found.add(target)
                    break
        df = df.rename(columns=col_rename)
        df = df.loc[:, ~df.columns.duplicated()]

        if "close" not in df.columns or "date" not in df.columns:
            return pd.DataFrame()

        df = df.dropna(subset=["close"])
        if df.empty:
            return pd.DataFrame()

        df["stock_id"] = stock_id
        date_s = df["date"]
        if isinstance(date_s, pd.DataFrame):
            date_s = date_s.iloc[:, 0]
        df["date"] = pd.to_datetime(date_s).dt.strftime("%Y-%m-%d")

        keep = ["date", "stock_id", "open", "high", "low", "close", "volume"]
        return df[[c for c in keep if c in df.columns]]
    except Exception:
        return pd.DataFrame()


def _normalize_price_df(df: pd.DataFrame) -> pd.DataFrame:
    """統一價量 DataFrame 欄位格式"""
    if df.empty:
        return df

    # 如果有 MultiIndex columns（yfinance 殘留），先展平
    if isinstance(df.columns, pd.MultiIndex):
        flat = []
        for c in df.columns:
            if isinstance(c, tuple):
                parts = [str(x).strip() for x in c if x and str(x).strip()]
                flat.append(parts[0] if parts else str(c))
            else:
                flat.append(str(c))
        df.columns = flat

    df = df.rename(columns={
        "date": "date",
        "stock_id": "stock_id",
        "Trading_Volume": "volume",
        "open": "open",
        "max": "high",
        "min": "low",
        "close": "close",
    })

    # 移除重複欄位名（concat 不同格式的 df 可能產生）
    df = df.loc[:, ~df.columns.duplicated()]

    keep_cols = ["date", "stock_id", "open", "high", "low", "close", "volume"]
    available = [c for c in keep_cols if c in df.columns]
    df = df[available].copy()

    # 處理日期（可能是 string / datetime / tz-aware datetime）
    if "date" in df.columns:
        try:
            df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
        except Exception:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            s = df[col]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            df[col] = pd.to_numeric(s, errors="coerce")
    if "volume" in df.columns:
        s = df["volume"]
        if isinstance(s, pd.DataFrame):
            s = s.iloc[:, 0]
        df["volume"] = pd.to_numeric(s, errors="coerce")

    sort_by = [c for c in ["stock_id", "date"] if c in df.columns]
    if sort_by:
        df = df.sort_values(sort_by)
    return df.reset_index(drop=True)


def fetch_twse_daily(stock_id: str, date_str: str) -> pd.DataFrame:
    """
    從證交所抓取單月日K資料 (上市股)
    date_str: YYYYMMDD 格式，只看年月
    回傳: date, stock_id, open, high, low, close, volume
    """
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {"response": "json", "date": date_str, "stockNo": stock_id}

    cache_key = f"twse_{stock_id}_{date_str[:6]}"
    hashed = hashlib.md5(cache_key.encode()).hexdigest()[:12]
    cache_file = CACHE_DIR / f"twse_{hashed}.parquet"

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=CACHE_TTL_PRICE_HOURS):
            return pd.read_parquet(cache_file)

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return pd.DataFrame()

    if data.get("stat") != "OK" or "data" not in data:
        return pd.DataFrame()

    rows = []
    for row in data["data"]:
        try:
            # 欄位: 日期, 成交股數, 成交金額, 開盤價, 最高價, 最低價, 收盤價, ...
            # 日期是民國年 如 113/01/02
            parts = row[0].split("/")
            y = int(parts[0]) + 1911
            date = f"{y}-{parts[1]}-{parts[2]}"
            vol = int(row[1].replace(",", ""))
            rows.append({
                "date": pd.Timestamp(date),
                "stock_id": stock_id,
                "open": float(row[3].replace(",", "")),
                "high": float(row[4].replace(",", "")),
                "low": float(row[5].replace(",", "")),
                "close": float(row[6].replace(",", "")),
                "volume": vol,
            })
        except (ValueError, IndexError):
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.to_parquet(cache_file, index=False)
    return df


def fetch_tpex_daily(stock_id: str, date_str: str) -> pd.DataFrame:
    """
    從櫃買中心抓取單月日K資料 (上櫃股)
    date_str: YYYYMMDD 格式
    """
    # 轉民國年
    y = int(date_str[:4]) - 1911
    m = date_str[4:6]
    roc_date = f"{y}/{m}/01"

    url = "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php"
    params = {"l": "zh-tw", "d": roc_date, "stkno": stock_id}

    cache_key = f"tpex_{stock_id}_{date_str[:6]}"
    hashed = hashlib.md5(cache_key.encode()).hexdigest()[:12]
    cache_file = CACHE_DIR / f"tpex_{hashed}.parquet"

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=CACHE_TTL_PRICE_HOURS):
            return pd.read_parquet(cache_file)

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return pd.DataFrame()

    if "aaData" not in data:
        return pd.DataFrame()

    rows = []
    for row in data["aaData"]:
        try:
            # 欄位: 日期, 成交股數, 成交金額, 開盤, 最高, 最低, 收盤, ...
            parts = row[0].split("/")
            y = int(parts[0]) + 1911
            date = f"{y}-{parts[1]}-{parts[2]}"
            rows.append({
                "date": pd.Timestamp(date),
                "stock_id": stock_id,
                "open": float(str(row[3]).replace(",", "")),
                "high": float(str(row[4]).replace(",", "")),
                "low": float(str(row[5]).replace(",", "")),
                "close": float(str(row[6]).replace(",", "")),
                "volume": int(str(row[1]).replace(",", "")),
            })
        except (ValueError, IndexError):
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.to_parquet(cache_file, index=False)
    return df


def _fetch_price_twse_tpex(stock_id: str, start_date: str,
                            end_date: str = None) -> pd.DataFrame:
    """
    TWSE → TPEx 價格備援 (單檔)
    按月迴圈下載，與 fetch_stock_prices_multi 相同邏輯
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()

    # Try TWSE first
    all_dfs = []
    try:
        current = start_dt
        while current <= end_dt:
            date_str = current.strftime("%Y%m%d")
            month_df = fetch_twse_daily(stock_id, date_str)
            if not month_df.empty:
                all_dfs.append(month_df)
            current = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
            time.sleep(0.5)
        if all_dfs:
            df = pd.concat(all_dfs, ignore_index=True)
            if end_date:
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass

    # Try TPEx
    all_dfs = []
    try:
        current = start_dt
        while current <= end_dt:
            date_str = current.strftime("%Y%m%d")
            month_df = fetch_tpex_daily(stock_id, date_str)
            if not month_df.empty:
                all_dfs.append(month_df)
            current = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
            time.sleep(0.5)
        if all_dfs:
            df = pd.concat(all_dfs, ignore_index=True)
            if end_date:
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass

    return pd.DataFrame()


def _fetch_prices_yfinance_batch(stock_ids: list, start_date: str,
                                  end_date: str = None,
                                  progress_callback=None) -> pd.DataFrame:
    """
    用 yfinance 批次下載台股價量資料（免費、無 API 限制）
    每批 50 檔，上市(.TW)與上櫃(.TWO)分開嘗試
    """
    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame()

    batch_size = 50
    all_dfs = []
    fetched_sids = set()

    for i in range(0, len(stock_ids), batch_size):
        batch = stock_ids[i:i + batch_size]
        if progress_callback:
            progress_callback(i, len(stock_ids),
                              f"下載價量資料 (yfinance)... ({i}/{len(stock_ids)})")

        # 第一輪: 嘗試 .TW（上市）
        tickers_tw = [f"{sid}.TW" for sid in batch]
        try:
            data = yf.download(
                tickers_tw, start=start_date, end=end_date,
                group_by="ticker", progress=False, threads=True,
                auto_adjust=True
            )
            if isinstance(data, pd.DataFrame) and not data.empty:
                for sid in batch:
                    ticker = f"{sid}.TW"
                    try:
                        df_s = _parse_yf_single(data, ticker, sid)
                        if isinstance(df_s, pd.DataFrame) and not df_s.empty:
                            all_dfs.append(df_s)
                            fetched_sids.add(sid)
                    except Exception:
                        continue
        except Exception:
            pass

        # 第二輪: 沒抓到的嘗試 .TWO（上櫃）
        missing = [sid for sid in batch if sid not in fetched_sids]
        if missing:
            tickers_two = [f"{sid}.TWO" for sid in missing]
            try:
                data2 = yf.download(
                    tickers_two, start=start_date, end=end_date,
                    group_by="ticker", progress=False, threads=True,
                    auto_adjust=True
                )
                if isinstance(data2, pd.DataFrame) and not data2.empty:
                    for sid in missing:
                        ticker = f"{sid}.TWO"
                        try:
                            df_s = _parse_yf_single(data2, ticker, sid)
                            if isinstance(df_s, pd.DataFrame) and not df_s.empty:
                                all_dfs.append(df_s)
                                fetched_sids.add(sid)
                        except Exception:
                            continue
            except Exception:
                pass

    if not all_dfs:
        return pd.DataFrame()
    # 過濾掉非 DataFrame 的項目
    valid_dfs = [d for d in all_dfs if isinstance(d, pd.DataFrame) and not d.empty]
    if not valid_dfs:
        return pd.DataFrame()
    return pd.concat(valid_dfs, ignore_index=True)


def fetch_stock_prices(stock_id: str = None, start_date: str = None,
                       end_date: str = None) -> pd.DataFrame:
    """
    取得股票日K資料
    stock_id: 個股代碼 (如 "2330")，None 表示取全市場
    回傳欄位: date, stock_id, open, high, low, close, volume
    """
    params = {"start_date": start_date}
    if end_date:
        params["end_date"] = end_date
    if stock_id:
        params["data_id"] = stock_id

    try:
        df = fetch_with_cache("TaiwanStockPrice", params)
        if not df.empty:
            return _normalize_price_df(df)
    except Exception:
        pass

    # Fallback: TWSE → TPEx (only when a single stock_id is given)
    if stock_id:
        return _fetch_price_twse_tpex(stock_id, start_date, end_date)

    return pd.DataFrame()


def fetch_stock_prices_batch(stock_ids: list, start_date: str,
                             end_date: str = None,
                             progress_callback=None) -> pd.DataFrame:
    """
    分批抓取多檔股票的價量資料
    優先順序: 1) Parquet 快取  2) yfinance 批次（免費無限）  3) FinMind 逐檔
    """
    all_dfs = []

    # === Phase 1: 檢查快取 ===
    cached_ids = []
    uncached_ids = []
    for sid in stock_ids:
        params = {"data_id": sid, "start_date": start_date}
        if end_date:
            params["end_date"] = end_date
        cache_file = _cache_path("TaiwanStockPrice", params)
        if cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
            if datetime.now() - mtime < timedelta(hours=CACHE_TTL_PRICE_HOURS):
                try:
                    all_dfs.append(pd.read_parquet(cache_file))
                    cached_ids.append(sid)
                    continue
                except Exception:
                    pass
        uncached_ids.append(sid)

    if progress_callback:
        progress_callback(0, len(stock_ids),
                          f"快取命中 {len(cached_ids)} 檔，需下載 {len(uncached_ids)} 檔")

    # === Phase 2: yfinance 批次下載（免費無限，不消耗 FinMind 額度）===
    if uncached_ids:
        if progress_callback:
            progress_callback(len(cached_ids), len(stock_ids),
                              f"yfinance 批次下載 {len(uncached_ids)} 檔...")
        yf_df = _fetch_prices_yfinance_batch(uncached_ids, start_date, end_date,
                                              progress_callback=progress_callback)
        if not yf_df.empty:
            yf_fetched = set(yf_df["stock_id"].unique())
            all_dfs.append(yf_df)

            # 寫入快取供下次使用
            for sid in yf_fetched:
                try:
                    sid_df = yf_df[yf_df["stock_id"] == sid]
                    params = {"data_id": sid, "start_date": start_date}
                    if end_date:
                        params["end_date"] = end_date
                    sid_df.to_parquet(_cache_path("TaiwanStockPrice", params), index=False)
                except Exception:
                    pass

            uncached_ids = [s for s in uncached_ids if s not in yf_fetched]

    # === Phase 3: 剩餘的用 FinMind 逐檔（消耗 API 額度）===
    if uncached_ids:
        if progress_callback:
            progress_callback(len(stock_ids) - len(uncached_ids), len(stock_ids),
                              f"FinMind 下載剩餘 {len(uncached_ids)} 檔...")
        api_calls = 0
        for sid in uncached_ids:
            try:
                params = {"data_id": sid, "start_date": start_date}
                if end_date:
                    params["end_date"] = end_date
                df = fetch_with_cache("TaiwanStockPrice", params, ttl_hours=18)
                if not df.empty:
                    all_dfs.append(df)
                    api_calls += 1
            except Exception:
                continue
            if api_calls % 50 == 0 and api_calls > 0:
                time.sleep(0.3)

    valid_dfs = [d for d in all_dfs if isinstance(d, pd.DataFrame) and not d.empty]
    if not valid_dfs:
        return pd.DataFrame()

    combined = pd.concat(valid_dfs, ignore_index=True)
    return _normalize_price_df(combined)


def fetch_stock_prices_multi(stock_id: str, start_date: str,
                             end_date: str = None) -> pd.DataFrame:
    """
    多來源價格擷取: FinMind → TWSE → TPEx
    自動判斷上市/上櫃並選擇適合的來源
    """
    # 優先用 FinMind
    df = fetch_stock_prices(stock_id, start_date, end_date)
    if not df.empty and len(df) >= 5:
        return df

    # 備援: TWSE (上市)
    try:
        all_dfs = []
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
        current = start_dt
        while current <= end_dt:
            date_str = current.strftime("%Y%m%d")
            month_df = fetch_twse_daily(stock_id, date_str)
            if not month_df.empty:
                all_dfs.append(month_df)
            current = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
            time.sleep(0.5)  # TWSE rate limit

        if all_dfs:
            df = pd.concat(all_dfs, ignore_index=True)
            if end_date:
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass

    # 備援: TPEx (上櫃)
    try:
        all_dfs = []
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
        current = start_dt
        while current <= end_dt:
            date_str = current.strftime("%Y%m%d")
            month_df = fetch_tpex_daily(stock_id, date_str)
            if not month_df.empty:
                all_dfs.append(month_df)
            current = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
            time.sleep(0.5)

        if all_dfs:
            df = pd.concat(all_dfs, ignore_index=True)
            if end_date:
                df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass

    return pd.DataFrame()


__all__ = [
    "_parse_yf_single",
    "_normalize_price_df",
    "fetch_twse_daily",
    "fetch_tpex_daily",
    "_fetch_price_twse_tpex",
    "_fetch_prices_yfinance_batch",
    "fetch_stock_prices",
    "fetch_stock_prices_batch",
    "fetch_stock_prices_multi",
]
