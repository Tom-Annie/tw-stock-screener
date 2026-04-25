# 專案架構

## 目錄結構

```
tw-stock-screener/
│
├── app.py                          # 主頁：市場掃描、排名、市場溫度、自動權重
│
├── pages/
│   ├── 1_個股分析.py                # 單一個股 8 策略詳細分析 + K線/RSI/MACD 圖表
│   ├── 2_我的庫存.py                # 庫存管理、損益追蹤、即時損益(MIS)、TG/LINE 推播
│   ├── 3_回測驗證.py                # 歷史回測策略績效驗證、勝率統計
│   ├── 4_策略設定.py                # 策略權重、RSI 參數、法人權重調整
│   ├── 5_策略教學.py                # 8 大策略說明文件
│   ├── 6_策略監控.py                # 策略歷史表現監控
│   └── 7_即時看盤.py                # TWSE MIS 即時報價(15-20s 延遲) + 自動刷新
│
├── strategies/                     # 八大評分策略
│   ├── base.py                     # BaseStrategy 抽象基類（score/details/_clamp）
│   ├── scorer.py                   # compute_composite_score 加權 + rank_stocks 排名
│   ├── runner.py                   # score_stock：8 策略 kwargs 映射 + 例外處理集中化
│   ├── ma_breakout.py              # 策略1：均線突破（MA5/10/20/60 突破+多頭排列）
│   ├── volume_price.py             # 策略2：量價齊揚（量比+連續天數+量能趨勢）
│   ├── relative_strength.py        # 策略3：相對強弱（RSI + 個股 vs 大盤超額報酬）
│   ├── institutional_flow.py       # 策略4：法人買賣超（投信/外資/自營商同步性）
│   ├── enhanced_technical.py       # 策略5：進階技術（KD/MACD/布林/OBV/乖離率）
│   ├── margin_analysis.py          # 策略6：融資融券（融資減+融券增=軋空訊號）
│   ├── us_market.py                # 策略7：美股連動（費半/TSM ADR/夜盤/匯率）
│   ├── shareholder.py              # 策略8：大戶籌碼（集保股權分散表集中度）
│   └── __init__.py
│
├── data/                            # 資料層：Parquet 快取 → yfinance → FinMind
│   ├── fetcher.py                   # façade，re-export 8 個子模組保持 import 相容
│   ├── cache.py                     # Parquet 快取底層（_cache_path / fetch_with_cache + 新鮮度檢查）
│   ├── finmind.py                   # FinMind API 基礎 + quota 監控
│   ├── prices.py                    # 價量（TWSE / TPEx JSON + yfinance 批次，cache key 含 asof）
│   ├── institutional.py             # 三大法人買賣超
│   ├── margin.py                    # 融資融券
│   ├── index.py                     # TAIEX / 櫃買指數 / 漲跌家數廣度
│   ├── us_market.py                 # 費半 / TSM / 夜盤/日盤期貨 / 美元台幣
│   ├── stock_info.py                # 股票清單 / 名稱查詢 / TDCC 集保
│   ├── realtime.py                  # TWSE MIS 即時報價(15-20s 延遲，免費)
│   └── __init__.py
│
├── utils/
│   ├── indicators.py               # 技術指標（MA/EMA/RSI/MACD/KD/布林/OBV/ATR/MDD）
│   ├── formatters.py               # 格式化工具（評級、顏色、數字）
│   ├── telegram_notify.py          # Telegram 推播（庫存提醒）
│   ├── line_notify.py              # LINE Notify（備用推播）
│   ├── auth.py                     # 密碼保護（APP_PASSWORD / APP_PASSWORDS）
│   ├── gist_store.py               # GitHub Gist 庫存持久化
│   ├── theme.py                    # 科技風格 UI 主題（自訂 CSS 注入）
│   ├── trading_calendar.py         # 台股交易日曆（最近交易日/盤中判定/yfinance 反查）
│   └── __init__.py
│
├── config/
│   ├── settings.py                 # 全域設定（權重、參數、閾值、FINMIND_TOKEN）
│   ├── tw_holidays.json            # 台股休市日（每年 12 月底更新次年）
│   └── __init__.py
│
├── scripts/
│   ├── daily_scan.py               # 每日排程掃描 + TG 推播 TOP 10（GitHub Actions）
│   ├── daily_local.py              # 每日本地分析 50 檔熱門科技股 + 存歷史 + TG 推播
│   ├── tg_bot.py                   # TG Bot 互動（/scan /stock /top /status）[Windows Task Scheduler 每 5 分鐘 --once 觸發]
│   └── test_scan.py                # 掃描流程整合測試（8 項：yfinance/策略/排名）
│
├── .github/workflows/
│   └── daily_scan.yml              # GitHub Actions 排程（平日 UTC 06:30）
│
├── .streamlit/
│   ├── config.toml                 # Streamlit 主題（深色底 #0a0f1a、主色 #00D2FF）
│   └── secrets.toml                # API keys（本地開發用，已 .gitignore）
│
├── ARCHITECTURE.md                 # 本文件
├── requirements.txt                # Python 套件依賴
└── .gitignore                      # 忽略 __pycache__、secrets.toml、*.parquet、.env
```

