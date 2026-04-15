"""
個股深度分析頁面
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="個股分析", page_icon="🔍", layout="wide")
from utils.theme import inject_custom_css, render_theme_selector
render_theme_selector()
inject_custom_css()
from utils.auth import require_auth
require_auth()
from data.fetcher import lookup_stock_name as _lookup_name
st.title("🔍 個股深度分析")

# 輸入股票代碼
col_input, col_btn = st.columns([3, 1])
with col_input:
    stock_id = st.text_input("輸入股票代碼", placeholder="例: 2330")
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    analyze = st.button("分析", type="primary")

# 輸入代碼後即時顯示名稱
if stock_id and stock_id.strip():
    _name = _lookup_name(stock_id.strip())
    if _name:
        st.markdown(f"**{stock_id.strip()} {_name}**")

if stock_id and analyze:
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
    from utils.indicators import moving_average, rsi, volume_ratio, macd, max_drawdown
    from config.settings import MA_PERIODS, RSI_PERIOD

    stock_id = stock_id.strip()
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    short_start = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")

    with st.spinner(f"載入 {stock_id} 資料..."):
        try:
            price_df = fetch_stock_prices(stock_id, start_date, end_date)
            if price_df.empty:
                st.error("找不到該股票資料，請確認代碼是否正確")
                st.stop()
            price_df = price_df.sort_values("date").reset_index(drop=True)
        except Exception as e:
            st.error(f"資料載入失敗: {e}")
            st.stop()

        # 法人資料
        try:
            inst_df = fetch_institutional_investors(stock_id, short_start, end_date)
        except Exception:
            inst_df = pd.DataFrame()

        # 融資融券
        try:
            margin_df = fetch_margin_data(stock_id, short_start, end_date)
        except Exception:
            margin_df = pd.DataFrame()

        # 美股/夜盤/日盤期貨
        sox_df = tsm_df = night_df = day_futures_df = pd.DataFrame()
        tsmc_close = 0.0
        try:
            sox_df = fetch_us_stock("^SOX", short_start, end_date)
        except Exception:
            pass
        try:
            tsm_df = fetch_us_stock("TSM", short_start, end_date)
        except Exception:
            pass
        try:
            night_df = fetch_night_futures(short_start, end_date)
        except Exception:
            pass
        try:
            day_futures_df = fetch_day_futures(short_start, end_date)
        except Exception:
            pass

        # 台積電收盤價
        if stock_id == "2330":
            tsmc_close = price_df["close"].iloc[-1]
        else:
            try:
                tsmc_p = fetch_stock_prices("2330", short_start, end_date)
                if not tsmc_p.empty:
                    tsmc_close = tsmc_p.sort_values("date")["close"].iloc[-1]
            except Exception:
                pass

        # 大盤指數
        taiex_close = None
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

        # 集保股權
        try:
            tdcc_df = fetch_tdcc_holders(stock_id)
        except Exception:
            tdcc_df = pd.DataFrame()

    # ===== 基本資訊 =====
    latest = price_df.iloc[-1]
    prev = price_df.iloc[-2] if len(price_df) > 1 else latest
    change = latest["close"] - prev["close"]
    change_pct = (change / prev["close"] * 100) if prev["close"] > 0 else 0

    _stock_name = _lookup_name(stock_id)
    st.markdown(f"## {stock_id} {_stock_name}")

    # 最大回撤
    mdd_pct, dd_series = max_drawdown(price_df["close"])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("收盤價", f"{latest['close']:.2f}", f"{change:+.2f} ({change_pct:+.1f}%)")
    c2.metric("最高", f"{latest['high']:.2f}")
    c3.metric("最低", f"{latest['low']:.2f}")
    c4.metric("成交量", f"{int(latest['volume']):,}")
    c5.metric("最大回撤", f"{mdd_pct:.1f}%")

    # ===== 八大策略分數 =====
    st.markdown("### 策略評分")

    strategy_map = {
        "突破均線": ("ma_breakout", MABreakoutStrategy(), {}),
        "量價齊揚": ("volume_price", VolumePriceStrategy(), {}),
        "相對強弱": ("relative_strength", RelativeStrengthStrategy(),
                     {"index_close": taiex_close} if taiex_close is not None and len(taiex_close) >= 20 else {}),
        "法人籌碼": ("institutional_flow", InstitutionalFlowStrategy(),
                     {"institutional_df": inst_df}),
        "技術綜合": ("enhanced_technical", EnhancedTechnicalStrategy(), {}),
        "融資融券": ("margin_analysis", MarginAnalysisStrategy(),
                     {"margin_df": margin_df}),
        "美股連動": ("us_market", USMarketStrategy(),
                     {"sox_df": sox_df, "tsm_df": tsm_df, "tsmc_close": tsmc_close,
                      "night_df": night_df, "day_futures_df": day_futures_df}),
        "大戶籌碼": ("shareholder", ShareholderStrategy(),
                     {"tdcc_df": tdcc_df}),
    }

    scores = {}
    details = {}
    score_keys = {}
    for label, (key, strat, kwargs) in strategy_map.items():
        try:
            scores[label] = strat.score(price_df, **kwargs)
            details[label] = strat.details(price_df, **kwargs)
        except Exception:
            scores[label] = 0
            details[label] = {"signal": "計算錯誤"}
        score_keys[key] = scores[label]

    # 綜合分數
    composite = compute_composite_score(score_keys)

    # 顯示綜合分數
    grade = "S" if composite > 80 else "A" if composite > 65 else "B" if composite > 50 else "C" if composite > 30 else "D"
    grade_color = "🟢" if grade in ("S", "A") else "🟡" if grade == "B" else "🔴"
    st.markdown(f"**{grade_color} 綜合分數：{composite:.0f} / 100（{grade} 級）**")

    scols = st.columns(8)
    for i, (label, score) in enumerate(scores.items()):
        color = "🟢" if score >= 65 else "🟡" if score >= 40 else "🔴"
        scols[i].metric(f"{color} {label}", f"{score:.0f}")
        sig = details[label].get("signal", "")
        if sig:
            scols[i].caption(sig)

    # ===== K線圖 =====
    st.markdown("### 技術分析圖表")

    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.45, 0.2, 0.15, 0.2],
        subplot_titles=("K線 + 均線", "成交量", "RSI", "MACD")
    )

    # K線
    fig.add_trace(go.Candlestick(
        x=price_df["date"],
        open=price_df["open"],
        high=price_df["high"],
        low=price_df["low"],
        close=price_df["close"],
        name="K線",
        increasing_line_color="#EF5350",  # 台股紅漲
        decreasing_line_color="#26A69A",
    ), row=1, col=1)

    # 均線
    colors = {"5": "#FF9800", "10": "#2196F3", "20": "#9C27B0", "60": "#607D8B"}
    for period in MA_PERIODS:
        ma = moving_average(price_df["close"], period)
        fig.add_trace(go.Scatter(
            x=price_df["date"], y=ma,
            name=f"MA{period}",
            line=dict(width=1, color=colors.get(str(period), "#999")),
        ), row=1, col=1)

    # 成交量
    vol_colors = ["#EF5350" if c >= o else "#26A69A"
                  for c, o in zip(price_df["close"], price_df["open"])]
    fig.add_trace(go.Bar(
        x=price_df["date"], y=price_df["volume"],
        name="成交量",
        marker_color=vol_colors,
        showlegend=False
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
        height=900,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0)
    )
    fig.update_xaxes(type="category", nticks=20)

    st.plotly_chart(fig, use_container_width=True)

    # ===== 回撤圖 =====
    if not dd_series.empty:
        with st.expander("📉 最大回撤走勢", expanded=False):
            fig_dd = go.Figure()
            fig_dd.add_trace(go.Scatter(
                x=price_df["date"], y=dd_series,
                fill="tozeroy", name="回撤",
                line=dict(color="#EF5350", width=1),
                fillcolor="rgba(239,83,80,0.3)",
            ))
            fig_dd.add_hline(y=mdd_pct, line_dash="dash", line_color="#FF9800",
                             annotation_text=f"最大回撤 {mdd_pct:.1f}%")
            fig_dd.update_layout(
                height=250, template="plotly_dark",
                yaxis_title="回撤 (%)",
                margin=dict(l=50, r=20, t=30, b=20),
            )
            st.plotly_chart(fig_dd, use_container_width=True)

    # ===== 法人籌碼圖 =====
    if not inst_df.empty:
        with st.expander("🏦 法人買賣超明細", expanded=False):
            inst_df = inst_df.sort_values("date")

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=inst_df["date"], y=inst_df.get("foreign_net", 0),
                name="外資", marker_color="#2196F3"
            ))
            fig2.add_trace(go.Bar(
                x=inst_df["date"], y=inst_df.get("trust_net", 0),
                name="投信", marker_color="#FF9800"
            ))
            fig2.add_trace(go.Bar(
                x=inst_df["date"], y=inst_df.get("dealer_net", 0),
                name="自營商", marker_color="#9C27B0"
            ))
            fig2.update_layout(
                barmode="group",
                height=400,
                template="plotly_dark",
                yaxis_title="買賣超 (張)",
                legend=dict(orientation="h")
            )
            st.plotly_chart(fig2, use_container_width=True)

    # ===== 同產業比較 =====
    if "ranked" in st.session_state and not st.session_state["ranked"].empty:
        ranked = st.session_state["ranked"]
        # 找到這檔股票的產業
        stock_row = ranked[ranked["stock_id"] == stock_id]
        if not stock_row.empty and "industry" in ranked.columns:
            industry = stock_row.iloc[0].get("industry", "")
            if industry:
                peers = ranked[ranked["industry"] == industry].head(10)
                if len(peers) > 1:
                    with st.expander("🏭 同產業比較", expanded=False):
                        st.markdown(f"### 同產業比較（{industry}）")

                        # 標記目前分析的股票
                        peer_data = []
                        for _, row in peers.iterrows():
                            is_current = "→" if row["stock_id"] == stock_id else ""
                            peer_data.append({
                                "": is_current,
                                "排名": int(row["rank"]),
                                "代碼": row["stock_id"],
                                "名稱": row.get("name", ""),
                                "收盤價": row["close"],
                                "綜合分數": row["composite_score"],
                                "等級": str(row["grade"]),
                            })
                        peer_df = pd.DataFrame(peer_data)
                        st.dataframe(peer_df, use_container_width=True, hide_index=True)

                        # 在同產業中的排名
                        all_peers = ranked[ranked["industry"] == industry]
                        peer_rank = all_peers["stock_id"].tolist().index(stock_id) + 1 if stock_id in all_peers["stock_id"].values else 0
                        if peer_rank > 0:
                            st.caption(f"{stock_id} 在 {industry} 產業 {len(all_peers)} 檔中排名第 {peer_rank}")
        else:
            st.caption("尚未執行主頁面掃描，無法顯示同產業比較。先到主頁面「開始分析」後再回來。")

        # === 歷史分數趨勢圖 ===
        from config.settings import CACHE_DIR as _HC
        import plotly.graph_objects as _htgo
        _hdir = _HC.parent / "history"
        if _hdir.exists():
            _hfiles = sorted(_hdir.glob("*.parquet"), reverse=True)[:30]
            _hdates, _hscores = [], []
            _score_keys = {
                "均線": "ma_breakout_score", "量價": "volume_price_score",
                "強弱": "relative_strength_score", "法人": "institutional_flow_score",
                "技術": "enhanced_technical_score", "融資": "margin_analysis_score",
                "美股": "us_market_score", "大戶": "shareholder_score",
            }
            _sub_trends = {k: [] for k in _score_keys}

            for _hf in _hfiles:
                try:
                    _hdf = pd.read_parquet(_hf)
                    _row = _hdf[_hdf["stock_id"] == stock_id]
                    if not _row.empty and "composite_score" in _hdf.columns:
                        _hdates.append(_hf.stem)
                        _hscores.append(_row["composite_score"].iloc[0])
                        for label, col in _score_keys.items():
                            _sub_trends[label].append(_row[col].iloc[0] if col in _row.columns else 0)
                    else:
                        for label in _score_keys:
                            _sub_trends[label].append(None)
                except Exception:
                    continue

            if len(_hdates) >= 2:
                st.markdown("---")
                with st.expander("📈 歷史分數趨勢", expanded=False):
                    _hdates_r = list(reversed(_hdates))
                    _hscores_r = list(reversed(_hscores))

                    _hfig = _htgo.Figure()
                    _hfig.add_trace(_htgo.Scatter(
                        x=_hdates_r, y=_hscores_r,
                        mode="lines+markers", name="綜合分數",
                        line=dict(color="#00D2FF", width=3),
                        marker=dict(size=8),
                    ))
                    for label in _score_keys:
                        vals = list(reversed(_sub_trends[label]))
                        if any(v is not None for v in vals):
                            _hfig.add_trace(_htgo.Scatter(
                                x=_hdates_r, y=vals,
                                mode="lines", name=label,
                                line=dict(width=1, dash="dot"),
                                opacity=0.6,
                            ))
                    _hfig.update_layout(
                        height=350, template="plotly_dark",
                        margin=dict(l=50, r=20, t=10, b=30),
                        yaxis=dict(title="分數", range=[0, 100]),
                        legend=dict(orientation="h", y=-0.15),
                        hovermode="x unified",
                    )
                    st.plotly_chart(_hfig, use_container_width=True)

                    # 分數變化摘要
                    if len(_hscores) >= 2:
                        _diff = round(_hscores[0] - _hscores[1], 1)
                        _arrow = "⬆️" if _diff > 0 else ("⬇️" if _diff < 0 else "➡️")
                        st.caption(f"{_arrow} 較前次分析：{'+' if _diff > 0 else ''}{_diff} 分")

elif not stock_id:
    st.info("請輸入股票代碼開始分析，例如：2330 (台積電)、2317 (鴻海)、2454 (聯發科)")
