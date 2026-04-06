"""
我的庫存管理頁面
記錄持股、分析損益、給出操作建議
每個使用者的庫存獨立儲存在伺服器上
"""
import json
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

st.set_page_config(page_title="我的庫存", page_icon="💼", layout="wide")
from utils.auth import require_auth
require_auth()
st.title("💼 我的庫存管理")
st.markdown("記錄你的持股，系統自動分析損益並給出操作建議")

# ===== 儲存 (GitHub Gist 為主，本地檔案備援) =====
from config.settings import CACHE_DIR
from utils import gist_store

PORTFOLIO_DIR = CACHE_DIR / "portfolios"
PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)


def _portfolio_path(username: str) -> Path:
    safe_name = "".join(c for c in username if c.isalnum() or c in "_-")
    return PORTFOLIO_DIR / f"{safe_name}.json"


def _load_portfolio(username: str) -> list:
    """讀取庫存：Gist 優先，本地備援"""
    # 1. 嘗試從 Gist 載入
    if gist_store.is_available():
        data = gist_store.load(username)
        if data:
            # 同步寫入本地（加速後續讀取）
            _save_local(username, data)
            return data

    # 2. 本地備援
    return _load_local(username)


def _save_portfolio(username: str, data: list):
    """儲存庫存：同時寫 Gist + 本地"""
    _save_local(username, data)
    if gist_store.is_available():
        gist_store.save(username, data)


def _load_local(username: str) -> list:
    path = _portfolio_path(username)
    if path.exists():
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(content, list):
                return content
        except Exception:
            pass
    return []


def _save_local(username: str, data: list):
    path = _portfolio_path(username)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def _lookup_name(sid: str) -> str:
    from data.fetcher import lookup_stock_name
    return lookup_stock_name(sid)


# ===== 使用者登入 =====
st.sidebar.markdown("### 使用者")
username = st.sidebar.text_input("輸入你的名稱", placeholder="例: Tom",
                                  key="portfolio_user")

if not username or not username.strip():
    storage_msg = "☁️ 庫存儲存在 **GitHub Gist**，更新版本不會遺失" if gist_store.is_available() \
        else "⚠️ 未設定 GITHUB_TOKEN，庫存僅存在本地（重新部署會遺失），建議用匯出備份"
    st.info(f"""
    ### 請先輸入使用者名稱

    在左側輸入你的名稱（英文或中文皆可），系統會自動載入你的庫存。

    - 每個名稱的庫存**獨立儲存**，不同使用者互不影響
    - 下次登入輸入相同名稱就能恢復你的庫存
    - 也可以用**匯出/匯入**功能備份到自己電腦

    {storage_msg}
    """)
    st.stop()

username = username.strip()

# 載入該使用者的庫存
if "portfolio_user_loaded" not in st.session_state or \
   st.session_state.get("portfolio_user_loaded") != username:
    st.session_state["portfolio"] = _load_portfolio(username)
    st.session_state["portfolio_user_loaded"] = username
    # 清除舊的分析結果
    if "portfolio_results" in st.session_state:
        del st.session_state["portfolio_results"]

st.sidebar.success(f"已登入: **{username}**")

# ===== 側邊欄：新增 / 匯入匯出 =====
st.sidebar.markdown("---")
st.sidebar.markdown("### 新增持股")
with st.sidebar.form("add_stock", clear_on_submit=True):
    new_id = st.text_input("股票代碼", placeholder="2330")
    new_shares = st.number_input("持有股數", min_value=0, value=1000, step=1000)
    new_cost = st.number_input("平均成本 (元)", min_value=0.0, value=0.0,
                               step=0.5, format="%.2f")
    add_btn = st.form_submit_button("新增", type="primary")

    if add_btn and new_id.strip():
        sid = new_id.strip()
        # 檢查是否已存在
        existing = [h for h in st.session_state["portfolio"]
                    if h["stock_id"] == sid]
        if existing:
            st.warning(f"{sid} 已在庫存中，請用編輯功能修改")
        else:
            name = _lookup_name(sid)
            st.session_state["portfolio"].append({
                "stock_id": sid,
                "name": name,
                "shares": int(new_shares),
                "avg_cost": float(new_cost),
            })
            _save_portfolio(username, st.session_state["portfolio"])
            st.success(f"已新增 {sid} {name}")
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 匯入/匯出")

