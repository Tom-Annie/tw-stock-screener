"""
資料擷取模組 - 整合 FinMind / TWSE / TPEx / yfinance / TDCC
"""
import time
import hashlib
import pandas as pd
import requests
from pathlib import Path
from datetime import datetime, timedelta

from config.settings import FINMIND_TOKEN, CACHE_DIR


FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"


def _cache_path(dataset: str, params: dict) -> Path:
    """產生快取檔案路徑"""
    key = f"{dataset}_{'_'.join(f'{k}={v}' for k, v in sorted(params.items()))}"
    hashed = hashlib.md5(key.encode()).hexdigest()[:12]
    return CACHE_DIR / f"{dataset}_{hashed}.parquet"


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


def fetch_with_cache(dataset: str, params: dict, ttl_hours: int = 12) -> pd.DataFrame:
    """帶快取的資料擷取，回傳 DataFrame。可透過 .attrs['cache_hit'] 判斷是否命中快取"""
    cache_file = _cache_path(dataset, params)

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=ttl_hours):
            df = pd.read_parquet(cache_file)
            df.attrs["cache_hit"] = True
            return df

    df = _fetch_finmind(dataset, params)
    df.attrs["cache_hit"] = False
    if not df.empty:
        df.to_parquet(cache_file, index=False)
    return df


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
            if datetime.now() - mtime < timedelta(hours=18):
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


def _parse_institutional_df(df: pd.DataFrame) -> pd.DataFrame:
    """解析 FinMind 法人買賣超原始資料"""
    df["date"] = pd.to_datetime(df["date"])
    df["buy"] = pd.to_numeric(df.get("buy", 0), errors="coerce").fillna(0)
    df["sell"] = pd.to_numeric(df.get("sell", 0), errors="coerce").fillna(0)

    result_rows = []
    for (date, sid), grp in df.groupby(["date", "stock_id"]):
        row = {"date": date, "stock_id": sid}
        for _, r in grp.iterrows():
            name = str(r.get("name", ""))
            net = r["buy"] - r["sell"]
            if "外資" in name or "Foreign" in name:
                row["foreign_buy"] = r["buy"]
                row["foreign_sell"] = r["sell"]
                row["foreign_net"] = net
            elif "投信" in name or "Trust" in name:
                row["trust_buy"] = r["buy"]
                row["trust_sell"] = r["sell"]
                row["trust_net"] = net
            elif "自營" in name or "Dealer" in name:
                row["dealer_net"] = row.get("dealer_net", 0) + net

        for col in ["foreign_buy", "foreign_sell", "foreign_net",
                     "trust_buy", "trust_sell", "trust_net", "dealer_net"]:
            row.setdefault(col, 0)
        row["total_net"] = row["foreign_net"] + row["trust_net"] + row["dealer_net"]
        result_rows.append(row)

    if not result_rows:
        return pd.DataFrame()
    result = pd.DataFrame(result_rows)
    return result.sort_values(["stock_id", "date"]).reset_index(drop=True)


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
        if datetime.now() - mtime < timedelta(hours=18):
            return pd.read_parquet(cache_file)

    # 優先用 yfinance (免費無限制)
    df = _fetch_us_yfinance(ticker, start_date, end_date)

    # 備援: FinMind
    if df.empty:
        df = _fetch_us_finmind(ticker, start_date, end_date)

    if not df.empty:
        df.to_parquet(cache_file, index=False)

    return df


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


# ===== TWSE / TPEx 備援價格來源 =====

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
        if datetime.now() - mtime < timedelta(hours=18):
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
        if datetime.now() - mtime < timedelta(hours=18):
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


# ===== TWSE/TPEx 備援: 法人、融資券、股票清單、加權指數 =====

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
            if datetime.now() - mtime < timedelta(hours=72):
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
            if datetime.now() - mtime < timedelta(hours=72):
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


def _fetch_taiex_yfinance(start_date: str,
                           end_date: str = None) -> pd.DataFrame:
    """用 yfinance 抓加權指數 ^TWII (備援)"""
    cache_key = f"taiex_yf_{start_date}_{end_date or 'now'}"
    hashed = hashlib.md5(cache_key.encode()).hexdigest()[:12]
    cache_file = CACHE_DIR / f"taiex_yf_{hashed}.parquet"

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=12):
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


def fetch_tpex_index(start_date: str, end_date: str = None) -> pd.DataFrame:
    """抓櫃買指數歷史（yfinance ^TWOII，失敗時回 FinMind 指標）"""
    cache_key = f"tpex_idx_{start_date}_{end_date or 'now'}"
    hashed = hashlib.md5(cache_key.encode()).hexdigest()[:12]
    cache_file = CACHE_DIR / f"tpex_idx_{hashed}.parquet"
    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=6):
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
        if datetime.now() - mtime < timedelta(hours=4):
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


# ===== TDCC 集保中心 - 股權分散表 =====

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
        if datetime.now() - mtime < timedelta(days=7):
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
