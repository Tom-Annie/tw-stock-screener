"""
台股分析系統 - 全域設定
"""
import os
from pathlib import Path

# FinMind API Token (免費註冊取得: https://finmind.github.io/)
# 設定環境變數 FINMIND_TOKEN 或直接填入
# 優先從 Streamlit Secrets 讀取，其次環境變數
try:
    import streamlit as st
    FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", os.getenv("FINMIND_TOKEN", ""))
except Exception:
    FINMIND_TOKEN = os.getenv("FINMIND_TOKEN", "")

# 快取目錄
CACHE_DIR = Path.home() / ".tw-stock-screener" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 均線參數
MA_PERIODS = [5, 10, 20, 60]

# RSI 參數
RSI_PERIOD = 14

# 量能參數
VOLUME_MA_PERIOD = 20       # 均量天數
VOLUME_SURGE_RATIO = 1.5    # 量能放大倍數門檻

# 法人籌碼參數
INSTITUTIONAL_LOOKBACK = 20  # 法人籌碼回溯天數
INST_TRUST_WEIGHT = 0.45     # 投信權重
INST_FOREIGN_WEIGHT = 0.40   # 外資權重
INST_DEALER_WEIGHT = 0.15    # 自營商權重

# RSI 強勢區間
RSI_BULLISH_LOW = 55
RSI_BULLISH_HIGH = 70

# 資料回溯天數 (需涵蓋最長均線 + 緩衝)
PRICE_LOOKBACK_DAYS = 120

# 策略權重 (預設)
# 註：shareholder 設為 0，因為 FinMind 免費帳號拿不到集保資料，
#     保留在 0 可避免排名偏差；升級 FinMind 後改回 0.13 即可。
DEFAULT_WEIGHTS = {
    "ma_breakout": 0.17,          # 突破均線
    "volume_price": 0.14,         # 量價齊揚
    "relative_strength": 0.17,    # 相對強弱
    "institutional_flow": 0.17,   # 法人籌碼
    "enhanced_technical": 0.14,   # 技術綜合
    "margin_analysis": 0.09,      # 融資融券
    "us_market": 0.12,            # 美股連動
    "shareholder": 0.00,          # 大戶籌碼（集保資料缺）
}

# 顯示設定
TOP_N_STOCKS = 30  # 預設顯示前 N 檔

# 快取 TTL（集中管理，data/fetcher.py 各處統一引用）
CACHE_TTL_PRICE_HOURS = 18       # 個股價量、法人、融資 日K 快取
CACHE_TTL_INDEX_HOURS = 12       # 指數快取（TAIEX / ^TWOII）
CACHE_TTL_INDEX_SHORT_HOURS = 6  # 短 TTL 指數 / 櫃買
CACHE_TTL_BREADTH_HOURS = 4      # 漲跌家數
CACHE_TTL_FUTURES_HOURS = 72     # 期貨
CACHE_TTL_STOCK_LIST_DAYS = 7    # 股票清單

# 策略最小可用資料天數
MIN_PRICE_ROWS = 40              # 少於此天數的股票跳過分析

# 自動權重 profile（依市場溫度，sum=100；shareholder=0 因 FinMind 集保缺資料）
AUTO_WEIGHT_PROFILES = {
    "過熱": {"ma_breakout": 14, "volume_price": 11, "relative_strength": 15,
             "institutional_flow": 19, "enhanced_technical": 16,
             "margin_analysis": 11, "us_market": 14, "shareholder": 0},
    "偏熱": {"ma_breakout": 22, "volume_price": 20, "relative_strength": 17,
             "institutional_flow": 13, "enhanced_technical": 11,
             "margin_analysis": 6, "us_market": 11, "shareholder": 0},
    "溫和": {"ma_breakout": 17, "volume_price": 14, "relative_strength": 17,
             "institutional_flow": 17, "enhanced_technical": 14,
             "margin_analysis": 9, "us_market": 12, "shareholder": 0},
    "偏冷": {"ma_breakout": 11, "volume_price": 11, "relative_strength": 14,
             "institutional_flow": 21, "enhanced_technical": 18,
             "margin_analysis": 11, "us_market": 14, "shareholder": 0},
    "極冷": {"ma_breakout": 9, "volume_price": 9, "relative_strength": 12,
             "institutional_flow": 22, "enhanced_technical": 17,
             "margin_analysis": 14, "us_market": 17, "shareholder": 0},
}
