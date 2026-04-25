"""
即時看盤 — TWSE MIS 報價(15-20 秒延遲)

排版:streamlit-elements 可拖拉 resize dashboard
表格:streamlit-aggrid 可凍結欄位 / 排序 / 條件式變色
刷新:streamlit-autorefresh + st.fragment 局部刷新
"""
import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="即時看盤", page_icon="📡", layout="wide")

from utils.theme import inject_custom_css, render_theme_selector
render_theme_selector()
inject_custom_css()
from utils.auth import require_auth
require_auth()

from data.realtime import fetch_mis_quote, fetch_mis_index
from utils.trading_calendar import is_trading_now

# ===== 套件相依(全部選用,缺哪個降級哪個) =====
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

try:
    from streamlit_elements import elements, mui, dashboard, html as el_html
    HAS_ELEMENTS = True
except ImportError:
    HAS_ELEMENTS = False

try:
    from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
    HAS_AGGRID = True
except ImportError:
    HAS_AGGRID = False


st.title("📡 即時看盤")

# ===== 控制列(注意:key= 與 index=/value= 共用會在多頁切換時 reset,
# 統一改成「session_state 預設值 + 純 key=」模式) =====
_DEFAULT_LIST = "2330,2454,2317,2412,3008,2382,2308,1301,1303,2891"
_REFRESH_OPTIONS = [3, 5, 10, 30, 60]
_LAYOUT_OPTIONS = ["可拖拉", "經典"]

# 種預設(只在 key 不存在時)
if "live_watchlist" not in st.session_state:
    st.session_state["live_watchlist"] = _DEFAULT_LIST
if "live_refresh_sec" not in st.session_state:
    st.session_state["live_refresh_sec"] = 5
if "live_auto_on" not in st.session_state:
    st.session_state["live_auto_on"] = True
if "live_layout_mode" not in st.session_state or \
        st.session_state["live_layout_mode"] not in _LAYOUT_OPTIONS:
    st.session_state["live_layout_mode"] = "可拖拉" if HAS_ELEMENTS else "經典"

ctl_l, ctl_m, ctl_r, ctl_x = st.columns([3, 1, 1, 1])
with ctl_l:
    raw = st.text_input("監控股票代碼(逗號分隔)", key="live_watchlist")
with ctl_m:
    refresh_sec = st.selectbox(
        "刷新秒數", _REFRESH_OPTIONS, key="live_refresh_sec"
    )
with ctl_r:
    auto = st.toggle("自動刷新", key="live_auto_on")
with ctl_x:
    layout_mode = st.radio(
        "排版", _LAYOUT_OPTIONS, horizontal=True, key="live_layout_mode",
    )

stock_ids = [s.strip() for s in raw.split(",") if s.strip()]
if not stock_ids:
    st.info("請輸入股票代碼")
    st.stop()

# ===== fragment 偵測(Streamlit ≥1.33),否則退回 autorefresh =====
HAS_FRAGMENT = hasattr(st, "fragment")
USE_FRAGMENT = HAS_FRAGMENT and auto

# 若用不到 fragment,改用全頁 autorefresh
if auto and not HAS_FRAGMENT:
    if HAS_AUTOREFRESH:
        st_autorefresh(interval=refresh_sec * 1000, key="live_autorefresh")
    else:
        st.warning("未安裝 streamlit-autorefresh,自動刷新停用")


# ===== 共用渲染:卡片 HTML =====
def _quote_card_html(q) -> str:
    if q["change"] > 0:
        arrow, color = "▲", "#ff4d4f"
    elif q["change"] < 0:
        arrow, color = "▼", "#10b981"
    else:
        arrow, color = "─", "#888"
    return f"""
    <div style="border:1px solid rgba(255,255,255,0.1); border-radius:8px;
                padding:12px; background:rgba(20,30,50,0.4); height:100%;">
      <div style="font-size:13px; color:#aaa;">
        {q['stock_id']} · {q['name']} · {q['market']}
      </div>
      <div style="font-size:26px; font-weight:bold; color:{color};">
        {q['price']:.2f} {arrow}
      </div>
      <div style="font-size:13px; color:{color};">
        {q['change']:+.2f} ({q['change_pct']:+.2f}%)
      </div>
      <div style="font-size:11px; color:#888; margin-top:6px; line-height:1.5;">
        開 {q['open']:.2f} ｜ 高 {q['high']:.2f} ｜ 低 {q['low']:.2f}<br/>
        量 {q['volume']:,}<br/>
        委買 {q['bid_price']:.2f} ｜ 委賣 {q['ask_price']:.2f}
      </div>
    </div>
    """


