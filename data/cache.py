"""
快取基礎設施 — 路徑產生 + 帶快取的 FinMind 資料擷取
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


def fetch_with_cache(dataset: str, params: dict, ttl_hours: int = 12) -> pd.DataFrame:
    """帶快取的資料擷取，回傳 DataFrame。可透過 .attrs['cache_hit'] 判斷是否命中快取"""
    # 延遲 import 避免循環依賴（finmind 模組會 import cache）
    from data.finmind import _fetch_finmind

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


__all__ = ["_cache_path", "fetch_with_cache"]
