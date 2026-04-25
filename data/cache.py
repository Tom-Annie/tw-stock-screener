"""
快取基礎設施 — 路徑產生 + 帶快取的 FinMind 資料擷取

新鮮度雙保險:
  1. mtime + ttl_hours(舊有機制)
  2. 若 df 含 'date' 欄,檢查最大日期是否 ≥ 最近交易日(避免 cache 內容過時)
"""
import hashlib
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from config.settings import CACHE_DIR


def _cache_path(dataset: str, params: dict) -> Path:
    """產生快取檔案路徑"""
    key = f"{dataset}_{'_'.join(f'{k}={v}' for k, v in sorted(params.items()))}"
    hashed = hashlib.md5(key.encode()).hexdigest()[:12]
    return CACHE_DIR / f"{dataset}_{hashed}.parquet"


def _is_data_fresh(df: pd.DataFrame, expected_latest: pd.Timestamp | None) -> bool:
    """檢查 df 內最新一筆日期是否 ≥ 預期最近交易日"""
    if expected_latest is None or df.empty or "date" not in df.columns:
        return True
    try:
        latest = pd.to_datetime(df["date"]).max()
        return latest.normalize() >= expected_latest.normalize()
    except Exception:
        return True


def fetch_with_cache(dataset: str, params: dict, ttl_hours: int = 12,
                      check_freshness: bool = True) -> pd.DataFrame:
    """
    帶快取的資料擷取,回傳 DataFrame。
    - mtime + ttl_hours 過期 → 重抓
    - check_freshness=True 且 df 含 date 欄 → 檢查最新日期 ≥ 最近交易日
    可透過 .attrs['cache_hit'] 判斷是否命中快取。
    """
    from data.finmind import _fetch_finmind

    cache_file = _cache_path(dataset, params)

    expected_latest = None
    if check_freshness:
        try:
            from utils.trading_calendar import latest_trading_day
            expected_latest = pd.Timestamp(latest_trading_day())
        except Exception:
            expected_latest = None

    if cache_file.exists():
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=ttl_hours):
            try:
                df = pd.read_parquet(cache_file)
                if _is_data_fresh(df, expected_latest):
                    df.attrs["cache_hit"] = True
                    return df
            except Exception:
                pass

    df = _fetch_finmind(dataset, params)
    df.attrs["cache_hit"] = False
    if not df.empty:
        df.to_parquet(cache_file, index=False)
    return df


__all__ = ["_cache_path", "fetch_with_cache"]
