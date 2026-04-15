"""
策略監控儀表板 — 看各策略近期分數分佈、健康狀況、異常偵測
"""
import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(page_title="策略監控", page_icon="📡", layout="wide")
from utils.theme import inject_custom_css, render_theme_selector
render_theme_selector()
inject_custom_css()
from utils.auth import require_auth
require_auth()

st.title("📡 策略監控儀表板")
st.caption("追蹤 8 支策略的分數分佈、健康狀況與異常訊號")

from config.settings import CACHE_DIR
from utils.data_quality import SCORE_COLS, check_scan_quality

HISTORY_DIR = CACHE_DIR.parent / "history"

STRAT_LABELS = {
    "ma_breakout_score": "均線突破",
    "volume_price_score": "量價齊揚",
    "relative_strength_score": "相對強弱",
    "institutional_flow_score": "法人籌碼",
    "enhanced_technical_score": "進階技術",
    "margin_analysis_score": "融資融券",
    "us_market_score": "美股連動",
    "shareholder_score": "大戶籌碼",
}


@st.cache_data(ttl=600)
def load_history(n_days: int = 30) -> pd.DataFrame:
    """載入最近 N 天的歷史，回傳 long-format DataFrame（date, stock_id, strategy, score）"""
    files = sorted(HISTORY_DIR.glob("*.parquet"), reverse=True)[:n_days]
    rows = []
    for f in files:
        date_str = f.stem
        try:
            df = pd.read_parquet(f)
        except Exception:
            continue
        for col in SCORE_COLS:
            if col not in df.columns:
                continue
            for sid, score in zip(df["stock_id"], df[col]):
                rows.append({
                    "date": date_str, "stock_id": sid,
                    "strategy": col, "score": score,
                })
    return pd.DataFrame(rows)


if not HISTORY_DIR.exists():
    st.warning(f"⚠️ 歷史目錄不存在：{HISTORY_DIR}")
    st.info("請先跑過至少一次 `scripts/daily_local.py` 或主頁的掃描，會自動存 parquet")
    st.stop()

files = sorted(HISTORY_DIR.glob("*.parquet"), reverse=True)
if not files:
    st.warning("目前沒有歷史快照。請先執行掃描。")
    st.stop()

col_a, col_b = st.columns([1, 3])
with col_a:
    n_days = st.number_input("查看最近幾天", 1, 90, value=min(30, len(files)))
with col_b:
    st.metric("可用歷史檔數", len(files))

df_long = load_history(n_days)
if df_long.empty:
    st.warning("歷史檔讀取失敗或全空")
    st.stop()

# 最新一份的資料品質
st.markdown("## 🚨 今日資料品質")
latest_file = files[0]
latest_df = pd.read_parquet(latest_file)
issues = check_scan_quality(latest_df)
if issues:
    st.error(f"發現 {len(issues)} 項異常：")
    for msg in issues:
        st.write(f"• {msg}")
else:
    st.success(f"✅ {latest_file.stem} 資料健康，無異常")

st.markdown("---")

# 各策略分數分佈統計
st.markdown("## 📊 策略健康總覽")
summary_rows = []
for col in SCORE_COLS:
    sub = df_long[df_long["strategy"] == col]["score"].dropna()
    if sub.empty:
        continue
    nunique = sub.nunique()
    summary_rows.append({
        "策略": STRAT_LABELS.get(col, col),
        "樣本數": len(sub),
        "均值": round(sub.mean(), 1),
        "中位數": round(sub.median(), 1),
        "標準差": round(sub.std(), 1),
        "最小": round(sub.min(), 1),
        "最大": round(sub.max(), 1),
        "唯一值": nunique,
        "健康": "⚠️ 卡常數" if nunique == 1 else (
            "⚠️ 低變異" if sub.std() < 2 else "✅"
        ),
    })
summary_df = pd.DataFrame(summary_rows)
st.dataframe(summary_df, use_container_width=True, hide_index=True)

st.markdown("---")

# 分佈比較（box plot via st.bar_chart on histogram bins）
st.markdown("## 📉 各策略分數分佈（最近 N 天）")
strat_pick = st.multiselect(
    "選擇策略（預設全選）",
    options=list(STRAT_LABELS.keys()),
    default=list(STRAT_LABELS.keys()),
    format_func=lambda k: STRAT_LABELS[k],
)
if strat_pick:
    # 並排 histograms
    bins = np.arange(0, 105, 5)
    hist_data = {}
    for col in strat_pick:
        sub = df_long[df_long["strategy"] == col]["score"].dropna()
        counts, _ = np.histogram(sub, bins=bins)
        hist_data[STRAT_LABELS.get(col, col)] = counts
    hist_df = pd.DataFrame(hist_data,
                            index=[f"{int(b)}-{int(b+5)}" for b in bins[:-1]])
    st.bar_chart(hist_df, height=350)

st.markdown("---")

# 每日平均分數趨勢
st.markdown("## 📈 策略平均分數走勢")
trend = df_long.groupby(["date", "strategy"])["score"].mean().reset_index()
trend_wide = trend.pivot(index="date", columns="strategy", values="score")
trend_wide = trend_wide.rename(columns=STRAT_LABELS).sort_index()
if len(trend_wide) >= 2:
    st.line_chart(trend_wide, height=350)
else:
    st.info("至少 2 天歷史才能畫趨勢圖")

st.markdown("---")

# 異常偵測歷史
st.markdown("## 🔍 歷史異常紀錄（逐日掃描結果）")
anomaly_rows = []
for f in files[:n_days]:
    try:
        df = pd.read_parquet(f)
        issues_f = check_scan_quality(df)
        if issues_f:
            for m in issues_f:
                anomaly_rows.append({"日期": f.stem, "異常": m})
    except Exception:
        pass

if anomaly_rows:
    st.dataframe(pd.DataFrame(anomaly_rows), use_container_width=True,
                 hide_index=True)
else:
    st.success("✅ 查看範圍內皆無異常")