## 資料流程

```
使用者操作 Streamlit UI
        │
        ▼
   data/fetcher.py ──→ ① Parquet 快取（免費、TTL 12~24hr）
        │                ② yfinance 批次下載（免費、無限）
        │                ③ FinMind API（600次/hr）
        │                ④ TWSE/TPEx 備援（免費、無 token）
        ▼
   strategies/*.py ──→ 8 策略各自評分 0~100
        │
        ▼
   scorer.py ──→ 加權總分 → S/A/B/C/D 評級
        │
        ▼
   排名顯示 / TG 推播 / 庫存提醒
```

## 三階段價量抓取

```
Phase 1: Parquet 快取命中 → 零成本
Phase 2: yfinance 批次下載 .TW/.TWO → 免費無限（主力）
Phase 3: FinMind 逐檔補齊 → 消耗 API 額度（備援）
```

## 兩階段市場掃描（>200 檔時）

```
Phase A: 價量策略初篩全部股票（免費）→ 取 TOP 200
Phase B: 完整 8 策略（法人/融資/集保）→ 消耗 API 額度
```

## 八大策略

| # | 策略 | 檔案 | 核心邏輯 |
|---|------|------|----------|
| 1 | 均線突破 | `ma_breakout.py` | 股價站上 MA5/10/20/60 + 均線多頭排列 |
| 2 | 量價齊揚 | `volume_price.py` | 價漲量增共振 + 量比 + 連續天數 |
| 3 | 相對強弱 | `relative_strength.py` | RSI 動能 + 個股 vs 大盤超額報酬 |
| 4 | 法人買賣超 | `institutional_flow.py` | 投信/外資/自營商同步買超 + 連續天數 |
| 5 | 進階技術 | `enhanced_technical.py` | KD 黃金交叉 + MACD + 布林 + OBV + 乖離率 |
| 6 | 融資融券 | `margin_analysis.py` | 融資減少(籌碼沉澱) + 融券增加(軋空) |
| 7 | 美股連動 | `us_market.py` | 費半趨勢 + TSM ADR 折溢價 + 夜盤期貨 + 匯率 |
| 8 | 大戶籌碼 | `shareholder.py` | 集保 400 張以上持股集中度變化 |

## 外部 API 呼叫

### FinMind（主要資料源）
| 函數 | Dataset | 用途 |
|------|---------|------|
| `check_finmind_usage()` | `/v2/user_info` | 查詢 API 剩餘額度 |
| `fetch_stock_prices()` | `TaiwanStockPrice` | 台股日K |
| `fetch_taiex()` | `TaiwanVariousIndicators5Seconds` | 加權指數 |
| `fetch_institutional_investors()` | `TaiwanStockInstitutionalInvestorsBuySell` | 三大法人 |
| `fetch_tdcc_holders()` | `TaiwanStockHoldingSharesPer` | 集保股權分散表 |
| `fetch_night_futures()` | `TaiwanFuturesDaily` (after_market) | 夜盤期貨 |
| `fetch_day_futures()` | `TaiwanFuturesDaily` (position) | 日盤期貨 |
| `fetch_margin_data()` | `TaiwanStockMarginPurchaseShortSale` | 融資融券 |
| `fetch_stock_list()` | `TaiwanStockInfo` | 股票清單 |

