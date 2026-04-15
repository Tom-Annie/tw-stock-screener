"""
資料層 façade — 向後相容 import，實作已拆到 data/ 各子模組

所有外部呼叫 `from data.fetcher import X` 均透過此檔案保持相容。
"""

# ── 快取基礎設施 ──────────────────────────────────────────────────────────────
from data.cache import (  # noqa: F401
    _cache_path,
    fetch_with_cache,
)

# ── FinMind API 基礎 ──────────────────────────────────────────────────────────
from data.finmind import (  # noqa: F401
    FINMIND_API_URL,
    _fetch_finmind,
    check_finmind_usage,
)

# ── 價量相關 ──────────────────────────────────────────────────────────────────
from data.prices import (  # noqa: F401
    _parse_yf_single,
    _normalize_price_df,
    fetch_twse_daily,
    fetch_tpex_daily,
    _fetch_price_twse_tpex,
    _fetch_prices_yfinance_batch,
    fetch_stock_prices,
    fetch_stock_prices_batch,
    fetch_stock_prices_multi,
)

# ── 法人籌碼 ──────────────────────────────────────────────────────────────────
from data.institutional import (  # noqa: F401
    _get_trading_days,
    _strip_commas,
    _parse_institutional_df,
    _fetch_institutional_twse,
    fetch_institutional_investors,
    fetch_institutional_batch,
)

# ── 融資融券 ──────────────────────────────────────────────────────────────────
from data.margin import (  # noqa: F401
    _fetch_margin_twse,
    fetch_margin_data,
    fetch_margin_batch,
)

# ── 指數相關 ──────────────────────────────────────────────────────────────────
from data.index import (  # noqa: F401
    _fetch_taiex_yfinance,
    fetch_taiex,
    fetch_tpex_index,
    fetch_market_breadth_twse,
)

# ── 美股 / 期貨 / 匯率 ────────────────────────────────────────────────────────
from data.us_market import (  # noqa: F401
    _fetch_us_yfinance,
    _fetch_us_finmind,
    fetch_us_stock,
    _get_usd_twd,
    fetch_night_futures,
    fetch_day_futures,
)

# ── 股票清單 / 名稱查詢 / TDCC ────────────────────────────────────────────────
from data.stock_info import (  # noqa: F401
    _fetch_stock_list_twse,
    lookup_stock_name,
    fetch_stock_list,
    fetch_tdcc_holders,
)

__all__ = [
    # cache
    "_cache_path",
    "fetch_with_cache",
    # finmind
    "FINMIND_API_URL",
    "_fetch_finmind",
    "check_finmind_usage",
    # prices
    "_parse_yf_single",
    "_normalize_price_df",
    "fetch_twse_daily",
    "fetch_tpex_daily",
    "_fetch_price_twse_tpex",
    "_fetch_prices_yfinance_batch",
    "fetch_stock_prices",
    "fetch_stock_prices_batch",
    "fetch_stock_prices_multi",
    # institutional
    "_get_trading_days",
    "_strip_commas",
    "_parse_institutional_df",
    "_fetch_institutional_twse",
    "fetch_institutional_investors",
    "fetch_institutional_batch",
    # margin
    "_fetch_margin_twse",
    "fetch_margin_data",
    "fetch_margin_batch",
    # index
    "_fetch_taiex_yfinance",
    "fetch_taiex",
    "fetch_tpex_index",
    "fetch_market_breadth_twse",
    # us_market
    "_fetch_us_yfinance",
    "_fetch_us_finmind",
    "fetch_us_stock",
    "_get_usd_twd",
    "fetch_night_futures",
    "fetch_day_futures",
    # stock_info
    "_fetch_stock_list_twse",
    "lookup_stock_name",
    "fetch_stock_list",
    "fetch_tdcc_holders",
]
