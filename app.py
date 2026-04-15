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

# ===== 主題切換 + CSS 注入 =====
from utils.theme import inject_custom_css, render_theme_selector
render_theme_selector()
inject_custom_css()

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
from config.settings import AUTO_WEIGHT_PROFILES as _AUTO_WEIGHT_PROFILES
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
    w1 = st.sidebar.slider("突破均線", 0, 100, 17, key="w1")
    w2 = st.sidebar.slider("量價齊揚", 0, 100, 14, key="w2")
    w3 = st.sidebar.slider("相對強弱", 0, 100, 17, key="w3")
    w4 = st.sidebar.slider("法人籌碼", 0, 100, 17, key="w4")
    w5 = st.sidebar.slider("技術綜合", 0, 100, 14, key="w5")
    w6 = st.sidebar.slider("融資融券", 0, 100, 9, key="w6")
    w7 = st.sidebar.slider("美股連動", 0, 100, 12, key="w7")
    w8 = st.sidebar.slider("大戶籌碼", 0, 100, 0, key="w8",
                           help="FinMind 免費帳號拿不到集保資料，預設 0；升級後可調回")
    _raw = [w1, w2, w3, w4, w5, w6, w7, w8]
else:
    # 自動模式：根據上次分析的市場溫度選擇權重
    _prev_temp = st.session_state.get("market_temp_label", "溫和")
    _auto_profile = _AUTO_WEIGHT_PROFILES.get(_prev_temp, _AUTO_WEIGHT_PROFILES["溫和"])
    _raw = [_auto_profile[k] for k in _WEIGHT_KEYS]
    st.sidebar.caption(f"目前溫度：**{_prev_temp}**")
    # 顯示自動權重（唯讀）
    with st.sidebar.expander("⚖️ 目前權重", expanded=False):
        for l, v in zip(_WEIGHT_LABELS, _raw):
            st.caption(f"**{l}**: {v}")

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

