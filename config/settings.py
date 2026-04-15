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
