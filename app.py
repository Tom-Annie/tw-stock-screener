"""
台股智慧選股系統 - 主頁面
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(
    page_title="台股智慧選股系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== 密碼保護 =====
from utils.auth import require_auth
require_auth()

# ===== 側邊欄 =====
st.sidebar.title("📈 台股智慧選股")
st.sidebar.markdown("---")

# 日期設定
end_date = st.sidebar.date_input("分析截止日", datetime.now())
end_date_str = end_date.strftime("%Y-%m-%d")

st.sidebar.markdown("### 策略權重")

# --- 自動權重預設組合 ---
_AUTO_WEIGHT_PROFILES = {
    "過熱": {"ma_breakout": 8, "volume_price": 6, "relative_strength": 12,
             "institutional_flow": 20, "enhanced_technical": 15,
             "margin_analysis": 18, "us_market": 12, "shareholder": 9},
    "偏熱": {"ma_breakout": 20, "volume_price": 18, "relative_strength": 15,
             "institutional_flow": 12, "enhanced_technical": 10,
             "margin_analysis": 5, "us_market": 10, "shareholder": 10},
    "溫和": {"ma_breakout": 15, "volume_price": 12, "relative_strength": 15,
             "institutional_flow": 15, "enhanced_technical": 12,
             "margin_analysis": 8, "us_market": 10, "shareholder": 13},
    "偏冷": {"ma_breakout": 8, "volume_price": 8, "relative_strength": 10,
             "institutional_flow": 20, "enhanced_technical": 18,
             "margin_analysis": 15, "us_market": 12, "shareholder": 9},
    "極冷": {"ma_breakout": 5, "volume_price": 5, "relative_strength": 10,
             "institutional_flow": 20, "enhanced_technical": 15,
             "margin_analysis": 18, "us_market": 17, "shareholder": 10},
}
_WEIGHT_KEYS = ["ma_breakout", "volume_price", "relative_strength",
                "institutional_flow", "enhanced_technical",
                "margin_analysis", "us_market", "shareholder"]
_WEIGHT_LABELS = ["突破均線", "量價齊揚", "相對強弱", "法人籌碼",
                  "技術綜合", "融資融券", "美股連動", "大戶籌碼"]

weight_mode = st.sidebar.radio(
    "權重模式",
    ["自動（依市場溫度）", "手動調整"],
    help="自動模式會根據上次分析的市場溫度調整權重"
)

if weight_mode == "手動調整":
    w1 = st.sidebar.slider("突破均線", 0, 100, 15, key="w1")
    w2 = st.sidebar.slider("量價齊揚", 0, 100, 12, key="w2")
    w3 = st.sidebar.slider("相對強弱", 0, 100, 15, key="w3")
    w4 = st.sidebar.slider("法人籌碼", 0, 100, 15, key="w4")
    w5 = st.sidebar.slider("技術綜合", 0, 100, 12, key="w5")
    w6 = st.sidebar.slider("融資融券", 0, 100, 8, key="w6")
    w7 = st.sidebar.slider("美股連動", 0, 100, 10, key="w7")
    w8 = st.sidebar.slider("大戶籌碼", 0, 100, 13, key="w8")
    _raw = [w1, w2, w3, w4, w5, w6, w7, w8]
else:
    # 自動模式：根據上次分析的市場溫度選擇權重
    _prev_temp = st.session_state.get("market_temp_label", "溫和")
    _auto_profile = _AUTO_WEIGHT_PROFILES.get(_prev_temp, _AUTO_WEIGHT_PROFILES["溫和"])
    _raw = [_auto_profile[k] for k in _WEIGHT_KEYS]
    st.sidebar.caption(f"目前溫度：**{_prev_temp}**")
    # 顯示自動權重（唯讀）
    _weight_text = " | ".join(f"{l}:{v}" for l, v in zip(_WEIGHT_LABELS, _raw))
    st.sidebar.caption(_weight_text)

total_w = sum(_raw)
weights = {k: v / max(total_w, 1) for k, v in zip(_WEIGHT_KEYS, _raw)}

top_n = st.sidebar.slider("顯示前 N 檔", 10, 100, 30)

st.sidebar.markdown("---")
st.sidebar.markdown("### FinMind API Token")
token_input = st.sidebar.text_input("Token (可選，提高額度)", type="password")
if token_input:
    import config.settings as cfg
    cfg.FINMIND_TOKEN = token_input

# 顯示 FinMind 剩餘額度
from data.fetcher import check_finmind_usage
from config.settings import FINMIND_TOKEN as _current_token
usage = check_finmind_usage()
if usage:
    used, limit = usage["used"], usage["limit"]
    remaining = max(limit - used, 0)
    pct = used / max(limit, 1)
    color = "🟢" if pct < 0.6 else ("🟡" if pct < 0.85 else "🔴")
    st.sidebar.caption(f"{color} API 額度：{used}/{limit}（剩餘 {remaining}）")
    st.sidebar.progress(min(pct, 1.0))
elif _current_token:
    st.sidebar.caption("⚠️ 無法查詢額度（Token 可能無效）")
else:
    st.sidebar.caption("ℹ️ 未設定 Token（免費 300 次/hr）")

st.sidebar.markdown("---")
st.sidebar.markdown("### 外部連結")
link_site = st.sidebar.selectbox("點擊股票代碼開啟", [
    "玩股網", "Yahoo 股市", "Google Finance", "Goodinfo", "CMoney"
])

LINK_TEMPLATES = {
    "玩股網": "https://www.wantgoo.com/stock/{sid}",
    "Yahoo 股市": "https://tw.stock.yahoo.com/quote/{sid}.TW",
    "Google Finance": "https://www.google.com/finance/quote/{sid}:TPE",
    "Goodinfo": "https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={sid}",
    "CMoney": "https://www.cmoney.tw/finance/{sid}/f00025",
}

def make_link(stock_id: str) -> str:
    """產生外部連結 URL"""
    tpl = LINK_TEMPLATES.get(link_site, LINK_TEMPLATES["玩股網"])
    return tpl.format(sid=stock_id)

st.sidebar.markdown("---")
st.sidebar.caption("資料來源：FinMind / 台灣證交所")

# ===== 主頁面 =====
st.title("🇹🇼 台股智慧選股系統")
st.markdown("結合 **八大策略** 的綜合選股平台（突破均線/量價齊揚/相對強弱/法人籌碼/技術綜合/融資融券/美股連動/大戶籌碼）")

st.markdown("---")

# 掃描設定
col_mode, col_industry = st.columns([1, 2])
with col_mode:
    scan_mode = st.radio(
        "掃描模式",
        ["快速掃描 (熱門 200 檔)", "完整掃描 (全市場)"],
        help="快速掃描只分析成交量前 200 大的股票，速度快很多"
    )

with col_industry:
    # 預載產業清單
    from config.settings import CACHE_DIR
    _industry_list = []
    _ind_cache = CACHE_DIR / "stock_list.parquet"
    _sl_cached = pd.DataFrame()
    if _ind_cache.exists():
        try:
            _sl_cached = pd.read_parquet(_ind_cache)
            if "industry" in _sl_cached.columns:
                _industry_list = sorted(
                    i for i in _sl_cached["industry"].dropna().unique()
                    if i and i not in ("ETF", "存託憑證", "創新板股票", "創新版股票")
                )
        except Exception:
            pass

    # 科技業快捷預設
    _TECH_INDUSTRIES = [
        "半導體業", "光電業", "電子零組件業", "電器電纜",
        "電腦及週邊設備業", "電子通路業", "通信網路業",
        "資訊服務業", "數位雲端",
    ]
    _tech_default = [i for i in _TECH_INDUSTRIES if i in _industry_list]

    use_tech_preset = st.checkbox("科技業快捷（上中下游）", value=True,
                                  help="預選半導體、光電、電子零組件、通信網路等科技產業")

    # 用 session_state 控制 default，避免 checkbox 切換時 default 衝突
    _ms_key = "industry_multiselect"
    if use_tech_preset:
        # 勾選時：若目前沒有選任何產業，帶入科技業預設
        if _ms_key not in st.session_state or not st.session_state[_ms_key]:
            st.session_state[_ms_key] = _tech_default
    else:
        # 取消勾選時：如果目前選的跟科技預設完全一樣，才清空（避免覆蓋手動選擇）
        if st.session_state.get(_ms_key) == _tech_default:
            st.session_state[_ms_key] = []

    selected_industries = st.multiselect(
        "篩選產業（不選 = 全部）",
        options=_industry_list,
        key=_ms_key,
        help="可選擇一個或多個產業，只分析這些產業的股票"
    )

# 預估 token 消耗
_est_stock_count = 0
if selected_industries and not _sl_cached.empty and "industry" in _sl_cached.columns:
    _est_stock_count = len(_sl_cached[
        _sl_cached["industry"].isin(selected_industries) &
        ~_sl_cached["stock_id"].isna()
    ])
elif not _sl_cached.empty and "industry" in _sl_cached.columns:
    _est_stock_count = len(_sl_cached[
        ~_sl_cached["industry"].isin(["ETF", "存託憑證", "創新板股票", "創新版股票"])
    ])
elif not _sl_cached.empty:
    _est_stock_count = len(_sl_cached)

# 超過 200 檔會用成交量篩到 200，所以實際下載/分析上限 200
_est_actual = min(_est_stock_count, 200)
_est_price_fallback = max(int(_est_actual * 0.1), 5)  # ~10% yfinance miss → FinMind fallback
_est_fixed = 5  # stock list + TAIEX + SOX + TSM + night futures
_est_vol_query = 1 if _est_stock_count > 200 else 0  # 成交量排名查詢
_est_institutional = _est_actual
_est_margin = _est_actual
_est_tdcc = _est_actual  # TDCC 集保：每檔 1 call
_est_phase_b = _est_actual
_est_total = _est_fixed + _est_vol_query + _est_price_fallback + _est_institutional + _est_margin + _est_tdcc

_quota_remaining = None
if usage:
    _quota_remaining = max(usage["limit"] - usage["used"], 0)

_quota_status = ""
if _quota_remaining is not None:
    if _est_total > _quota_remaining:
        _quota_status = f" | 剩餘 {_quota_remaining} ⚠️ **額度可能不足**"
    else:
        _quota_status = f" | 剩餘 {_quota_remaining} ✅"
st.caption(
    f"預估分析 **{_est_stock_count}** 檔"
    f"（Phase B: {_est_phase_b} 檔）"
    f"→ 約需 **{_est_total}** 次 API 呼叫{_quota_status}"
)

run_btn = st.button("🚀 開始分析", type="primary", use_container_width=True)

if run_btn:
    from data.fetcher import (fetch_stock_list, fetch_stock_prices,
                              fetch_stock_prices_batch,
                              fetch_institutional_investors,
                              fetch_institutional_batch,
                              fetch_margin_batch,
                              fetch_us_stock, fetch_night_futures,
                              fetch_day_futures, fetch_tdcc_holders,
                              fetch_taiex)
    import time
    from strategies.ma_breakout import MABreakoutStrategy
    from strategies.volume_price import VolumePriceStrategy
    from strategies.relative_strength import RelativeStrengthStrategy
    from strategies.institutional_flow import InstitutionalFlowStrategy
    from strategies.enhanced_technical import EnhancedTechnicalStrategy
    from strategies.margin_analysis import MarginAnalysisStrategy
    from strategies.us_market import USMarketStrategy
    from strategies.shareholder import ShareholderStrategy
    from strategies.scorer import rank_stocks, get_strategy_summary

    start_date = (end_date - timedelta(days=100)).strftime("%Y-%m-%d")
    is_quick = "快速" in scan_mode

    progress = st.progress(0, text="載入股票清單...")
    status_text = st.empty()

    # Step 1: 取得股票清單
    try:
        stock_list = fetch_stock_list()
        if stock_list.empty:
            st.error("無法取得股票清單，請確認網路連線或 API Token")
            st.stop()
    except Exception as e:
        st.error(f"取得股票清單失敗: {e}")
        st.stop()

    # 產業篩選
    if selected_industries:
        stock_list = stock_list[stock_list["industry"].isin(selected_industries)].copy()
        if stock_list.empty:
            st.error("所選產業沒有符合的股票")
            st.stop()
        status_text.info(f"已篩選 {', '.join(selected_industries)}，共 {len(stock_list)} 檔")

    # 超過 200 檔時，用成交量篩選 TOP 200（節省 API 額度）
    target_stocks = stock_list["stock_id"].tolist()
    if len(target_stocks) > 200:
        status_text.info(f"共 {len(target_stocks)} 檔，篩選成交量前 200 大...")
        try:
            recent_date = (end_date - timedelta(days=5)).strftime("%Y-%m-%d")
            recent_prices = fetch_stock_prices(start_date=recent_date,
                                               end_date=end_date_str)
            if not recent_prices.empty:
                latest = recent_prices.sort_values("date").groupby("stock_id").tail(1)
                latest = latest[latest["stock_id"].isin(target_stocks)]
                top_vol = latest.nlargest(200, "volume")["stock_id"].tolist()
                target_stocks = top_vol
        except Exception:
            pass

        if len(target_stocks) > 200:
            target_stocks = target_stocks[:200]

    total_stocks = len(target_stocks)
    status_text.info(f"將分析 {total_stocks} 檔股票")
    progress.progress(5, text=f"準備下載 {total_stocks} 檔價量資料...")

    # Step 2: 分批抓取價量資料
    def update_progress(current, total, msg):
        pct = 5 + int((current / max(total, 1)) * 45)
        progress.progress(min(pct, 50), text=msg)

    try:
        all_prices = fetch_stock_prices_batch(
            target_stocks, start_date, end_date_str,
            progress_callback=update_progress
        )
        if all_prices.empty:
            st.error("無法取得價量資料，請稍後再試或檢查 API Token")
            st.stop()
        status_text.info(f"已下載 {all_prices['stock_id'].nunique()} 檔股票資料")
    except Exception as e:
        st.error(f"取得價量資料失敗: {e}")
        st.stop()

    # Step 3: 取得美股與夜盤資料 (全市場共用，只抓一次)
    progress.progress(55, text="下載美股/夜盤/大盤資料...")
    us_start = (end_date - timedelta(days=40)).strftime("%Y-%m-%d")
    sox_df = pd.DataFrame()
    tsm_df = pd.DataFrame()
    night_df = pd.DataFrame()
    day_futures_df = pd.DataFrame()
    tsmc_close = 0.0
    taiex_close = None

    try:
        sox_df = fetch_us_stock("^SOX", us_start, end_date_str)
    except Exception:
        pass
    try:
        tsm_df = fetch_us_stock("TSM", us_start, end_date_str)
    except Exception:
        pass
    try:
        night_df = fetch_night_futures(us_start, end_date_str)
    except Exception:
        pass
    try:
        day_futures_df = fetch_day_futures(us_start, end_date_str)
    except Exception:
        pass

    if not all_prices.empty:
        tsmc_prices = all_prices[all_prices["stock_id"] == "2330"]
        if not tsmc_prices.empty:
            tsmc_close = tsmc_prices.sort_values("date")["close"].iloc[-1]

    try:
        taiex_df = fetch_taiex(start_date, end_date_str)
        if not taiex_df.empty:
            taiex_df = taiex_df.sort_values("date")
            if "close" in taiex_df.columns:
                taiex_close = taiex_df["close"]
            elif "price" in taiex_df.columns:
                taiex_close = taiex_df["price"]
    except Exception:
        pass

    # Step 4: 初始化策略
    ma_strategy = MABreakoutStrategy()
    vp_strategy = VolumePriceStrategy()
    rs_strategy = RelativeStrengthStrategy()
    inst_strategy = InstitutionalFlowStrategy()
    et_strategy = EnhancedTechnicalStrategy()
    margin_strategy = MarginAnalysisStrategy()
    us_strategy = USMarketStrategy()
    sh_strategy = ShareholderStrategy()

    # ============================================================
    # Step 5: 完整掃描兩階段策略（節省 FinMind API 額度）
    #   Phase A: 用純價量策略（不耗 FinMind）對全部股票初篩
    #   Phase B: 只對 TOP 200 抓法人/融資/大戶，完整 8 策略評分
    # 快速掃描（<=200 檔）直接跑 Phase B
    # ============================================================

    valid_stocks = stock_list[
        stock_list["stock_id"].isin(target_stocks) &
        stock_list["stock_id"].isin(all_prices["stock_id"].unique())
    ]

    # 判斷是否需要兩階段
    need_two_phase = len(valid_stocks) > 200

    if need_two_phase:
        # === Phase A: 純價量策略初篩 ===
        progress.progress(58, text=f"Phase A: 價量策略初篩 {len(valid_stocks)} 檔...")
        status_text.info(f"完整掃描：先用價量策略篩選 {len(valid_stocks)} 檔 → TOP 200")

        phase_a_scores = []
        total_a = len(valid_stocks)
        for idx, (_, stock) in enumerate(valid_stocks.iterrows()):
            sid = stock["stock_id"]
            if idx % 50 == 0:
                pct = 58 + int((idx / max(total_a, 1)) * 12)
                progress.progress(min(pct, 70),
                                  text=f"初篩中... ({idx}/{total_a})")

            price_df = all_prices[all_prices["stock_id"] == sid].copy()
            if len(price_df) < 60:
                continue
            price_df = price_df.sort_values("date").reset_index(drop=True)

            try:
                s1 = ma_strategy.score(price_df)
            except Exception:
                s1 = 0
            try:
                s2 = vp_strategy.score(price_df)
            except Exception:
                s2 = 0
            try:
                rs_kwargs = {}
                if taiex_close is not None and len(taiex_close) >= 20:
                    rs_kwargs["index_close"] = taiex_close
                s3 = rs_strategy.score(price_df, **rs_kwargs)
            except Exception:
                s3 = 0
            try:
                s4 = et_strategy.score(price_df)
            except Exception:
                s4 = 0
            try:
                s5 = us_strategy.score(
                    price_df, sox_df=sox_df, tsm_df=tsm_df,
                    tsmc_close=tsmc_close, night_df=night_df,
                    day_futures_df=day_futures_df)
            except Exception:
                s5 = 0

            # 加權平均（用 5 策略的權重重新歸一化）
            w_sum = (weights["ma_breakout"] + weights["volume_price"] +
                     weights["relative_strength"] + weights["enhanced_technical"] +
                     weights["us_market"])
            if w_sum > 0:
                preliminary = (
                    s1 * weights["ma_breakout"] +
                    s2 * weights["volume_price"] +
                    s3 * weights["relative_strength"] +
                    s4 * weights["enhanced_technical"] +
                    s5 * weights["us_market"]
                ) / w_sum
            else:
                preliminary = (s1 + s2 + s3 + s4 + s5) / 5

            phase_a_scores.append({"stock_id": sid, "preliminary_score": preliminary})

        # 取 TOP 200
        phase_a_df = pd.DataFrame(phase_a_scores)
        top200_ids = phase_a_df.nlargest(200, "preliminary_score")["stock_id"].tolist()

        # 縮減 valid_stocks 為 TOP 200
        valid_stocks = valid_stocks[valid_stocks["stock_id"].isin(top200_ids)]
        status_text.info(f"初篩完成，從 {total_a} 檔中選出 TOP {len(valid_stocks)} 進入完整分析")

    # === Phase B: 完整 8 策略（只對 <=200 檔抓法人/融資）===
    progress.progress(70, text="下載法人籌碼資料...")
    inst_start = (end_date - timedelta(days=30)).strftime("%Y-%m-%d")
    phase_b_ids = valid_stocks["stock_id"].tolist()

    all_institutional = pd.DataFrame()
    def update_inst_progress(current, total, msg):
        pct = 70 + int((current / max(total, 1)) * 8)
        progress.progress(min(pct, 78), text=msg)

    try:
        all_institutional = fetch_institutional_batch(
            phase_b_ids, inst_start, end_date_str,
            progress_callback=update_inst_progress
        )
    except Exception as e:
        st.warning(f"法人籌碼資料取得失敗: {e}，該策略將以0分計算")

    progress.progress(78, text="下載融資融券資料...")
    all_margin = pd.DataFrame()
    def update_margin_progress(current, total, msg):
        pct = 78 + int((current / max(total, 1)) * 5)
        progress.progress(min(pct, 83), text=msg)

    try:
        all_margin = fetch_margin_batch(
            phase_b_ids, inst_start, end_date_str,
            progress_callback=update_margin_progress
        )
    except Exception as e:
        st.warning(f"融資融券資料取得失敗: {e}，該策略將以0分計算")

    progress.progress(83, text="計算完整策略分數...")

    # Step 6: 逐股計算完整 8 策略
    results = []
    total = len(valid_stocks)

    for idx, (_, stock) in enumerate(valid_stocks.iterrows()):
        sid = stock["stock_id"]

        if idx % 20 == 0:
            pct = 83 + int((idx / max(total, 1)) * 12)
            progress.progress(min(pct, 95),
                              text=f"完整分析... ({idx}/{total}) {sid}")

        price_df = all_prices[all_prices["stock_id"] == sid].copy()
        if len(price_df) < 60:
            continue
        price_df = price_df.sort_values("date").reset_index(drop=True)

        # 計算各策略分數
        try:
            ma_score = ma_strategy.score(price_df)
            ma_detail = ma_strategy.details(price_df)
        except Exception:
            ma_score, ma_detail = 0, {"signal": "計算錯誤"}

        try:
            vp_score = vp_strategy.score(price_df)
            vp_detail = vp_strategy.details(price_df)
        except Exception:
            vp_score, vp_detail = 0, {"signal": "計算錯誤"}

        try:
            rs_kwargs = {}
            if taiex_close is not None and len(taiex_close) >= 20:
                rs_kwargs["index_close"] = taiex_close
            rs_score = rs_strategy.score(price_df, **rs_kwargs)
            rs_detail = rs_strategy.details(price_df, **rs_kwargs)
        except Exception:
            rs_score, rs_detail = 0, {"signal": "計算錯誤"}

        try:
            inst_df = pd.DataFrame()
            if not all_institutional.empty:
                inst_df = all_institutional[
                    all_institutional["stock_id"] == sid
                ].copy()

            inst_score = inst_strategy.score(price_df, institutional_df=inst_df)
            inst_detail = inst_strategy.details(price_df, institutional_df=inst_df)
        except Exception:
            inst_score, inst_detail = 0, {"signal": "計算錯誤"}

        try:
            et_score = et_strategy.score(price_df)
            et_detail = et_strategy.details(price_df)
        except Exception:
            et_score, et_detail = 0, {"signal": "計算錯誤"}

        try:
            margin_df = pd.DataFrame()
            if not all_margin.empty:
                margin_df = all_margin[
                    all_margin["stock_id"] == sid
                ].copy()

            margin_score = margin_strategy.score(price_df, margin_df=margin_df)
            margin_detail = margin_strategy.details(price_df, margin_df=margin_df)
        except Exception:
            margin_score, margin_detail = 0, {"signal": "計算錯誤"}

        try:
            us_score = us_strategy.score(
                price_df,
                sox_df=sox_df, tsm_df=tsm_df, tsmc_close=tsmc_close,
                night_df=night_df, day_futures_df=day_futures_df
            )
            us_detail = us_strategy.details(
                price_df,
                sox_df=sox_df, tsm_df=tsm_df, tsmc_close=tsmc_close,
                night_df=night_df, day_futures_df=day_futures_df
            )
        except Exception:
            us_score, us_detail = 0, {"signal": "計算錯誤"}

        try:
            tdcc_df = fetch_tdcc_holders(sid)
            sh_score = sh_strategy.score(price_df, tdcc_df=tdcc_df)
            sh_detail = sh_strategy.details(price_df, tdcc_df=tdcc_df)
            if idx % 10 == 9:
                time.sleep(0.5)
        except Exception:
            sh_score, sh_detail = 0, {"signal": "計算錯誤"}

        name = stock.get("name", sid)
        industry = stock.get("industry", "")
        latest_close = price_df["close"].iloc[-1]
        latest_vol = price_df["volume"].iloc[-1]

        # 波動率風險指標
        from utils.indicators import volatility_risk
        try:
            vrisk = volatility_risk(price_df["high"], price_df["low"], price_df["close"])
        except Exception:
            vrisk = {"atr_pct": 0, "risk_level": "N/A", "atr_trend": "N/A"}

        results.append({
            "stock_id": sid,
            "name": name,
            "industry": industry,
            "close": round(latest_close, 2),
            "volume": int(latest_vol),
            "ma_breakout_score": round(ma_score, 1),
            "volume_price_score": round(vp_score, 1),
            "relative_strength_score": round(rs_score, 1),
            "institutional_flow_score": round(inst_score, 1),
            "enhanced_technical_score": round(et_score, 1),
            "margin_analysis_score": round(margin_score, 1),
            "us_market_score": round(us_score, 1),
            "shareholder_score": round(sh_score, 1),
            "risk_level": vrisk["risk_level"],
            "atr_pct": vrisk["atr_pct"],
            "atr_trend": vrisk["atr_trend"],
            "ma_signal": ma_detail.get("signal", ""),
            "vp_signal": vp_detail.get("signal", ""),
            "rs_signal": rs_detail.get("signal", ""),
            "inst_signal": inst_detail.get("signal", ""),
            "et_signal": et_detail.get("signal", ""),
            "margin_signal": margin_detail.get("signal", ""),
            "us_signal": us_detail.get("signal", ""),
            "sh_signal": sh_detail.get("signal", ""),
        })

    progress.progress(98, text="產生排名...")

    # Step 6: 排名（用使用者選擇的權重）
    ranked = rank_stocks(results, weights)

    # Step 6b: 用固定基準權重計算市場溫度（避免迴圈偏差）
    # 溫度計必須用固定權重，否則「權重→溫度→權重」會來回跳動
    from config.settings import DEFAULT_WEIGHTS as _BASE_W
    _base_ranked = rank_stocks(results, _BASE_W)
    st.session_state["_base_ranked_for_temp"] = _base_ranked

    progress.progress(100, text="完成!")

    # 顯示實際 API 消耗（usage 在頁面載入時取得，可能為 None）
    _usage_before = usage  # 分析前快照
    _usage_after = check_finmind_usage()
    if _usage_after and _usage_before:
        _actual_used = _usage_after["used"] - _usage_before["used"]
        _remaining_after = max(_usage_after["limit"] - _usage_after["used"], 0)
        st.success(
            f"分析完成！本次消耗 **{_actual_used}** 次 API 呼叫"
            f"（剩餘 {_remaining_after}/{_usage_after['limit']}）"
        )
    elif _usage_after:
        _remaining_after = max(_usage_after["limit"] - _usage_after["used"], 0)
        st.success(f"分析完成！API 剩餘 {_remaining_after}/{_usage_after['limit']}")

    if ranked.empty:
        st.warning("沒有符合條件的股票")
        st.stop()

    # 保存到 session state
    st.session_state["ranked"] = ranked
    st.session_state["analysis_date"] = end_date_str
    st.session_state["analysis_industries"] = selected_industries

# ===== 顯示結果 =====
if "ranked" in st.session_state:
    ranked = st.session_state["ranked"]
    analysis_date = st.session_state.get("analysis_date", "")

    _ind_label = st.session_state.get("analysis_industries", [])
    _ind_text = f" — {', '.join(_ind_label)}" if _ind_label else ""
    st.markdown(f"### 分析結果 ({analysis_date}{_ind_text})")

    # 摘要統計
    from strategies.scorer import get_strategy_summary
    summary = get_strategy_summary(ranked)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("分析股票數", summary.get("total_stocks", 0))
    col2.metric("S級 (>80分)", summary.get("s_grade", 0))
    col3.metric("A級 (65-80分)", summary.get("a_grade", 0))
    col4.metric("平均分數", summary.get("avg_composite", 0))

    # ===== 市場溫度計（用固定基準權重，避免迴圈偏差）=====
    import plotly.graph_objects as _go
    _temp_ranked = st.session_state.get("_base_ranked_for_temp", ranked)
    total = len(_temp_ranked)
    if total > 0:
        s_pct = len(_temp_ranked[_temp_ranked["grade"] == "S"]) / total * 100
        a_pct = len(_temp_ranked[_temp_ranked["grade"] == "A"]) / total * 100
        b_pct = len(_temp_ranked[_temp_ranked["grade"] == "B"]) / total * 100
        c_pct = len(_temp_ranked[_temp_ranked["grade"] == "C"]) / total * 100
        d_pct = len(_temp_ranked[_temp_ranked["grade"] == "D"]) / total * 100
        hot_pct = s_pct + a_pct  # S+A 佔比 = 市場熱度（固定權重計算）

        # 溫度判斷
        if hot_pct >= 40:
            temp_label, temp_color = "過熱", "#EF5350"
        elif hot_pct >= 25:
            temp_label, temp_color = "偏熱", "#FF9800"
        elif hot_pct >= 15:
            temp_label, temp_color = "溫和", "#4CAF50"
        elif hot_pct >= 5:
            temp_label, temp_color = "偏冷", "#2196F3"
        else:
            temp_label, temp_color = "極冷", "#9E9E9E"

        # 儲存溫度供自動權重使用
        st.session_state["market_temp_label"] = temp_label

        t_col1, t_col2 = st.columns([1, 2])
        with t_col1:
            fig_gauge = _go.Figure(_go.Indicator(
                mode="gauge+number",
                value=hot_pct,
                number={"suffix": "%", "font": {"size": 36}},
                title={"text": f"市場溫度：{temp_label}", "font": {"size": 16}},
                gauge={
                    "axis": {"range": [0, 100], "ticksuffix": "%"},
                    "bar": {"color": temp_color},
                    "steps": [
                        {"range": [0, 5], "color": "#E0E0E0"},
                        {"range": [5, 15], "color": "#BBDEFB"},
                        {"range": [15, 25], "color": "#C8E6C9"},
                        {"range": [25, 40], "color": "#FFE0B2"},
                        {"range": [40, 100], "color": "#FFCDD2"},
                    ],
                    "threshold": {
                        "line": {"color": "white", "width": 2},
                        "thickness": 0.75,
                        "value": hot_pct,
                    },
                },
            ))
            fig_gauge.update_layout(
                height=220, margin=dict(l=20, r=20, t=40, b=10),
                template="plotly_dark",
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        with t_col2:
            st.markdown("#### 等級分佈")
            dist_fig = _go.Figure(_go.Bar(
                x=["S(>80)", "A(65-80)", "B(50-65)", "C(30-50)", "D(<30)"],
                y=[s_pct, a_pct, b_pct, c_pct, d_pct],
                marker_color=["#FFD700", "#4CAF50", "#FF9800", "#9E9E9E", "#EF5350"],
                text=[f"{v:.0f}%" for v in [s_pct, a_pct, b_pct, c_pct, d_pct]],
                textposition="auto",
            ))
            dist_fig.update_layout(
                height=220, template="plotly_dark",
                yaxis_title="佔比 (%)",
                margin=dict(l=50, r=20, t=10, b=30),
            )
            st.plotly_chart(dist_fig, use_container_width=True)

        # 溫度建議 + 自動權重提示
        _advice = {
            "過熱": ("warning", "市場過熱，S+A 級佔比偏高，留意追高風險，可考慮減碼或嚴設停利",
                     "自動權重已提高：法人籌碼、融資融券、技術綜合（偏防禦）"),
            "偏熱": ("info", "市場偏熱，多數股票動能強，適合順勢操作但注意控制部位",
                     "自動權重已提高：突破均線、量價齊揚（順勢操作）"),
            "溫和": ("success", "市場溫和，選股空間適中，適合精選高分標的佈局",
                     "自動權重使用預設均衡配置"),
            "偏冷": ("info", "市場偏冷，強勢股稀少，建議保守觀望或只操作少數強勢股",
                     "自動權重已提高：法人籌碼、技術綜合、融資融券（偏價值）"),
            "極冷": ("warning", "市場極冷，幾乎沒有高分標的，建議持有現金等待轉機",
                     "自動權重已提高：法人籌碼、融資融券、美股連動（關注外資動向）"),
        }
        _level, _msg, _weight_hint = _advice.get(temp_label, ("info", "", ""))
        getattr(st, _level)(_msg)
        if weight_mode == "自動（依市場溫度）":
            st.caption(f"🔄 {_weight_hint}（下次分析自動套用新權重）")

    st.markdown("---")

    # Tab 分頁
    tab_all, tab_ma, tab_vp, tab_rs, tab_inst, tab_et, tab_margin, tab_us, tab_sh = st.tabs([
        "🏆 綜合排名", "📊 突破均線", "📈 量價齊揚", "💪 相對強弱",
        "🏦 法人籌碼", "🔧 技術綜合", "💰 融資融券", "🌏 美股連動", "👥 大戶籌碼"
    ])

    # 幫 ranked 加上連結欄位
    ranked["link"] = ranked["stock_id"].apply(make_link)

    def show_table(df, cols, col_names, link_label="代碼"):
        """顯示含可點擊連結的表格"""
        display = df[cols].copy()
        display.columns = col_names

        # 用 column_config 讓代碼欄位變成可點擊連結
        col_config = {
            link_label: st.column_config.LinkColumn(
                link_label,
                display_text=r"https://.*?/(?:stock/|quote/|finance/|.*STOCK_ID=)(\d{4}).*",
                help=f"點擊開啟 {link_site}",
                width="small",
            )
        }
        st.dataframe(display, use_container_width=True,
                      hide_index=True, column_config=col_config)

    with tab_all:
        st.subheader("綜合排名 TOP")
        top = ranked.head(top_n)
        # 風險欄位：如果存在就顯示
        risk_cols = []
        risk_names = []
        if "risk_level" in ranked.columns:
            risk_cols = ["risk_level", "atr_pct"]
            risk_names = ["風險", "ATR%"]
        show_table(
            top,
            ["rank", "link", "name", "industry", "close",
             "composite_score", "grade"] + risk_cols + [
             "ma_breakout_score", "volume_price_score",
             "relative_strength_score", "institutional_flow_score",
             "enhanced_technical_score", "margin_analysis_score",
             "us_market_score", "shareholder_score"],
            ["排名", "代碼", "名稱", "產業", "收盤價",
             "綜合分數", "等級"] + risk_names + [
             "均線分", "量價分", "強弱分", "籌碼分",
             "技術分", "融資融券分", "美股分", "大戶分"]
        )

    with tab_ma:
        st.subheader("突破均線 TOP")
        ma_top = ranked.nlargest(top_n, "ma_breakout_score")
        show_table(
            ma_top,
            ["rank", "link", "name", "close", "ma_breakout_score", "ma_signal"],
            ["綜合排名", "代碼", "名稱", "收盤價", "均線分數", "訊號"]
        )

    with tab_vp:
        st.subheader("量價齊揚 TOP")
        vp_top = ranked.nlargest(top_n, "volume_price_score")
        show_table(
            vp_top,
            ["rank", "link", "name", "close", "volume_price_score", "vp_signal"],
            ["綜合排名", "代碼", "名稱", "收盤價", "量價分數", "訊號"]
        )

    with tab_rs:
        st.subheader("相對強弱 TOP")
        rs_top = ranked.nlargest(top_n, "relative_strength_score")
        show_table(
            rs_top,
            ["rank", "link", "name", "close", "relative_strength_score", "rs_signal"],
            ["綜合排名", "代碼", "名稱", "收盤價", "強弱分數", "訊號"]
        )

    with tab_inst:
        st.subheader("法人籌碼 TOP")
        inst_top = ranked.nlargest(top_n, "institutional_flow_score")
        show_table(
            inst_top,
            ["rank", "link", "name", "close", "institutional_flow_score", "inst_signal"],
            ["綜合排名", "代碼", "名稱", "收盤價", "籌碼分數", "訊號"]
        )

    with tab_et:
        st.subheader("技術綜合 TOP")
        et_top = ranked.nlargest(top_n, "enhanced_technical_score")
        show_table(
            et_top,
            ["rank", "link", "name", "close", "enhanced_technical_score", "et_signal"],
            ["綜合排名", "代碼", "名稱", "收盤價", "技術分數", "訊號"]
        )

    with tab_margin:
        st.subheader("融資融券 TOP")
        margin_top = ranked.nlargest(top_n, "margin_analysis_score")
        show_table(
            margin_top,
            ["rank", "link", "name", "close", "margin_analysis_score", "margin_signal"],
            ["綜合排名", "代碼", "名稱", "收盤價", "融資融券分數", "訊號"]
        )

    with tab_us:
        st.subheader("美股連動分析")
        st.caption("此策略分數對所有股票相同（反映整體市場氛圍），高分代表美股/夜盤偏多")
        us_top = ranked.head(top_n)
        show_table(
            us_top,
            ["rank", "link", "name", "close", "us_market_score", "us_signal"],
            ["綜合排名", "代碼", "名稱", "收盤價", "美股連動分", "訊號"]
        )

    with tab_sh:
        st.subheader("大戶籌碼 TOP")
        st.caption("集保股權分散表分析，大戶持股增加+散戶減少=籌碼集中（偏多訊號）")
        sh_top = ranked.nlargest(top_n, "shareholder_score")
        show_table(
            sh_top,
            ["rank", "link", "name", "close", "shareholder_score", "sh_signal"],
            ["綜合排名", "代碼", "名稱", "收盤價", "大戶籌碼分", "訊號"]
        )

    # 下載按鈕
    st.markdown("---")
    csv = ranked.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 下載完整分析結果 (CSV)",
        csv,
        f"stock_analysis_{analysis_date}.csv",
        "text/csv"
    )

else:
    st.markdown("""
    ### 使用說明

    1. **設定 FinMind Token** (選填)：至 [FinMind](https://finmind.github.io/) 免費註冊取得 Token，可提高 API 請求額度
    2. **調整策略權重**：在左側滑桿調整八大策略的權重比例
    3. **點擊「開始分析」**：系統將自動下載最新資料並計算

    ---

    ### 八大選股策略

    | 策略 | 說明 | 核心指標 |
    |------|------|----------|
    | **突破均線** | 偵測股價突破均線 | 站上 MA5/10/20/60 數量、多頭排列 |
    | **量價齊揚** | 價漲量增共振 | 量比、連續天數、量能趨勢 |
    | **相對強弱** | 動能指標 | RSI(14)、vs 大盤超額報酬 |
    | **法人籌碼** | 三大法人動向 | 外資/投信買賣超、連續天數 |
    | **技術綜合** | 多重指標交叉驗證 | KD/布林/OBV/MACD/乖離率 |
    | **融資融券** | 籌碼沉澱分析 | 融資變化、融券變化、券資比 |
    | **美股連動** | 國際市場氛圍 | 費半趨勢、台積電ADR折溢價、夜盤價差 |
    | **大戶籌碼** | 集保股權分散表 | 大戶持股比例、增減變化、散戶動向 |

    > 完整策略說明請前往左側選單的 **「策略教學」** 頁面

    ---

    ### 評分等級

    - **S 級** (>80分)：強烈關注 — 多數策略同時看多
    - **A 級** (65-80分)：值得追蹤 — 基本面技術面俱佳
    - **B 級** (50-65分)：觀望 — 訊號不夠明確
    - **C 級** (30-50分)：偏弱 — 僅少數策略正面
    - **D 級** (<30分)：避開 — 多數策略偏空

    ---

    ### 黃金訊號組合（重點關注）

    - **法人同買 + 融資減少 + KD/MACD 黃金交叉** → 主力進場＋籌碼乾淨＋技術啟動
    - **均線多頭排列 + 量價齊揚 + RSI 50~65** → 趨勢確立＋動能充足＋尚未過熱

    ### 危險訊號（應該避開）

    - **融資暴增 + RSI > 80 + 乖離過大** → 散戶追高末段，通常是波段高點
    - **法人全賣 + 量縮 + 均線跌破** → 趨勢反轉向下
    """)