# ===== 排版 1:可拖拉 dashboard(streamlit-elements) =====
def _render_elements_dashboard(quotes, idx_df):
    n = len(quotes)
    cards_w = 12         # 報價區佔整列
    cards_h = max(4, (n + 3) // 4 * 2)  # 每 4 檔一行,高度 2

    layout = [
        dashboard.Item("indices", 0, 0, 12, 2, isResizable=True, isDraggable=True),
        dashboard.Item("quotes", 0, 2, cards_w, cards_h,
                       isResizable=True, isDraggable=True),
        dashboard.Item("depth", 0, 2 + cards_h, 6, 4,
                       isResizable=True, isDraggable=True),
        dashboard.Item("info", 6, 2 + cards_h, 6, 4,
                       isResizable=True, isDraggable=True),
    ]

    with elements("live_dashboard"):
        with dashboard.Grid(layout, draggableHandle=".drag-handle"):

            # === Panel 1: 大盤指數 ===
            with mui.Paper(key="indices", elevation=3,
                            sx={"p": 2, "background": "rgba(15,25,45,0.6)"}):
                mui.Typography("📊 大盤指數",
                                className="drag-handle",
                                sx={"cursor": "move", "fontSize": 14,
                                    "color": "#aaa", "mb": 1})
                with mui.Stack(direction="row", spacing=3):
                    for _, r in idx_df.iterrows():
                        c = "#ff4d4f" if r["change"] > 0 else (
                            "#10b981" if r["change"] < 0 else "#888")
                        with mui.Box(sx={"flex": 1}):
                            mui.Typography(r["name"],
                                            sx={"fontSize": 12, "color": "#888"})
                            mui.Typography(f"{r['price']:.2f}",
                                            sx={"fontSize": 22, "fontWeight": "bold",
                                                "color": c})
                            mui.Typography(
                                f"{r['change']:+.2f} ({r['change_pct']:+.2f}%)",
                                sx={"fontSize": 13, "color": c})

            # === Panel 2: 報價卡片牆 ===
            with mui.Paper(key="quotes", elevation=3,
                            sx={"p": 2, "background": "rgba(15,25,45,0.6)",
                                "overflow": "auto"}):
                mui.Typography("💹 個股報價",
                                className="drag-handle",
                                sx={"cursor": "move", "fontSize": 14,
                                    "color": "#aaa", "mb": 1})
                with mui.Grid(container=True, spacing=1):
                    for _, q in quotes.iterrows():
                        with mui.Grid(item=True, xs=12, sm=6, md=4, lg=3):
                            el_html.div(
                                _quote_card_html(q),
                                dangerouslySetInnerHTML={
                                    "__html": _quote_card_html(q)},
                            ) if False else mui.Paper(
                                children=el_html.div(
                                    dangerouslySetInnerHTML={
                                        "__html": _quote_card_html(q)}),
                                elevation=0, sx={"background": "transparent"},
                            )

            # === Panel 3: 五檔買賣盤(取第一檔示意) ===
            with mui.Paper(key="depth", elevation=3,
                            sx={"p": 2, "background": "rgba(15,25,45,0.6)"}):
                mui.Typography("📈 委買委賣(第一檔)",
                                className="drag-handle",
                                sx={"cursor": "move", "fontSize": 14,
                                    "color": "#aaa", "mb": 1})
                with mui.Stack(spacing=0.5):
                    for _, q in quotes.iterrows():
                        c = "#ff4d4f" if q["change"] > 0 else (
                            "#10b981" if q["change"] < 0 else "#888")
                        with mui.Stack(direction="row", spacing=1,
                                        sx={"alignItems": "center"}):
                            mui.Typography(f"{q['stock_id']}",
                                            sx={"width": 60, "fontSize": 12})
                            mui.Typography(f"買 {q['bid_price']:.2f}×{q['bid_vol']}",
                                            sx={"flex": 1, "fontSize": 12,
                                                "color": "#10b981"})
                            mui.Typography(f"賣 {q['ask_price']:.2f}×{q['ask_vol']}",
                                            sx={"flex": 1, "fontSize": 12,
                                                "color": "#ff4d4f"})
                            mui.Typography(f"{q['price']:.2f}",
                                            sx={"width": 60, "fontSize": 12,
                                                "color": c})

            # === Panel 4: 排行(漲幅榜) ===
            with mui.Paper(key="info", elevation=3,
                            sx={"p": 2, "background": "rgba(15,25,45,0.6)"}):
                mui.Typography("🚀 漲幅排行",
                                className="drag-handle",
                                sx={"cursor": "move", "fontSize": 14,
                                    "color": "#aaa", "mb": 1})
                ranked = quotes.sort_values("change_pct", ascending=False)
                with mui.Stack(spacing=0.5):
                    for i, (_, q) in enumerate(ranked.iterrows(), 1):
                        c = "#ff4d4f" if q["change"] > 0 else (
                            "#10b981" if q["change"] < 0 else "#888")
                        with mui.Stack(direction="row", spacing=1):
                            mui.Typography(f"#{i}",
                                            sx={"width": 30, "fontSize": 12,
                                                "color": "#888"})
                            mui.Typography(f"{q['stock_id']} {q['name']}",
                                            sx={"flex": 1, "fontSize": 12})
                            mui.Typography(f"{q['change_pct']:+.2f}%",
                                            sx={"width": 80, "fontSize": 12,
                                                "color": c, "textAlign": "right"})


# ===== 排版 2:經典(垂直堆疊) =====
def _render_classic(quotes, idx_df):
    if not idx_df.empty:
        cols = st.columns(len(idx_df))
        for col, (_, r) in zip(cols, idx_df.iterrows()):
            delta = f"{r['change']:+.2f} ({r['change_pct']:+.2f}%)"
            col.metric(r["name"], f"{r['price']:.2f}", delta,
                        delta_color="inverse")

    PER_ROW = 4
    for i in range(0, len(quotes), PER_ROW):
        row = quotes.iloc[i:i + PER_ROW]
        cols = st.columns(len(row))
        for col, (_, q) in zip(cols, row.iterrows()):
            col.markdown(_quote_card_html(q), unsafe_allow_html=True)


# ===== 主資料區塊(fragment 局部刷新) =====
def _render_data_panel():
    """抓資料 + 渲染 dashboard + 渲染表格 — 受 fragment 控制只重跑這部分"""
    quotes = fetch_mis_quote(stock_ids)
    idx_df = fetch_mis_index(["t00", "o00"])

    trading = is_trading_now()
    status_emoji = "🟢 盤中" if trading else "⚪ 盤後/休市"
    st.caption(f"{status_emoji} ｜ TWSE MIS 延遲 ~15-20 秒 ｜ "
               f"刷新時間 {datetime.now().strftime('%H:%M:%S')}")

    if quotes.empty:
        st.error("沒有取得任何報價(可能 API 無回應或代碼錯誤)")
        return

    if layout_mode == "可拖拉" and HAS_ELEMENTS:
        _render_elements_dashboard(quotes, idx_df)
    else:
        if layout_mode == "可拖拉" and not HAS_ELEMENTS:
            st.warning("未安裝 streamlit-elements,降級為經典排版")
        _render_classic(quotes, idx_df)

    # 詳細表格(AgGrid)
    st.markdown("### 📋 完整報價表")
    table_df = quotes[[
        "stock_id", "name", "market", "price", "change", "change_pct",
        "open", "high", "low", "yesterday_close", "volume",
        "bid_price", "ask_price", "time",
    ]].rename(columns={
        "stock_id": "代碼", "name": "名稱", "market": "市場",
        "price": "現價", "change": "漲跌", "change_pct": "漲跌%",
        "open": "開盤", "high": "最高", "low": "最低",
        "yesterday_close": "昨收", "volume": "成交量",
        "bid_price": "委買", "ask_price": "委賣", "time": "時間",
    })

    if HAS_AGGRID:
        gb = GridOptionsBuilder.from_dataframe(table_df)
        gb.configure_default_column(resizable=True, sortable=True, filter=True,
                                      cellStyle={"fontSize": "13px"})
        gb.configure_column("代碼", pinned="left", width=80)
        gb.configure_column("名稱", pinned="left", width=120)
        gb.configure_column("成交量", type=["numericColumn"],
                              valueFormatter="x.toLocaleString()")
        color_js = JsCode("""
        function(params) {
            const v = params.value;
            if (v > 0) return {'color': '#ff4d4f', 'fontWeight': 'bold'};
            if (v < 0) return {'color': '#10b981', 'fontWeight': 'bold'};
            return {'color': '#888'};
        }
        """)
        for col in ["漲跌", "漲跌%"]:
            gb.configure_column(col, cellStyle=color_js)
        gb.configure_grid_options(domLayout="autoHeight")
        AgGrid(
            table_df, gridOptions=gb.build(),
            allow_unsafe_jscode=True, theme="alpine-dark",
            fit_columns_on_grid_load=False, update_mode="NO_UPDATE",
            height=min(60 + 35 * len(table_df), 600),
        )
    else:
        st.dataframe(table_df, use_container_width=True, hide_index=True)


if USE_FRAGMENT:
    # st.fragment(run_every=N) 只重跑此 fragment,控制列不會重畫
    fragment_decorated = st.fragment(run_every=refresh_sec)(_render_data_panel)
    fragment_decorated()
else:
    _render_data_panel()
