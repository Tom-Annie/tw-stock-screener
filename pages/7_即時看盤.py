"""
即時看盤 — TWSE MIS 報價(15-20 秒延遲),預設每 5 秒自動刷新
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

st.title("📡 即時看盤")

# ===== 控制列 =====
ctl_l, ctl_m, ctl_r = st.columns([2, 1, 1])
with ctl_l:
    default_list = "2330,2454,2317,2412,3008,2382,2308,1301,1303,2891"
    raw = st.text_input(
        "監控股票代碼(逗號分隔)",
        value=st.session_state.get("live_watchlist", default_list),
        key="live_watchlist_input",
    )
    st.session_state["live_watchlist"] = raw
with ctl_m:
    refresh_sec = st.selectbox(
        "刷新頻率(秒)", [3, 5, 10, 30, 60], index=1, key="live_refresh_sec"
    )
with ctl_r:
    auto = st.toggle("自動刷新", value=True, key="live_auto_on")

if auto:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=refresh_sec * 1000, key="live_autorefresh")
    except ImportError:
        st.warning("尚未安裝 streamlit-autorefresh,請手動點刷新")

stock_ids = [s.strip() for s in raw.split(",") if s.strip()]
if not stock_ids:
    st.info("請輸入股票代碼")
    st.stop()

# ===== 大盤指數 =====
idx_df = fetch_mis_index(["t00", "o00"])
if not idx_df.empty:
    cols = st.columns(len(idx_df))
    for col, (_, r) in zip(cols, idx_df.iterrows()):
        delta = f"{r['change']:+.2f} ({r['change_pct']:+.2f}%)"
        col.metric(r["name"], f"{r['price']:.2f}", delta,
                    delta_color="inverse")

# ===== 個股報價 =====
quotes = fetch_mis_quote(stock_ids)
if quotes.empty:
    st.error("沒有取得任何報價(可能 API 暫時無回應或股票代碼錯誤)")
    st.stop()

# 盤中/盤後狀態
trading = is_trading_now()
status_emoji = "🟢 盤中" if trading else "⚪ 盤後/休市"
st.caption(f"{status_emoji} ｜ 資料來源:TWSE MIS(延遲 ~15-20 秒)｜ "
           f"更新時間:{datetime.now().strftime('%H:%M:%S')}")

# ===== 報價卡片(每行 4 檔) =====
PER_ROW = 4
for i in range(0, len(quotes), PER_ROW):
    row = quotes.iloc[i:i + PER_ROW]
    cols = st.columns(len(row))
    for col, (_, q) in zip(cols, row.iterrows()):
        if q["change"] > 0:
            arrow = "▲"; color = "#ff4444"
        elif q["change"] < 0:
            arrow = "▼"; color = "#00cc66"
        else:
            arrow = "─"; color = "#888"
        col.markdown(
            f"""
            <div style="border:1px solid #333; border-radius:8px;
                        padding:12px; background:rgba(20,30,50,0.4);">
              <div style="font-size:14px; color:#aaa;">
                {q['stock_id']} · {q['name']} · {q['market']}
              </div>
              <div style="font-size:28px; font-weight:bold; color:{color};">
                {q['price']:.2f} {arrow}
              </div>
              <div style="font-size:14px; color:{color};">
                {q['change']:+.2f} ({q['change_pct']:+.2f}%)
              </div>
              <div style="font-size:12px; color:#888; margin-top:4px;">
                開 {q['open']:.2f} ｜ 高 {q['high']:.2f} ｜ 低 {q['low']:.2f}<br/>
                量 {q['volume']:,} ｜ 委買 {q['bid_price']:.2f} ｜ 委賣 {q['ask_price']:.2f}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ===== 詳細表格 =====
with st.expander("📋 完整報價表"):
    show = quotes[[
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
    st.dataframe(show, use_container_width=True, hide_index=True)
