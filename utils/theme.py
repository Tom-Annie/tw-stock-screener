"""
科技風格 UI 主題
注入自訂 CSS 讓 Streamlit 頁面更有科技感
"""
import streamlit as st


def inject_custom_css():
    """注入全域自訂 CSS"""
    st.markdown(_CSS, unsafe_allow_html=True)


_CSS = """
<style>
/* ===== 全域字體與背景 ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
code, .stCode, pre {
    font-family: 'JetBrains Mono', monospace !important;
}

/* ===== 主標題漸層 ===== */
h1 {
    background: linear-gradient(135deg, #00D2FF 0%, #7A5FFF 50%, #FF6FD8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700 !important;
    letter-spacing: -0.5px;
}
h2, h3 {
    color: #E0E8FF !important;
    font-weight: 600 !important;
}

/* ===== 玻璃卡片效果 — Metric ===== */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(0,210,255,0.08) 0%, rgba(122,95,255,0.08) 100%);
    border: 1px solid rgba(0,210,255,0.2);
    border-radius: 12px;
    padding: 16px 20px;
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
    box-shadow: 0 0 15px rgba(0,210,255,0.05);
}
[data-testid="stMetric"]:hover {
    border-color: rgba(0,210,255,0.5);
    box-shadow: 0 0 25px rgba(0,210,255,0.15);
    transform: translateY(-2px);
}
[data-testid="stMetricLabel"] {
    color: #8899BB !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
[data-testid="stMetricValue"] {
    color: #00D2FF !important;
    font-weight: 700 !important;
    font-size: 1.8rem !important;
}

/* ===== 資料表格 ===== */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(0,210,255,0.15);
    border-radius: 10px;
    overflow: hidden;
}
[data-testid="stDataFrame"] table {
    font-size: 0.88rem;
}
[data-testid="stDataFrame"] th {
    background: rgba(0,210,255,0.1) !important;
    color: #00D2FF !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    font-size: 0.8rem !important;
    letter-spacing: 0.5px;
}
[data-testid="stDataFrame"] tr:hover td {
    background: rgba(0,210,255,0.06) !important;
}

/* ===== 按鈕 ===== */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00D2FF 0%, #7A5FFF 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    letter-spacing: 0.5px;
    padding: 0.6rem 2rem !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(0,210,255,0.25) !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 25px rgba(0,210,255,0.4) !important;
    transform: translateY(-1px);
}
.stButton > button:not([kind="primary"]) {
    border: 1px solid rgba(0,210,255,0.3) !important;
    border-radius: 8px !important;
    color: #00D2FF !important;
    transition: all 0.2s ease !important;
}
.stButton > button:not([kind="primary"]):hover {
    background: rgba(0,210,255,0.1) !important;
    border-color: #00D2FF !important;
}

/* ===== 進度條 ===== */
.stProgress > div > div {
    background: linear-gradient(90deg, #00D2FF, #7A5FFF, #FF6FD8) !important;
    border-radius: 10px;
}

/* ===== Sidebar ===== */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%) !important;
    border-right: 1px solid rgba(0,210,255,0.1);
}
[data-testid="stSidebar"] .stMarkdown hr {
    border-color: rgba(0,210,255,0.15) !important;
    margin: 1rem 0;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    background: none;
    -webkit-text-fill-color: #00D2FF;
    font-size: 1rem !important;
}

/* ===== Tabs ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: rgba(0,210,255,0.05);
    border-radius: 10px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 8px 16px !important;
    font-weight: 500 !important;
    color: #8899BB !important;
    transition: all 0.2s ease;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(0,210,255,0.15), rgba(122,95,255,0.15)) !important;
    color: #00D2FF !important;
    border-bottom: none !important;
}

/* ===== Slider ===== */
[data-testid="stSlider"] [role="slider"] {
    background: #00D2FF !important;
    box-shadow: 0 0 8px rgba(0,210,255,0.4);
}
[data-testid="stSlider"] [data-testid="stTickBar"] > div {
    background: linear-gradient(90deg, #00D2FF, #7A5FFF) !important;
}

/* ===== 警告/成功/資訊框 ===== */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border-left-width: 4px !important;
    backdrop-filter: blur(5px);
}

/* ===== Selectbox / Multiselect ===== */
[data-baseweb="select"], [data-baseweb="input"] {
    border-radius: 8px !important;
}

/* ===== Radio ===== */
.stRadio > div {
    gap: 0.3rem;
}

/* ===== Checkbox ===== */
.stCheckbox label span {
    font-weight: 500;
}

/* ===== Caption (token 顯示等) ===== */
.stCaption {
    font-family: 'JetBrains Mono', monospace !important;
}

/* ===== Download 按鈕 ===== */
.stDownloadButton > button {
    background: transparent !important;
    border: 1px solid rgba(0,210,255,0.3) !important;
    border-radius: 8px !important;
    color: #00D2FF !important;
}
.stDownloadButton > button:hover {
    background: rgba(0,210,255,0.1) !important;
    box-shadow: 0 0 15px rgba(0,210,255,0.15);
}

/* ===== 微調 Plotly 圖表容器 ===== */
[data-testid="stPlotlyChart"] {
    border: 1px solid rgba(0,210,255,0.1);
    border-radius: 12px;
    overflow: hidden;
}

/* ===== 頁面底部漸層分隔線 ===== */
.main .block-container {
    padding-top: 2rem;
}
</style>
"""