# 匯出
if st.session_state["portfolio"]:
    export_data = json.dumps(st.session_state["portfolio"],
                             ensure_ascii=False, indent=2)
    st.sidebar.download_button(
        "📥 匯出庫存 (JSON)",
        export_data,
        f"portfolio_{username}_{datetime.now().strftime('%Y%m%d')}.json",
        "application/json"
    )

# 匯入
uploaded = st.sidebar.file_uploader("📤 匯入庫存 (JSON)", type=["json"])
if uploaded:
    try:
        data = json.loads(uploaded.read().decode("utf-8"))
        if isinstance(data, list) and all("stock_id" in item for item in data):
            for item in data:
                if not item.get("name"):
                    item["name"] = _lookup_name(item["stock_id"])
                if "shares" not in item:
                    item["shares"] = 0
                if "avg_cost" not in item:
                    item["avg_cost"] = 0.0
            st.session_state["portfolio"] = data
            _save_portfolio(username, data)
            # 強制下次 rerun 重新載入，確保資料一致
            st.session_state["portfolio_user_loaded"] = None
            st.sidebar.success(f"已匯入 {len(data)} 筆持股")
            st.rerun()
        else:
            st.sidebar.error("JSON 格式錯誤，需為 list 且每筆含 stock_id")
    except Exception as e:
        st.sidebar.error(f"匯入失敗: {e}")


# ===== 主頁面 =====
portfolio = st.session_state["portfolio"]

if not portfolio:
    st.info(f"""
    ### {username} 的庫存目前是空的

    1. 在左側「新增持股」輸入股票代碼、股數和平均成本
    2. 系統會自動抓取最新價格並計算損益
    3. 根據八大策略分析給出操作建議

    **資料自動儲存：** 庫存會同步到 GitHub Gist，即使系統更新也不會遺失。
    也可以用匯出功能備份到自己電腦。
    """)
    st.stop()

# ===== 編輯庫存 =====
st.markdown("### 目前庫存")

# 編輯表格
edit_cols = st.columns([1, 2, 1.5, 1.5, 1])
edit_cols[0].markdown("**代碼**")
edit_cols[1].markdown("**名稱**")
edit_cols[2].markdown("**股數**")
edit_cols[3].markdown("**成本**")
edit_cols[4].markdown("**操作**")

to_delete = None
for i, holding in enumerate(portfolio):
    cols = st.columns([1, 2, 1.5, 1.5, 1])
    cols[0].text(holding["stock_id"])
    cols[1].text(holding.get("name", ""))
    new_s = cols[2].number_input(
        "股數", value=holding["shares"], min_value=0,
        step=1000, key=f"shares_{i}", label_visibility="collapsed"
    )
    new_c = cols[3].number_input(
        "成本", value=holding["avg_cost"], min_value=0.0,
        step=0.5, format="%.2f", key=f"cost_{i}", label_visibility="collapsed"
    )
    if cols[4].button("刪除", key=f"del_{i}"):
        to_delete = i

    # 更新數值 (有變動時自動存檔)
    if portfolio[i]["shares"] != int(new_s) or portfolio[i]["avg_cost"] != float(new_c):
        portfolio[i]["shares"] = int(new_s)
        portfolio[i]["avg_cost"] = float(new_c)
        _save_portfolio(username, portfolio)
    portfolio[i]["shares"] = int(new_s)
    portfolio[i]["avg_cost"] = float(new_c)

if to_delete is not None:
    portfolio.pop(to_delete)
    _save_portfolio(username, portfolio)
    st.rerun()

