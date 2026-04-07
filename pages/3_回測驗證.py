"""
回測驗證頁面
驗證選股策略的歷史表現
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="回測驗證", page_icon="📉", layout="wide")
from utils.theme import inject_custom_css
inject_custom_css()
from utils.auth import require_auth
require_auth()
st.title("📉 策略回測驗證")
st.markdown("用歷史資料驗證選股策略的實際表現")


def _lookup_name(sid: str) -> str:
    from data.fetcher import lookup_stock_name
    return lookup_stock_name(sid)


# 輸入
col1, col2, col3 = st.columns(3)
with col1:
    stock_id = st.text_input("股票代碼", placeholder="例: 2330")
with col2:
    lookback_days = st.selectbox("回測天數", [30, 60, 90, 120], index=1)
with col3:
    hold_days = st.selectbox("持有天數 (買入後幾天賣出)", [1, 3, 5, 10, 20], index=2)

# 輸入代碼後即時顯示名稱
if stock_id and stock_id.strip():
    _name = _lookup_name(stock_id.strip())
    if _name:
        st.markdown(f"**{stock_id.strip()} {_name}**")

run_backtest = st.button("開始回測", type="primary")

if stock_id and run_backtest:
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

    stock_id = stock_id.strip()
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days + 120)).strftime("%Y-%m-%d")
    short_start = (datetime.now() - timedelta(days=lookback_days + 40)).strftime("%Y-%m-%d")

    _stock_name = _lookup_name(stock_id)
    _display = f"{stock_id} {_stock_name}" if _stock_name else stock_id
    with st.spinner(f"載入 {_display} 歷史資料..."):
        try:
            price_df = fetch_stock_prices(stock_id, start_date, end_date)
            if price_df.empty or len(price_df) < 80:
                st.error("資料不足，請確認代碼或縮短回測天數")
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

        # 美股/夜盤 (全回測期間共用)
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
        if stock_id == "2330" and not price_df.empty:
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

    # 初始化八大策略
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

    st.info(f"📊 {_display}｜回測期間: 最近 {lookback_days} 個交易日，持有 {hold_days} 天後賣出")

    # 逐日回測
    results = []
    min_start = 60  # 至少需要 60 天歷史才能計算

    progress = st.progress(0)
    total_days = len(price_df) - min_start - hold_days

    for i in range(min_start, len(price_df) - hold_days):
        pct = int((i - min_start) / max(total_days, 1) * 100)
        progress.progress(min(pct, 100))

        # 用到第 i 天的資料算分
        window = price_df.iloc[:i + 1].copy()
        buy_date = price_df.iloc[i]["date"]
        buy_price = price_df.iloc[i]["close"]
        sell_price = price_df.iloc[i + hold_days]["close"]
        ret = (sell_price / buy_price - 1) * 100

        # 計算各策略分數
        scores = {}
        for key, strat in strategies.items():
            try:
                kwargs = {}
                if key == "institutional_flow" and not inst_df.empty:
                    inst_window = inst_df[inst_df["date"] <= buy_date].tail(20)
                    kwargs["institutional_df"] = inst_window
                elif key == "margin_analysis" and not margin_df.empty:
                    margin_window = margin_df[margin_df["date"] <= buy_date].tail(20)
                    kwargs["margin_df"] = margin_window
                elif key == "relative_strength":
                    if taiex_close is not None and len(taiex_close) >= 20:
                        kwargs["index_close"] = taiex_close
                elif key == "us_market":
                    kwargs.update(
                        sox_df=sox_df, tsm_df=tsm_df, tsmc_close=tsmc_close,
                        night_df=night_df, day_futures_df=day_futures_df
                    )
                elif key == "shareholder" and not tdcc_df.empty:
                    kwargs["tdcc_df"] = tdcc_df
                scores[key] = strat.score(window, **kwargs)
            except Exception:
                scores[key] = 0

        composite = compute_composite_score(scores)

        results.append({
            "date": buy_date,
            "buy_price": round(buy_price, 2),
            "sell_price": round(sell_price, 2),
            "return_pct": round(ret, 2),
            "composite_score": round(composite, 1),
            **{f"{k}_score": round(v, 1) for k, v in scores.items()}
        })

    progress.progress(100)
    df = pd.DataFrame(results)

    if df.empty:
        st.warning("回測資料不足")
        st.stop()

    # 只看回測期間
    df = df.tail(lookback_days)

    # ===== 分析結果 =====
    st.markdown("---")
    st.markdown("### 回測結果")

    # 按綜合分數分組分析
    df["grade"] = pd.cut(
        df["composite_score"],
        bins=[-1, 30, 50, 65, 80, 101],
        labels=["D(<30)", "C(30-50)", "B(50-65)", "A(65-80)", "S(>80)"]
    )

    # 各等級勝率統計
    grade_stats = df.groupby("grade", observed=True).agg(
        count=("return_pct", "count"),
        win_rate=("return_pct", lambda x: (x > 0).mean() * 100),
        avg_return=("return_pct", "mean"),
        max_return=("return_pct", "max"),
        max_loss=("return_pct", "min"),
    ).round(2)

    col_a, col_b, col_c, col_d = st.columns(4)

    # 高分組 (>=65) 的統計
    high_score = df[df["composite_score"] >= 65]
    low_score = df[df["composite_score"] < 65]

    overall_wr = (df["return_pct"] > 0).mean() * 100
    high_wr = (high_score["return_pct"] > 0).mean() * 100 if len(high_score) > 0 else 0
    high_avg = high_score["return_pct"].mean() if len(high_score) > 0 else 0
    low_wr = (low_score["return_pct"] > 0).mean() * 100 if len(low_score) > 0 else 0

    col_a.metric("整體勝率", f"{overall_wr:.1f}%")
    col_b.metric("高分組(>=65)勝率", f"{high_wr:.1f}%",
                 delta=f"{high_wr - overall_wr:+.1f}%" if len(high_score) > 0 else None)
    col_c.metric("高分組平均報酬", f"{high_avg:+.2f}%")
    col_d.metric("回測交易天數", f"{len(df)}")

    # 各等級勝率表
    with st.expander("📊 各等級詳細統計", expanded=False):
        grade_display = grade_stats.copy()
        grade_display.columns = ["交易次數", "勝率%", "平均報酬%", "最大獲利%", "最大虧損%"]
        st.dataframe(grade_display, use_container_width=True)

    # 最大回撤
    from utils.indicators import max_drawdown as calc_mdd

    # 累積報酬曲線
    st.markdown("#### 累積報酬曲線")

    # 策略: 只在高分時買入
    df["strategy_return"] = df.apply(
        lambda r: r["return_pct"] if r["composite_score"] >= 65 else 0, axis=1
    )
    df["cumulative_strategy"] = (1 + df["strategy_return"] / 100).cumprod() * 100 - 100
    df["cumulative_buyhold"] = (1 + df["return_pct"] / 100).cumprod() * 100 - 100

    # 計算策略與對照組的最大回撤
    strat_equity = (1 + df["strategy_return"] / 100).cumprod()
    bh_equity = (1 + df["return_pct"] / 100).cumprod()
    strat_mdd, strat_dd = calc_mdd(strat_equity)
    bh_mdd, bh_dd = calc_mdd(bh_equity)

    md1, md2 = st.columns(2)
    md1.metric("策略最大回撤", f"{strat_mdd:.1f}%")
    md2.metric("對照組最大回撤", f"{bh_mdd:.1f}%",
               delta=f"{bh_mdd - strat_mdd:+.1f}%" if strat_mdd != 0 else None,
               delta_color="inverse")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumulative_strategy"],
        name="策略 (>=65分才買)", line=dict(color="#FF9800", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["cumulative_buyhold"],
        name="每天都買 (對照組)", line=dict(color="#666", width=1, dash="dash")
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="white", opacity=0.3)
    fig.update_layout(
        height=400, template="plotly_dark",
        yaxis_title="累積報酬 (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 回撤走勢圖
    with st.expander("📉 回撤走勢圖", expanded=False):
        fig_dd = go.Figure()
        if not strat_dd.empty:
            fig_dd.add_trace(go.Scatter(
                x=df["date"], y=strat_dd,
                fill="tozeroy", name="策略回撤",
                line=dict(color="#FF9800", width=1),
                fillcolor="rgba(255,152,0,0.2)",
            ))
        if not bh_dd.empty:
            fig_dd.add_trace(go.Scatter(
                x=df["date"], y=bh_dd,
                name="對照組回撤",
                line=dict(color="#666", width=1, dash="dash"),
            ))
        fig_dd.update_layout(
            height=250, template="plotly_dark",
            yaxis_title="回撤 (%)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=50, r=20, t=30, b=20),
        )
        st.plotly_chart(fig_dd, use_container_width=True)

    # 分數 vs 報酬散佈圖
    st.markdown("#### 綜合分數 vs 實際報酬")
    fig2 = go.Figure()
    colors = ["#EF5350" if r < 0 else "#26A69A" for r in df["return_pct"]]
    fig2.add_trace(go.Scatter(
        x=df["composite_score"], y=df["return_pct"],
        mode="markers", marker=dict(color=colors, size=6, opacity=0.6),
        name="交易",
        hovertemplate="分數: %{x}<br>報酬: %{y:.2f}%<extra></extra>"
    ))
    fig2.add_hline(y=0, line_dash="dot", line_color="white", opacity=0.3)
    fig2.add_vline(x=65, line_dash="dot", line_color="#FF9800", opacity=0.5,
                   annotation_text="A級門檻")
    fig2.update_layout(
        height=400, template="plotly_dark",
        xaxis_title="綜合分數", yaxis_title="報酬率 (%)"
    )
    st.plotly_chart(fig2, use_container_width=True)

    # 各策略相關性
    with st.expander("🔬 各策略相關性分析", expanded=False):
        score_cols = [c for c in df.columns if c.endswith("_score")]
        correlations = {}
        for col in score_cols:
            corr = df[col].corr(df["return_pct"])
            name = col.replace("_score", "")
            correlations[name] = round(corr, 3)

        corr_df = pd.DataFrame([correlations]).T
        corr_df.columns = ["與報酬的相關係數"]
        corr_df = corr_df.sort_values("與報酬的相關係數", ascending=False)
        st.dataframe(corr_df, use_container_width=True)

        st.caption("相關係數越高，代表該策略對預測漲跌越有效。可根據此結果調整主頁面的策略權重。")

else:
    st.markdown("""
    ### 使用方式

    1. 輸入股票代碼
    2. 選擇回測天數和持有天數
    3. 點擊「開始回測」

    ### 回測邏輯

    - 模擬每個交易日用當時可用的資料計算 **八大策略** 分數
    - 假設當天收盤買入，N 天後收盤賣出
    - 統計不同評分等級的勝率和報酬

    ### 怎麼看結果

    - **高分組勝率 > 整體勝率** → 策略有效
    - **累積報酬曲線向上** → 策略長期可獲利
    - **相關性高的策略** → 加大權重
    """)