### yfinance（免費備援）
| 函數 | 標的 | 用途 |
|------|------|------|
| `_fetch_prices_yfinance_batch()` | `.TW` / `.TWO` | 台股價量（主力來源） |
| `_fetch_us_yfinance()` | `TSM`, `^SOX` | 美股資料 |
| `_fetch_taiex_yfinance()` | `^TWII` | 加權指數備援 |
| `_get_usd_twd()` | `TWD=X` | USD/TWD 匯率 |

### Telegram Bot API
| 檔案 | 函數 | 用途 |
|------|------|------|
| `utils/telegram_notify.py` | `send()` | 庫存提醒（讀 Streamlit secrets） |
| `scripts/daily_scan.py` | `send_telegram()` | 每日 TOP 10 推播（讀環境變數） |

### GitHub Gist API
| 函數 | 用途 |
|------|------|
| `gist_store.load()` | 讀取庫存 JSON |
| `gist_store.save()` | 儲存庫存 JSON |

### TWSE / TPEx（備援，免費無 token）
| 函數 | 用途 |
|------|------|
| `fetch_twse_daily()` | 個股月K |
| `_fetch_institutional_twse()` | 三大法人 |
| `_fetch_margin_twse()` | 融資融券 |
| `_fetch_stock_list_twse()` | 股票清單 |
| `fetch_tpex_daily()` | 上櫃月K |

## 關鍵函數索引

### data/fetcher.py
| 函數 | 說明 |
|------|------|
| `_fetch_finmind(dataset, params)` | 所有 FinMind API 呼叫的核心 |
| `fetch_with_cache(dataset, params, ttl_hours)` | Parquet 快取包裝層 |
| `_parse_yf_single(data, ticker, stock_id)` | 解析 yfinance MultiIndex（支援新舊版） |
| `_normalize_price_df(df)` | 統一價量 DataFrame 欄位格式 |
| `fetch_stock_prices_batch(stock_ids, ...)` | 三階段批次抓取 |

### utils/indicators.py
| 函數 | 說明 |
|------|------|
| `moving_average(series, period)` | 簡單移動平均 |
| `exponential_moving_average(series, period)` | 指數移動平均 |
| `rsi(series, period)` | 相對強弱指標 |
| `macd(series, fast, slow, signal)` | MACD + Signal + Histogram |
| `stochastic_kd(high, low, close, k, d)` | KD 隨機指標 |
| `bollinger_bands(series, period, std)` | 布林通道 |
| `obv(close, volume)` | 能量潮 |
| `atr(high, low, close, period)` | 平均真實波幅 |
| `volatility_risk(high, low, close)` | ATR% 風險等級 |
| `max_drawdown(close)` | 最大回撤 |

## 環境設定

### Streamlit Cloud（網頁部署）
```toml
# .streamlit/secrets.toml（在 Streamlit Cloud Settings → Secrets 設定）
FINMIND_TOKEN = "eyJ..."
TELEGRAM_BOT_TOKEN = "7123456789:AAH..."
TELEGRAM_CHAT_ID = "-100..."
GITHUB_TOKEN = "ghp_..."
APP_PASSWORD = "your_password"
```

### GitHub Actions（每日排程）
```
Repository Secrets:
  FINMIND_TOKEN
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
```

### Windows Task Scheduler（TG Bot 輪詢）

任務名稱：`台股TG Bot`
頻率：每 5 分鐘
指令：
```
conhost.exe --headless wsl.exe -e bash -c "python3 /mnt/c/Users/User/tw-stock-screener/scripts/tg_bot.py --once >> /tmp/tg_bot.log 2>&1"
```
- 以 `conhost --headless` 包裝，避免彈出命令列視窗
- `tg_bot.py --once` 每次執行一次即退出，非常駐 Bot
- Log：`/tmp/tg_bot.log`

**規則**：之後若要新增 Windows 端排程呼叫 WSL/CMD/PowerShell，一律採背景無視窗模式（`conhost --headless`、任務設定「不論使用者登入與否均執行」、或改用 WSL cron/systemd timer），不可彈出黑窗。

### 快取目錄
```
~/.tw-stock-screener/cache/          # Parquet 快取檔
~/.tw-stock-screener/cache/stock_list.parquet   # 股票清單快取
```

## 自動權重系統