# ===== 操作建議邏輯 =====
def _recommend_action(composite, scores, pnl_pct, avg_cost):
    """根據策略分數和損益給出操作建議"""
    if avg_cost <= 0:
        if composite >= 70:
            return {"action": "持有", "color": "green",
                    "reason": "策略分數高，趨勢良好"}
        elif composite >= 50:
            return {"action": "觀望", "color": "orange",
                    "reason": "策略分數中等，注意趨勢變化"}
        else:
            return {"action": "留意風險", "color": "red",
                    "reason": "策略分數偏低，考慮是否減碼"}

    high_score = composite >= 65
    mid_score = 40 <= composite < 65
    low_score = composite < 40

    big_profit = pnl_pct > 15
    profit = pnl_pct > 5
    small_profit = 0 < pnl_pct <= 5
    small_loss = -5 <= pnl_pct < 0
    big_loss = pnl_pct < -10
    loss = pnl_pct < -5

    if high_score and big_profit:
        return {"action": "分批獲利", "color": "green",
                "reason": f"獲利 {pnl_pct:+.1f}% 且分數 {composite}，可考慮先賣一半鎖定獲利，剩下續抱"}
    elif high_score and profit:
        return {"action": "持有續抱", "color": "green",
                "reason": f"獲利 {pnl_pct:+.1f}%，策略分數 {composite} 仍強，繼續持有"}
    elif high_score and small_profit:
        return {"action": "持有", "color": "green",
                "reason": f"小幅獲利，策略分數高 {composite}，持續看好"}
    elif high_score and small_loss:
        return {"action": "攤平加碼", "color": "blue",
                "reason": f"小幅虧損 {pnl_pct:+.1f}%，但策略分數 {composite} 高，可考慮攤平降低成本"}
    elif high_score and loss:
        return {"action": "攤平或持有", "color": "blue",
                "reason": f"虧損 {pnl_pct:+.1f}%，但策略面仍佳 {composite}，若看好可攤平"}

    elif mid_score and big_profit:
        return {"action": "獲利了結", "color": "orange",
                "reason": f"獲利 {pnl_pct:+.1f}% 但策略分數降至 {composite}，動能減弱建議先獲利"}
    elif mid_score and profit:
        return {"action": "減碼一半", "color": "orange",
                "reason": f"獲利 {pnl_pct:+.1f}%，分數 {composite} 中等，可先減碼鎖定部分獲利"}
    elif mid_score and small_profit:
        return {"action": "觀望", "color": "orange",
                "reason": f"微幅獲利，策略分數 {composite} 中等，密切觀察趨勢"}
    elif mid_score and small_loss:
        return {"action": "觀望", "color": "orange",
                "reason": f"小幅虧損 {pnl_pct:+.1f}%，分數 {composite} 尚可，暫不操作"}
    elif mid_score and big_loss:
        return {"action": "考慮停損", "color": "red",
                "reason": f"虧損 {pnl_pct:+.1f}%，分數 {composite} 不夠強，應考慮停損"}

    elif low_score and profit:
        return {"action": "獲利了結", "color": "red",
                "reason": f"策略分數僅 {composite}，趨勢轉弱，獲利 {pnl_pct:+.1f}% 建議出場"}
    elif low_score and small_loss:
        return {"action": "停損", "color": "red",
                "reason": f"策略分數低 {composite}，虧損 {pnl_pct:+.1f}%，建議停損避免擴大"}
    elif low_score and big_loss:
        return {"action": "停損", "color": "red",
                "reason": f"策略分數低 {composite}，虧損已達 {pnl_pct:+.1f}%，強烈建議停損"}

    return {"action": "觀望", "color": "orange",
            "reason": f"策略分數 {composite}，損益 {pnl_pct:+.1f}%，持續觀察"}