# ===== 大盤概況 =====
with st.expander("📈 大盤概況", expanded=False):
    @st.cache_data(ttl=300, show_spinner=False)
    def _load_taiex():
        from data.fetcher import _fetch_taiex_yfinance
        from datetime import timedelta, datetime as _dt
        _end = _dt.now().strftime("%Y-%m-%d")
        _start = (_dt.now() - timedelta(days=120)).strftime("%Y-%m-%d")
        return _fetch_taiex_yfinance(_start, _end)

    _taiex_df = _load_taiex()
    if not _taiex_df.empty and "close" in _taiex_df.columns and len(_taiex_df) >= 20:
        import plotly.graph_objects as go
        from utils.indicators import moving_average, rsi, stochastic_kd, macd

        _taiex_df = _taiex_df.sort_values("date").reset_index(drop=True)
        _close = _taiex_df["close"]
        _high = _taiex_df.get("high", _close)
        _low = _taiex_df.get("low", _close)
        _dates = _taiex_df["date"]

        # 指標計算
        _ma20 = moving_average(_close, 20)
        _ma60 = moving_average(_close, 60)
        _rsi14 = rsi(_close, 14)
        _k, _d = stochastic_kd(_high, _low, _close)
        _macd_dif, _macd_dem, _macd_hist = macd(_close)

        # 最新數據
        _last_close = _close.iloc[-1]
        _prev_close = _close.iloc[-2] if len(_close) >= 2 else _last_close
        _chg = _last_close - _prev_close
        _chg_pct = (_chg / _prev_close * 100) if _prev_close != 0 else 0
        _last_rsi = _rsi14.iloc[-1] if not _rsi14.empty else 0
        _last_k = _k.iloc[-1] if not _k.empty else 0
        _last_d = _d.iloc[-1] if not _d.empty else 0

        # 指標概覽
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("加權指數", f"{_last_close:,.0f}",
                    delta=f"{_chg:+,.0f} ({_chg_pct:+.2f}%)")
        _rsi_label = "過熱" if _last_rsi > 70 else ("偏強" if _last_rsi > 55 else ("中性" if _last_rsi > 45 else "偏弱"))
        mc2.metric("RSI(14)", f"{_last_rsi:.1f}", delta=_rsi_label)
        _kd_label = "高檔鈍化" if _last_k > 80 else ("多方" if _last_k > 50 else ("空方" if _last_k > 20 else "低檔"))
        mc3.metric("KD", f"K:{_last_k:.0f} D:{_last_d:.0f}", delta=_kd_label)
        _ma20_val = _ma20.iloc[-1] if not _ma20.empty else 0
        _ma_label = f"站上 MA20" if _last_close > _ma20_val else "跌破 MA20"
        mc4.metric("MA20", f"{_ma20_val:,.0f}", delta=_ma_label)

        # ===== 市場廣度：櫃買指數 + 量能 + 漲跌家數 =====
        @st.cache_data(ttl=300, show_spinner=False)
        def _load_tpex():
            from data.fetcher import fetch_tpex_index
            from datetime import timedelta as _td, datetime as _dt
            _e = _dt.now().strftime("%Y-%m-%d")
            _s = (_dt.now() - _td(days=60)).strftime("%Y-%m-%d")
            return fetch_tpex_index(_s, _e)

        @st.cache_data(ttl=600, show_spinner=False)
        def _load_breadth():
            from data.fetcher import fetch_market_breadth_twse
            from datetime import datetime as _dt, timedelta as _td
            # 嘗試今日 → 往前 5 天，遇假日回退
            for _i in range(5):
                _d = (_dt.now() - _td(days=_i)).strftime("%Y%m%d")
                _r = fetch_market_breadth_twse(_d)
                if _r and _r.get("up", 0) + _r.get("down", 0) > 0:
                    return _r
            return {}

        _tpex_df = _load_tpex()
        _breadth = _load_breadth()

        bc1, bc2, bc3, bc4 = st.columns(4)

        # 櫃買指數
        if not _tpex_df.empty and len(_tpex_df) >= 2:
            _t_close = _tpex_df["close"].iloc[-1]
            _t_prev = _tpex_df["close"].iloc[-2]
            _t_chg = _t_close - _t_prev
            _t_chg_pct = (_t_chg / _t_prev * 100) if _t_prev else 0
            bc1.metric("櫃買指數", f"{_t_close:,.2f}",
                       delta=f"{_t_chg:+.2f} ({_t_chg_pct:+.2f}%)")
        else:
            bc1.metric("櫃買指數", "N/A", delta="資料缺")

        # 大盤量能（加權成交量 vs 20日均量）
        if "volume" in _taiex_df.columns and len(_taiex_df) >= 20:
            _vol_series = pd.to_numeric(_taiex_df["volume"], errors="coerce")
            _last_vol = _vol_series.iloc[-1]
            _vol_ma20 = _vol_series.rolling(20).mean().iloc[-1]
            _vol_ratio = (_last_vol / _vol_ma20) if _vol_ma20 else 0
            _vol_label = "爆量" if _vol_ratio >= 1.5 else ("放量" if _vol_ratio >= 1.2 else ("量縮" if _vol_ratio < 0.8 else "均量"))
            bc2.metric("量比（vs 20MA）", f"{_vol_ratio:.2f}x", delta=_vol_label)
        else:
            bc2.metric("量比（vs 20MA）", "N/A")

        # 漲家數 / 跌家數 / 漲跌比
        if _breadth and (_breadth.get("up", 0) + _breadth.get("down", 0)) > 0:
            _u = _breadth["up"]
            _d_cnt = _breadth["down"]
            _ratio = (_u / _d_cnt) if _d_cnt else 0
            _breadth_label = "普漲" if _ratio >= 2 else ("多強" if _ratio >= 1.2 else ("空強" if _ratio < 0.8 else "均衡"))
            bc3.metric("漲 / 跌家數",
                       f"{_u:,} / {_d_cnt:,}",
                       delta=f"漲停 {_breadth.get('limit_up',0)} / 跌停 {_breadth.get('limit_down',0)}")
            bc4.metric("漲跌比 A/D", f"{_ratio:.2f}", delta=_breadth_label)
        else:
            bc3.metric("漲 / 跌家數", "N/A", delta="未收盤或資料缺")
            bc4.metric("漲跌比 A/D", "N/A")

        # K 線 + MA 走勢圖
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=_dates, open=_taiex_df.get("open", _close),
            high=_high, low=_low, close=_close,
            name="加權指數", increasing_line_color="#EF5350",
            decreasing_line_color="#26A69A",
        ))
        fig.add_trace(go.Scatter(
            x=_dates, y=_ma20, name="MA20",
            line=dict(color="#FFA726", width=1.5, dash="dot"),
        ))
        if len(_close) >= 60:
            fig.add_trace(go.Scatter(
                x=_dates, y=_ma60, name="MA60",
                line=dict(color="#42A5F5", width=1.5, dash="dot"),
            ))
        fig.update_layout(
            height=350, template="plotly_dark",
            margin=dict(l=50, r=20, t=10, b=10),
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        fig.update_xaxes(type="category", nticks=15)
        st.plotly_chart(fig, use_container_width=True)

        # RSI + KD + MACD 副圖
        _sub_tab1, _sub_tab2 = st.columns(2)
        with _sub_tab1:
            fig_rsi = go.Figure()
            fig_rsi.add_trace(go.Scatter(x=_dates, y=_rsi14, name="RSI",
                                          line=dict(color="#AB47BC", width=1.5)))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="#EF5350", opacity=0.5)
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="#26A69A", opacity=0.5)
            fig_rsi.add_hrect(y0=30, y1=70, fillcolor="gray", opacity=0.1)
            fig_rsi.update_layout(height=180, template="plotly_dark",
                                   margin=dict(l=50, r=20, t=25, b=10),
                                   title=dict(text="RSI(14)", font=dict(size=12)))
            fig_rsi.update_xaxes(type="category", nticks=10)
            st.plotly_chart(fig_rsi, use_container_width=True)
        with _sub_tab2:
            fig_kd = go.Figure()
            fig_kd.add_trace(go.Scatter(x=_dates, y=_k, name="K",
                                         line=dict(color="#FF7043", width=1.5)))
            fig_kd.add_trace(go.Scatter(x=_dates, y=_d, name="D",
                                         line=dict(color="#42A5F5", width=1.5)))
            fig_kd.add_hline(y=80, line_dash="dash", line_color="#EF5350", opacity=0.5)
            fig_kd.add_hline(y=20, line_dash="dash", line_color="#26A69A", opacity=0.5)
            fig_kd.update_layout(height=180, template="plotly_dark",
                                  margin=dict(l=50, r=20, t=25, b=10),
                                  title=dict(text="KD(9,3)", font=dict(size=12)),
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
            fig_kd.update_xaxes(type="category", nticks=10)
            st.plotly_chart(fig_kd, use_container_width=True)
    else:
        st.caption("大盤資料暫時無法載入")

st.markdown("---")

# 掃描設定
col_mode, col_phase, col_industry = st.columns([1, 1, 2])
with col_mode:
    scan_mode = st.radio(
        "掃描模式",
        ["快速掃描", "完整掃描 (全市場)"],
        help="快速掃描只分析熱門股票，速度快很多"
    )
with col_phase:
    phase_b_limit = st.select_slider(
        "分析檔數上限",
        options=[50, 100, 150, 200],
        value=50,
        help="Phase B 完整策略分析的最大股票數（影響 API 用量和速度）"
    )

with col_industry:
    # 預載產業清單（先讀快取，沒快取就立刻抓一次）
    from config.settings import CACHE_DIR
    _industry_list = []
    _ind_cache = CACHE_DIR / "stock_list.parquet"
    _sl_cached = pd.DataFrame()

    @st.cache_data(ttl=3600)
    def _preload_stock_list():
        """預載股票清單到記憶體快取（避免每次 rerun 都 API 呼叫）"""
        from data.fetcher import fetch_stock_list
        try:
            return fetch_stock_list()
        except Exception:
            return pd.DataFrame()

    if _ind_cache.exists():
        try:
            _sl_cached = pd.read_parquet(_ind_cache)
        except Exception:
            pass

    # 快取不存在或沒有 industry 欄位時，直接 API 抓一次
    if _sl_cached.empty or "industry" not in _sl_cached.columns:
        _sl_cached = _preload_stock_list()

    if not _sl_cached.empty and "industry" in _sl_cached.columns:
        _industry_list = sorted(
            i for i in _sl_cached["industry"].dropna().unique()
            if i and i not in ("ETF", "存託憑證", "創新板股票", "創新版股票")
        )

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

_est_actual = min(_est_stock_count, phase_b_limit)
_est_price_fallback = max(int(_est_actual * 0.1), 5)
_est_fixed = 5  # stock list + TAIEX + SOX + TSM + night futures
_est_vol_query = 1 if _est_stock_count > phase_b_limit else 0
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
    token_display = st.empty()

    # 即時 Log 面板
    _log_lines = []
    _log_container = st.expander("📋 執行 Log（點開查看詳情）", expanded=False)
    _log_display = _log_container.empty()

    def _log(msg, level="INFO"):
        """寫入 log 面板"""
        from datetime import datetime as _dt
        prefix = {"INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌", "OK": "✅"}.get(level, "")
        _log_lines.append(f"`{_dt.now():%H:%M:%S}` {prefix} {msg}")
        _log_display.markdown("\n\n".join(_log_lines[-50:]))

    # 即時 token 用量追蹤
    _usage_start = check_finmind_usage()
    _usage_start_used = _usage_start["used"] if _usage_start else 0
    _usage_start_limit = _usage_start["limit"] if _usage_start else 600

    def _update_token_display(step_label: str = ""):
        """查詢並顯示目前 API 已用量"""
        _now = check_finmind_usage()
        if _now:
            _consumed = _now["used"] - _usage_start_used
            _remain = max(_now["limit"] - _now["used"], 0)
            _pct = _now["used"] / max(_now["limit"], 1)
            _color = "🟢" if _pct < 0.6 else ("🟡" if _pct < 0.85 else "🔴")
            token_display.caption(
                f"{_color} API：本次已用 **{_consumed}** 次"
                f" | 剩餘 **{_remain}**/{_now['limit']}"
                f"{f' — {step_label}' if step_label else ''}"
            )

    # Step 1: 取得股票清單
    _log("開始載入股票清單...")
    try:
        stock_list = fetch_stock_list()
        if stock_list.empty:
            _log("股票清單為空", "ERROR")
            st.error("無法取得股票清單，請確認網路連線或 API Token")
            st.stop()
        _log(f"股票清單載入完成，共 {len(stock_list)} 檔", "OK")
    except Exception as e:
        _log(f"股票清單失敗: {e}", "ERROR")
        st.error(f"取得股票清單失敗: {e}")
        st.stop()

    # 產業篩選
    if selected_industries:
        stock_list = stock_list[stock_list["industry"].isin(selected_industries)].copy()
        if stock_list.empty:
            _log(f"所選產業無股票: {selected_industries}", "ERROR")
            st.error("所選產業沒有符合的股票")
            st.stop()
        _log(f"產業篩選完成: {len(stock_list)} 檔 ({', '.join(selected_industries)})", "OK")
        status_text.info(f"已篩選 {', '.join(selected_industries)}，共 {len(stock_list)} 檔")

    # 超過上限時，用成交量篩選 TOP N（節省 API 額度）
    target_stocks = stock_list["stock_id"].tolist()
    if len(target_stocks) > phase_b_limit:
        status_text.info(f"共 {len(target_stocks)} 檔，篩選成交量前 {phase_b_limit} 大...")
        try:
            recent_date = (end_date - timedelta(days=5)).strftime("%Y-%m-%d")
            recent_prices = fetch_stock_prices(start_date=recent_date,
                                               end_date=end_date_str)
            if not recent_prices.empty:
                latest = recent_prices.sort_values("date").groupby("stock_id").tail(1)
                latest = latest[latest["stock_id"].isin(target_stocks)]
                top_vol = latest.nlargest(phase_b_limit, "volume")["stock_id"].tolist()
                target_stocks = top_vol
        except Exception:
            pass

        if len(target_stocks) > phase_b_limit:
            target_stocks = target_stocks[:phase_b_limit]

    total_stocks = len(target_stocks)
    status_text.info(f"將分析 {total_stocks} 檔股票")
    progress.progress(5, text=f"準備下載 {total_stocks} 檔價量資料...")

    # Step 2: 分批抓取價量資料
    def update_progress(current, total, msg):
        pct = 5 + int((current / max(total, 1)) * 45)
        progress.progress(min(pct, 50), text=msg)

    _log(f"開始下載 {total_stocks} 檔價量資料 (yfinance → FinMind)...")
    try:
        all_prices = fetch_stock_prices_batch(
            target_stocks, start_date, end_date_str,
            progress_callback=update_progress
        )
        if all_prices.empty:
            _log("價量資料回傳為空", "ERROR")
            st.error("無法取得價量資料，請稍後再試或檢查 API Token")
            st.stop()
        _n_stocks = all_prices['stock_id'].nunique()
        _log(f"價量資料完成: {_n_stocks} 檔, {len(all_prices)} 筆, "
             f"欄位={list(all_prices.columns)}", "OK")
        status_text.info(f"已下載 {_n_stocks} 檔股票資料")
        _update_token_display("價量資料完成")
    except Exception as e:
        import traceback
        _log(f"價量資料失敗: {e}", "ERROR")
        _log(f"Traceback: {traceback.format_exc()}", "ERROR")
        st.error(f"取得價量資料失敗: {e}")
        st.code(traceback.format_exc(), language="text")
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

    _log("下載美股/大盤資料...")
    try:
        sox_df = fetch_us_stock("^SOX", us_start, end_date_str)
        _log(f"費半: {len(sox_df)} 筆", "OK")
    except Exception as e:
        _log(f"費半失敗: {e}", "WARN")
    try:
        tsm_df = fetch_us_stock("TSM", us_start, end_date_str)
        _log(f"TSM: {len(tsm_df)} 筆", "OK")
    except Exception as e:
        _log(f"TSM 失敗: {e}", "WARN")
    try:
        night_df = fetch_night_futures(us_start, end_date_str)
        _log(f"夜盤: {len(night_df)} 筆", "OK")
    except Exception as e:
        _log(f"夜盤失敗: {e}", "WARN")
    try:
        day_futures_df = fetch_day_futures(us_start, end_date_str)
        _log(f"日盤期貨: {len(day_futures_df)} 筆", "OK")
    except Exception as e:
        _log(f"日盤期貨失敗: {e}", "WARN")

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
    _update_token_display("美股/大盤完成")

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
    #   Phase B: 只對 TOP N 抓法人/融資/大戶，完整 8 策略評分
    # 檔數 <= phase_b_limit 直接跑 Phase B
    # ============================================================

    valid_stocks = stock_list[
        stock_list["stock_id"].isin(target_stocks) &
        stock_list["stock_id"].isin(all_prices["stock_id"].unique())
    ]

    # 判斷是否需要兩階段
    need_two_phase = len(valid_stocks) > phase_b_limit

    if need_two_phase:
        # === Phase A: 純價量策略初篩 ===
        progress.progress(58, text=f"Phase A: 價量策略初篩 {len(valid_stocks)} 檔...")
        status_text.info(f"完整掃描：先用價量策略篩選 {len(valid_stocks)} 檔 → TOP {phase_b_limit}")

        phase_a_scores = []
        total_a = len(valid_stocks)
        for idx, (_, stock) in enumerate(valid_stocks.iterrows()):
            sid = stock["stock_id"]
            if idx % 50 == 0:
                pct = 58 + int((idx / max(total_a, 1)) * 12)
                progress.progress(min(pct, 70),
                                  text=f"初篩中... ({idx}/{total_a})")

            price_df = all_prices[all_prices["stock_id"] == sid].copy()
            if len(price_df) < 40:  # 降低門檻 60→40 天
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

        phase_a_df = pd.DataFrame(phase_a_scores)
        top_ids = phase_a_df.nlargest(phase_b_limit, "preliminary_score")["stock_id"].tolist()
        valid_stocks = valid_stocks[valid_stocks["stock_id"].isin(top_ids)]
        status_text.info(f"初篩完成，從 {total_a} 檔中選出 TOP {len(valid_stocks)} 進入完整分析")

    # === Phase B: 完整 8 策略 ===
    progress.progress(70, text="下載法人籌碼資料...")
    inst_start = (end_date - timedelta(days=30)).strftime("%Y-%m-%d")
    phase_b_ids = valid_stocks["stock_id"].tolist()

    all_institutional = pd.DataFrame()
    def update_inst_progress(current, total, msg):
        pct = 70 + int((current / max(total, 1)) * 8)
        progress.progress(min(pct, 78), text=msg)

    _log(f"下載法人籌碼: {len(phase_b_ids)} 檔...")
    try:
        all_institutional = fetch_institutional_batch(
            phase_b_ids, inst_start, end_date_str,
            progress_callback=update_inst_progress
        )
        _log(f"法人資料: {len(all_institutional)} 筆", "OK")
    except Exception as e:
        _log(f"法人資料失敗: {e}", "WARN")
        st.warning(f"法人籌碼資料取得失敗: {e}，該策略將以0分計算")
    _update_token_display("法人資料完成")

    progress.progress(78, text="下載融資融券資料...")
    all_margin = pd.DataFrame()
    def update_margin_progress(current, total, msg):
        pct = 78 + int((current / max(total, 1)) * 5)
        progress.progress(min(pct, 83), text=msg)

    _log(f"下載融資融券: {len(phase_b_ids)} 檔...")
    try:
        all_margin = fetch_margin_batch(
            phase_b_ids, inst_start, end_date_str,
            progress_callback=update_margin_progress
        )
        _log(f"融資融券: {len(all_margin)} 筆", "OK")
    except Exception as e:
        _log(f"融資融券失敗: {e}", "WARN")
        st.warning(f"融資融券資料取得失敗: {e}，該策略將以0分計算")
    _update_token_display("融資融券完成")

    progress.progress(83, text="計算完整策略分數...")

    # Step 6: 逐股計算完整 8 策略
    from utils.indicators import volatility_risk  # 迴圈前 import，避免每檔股票重複 import
    results = []
    total = len(valid_stocks)
    _skipped_insufficient = []  # 追蹤被跳過的股票

    for idx, (_, stock) in enumerate(valid_stocks.iterrows()):
        sid = stock["stock_id"]

        if idx % 20 == 0:
            pct = 83 + int((idx / max(total, 1)) * 12)
            progress.progress(min(pct, 95),
                              text=f"完整分析... ({idx}/{total}) {sid}")
        if idx % 50 == 0 and idx > 0:
            _update_token_display(f"策略計算 {idx}/{total}")

        price_df = all_prices[all_prices["stock_id"] == sid].copy()
        if len(price_df) < 40:  # 降低門檻 60→40 天（~2 個月）
            _skipped_insufficient.append((sid, stock.get("name", sid), len(price_df)))
            continue
        price_df = price_df.sort_values("date").reset_index(drop=True)

        # 計算各策略分數
        _stock_errors = []
        try:
            ma_score = ma_strategy.score(price_df)
            ma_detail = ma_strategy.details(price_df)
        except Exception as e:
            ma_score, ma_detail = 0, {"signal": "計算錯誤"}
            _stock_errors.append(f"均線:{e}")

        try:
            vp_score = vp_strategy.score(price_df)
            vp_detail = vp_strategy.details(price_df)
        except Exception as e:
            vp_score, vp_detail = 0, {"signal": "計算錯誤"}
            _stock_errors.append(f"量價:{e}")

        try:
            rs_kwargs = {}
            if taiex_close is not None and len(taiex_close) >= 20:
                rs_kwargs["index_close"] = taiex_close
            rs_score = rs_strategy.score(price_df, **rs_kwargs)
            rs_detail = rs_strategy.details(price_df, **rs_kwargs)
        except Exception as e:
            rs_score, rs_detail = 0, {"signal": "計算錯誤"}
            _stock_errors.append(f"RSI:{e}")

        try:
            inst_df = pd.DataFrame()
            if not all_institutional.empty:
                inst_df = all_institutional[
                    all_institutional["stock_id"] == sid
                ].copy()

            inst_score = inst_strategy.score(price_df, institutional_df=inst_df)
            inst_detail = inst_strategy.details(price_df, institutional_df=inst_df)
        except Exception as e:
            inst_score, inst_detail = 0, {"signal": "計算錯誤"}
            _stock_errors.append(f"法人:{e}")

        try:
            et_score = et_strategy.score(price_df)
            et_detail = et_strategy.details(price_df)
        except Exception as e:
            et_score, et_detail = 0, {"signal": "計算錯誤"}
            _stock_errors.append(f"技術:{e}")

        try:
            margin_df = pd.DataFrame()
            if not all_margin.empty:
                margin_df = all_margin[
                    all_margin["stock_id"] == sid
                ].copy()

            margin_score = margin_strategy.score(price_df, margin_df=margin_df)
            margin_detail = margin_strategy.details(price_df, margin_df=margin_df)
        except Exception as e:
            margin_score, margin_detail = 0, {"signal": "計算錯誤"}
            _stock_errors.append(f"融資:{e}")

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
        except Exception as e:
            us_score, us_detail = 0, {"signal": "計算錯誤"}
            _stock_errors.append(f"美股:{e}")

        try:
            tdcc_df = fetch_tdcc_holders(sid)
            sh_score = sh_strategy.score(price_df, tdcc_df=tdcc_df)
            sh_detail = sh_strategy.details(price_df, tdcc_df=tdcc_df)
            if idx % 10 == 9:
                time.sleep(0.5)
        except Exception as e:
            sh_score, sh_detail = 0, {"signal": "計算錯誤"}
            _stock_errors.append(f"籌碼:{e}")

        if _stock_errors:
            _log(f"{sid} {stock.get('name', '')}: {'; '.join(_stock_errors)}", "WARN")

        name = stock.get("name", sid)
        industry = stock.get("industry", "")
        latest_close = price_df["close"].iloc[-1]
        latest_vol = price_df["volume"].iloc[-1] if "volume" in price_df.columns else 0
        if pd.isna(latest_close) or pd.isna(latest_vol):
            _log(f"{sid} 最後一筆資料有 NaN (close={latest_close}, vol={latest_vol})，跳過", "WARN")
            continue
        latest_vol = int(latest_vol)

        # 波動率風險指標
        try:
            vrisk = volatility_risk(price_df["high"], price_df["low"], price_df["close"])
        except Exception:
            vrisk = {"atr_pct": 0, "risk_level": "N/A", "atr_trend": "N/A"}

        results.append({
            "stock_id": sid,
            "name": name,
            "industry": industry,
            "close": round(latest_close, 2),
            "volume": latest_vol,
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

    # 最終 log 摘要
    if not ranked.empty:
        _s = len(ranked[ranked["grade"] == "S"])
        _a = len(ranked[ranked["grade"] == "A"])
        _b = len(ranked[ranked["grade"] == "B"])
        _log(f"分析完成: {len(ranked)} 檔 | S:{_s} A:{_a} B:{_b} | "
             f"最高 {ranked.iloc[0]['composite_score']:.1f} 分", "OK")

    # 顯示被跳過的股票（資料不足 40 天）
    if _skipped_insufficient:
        with st.expander(f"⚠️ {len(_skipped_insufficient)} 檔因資料不足被跳過（點擊查看）"):
            _skip_df = pd.DataFrame(_skipped_insufficient,
                                     columns=["代碼", "名稱", "實際天數"])
            _skip_df = _skip_df.sort_values("實際天數")
            st.dataframe(_skip_df, use_container_width=True, hide_index=True)
            st.caption("常見原因：新上市未滿 40 交易日、yfinance 抓不到、停牌、下市")

    # 最終 token 用量
    _update_token_display("分析完成 ✅")

    if ranked.empty:
        st.warning("沒有符合條件的股票")
        st.stop()

    # 保存到 session state
    st.session_state["ranked"] = ranked
    st.session_state["analysis_date"] = end_date_str
    st.session_state["analysis_industries"] = selected_industries

    # 自動存歷史記錄
    from config.settings import CACHE_DIR
    _history_dir = CACHE_DIR.parent / "history"
    _history_dir.mkdir(parents=True, exist_ok=True)
    _history_file = _history_dir / f"{end_date_str}.parquet"
    try:
        ranked.to_parquet(_history_file, index=False)
    except Exception:
        pass

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

    # ===== 雙權重 S+A% 並列（讓權重造成的落差透明化）=====
    _base_r = st.session_state.get("_base_ranked_for_temp")
    _total = len(ranked)
    if _total > 0 and _base_r is not None and len(_base_r) > 0:
        _curr_sa = (len(ranked[ranked["grade"].isin(["S", "A"])]) / _total) * 100
        _base_sa = (len(_base_r[_base_r["grade"].isin(["S", "A"])]) / len(_base_r)) * 100
        _gap = _curr_sa - _base_sa

        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("市場原始熱度（固定權重 S+A%）", f"{_base_sa:.0f}%",
                   help="用預設均衡權重算出，反映市場真實廣度，溫度計也是用這個")
        cc2.metric("你看到的 S+A%（當前權重）", f"{_curr_sa:.0f}%",
                   delta=f"{_gap:+.0f}% vs 原始",
                   delta_color="normal",
                   help="用你目前側邊欄權重算出，就是下面列表的實際分布")
        _bias_msg = (
            "⚖️ 你的權重和均衡相近" if abs(_gap) < 5 else
            (f"🔼 你的權重「放大」市場熱度 +{_gap:.0f}%（結果比真實廣度更樂觀）"
             if _gap >= 5 else
             f"🔽 你的權重「壓縮」市場熱度 {_gap:.0f}%（熱股被降權，列表看起來比市場冷）")
        )
        cc3.markdown(f"#### 權重偏向\n{_bias_msg}")

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

        with st.expander("📊 市場溫度與等級分佈", expanded=False):
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
    tab_all, tab_history, tab_ma, tab_vp, tab_rs, tab_inst, tab_et, tab_margin, tab_us, tab_sh = st.tabs([
        "🏆 綜合排名", "📅 歷史比對", "📊 突破均線", "📈 量價齊揚", "💪 相對強弱",
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

    with tab_history:
        st.subheader("📅 歷史比對分析")
        from config.settings import CACHE_DIR as _H_CACHE
        import plotly.graph_objects as _hgo
        _hist_dir = _H_CACHE.parent / "history"
        _hist_files = sorted(_hist_dir.glob("*.parquet"), reverse=True) if _hist_dir.exists() else []

        if len(_hist_files) < 2:
            st.info("需要至少 2 天的歷史資料才能比對。每次分析會自動儲存，明天再來看！")
        else:
            # 載入最近 N 天歷史
            _hist_data = {}
            for f in _hist_files[:30]:  # 最多 30 天
                _d = f.stem  # date string
                try:
                    _hist_data[_d] = pd.read_parquet(f)
                except Exception:
                    continue

            _dates = sorted(_hist_data.keys(), reverse=True)
            _today_key = _dates[0]
            _yesterday_key = _dates[1] if len(_dates) > 1 else None

            _today_df = _hist_data[_today_key]
            _yesterday_df = _hist_data[_yesterday_key] if _yesterday_key else pd.DataFrame()

            if not _yesterday_df.empty and "composite_score" in _today_df.columns:
                _t = _today_df[["stock_id", "name", "composite_score", "grade", "rank"]].copy()
                _y = _yesterday_df[["stock_id", "composite_score", "grade", "rank"]].copy()
                _y.columns = ["stock_id", "prev_score", "prev_grade", "prev_rank"]
                _merged = _t.merge(_y, on="stock_id", how="left")
                _merged["score_chg"] = (_merged["composite_score"] - _merged["prev_score"]).round(1)
                _merged["rank_chg"] = (_merged["prev_rank"] - _merged["rank"]).fillna(0).astype(int)

                # --- 新進榜 ---
                _today_ids = set(_today_df["stock_id"])
                _yesterday_ids = set(_yesterday_df["stock_id"]) if not _yesterday_df.empty else set()
                _new_entries = _today_df[_today_df["stock_id"].isin(_today_ids - _yesterday_ids)]
                if not _new_entries.empty:
                    st.markdown(f"#### 🆕 新進榜（{len(_new_entries)} 檔）")
                    _ne = _new_entries[["rank", "stock_id", "name", "composite_score", "grade"]].head(20)
                    _ne.columns = ["排名", "代碼", "名稱", "綜合分數", "等級"]
                    st.dataframe(_ne, use_container_width=True, hide_index=True)

                # --- 排名躍升 TOP 10 ---
                _rank_up = _merged[_merged["rank_chg"] > 0].nlargest(10, "rank_chg")
                if not _rank_up.empty:
                    st.markdown("#### 🚀 排名躍升 TOP 10")
                    _ru = _rank_up[["rank", "stock_id", "name", "composite_score", "rank_chg", "score_chg"]].copy()
                    _ru.columns = ["今日排名", "代碼", "名稱", "綜合分數", "排名上升", "分數變化"]
                    st.dataframe(_ru, use_container_width=True, hide_index=True)

                # --- 評級升級 ---
                _grade_order = {"D": 0, "C": 1, "B": 2, "A": 3, "S": 4}
                _merged["grade_val"] = _merged["grade"].map(_grade_order)
                _merged["prev_grade_val"] = _merged["prev_grade"].map(_grade_order)
                _upgraded = _merged[_merged["grade_val"] > _merged["prev_grade_val"]].dropna(subset=["prev_grade"])
                if not _upgraded.empty:
                    st.markdown(f"#### ⬆️ 評級升級（{len(_upgraded)} 檔）")
                    _ug = _upgraded[["rank", "stock_id", "name", "prev_grade", "grade", "score_chg"]].head(20).copy()
                    _ug.columns = ["排名", "代碼", "名稱", "前次等級", "現在等級", "分數變化"]
                    st.dataframe(_ug, use_container_width=True, hide_index=True)

                # --- 連續升溫（需 3+ 天資料）---
                if len(_dates) >= 3:
                    _streak_data = {}
                    for sid in _today_df["stock_id"].tolist()[:200]:
                        scores = []
                        for d in _dates[:7]:  # 看最近 7 天
                            _hdf = _hist_data.get(d)
                            if _hdf is not None and "composite_score" in _hdf.columns:
                                row = _hdf[_hdf["stock_id"] == sid]
                                if not row.empty:
                                    scores.append(row["composite_score"].iloc[0])
                                else:
                                    break
                            else:
                                break
                        if len(scores) >= 3:
                            # 計算實際連續天數（而非 scores 總長度）
                            _rise_days = 0
                            for i in range(len(scores) - 1):
                                if scores[i] > scores[i + 1]:
                                    _rise_days += 1
                                else:
                                    break
                            _fall_days = 0
                            for i in range(len(scores) - 1):
                                if scores[i] < scores[i + 1]:
                                    _fall_days += 1
                                else:
                                    break
                            if _rise_days >= 2:
                                _streak_data[sid] = {
                                    "trend": "🔥 升溫",
                                    "days": _rise_days + 1,
                                    "current": scores[0],
                                    "change": round(scores[0] - scores[_rise_days], 1),
                                }
                            elif _fall_days >= 2:
                                _streak_data[sid] = {
                                    "trend": "❄️ 降溫",
                                    "days": _fall_days + 1,
                                    "current": scores[0],
                                    "change": round(scores[0] - scores[_fall_days], 1),
                                }

                    if _streak_data:
                        _rising = {k: v for k, v in _streak_data.items() if "升溫" in v["trend"]}
                        _falling = {k: v for k, v in _streak_data.items() if "降溫" in v["trend"]}

                        if _rising:
                            st.markdown(f"#### 🔥 連續升溫（{len(_rising)} 檔）")
                            _rise_rows = []
                            for sid, info in sorted(_rising.items(), key=lambda x: -x[1]["change"]):
                                name = _today_df[_today_df["stock_id"] == sid]["name"].iloc[0] if sid in _today_df["stock_id"].values else sid
                                _chg = info["change"]
                                _rise_rows.append({"代碼": sid, "名稱": name, "現在分數": info["current"],
                                                   "累計變化": f"+{_chg}" if _chg > 0 else str(_chg), "連續天數": info["days"]})
                            st.dataframe(pd.DataFrame(_rise_rows).head(15), use_container_width=True, hide_index=True)

                        if _falling:
                            st.markdown(f"#### ❄️ 連續降溫（{len(_falling)} 檔）")
                            _fall_rows = []
                            for sid, info in sorted(_falling.items(), key=lambda x: x[1]["change"]):
                                name = _today_df[_today_df["stock_id"] == sid]["name"].iloc[0] if sid in _today_df["stock_id"].values else sid
                                _chg_f = info["change"]
                                _fall_rows.append({"代碼": sid, "名稱": name, "現在分數": info["current"],
                                                   "累計變化": f"{_chg_f}" if _chg_f < 0 else f"-{abs(_chg_f)}", "連續天數": info["days"]})
                            st.dataframe(pd.DataFrame(_fall_rows).head(15), use_container_width=True, hide_index=True)

                # --- 整體分數趨勢圖 ---
                if len(_dates) >= 2:
                    st.markdown("#### 📈 市場平均分數趨勢")
                    _trend_dates = []
                    _trend_avg = []
                    _trend_s_count = []
                    for d in reversed(_dates[:30]):
                        _hdf = _hist_data.get(d)
                        if _hdf is not None and "composite_score" in _hdf.columns:
                            _trend_dates.append(d)
                            _trend_avg.append(round(_hdf["composite_score"].mean(), 1))
                            _trend_s_count.append(len(_hdf[_hdf["grade"] == "S"]) if "grade" in _hdf.columns else 0)

                    if _trend_dates:
                        _trend_fig = _hgo.Figure()
                        _trend_fig.add_trace(_hgo.Scatter(
                            x=_trend_dates, y=_trend_avg,
                            mode="lines+markers", name="平均分數",
                            line=dict(color="#00D2FF", width=2),
                        ))
                        _trend_fig.add_trace(_hgo.Bar(
                            x=_trend_dates, y=_trend_s_count,
                            name="S 級數量", yaxis="y2",
                            marker_color="rgba(255,215,0,0.5)",
                        ))
                        _trend_fig.update_layout(
                            height=300, template="plotly_dark",
                            margin=dict(l=50, r=50, t=10, b=30),
                            yaxis=dict(title="平均分數"),
                            yaxis2=dict(title="S 級數量", overlaying="y", side="right"),
                            legend=dict(orientation="h", y=1.1),
                        )
                        st.plotly_chart(_trend_fig, use_container_width=True)
            else:
                st.info("歷史資料格式不相容或只有一天，無法比對")

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
    with st.expander("📖 使用說明與評分等級", expanded=True):
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
