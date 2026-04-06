# 專案架構

```
tw-stock-screener/
│
├── app.py                          # 主頁：市場掃描、排名、市場溫度、自動權重
│
├── pages/
│   ├── 1_個股分析.py                # 單一個股 8 策略詳細分析 + 圖表
│   ├── 2_我的庫存.py                # 庫存管理、損益追蹤、TG 推播提醒
│   ├── 3_回測驗證.py                # 歷史回測策略績效驗證
│   ├── 4_策略設定.py                # 策略權重、RSI 參數、法人權重調整
│   └── 5_策略教學.py                # 8 大策略說明文件
│
├── strategies/                     # 八大評分策略
│   ├── base.py                     # BaseStrategy 基類 (_clamp 0~100)
│   ├── scorer.py                   # compute_composite_score 加權總分
│   ├── ma_breakout.py              # 策略1：均線突破
│   ├── volume_price.py             # 策略2：量價齊揚
│   ├── relative_strength.py        # 策略3：相對強弱（個股 vs 大盤）
│   ├── institutional_flow.py       # 策略4：法人買賣超（投信/外資/自營商）
│   ├── enhanced_technical.py       # 策略5：進階技術指標（KD/MACD/布林/OBV）
│   ├── margin_analysis.py          # 策略6：融資融券分析
│   ├── us_market.py                # 策略7：美股連動（費半/TSM/夜盤/期貨）
│   └── shareholder.py              # 策略8：大戶籌碼集中度（集保股權分散表）
│
├── data/
│   ├── fetcher.py                  # 資料層：Parquet 快取 → yfinance → FinMind API
│   └── __init__.py
│
├── utils/
│   ├── indicators.py               # 技術指標（MA/EMA/RSI/MACD/KD/布林/OBV/ATR/MDD）
│   ├── formatters.py               # 格式化工具（評級、顏色、數字）
│   ├── telegram_notify.py          # Telegram 推播（庫存提醒）
│   ├── line_notify.py              # LINE Notify（備用）
│   ├── auth.py                     # 使用者驗證
│   ├── gist_store.py               # GitHub Gist 庫存持久化
│   └── __init__.py
│
├── config/
│   ├── settings.py                 # 全域設定（權重、參數、閾值）
│   └── __init__.py
│
├── scripts/
│   └── daily_scan.py               # 每日排程掃描 + TG 推播 TOP 10
│
├── .github/workflows/
│   └── daily_scan.yml              # GitHub Actions 排程（每日自動執行）
│
├── .streamlit/
│   ├── config.toml                 # Streamlit 主題設定
│   └── secrets.toml                # API keys（本地開發用）
│
└── requirements.txt                # Python 套件依賴
```

## 資料流程

```
使用者操作 Streamlit UI
        │
        ▼
   data/fetcher.py ──→ ① Parquet 快取（免費）
        │                ② yfinance 批次下載（免費）
        │                ③ FinMind API（600次/hr）
        ▼
   strategies/*.py ──→ 8 策略各自評分 0~100
        │
        ▼
   scorer.py ──→ 加權總分 → S/A/B/C/D 評級
        │
        ▼
   排名顯示 / TG 推播 / 庫存提醒
```

## 八大策略

| # | 策略 | 檔案 | 說明 |
|---|------|------|------|
| 1 | 均線突破 | `ma_breakout.py` | 股價站上多條均線、均線多頭排列 |
| 2 | 量價齊揚 | `volume_price.py` | 價漲量增共振、連續量價齊揚天數 |
| 3 | 相對強弱 | `relative_strength.py` | 個股 vs 大盤超額報酬 + RSI |
| 4 | 法人買賣超 | `institutional_flow.py` | 投信/外資/自營商買賣超同步性 |
| 5 | 進階技術 | `enhanced_technical.py` | KD/MACD/布林通道/OBV/乖離率 |
| 6 | 融資融券 | `margin_analysis.py` | 融資減+融券增=軋空訊號 |
| 7 | 美股連動 | `us_market.py` | 費半/TSM ADR/夜盤期貨/台幣匯率 |
| 8 | 大戶籌碼 | `shareholder.py` | 集保股權分散表、大戶持股集中度 |

## 外部服務

| 服務 | 用途 | 設定位置 |
|------|------|----------|
| FinMind API | 台股價量/法人/融資/集保資料 | `FINMIND_TOKEN` |
| yfinance | 台股價量備援 + 美股資料 | 免費，無需 token |
| Telegram Bot | 每日掃描推播 + 庫存提醒 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| GitHub Gist | 庫存資料持久化 | `GITHUB_TOKEN` |
| GitHub Actions | 每日排程執行 `daily_scan.py` | Repository Secrets |
| Streamlit Cloud | 網頁部署 | `.streamlit/secrets.toml` |