def _draw_charts(price_df, inst_df, stock_id):
    """繪製個股技術分析圖表"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from utils.indicators import moving_average, rsi, macd
    from config.settings import MA_PERIODS, RSI_PERIOD

    st.markdown("#### 技術分析圖表")

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.45, 0.2, 0.15, 0.2],
        subplot_titles=("K線 + 均線", "成交量", "RSI", "MACD")
    )

    # K線
    fig.add_trace(go.Candlestick(
        x=price_df["date"],
        open=price_df["open"], high=price_df["high"],
        low=price_df["low"], close=price_df["close"],
        name="K線",
        increasing_line_color="#EF5350",
        decreasing_line_color="#26A69A",
    ), row=1, col=1)

    # 均線
    ma_colors = {"5": "#FF9800", "10": "#2196F3",
                 "20": "#9C27B0", "60": "#607D8B"}
    for period in MA_PERIODS:
        ma = moving_average(price_df["close"], period)
        fig.add_trace(go.Scatter(
            x=price_df["date"], y=ma,
            name=f"MA{period}",
            line=dict(width=1, color=ma_colors.get(str(period), "#999")),
        ), row=1, col=1)

    # 成交量
    vol_colors = ["#EF5350" if c >= o else "#26A69A"
                  for c, o in zip(price_df["close"], price_df["open"])]
    fig.add_trace(go.Bar(
        x=price_df["date"], y=price_df["volume"],
        name="成交量", marker_color=vol_colors, showlegend=False
    ), row=2, col=1)

    # RSI
    rsi_vals = rsi(price_df["close"], RSI_PERIOD)
    fig.add_trace(go.Scatter(
        x=price_df["date"], y=rsi_vals,
        name=f"RSI({RSI_PERIOD})",
        line=dict(color="#FF9800", width=1.5)
    ), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red",
                  opacity=0.5, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green",
                  opacity=0.5, row=3, col=1)

    # MACD
    dif, dem, hist = macd(price_df["close"])
    fig.add_trace(go.Scatter(
        x=price_df["date"], y=dif, name="DIF",
        line=dict(color="#2196F3", width=1)
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=price_df["date"], y=dem, name="MACD",
        line=dict(color="#FF9800", width=1)
    ), row=4, col=1)
    hist_colors = ["#EF5350" if v >= 0 else "#26A69A" for v in hist]
    fig.add_trace(go.Bar(
        x=price_df["date"], y=hist, name="柱狀體",
        marker_color=hist_colors, showlegend=False
    ), row=4, col=1)

    fig.update_layout(
        height=700,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=50, r=20, t=30, b=20),
    )
    fig.update_xaxes(type="category", nticks=15)
    st.plotly_chart(fig, use_container_width=True, key=f"chart_{stock_id}")

    # 法人籌碼圖
    if inst_df is not None and not inst_df.empty:
        st.markdown("#### 法人買賣超")
        _inst = inst_df.sort_values("date")

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=_inst["date"], y=_inst.get("foreign_net", 0),
            name="外資", marker_color="#2196F3"
        ))
        fig2.add_trace(go.Bar(
            x=_inst["date"], y=_inst.get("trust_net", 0),
            name="投信", marker_color="#FF9800"
        ))
        fig2.add_trace(go.Bar(
            x=_inst["date"], y=_inst.get("dealer_net", 0),
            name="自營商", marker_color="#9C27B0"
        ))
        fig2.update_layout(
            barmode="group", height=300, template="plotly_dark",
            yaxis_title="買賣超 (張)",
            legend=dict(orientation="h"),
            margin=dict(l=50, r=20, t=10, b=20),
        )
        st.plotly_chart(fig2, use_container_width=True,
                        key=f"inst_{stock_id}")


# ===== 分析按鈕 =====
st.markdown("---")
analyze_btn = st.button("🔍 分析庫存", type="primary", use_container_width=True)

if analyze_btn:
    from data.fetcher import (fetch_stock_prices, fetch_institutional_investors,
                              fetch_margin_data, fetch_us_stock,
                              fetch_night_futures, fetch_day_futures,
                              fetch_tdcc_holders, fetch_taiex)
    from strategies.ma_breakout import MABreakoutStrategy
    from strategies.volume_price import VolumePriceStrategy
    from strategies.relative_strength import RelativeStrengthStrategy
    from strategies.institutional_flow import InstitutionalFlowStrategy
    from strategies.enhanced_technical import EnhancedTechnicalStrategy
    from strategies.margin_analysis import MarginAnalysisStrategy
    from strategies.us_market import USMarketStrategy
    from strategies.shareholder import ShareholderStrategy
    from strategies.scorer import compute_composite_score

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
    inst_start = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
    us_start = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")

    # 美股/夜盤/大盤 (全庫存共用)
    progress = st.progress(0, text="下載美股/夜盤/大盤資料...")
    sox_df = tsm_df = night_df = day_futures_df = pd.DataFrame()
    tsmc_close = 0.0
    taiex_close = None
    try:
        sox_df = fetch_us_stock("^SOX", us_start, end_date)
    except Exception:
        pass
    try:
        tsm_df = fetch_us_stock("TSM", us_start, end_date)
    except Exception:
        pass
    try:
        night_df = fetch_night_futures(us_start, end_date)
    except Exception:
        pass
    try:
        day_futures_df = fetch_day_futures(us_start, end_date)
    except Exception:
        pass
    try:
        taiex_df = fetch_taiex(start_date, end_date)
        if not taiex_df.empty:
            taiex_df = taiex_df.sort_values("date")
            if "close" in taiex_df.columns:
                taiex_close = taiex_df["close"]
            elif "price" in taiex_df.columns:
                taiex_close = taiex_df["price"]
    except Exception:
        pass

    strategies = {
        "ma_breakout": MABreakoutStrategy(),
        "volume_price": VolumePriceStrategy(),
        "relative_strength": RelativeStrengthStrategy(),
        "institutional_flow": InstitutionalFlowStrategy(),
        "enhanced_technical": EnhancedTechnicalStrategy(),
        "margin_analysis": MarginAnalysisStrategy(),
        "us_market": USMarketStrategy(),
        "shareholder": ShareholderStrategy(),
    }

    results = []
    total = len(portfolio)

    for idx, holding in enumerate(portfolio):
        sid = holding["stock_id"]
        progress.progress(int((idx / total) * 100),
                          text=f"分析 {sid} {holding.get('name', '')}...")

        try:
            price_df = fetch_stock_prices(sid, start_date, end_date)
            if price_df.empty or len(price_df) < 30:
                results.append({**holding, "error": "資料不足"})
                continue
            price_df = price_df.sort_values("date").reset_index(drop=True)
        except Exception as e:
            results.append({**holding, "error": str(e)})
            continue

        current_price = price_df["close"].iloc[-1]

        # 最大回撤
        from utils.indicators import max_drawdown as calc_mdd
        mdd_pct, _ = calc_mdd(price_df["close"])

        # 台積電收盤價 (for ADR)
        if sid == "2330":
            tsmc_close = current_price
        if tsmc_close == 0:
            # 嘗試從庫存其他地方取
            try:
                tsmc_p = fetch_stock_prices("2330", us_start, end_date)
                if not tsmc_p.empty:
                    tsmc_close = tsmc_p.sort_values("date")["close"].iloc[-1]
            except Exception:
                pass

        # 法人
        try:
            inst_df = fetch_institutional_investors(sid, inst_start, end_date)
        except Exception:
            inst_df = pd.DataFrame()

        # 融資融券
        try:
            margin_df = fetch_margin_data(sid, inst_start, end_date)
        except Exception:
            margin_df = pd.DataFrame()

        # TDCC 大戶籌碼
        try:
            tdcc_df = fetch_tdcc_holders(sid)
        except Exception:
            tdcc_df = pd.DataFrame()

        # 計算各策略分數
        scores = {}
        details = {}
        for key, strat in strategies.items():
            try:
                kwargs = {}
                if key == "institutional_flow":
                    kwargs["institutional_df"] = inst_df
                elif key == "margin_analysis":
                    kwargs["margin_df"] = margin_df
                elif key == "relative_strength":
                    if taiex_close is not None and len(taiex_close) >= 20:
                        kwargs["index_close"] = taiex_close
                elif key == "us_market":
                    kwargs.update(
                        sox_df=sox_df, tsm_df=tsm_df, tsmc_close=tsmc_close,
                        night_df=night_df, day_futures_df=day_futures_df
                    )
                elif key == "shareholder":
                    kwargs["tdcc_df"] = tdcc_df
                scores[key] = strat.score(price_df, **kwargs)
                details[key] = strat.details(price_df, **kwargs)
            except Exception:
                scores[key] = 0
                details[key] = {"signal": ""}

        composite = compute_composite_score(scores)

        # 損益計算
        avg_cost = holding["avg_cost"]
        shares = holding["shares"]
        if avg_cost > 0:
            pnl_pct = (current_price - avg_cost) / avg_cost * 100
            pnl_amount = (current_price - avg_cost) * shares
        else:
            pnl_pct = 0
            pnl_amount = 0

        # 操作建議
        action = _recommend_action(composite, scores, pnl_pct, avg_cost)

        results.append({
            **holding,
            "current_price": round(current_price, 2),
            "pnl_pct": round(pnl_pct, 2),
            "pnl_amount": round(pnl_amount, 0),
            "composite": round(composite, 1),
            "mdd_pct": mdd_pct,
            "scores": scores,
            "details": details,
            "action": action,
            "price_df": price_df,
            "inst_df": inst_df,
        })

    progress.progress(100, text="分析完成!")
    st.session_state["portfolio_results"] = results


# ===== 顯示分析結果 =====
if "portfolio_results" in st.session_state:
    results = st.session_state["portfolio_results"]
    st.markdown("---")
    st.markdown("### 庫存分析結果")

    # 總覽
    valid = [r for r in results if "error" not in r]
    if valid:
        total_cost = sum(r["avg_cost"] * r["shares"] for r in valid
                         if r["avg_cost"] > 0)
        total_value = sum(r["current_price"] * r["shares"] for r in valid
                          if r["avg_cost"] > 0)
        total_pnl = total_value - total_cost if total_cost > 0 else 0
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("持股檔數", f"{len(valid)}")
        mc2.metric("投入成本", f"${total_cost:,.0f}")
        mc3.metric("目前市值", f"${total_value:,.0f}",
                    delta=f"{total_pnl_pct:+.1f}%" if total_cost > 0 else None)
        mc4.metric("未實現損益", f"${total_pnl:+,.0f}",
                    delta=f"{total_pnl_pct:+.1f}%" if total_cost > 0 else None)

    st.markdown("---")

    # 逐檔顯示
    for r in results:
        sid = r["stock_id"]
        name = r.get("name", "")

        if "error" in r:
            st.warning(f"**{sid} {name}** — {r['error']}")
            continue

        action = r["action"]
        color_map = {"green": "🟢", "blue": "🔵", "orange": "🟡", "red": "🔴"}
        icon = color_map.get(action["color"], "⚪")

        with st.expander(
            f"{icon} **{sid} {name}** — {action['action']}　"
            f"｜現價 {r['current_price']}　"
            f"｜損益 {r['pnl_pct']:+.1f}%　"
            f"｜分數 {r['composite']}",
            expanded=True
        ):
            # 上半：損益 + 建議
            ac1, ac2 = st.columns([1, 2])
            with ac1:
                st.markdown("#### 損益")
                if r["avg_cost"] > 0:
                    st.markdown(f"""