市場溫度由 S+A 級佔比決定（使用固定 DEFAULT_WEIGHTS 計算，避免迴圈偏差）：

| 溫度 | S+A 佔比 | 策略傾向 |
|------|----------|----------|
| 過熱 | ≥40% | 偏防禦（法人+融資+技術） |
| 偏熱 | ≥25% | 順勢操作（均線+量價） |
| 溫和 | ≥15% | 均衡配置 |
| 偏冷 | ≥5% | 偏價值（法人+技術+融資） |
| 極冷 | <5% | 關注外資動向（法人+融資+美股） |

## 資料新鮮度策略(避免顯示舊資料)

**雙保險機制**:

1. **mtime + TTL**(`data/cache.py`):快取檔超過 `CACHE_TTL_PRICE_HOURS`(預設 3 小時)直接判失效
2. **資料截止日檢查**(`_is_data_fresh`):若 cache 內 `date` 欄最大值 < 「最近交易日」(由 `utils/trading_calendar.latest_trading_day()` 計算),也判失效

**Cache key 加 asof**(`data/prices.py`):`fetch_stock_prices_batch` 將「最近交易日」放進 cache key,確保每天首次呼叫一定是新 key,跨日不會誤命中。

**主頁強制刷新按鈕**(`app.py`):一鍵清掉 TaiwanStockPrice / Institutional / Margin / breadth / taiex 等 parquet + `st.cache_data.clear()`。

## 即時資料層(`data/realtime.py`)

**TWSE MIS API**:`https://mis.twse.com.tw/stock/api/getStockInfo.jsp`
- 完全免費、無需 token
- 延遲 ~15-20 秒
- 同時送 `tse_xxx.tw|otc_xxx.tw` 一次取上市/上櫃
- 提供:現價、開高低、昨收、漲跌、成交量、五檔買賣、成交時間
- 也支援大盤指數(`t00`=加權、`o00`=櫃買)

**使用場景**:
| 頁面 | 用途 |
|------|------|
| `pages/7_即時看盤.py` | 多檔報價卡片牆 + 自動刷新(3-60 秒) |
| `pages/2_我的庫存.py` | 「即時損益」區塊,顯示總市值/未實現損益/個股漲跌 |

**注意事項**:
- TWSE MIS 對單 IP 有頻率上限,建議刷新 ≥5 秒
- 多人同時看 = 多倍呼叫,Streamlit Cloud 上要小心
- 盤後仍會回傳「最後一筆撮合」,用 `is_trading_now()` 判斷盤中/盤後

## 排版增強套件(2026-04 引入)

| 套件 | 用途 | 使用頁面 |
|------|------|----------|
| `streamlit-elements` | 可拖拉/resize 的 dashboard grid(MUI) | `pages/7_即時看盤.py`「可拖拉」模式 |
| `streamlit-aggrid` | 凍結欄位、排序、條件式變色的高階表格 | `pages/7_即時看盤.py` 詳細表、`pages/2_我的庫存.py` 即時損益表 |
| `streamlit-extras` | tagger / badge 等小元件 | `app.py` 主頁狀態徽章 |
| `streamlit-autorefresh` | 全頁自動刷新(fragment 不可用時的 fallback) | `pages/7_即時看盤.py`、`pages/2_我的庫存.py` |
| `st.fragment(run_every=N)` | Streamlit ≥1.33 內建,局部刷新避免整頁重畫 | `pages/7_即時看盤.py` 主資料區塊 |

**降級策略**:每個 import 都用 try/except,缺套件時自動 fallback 到原始 `st.dataframe` / 純 columns 排版,部署環境有缺裝也不會壞。

## 特殊設計備註

- `daily_scan.py` 直接用 `requests.post` 發 Telegram，不用 `utils/telegram_notify`，因為 GitHub Actions 沒有 `st.secrets`
- `daily_scan.py` 融資融券和集保權重設為 0，避免缺資料影響排名
- `pages/4_策略設定.py` 直接修改 `config.settings` 模組屬性（`cfg.RSI_PERIOD = ...`），只在同一 session 內生效
- 科技業快捷預設用 `session_state` 控制 multiselect 值，避免 checkbox 切換時 Streamlit default 衝突
- 超過 200 檔時統一用成交量篩選 TOP 200，再進 Phase B 完整分析