| 項目 | 數值 |
|------|------|
| 平均成本 | {r['avg_cost']:.2f} |
| 現價 | {r['current_price']:.2f} |
| 持股 | {r['shares']:,} 股 |
| 損益率 | **{r['pnl_pct']:+.2f}%** |
| 未實現損益 | **${r['pnl_amount']:+,.0f}** |
| 近期最大回撤 | **{r.get('mdd_pct', 0):.1f}%** |
""")
                else:
                    st.markdown(f"現價 **{r['current_price']}**，持股 **{r['shares']:,}** 股")
                    st.caption("未填入成本，無法計算損益")

            with ac2:
                st.markdown("#### 操作建議")
                if action["color"] == "green":
                    st.success(f"**{action['action']}**\n\n{action['reason']}")
                elif action["color"] == "blue":
                    st.info(f"**{action['action']}**\n\n{action['reason']}")
                elif action["color"] == "orange":
                    st.warning(f"**{action['action']}**\n\n{action['reason']}")
                else:
                    st.error(f"**{action['action']}**\n\n{action['reason']}")

            # 下半：八大策略分數
            st.markdown("#### 八大策略分數")
            score_names = {
                "ma_breakout": "突破均線",
                "volume_price": "量價齊揚",
                "relative_strength": "相對強弱",
                "institutional_flow": "法人籌碼",
                "enhanced_technical": "技術綜合",
                "margin_analysis": "融資融券",
                "us_market": "美股連動",
                "shareholder": "大戶籌碼",
            }
            scols = st.columns(8)
            for j, (key, label) in enumerate(score_names.items()):
                s = r["scores"].get(key, 0)
                color = "🟢" if s >= 65 else "🟡" if s >= 40 else "🔴"
                scols[j].metric(f"{color} {label}", f"{s:.0f}")

            # 訊號
            signals = []
            for key, label in score_names.items():
                sig = r["details"].get(key, {}).get("signal", "")
                if sig and sig not in ("", "無明顯訊號", "資料不足", "無美股/夜盤資料",
                                        "籌碼中性", "無融資融券資料", "計算錯誤"):
                    signals.append(f"**{label}**: {sig}")
            if signals:
                st.markdown("**關鍵訊號：** " + "　｜　".join(signals))

            # 技術分析圖表
            _price_df = r.get("price_df")
            _inst_df = r.get("inst_df")
            if _price_df is not None and not _price_df.empty:
                _draw_charts(_price_df, _inst_df, sid)

    # 操作摘要表
    st.markdown("---")
    st.markdown("### 操作摘要")

    summary_data = []
    for r in results:
        if "error" in r:
            continue
        summary_data.append({
            "代碼": r["stock_id"],
            "名稱": r.get("name", ""),
            "現價": r["current_price"],
            "成本": r["avg_cost"],
            "損益%": r["pnl_pct"],
            "最大回撤%": r.get("mdd_pct", 0),
            "綜合分數": r["composite"],
            "建議": r["action"]["action"],
            "原因": r["action"]["reason"],
        })

    if summary_data:
        summary_df = pd.DataFrame(summary_data)

        # 根據建議類型上色
        def _color_action(val):
            colors = {
                "持有續抱": "background-color: #1B5E20; color: white",
                "持有": "background-color: #2E7D32; color: white",
                "分批獲利": "background-color: #33691E; color: white",
                "攤平加碼": "background-color: #1565C0; color: white",
                "攤平或持有": "background-color: #1976D2; color: white",
                "觀望": "background-color: #E65100; color: white",
                "減碼一半": "background-color: #EF6C00; color: white",
                "獲利了結": "background-color: #BF360C; color: white",
                "考慮停損": "background-color: #C62828; color: white",
                "停損": "background-color: #B71C1C; color: white",
                "留意風險": "background-color: #D32F2F; color: white",
            }
            return colors.get(val, "")

        styled = summary_df.style.map(_color_action, subset=["建議"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # 匯出分析報告 + LINE 通知
    dl_col, line_col = st.columns(2)
    if summary_data:
        csv = summary_df.to_csv(index=False).encode("utf-8-sig")
        dl_col.download_button(
            "📥 下載分析報告 (CSV)",
            csv,
            f"portfolio_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )

    from utils import telegram_notify
    if telegram_notify.is_available():
        if line_col.button("📱 發送 Telegram 通知"):
            msg = telegram_notify.format_portfolio_alert(results)
            if msg and telegram_notify.send(msg):
                line_col.success("已發送 Telegram 通知!")
            else:
                line_col.error("Telegram 通知發送失敗")
    else:
        line_col.caption("設定 TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID 即可推播到 Telegram")

    # ===== 持股相關性分析 =====
    valid_with_price = [r for r in results
                        if "error" not in r and r.get("price_df") is not None
                        and not r["price_df"].empty]
    if len(valid_with_price) >= 2:
        import plotly.graph_objects as _go
        import numpy as np

        st.markdown("---")
        st.markdown("### 持股相關性")
        st.caption("數值越接近 1 代表走勢越同步，持股高度相關代表風險集中")

        # 建立收盤價矩陣
        close_dict = {}
        for r in valid_with_price:
            sid = r["stock_id"]
            pdf = r["price_df"].set_index("date")["close"]
            close_dict[f"{sid} {r.get('name', '')}"] = pdf

        close_df = pd.DataFrame(close_dict).dropna()
        if len(close_df) >= 20 and len(close_df.columns) >= 2:
            corr_matrix = close_df.corr()

            # Heatmap
            labels = list(corr_matrix.columns)
            fig_corr = _go.Figure(data=_go.Heatmap(
                z=corr_matrix.values,
                x=labels, y=labels,
                colorscale="RdYlGn_r",
                zmin=-1, zmax=1,
                text=np.round(corr_matrix.values, 2),
                texttemplate="%{text}",
                textfont={"size": 11},
            ))
            fig_corr.update_layout(
                height=max(300, len(labels) * 50),
                template="plotly_dark",
                margin=dict(l=10, r=10, t=10, b=10),
            )
            st.plotly_chart(fig_corr, use_container_width=True)

            # 高相關性警告
            high_corr_pairs = []
            for i in range(len(labels)):
                for j in range(i + 1, len(labels)):
                    c = corr_matrix.iloc[i, j]
                    if c > 0.85:
                        high_corr_pairs.append((labels[i], labels[j], c))

            if high_corr_pairs:
                pair_text = "、".join(
                    f"**{a}** / **{b}** ({c:.2f})" for a, b, c in high_corr_pairs
                )
                st.warning(f"以下持股走勢高度相關（>0.85），風險較集中：{pair_text}")
            else:
                st.success("持股之間相關性適中，風險分散良好")

    # ===== 調倉建議：賣出後推薦替代標的 =====
    EXIT_ACTIONS = {"停損", "獲利了結", "考慮停損", "留意風險"}
    exit_stocks = [r for r in results
                   if "error" not in r and r["action"]["action"] in EXIT_ACTIONS]

    if exit_stocks:
        st.markdown("---")
        st.markdown("### 調倉建議")

        # 計算可釋放資金
        freed_capital = sum(
            r["current_price"] * r["shares"] for r in exit_stocks
            if r.get("avg_cost", 0) > 0
        )
        exit_ids = {r["stock_id"] for r in exit_stocks}
        hold_ids = {r["stock_id"] for r in results if "error" not in r}

        st.markdown(
            f"以下 **{len(exit_stocks)} 檔**建議出場，"
            f"預估可釋放資金約 **${freed_capital:,.0f}**"
        )

        # 顯示建議出場的標的
        exit_info = []
        for r in exit_stocks:
            val = r["current_price"] * r["shares"]
            exit_info.append(
                f"- **{r['stock_id']} {r.get('name','')}** "
                f"— {r['action']['action']}，"
                f"市值 ${val:,.0f}，分數 {r['composite']}"
            )
        st.warning("\n".join(exit_info))

        # 找推薦替代標的
        st.markdown("#### 推薦替代標的")
        st.caption("從主頁面分析結果或熱門股中，挑選綜合分數高且不在你庫存中的標的")

        # 優先用主頁面的分析結果
        if "ranked" in st.session_state and not st.session_state["ranked"].empty:
            ranked = st.session_state["ranked"]
            # 排除已持有的
            candidates = ranked[~ranked["stock_id"].isin(hold_ids)].copy()
            candidates = candidates[candidates["composite_score"] >= 60]
            candidates = candidates.head(10)

            if not candidates.empty:
                st.success(
                    f"以下為綜合分數 ≥ 60 的推薦標的"
                    f"（已排除目前持有的 {len(hold_ids)} 檔）"
                )
                show_cols = ["rank", "stock_id", "name", "industry", "close",
                             "composite_score", "grade"]
                display_cols = ["排名", "代碼", "名稱", "產業", "收盤價",
                                "綜合分數", "等級"]
                available = [c for c in show_cols if c in candidates.columns]
                display = candidates[available].copy()
                display.columns = display_cols[:len(available)]
                st.dataframe(display, use_container_width=True, hide_index=True)

                # 資金分配建議
                if freed_capital > 0 and len(candidates) > 0:
                    st.markdown("#### 資金分配建議")
                    n_picks = min(len(candidates), 5)
                    top_picks = candidates.head(n_picks)
                    per_stock = freed_capital / n_picks

                    alloc_data = []
                    for _, row in top_picks.iterrows():
                        price = row["close"]
                        if price > 0:
                            est_shares = int(per_stock // price // 1000) * 1000
                            est_cost = est_shares * price
                        else:
                            est_shares = 0
                            est_cost = 0
                        alloc_data.append({
                            "代碼": row["stock_id"],
                            "名稱": row.get("name", ""),
                            "現價": row["close"],
                            "綜合分數": row["composite_score"],
                            "建議股數": f"{est_shares:,}",
                            "預估金額": f"${est_cost:,.0f}",
                        })

                    alloc_df = pd.DataFrame(alloc_data)
                    st.dataframe(alloc_df, use_container_width=True,
                                 hide_index=True)
                    st.caption(
                        f"以釋放資金 ${freed_capital:,.0f} "
                        f"平均分配至 {n_picks} 檔，每檔約 ${per_stock:,.0f}，"
                        f"股數以整張(1000股)計"
                    )
            else:
                st.info("目前沒有綜合分數 ≥ 60 的推薦標的，市場整體偏弱，建議保留現金觀望。")

        else:
            # 沒有主頁面分析結果，用快速掃描
            st.info("尚未執行主頁面的「開始分析」，無法推薦替代標的。")
            st.markdown("""
            **如何取得推薦：**
            1. 先到主頁面點擊「開始分析」完成全市場掃描
            2. 再回到此頁面重新「分析庫存」
            3. 系統會從掃描結果中挑選高分標的推薦給你
            """)
