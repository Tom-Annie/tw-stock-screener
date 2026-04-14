"""
UI 風格主題：科技、簡約、炫泡
在 sidebar 提供切換按鈕
"""
import streamlit as st

_DEFAULT_THEME = "科技"


def _get_current_theme() -> str:
    return st.session_state.get("ui_theme", _DEFAULT_THEME)


def render_theme_selector():
    """在 sidebar 渲染主題切換器（radio）"""
    current = _get_current_theme()
    options = list(_THEMES.keys())
    try:
        idx = options.index(current)
    except ValueError:
        idx = 0
    choice = st.sidebar.radio(
        "🎨 介面風格",
        options=options,
        index=idx,
        horizontal=True,
        key="ui_theme",
    )
    return choice


def inject_custom_css():
    """根據目前主題注入 CSS"""
    theme = _get_current_theme()
    css = _THEMES.get(theme, _THEMES[_DEFAULT_THEME])
    st.markdown(css, unsafe_allow_html=True)


# ============ 主題 1：科技（原本的藍紫漸層） ============
_THEME_TECH = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
code, .stCode, pre { font-family: 'JetBrains Mono', monospace !important; }

h1 {
    background: linear-gradient(135deg, #00D2FF 0%, #7A5FFF 50%, #FF6FD8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700 !important;
    letter-spacing: -0.5px;
}
h2, h3 { color: #E0E8FF !important; font-weight: 600 !important; }

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
    color: #8899BB !important; font-size: 0.85rem !important;
    text-transform: uppercase; letter-spacing: 0.5px;
}
[data-testid="stMetricValue"] { color: #00D2FF !important; font-weight: 700 !important; font-size: 1.8rem !important; }

[data-testid="stDataFrame"] {
    border: 1px solid rgba(0,210,255,0.15);
    border-radius: 10px; overflow: hidden;
}
[data-testid="stDataFrame"] th {
    background: rgba(0,210,255,0.1) !important;
    color: #00D2FF !important; font-weight: 600 !important;
    text-transform: uppercase; letter-spacing: 0.5px;
}
[data-testid="stDataFrame"] tr:hover td { background: rgba(0,210,255,0.06) !important; }

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00D2FF 0%, #7A5FFF 100%) !important;
    border: none !important; border-radius: 10px !important;
    font-weight: 600 !important; padding: 0.6rem 2rem !important;
    box-shadow: 0 4px 15px rgba(0,210,255,0.25) !important;
    transition: all 0.3s ease !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 25px rgba(0,210,255,0.4) !important;
    transform: translateY(-1px);
}

.stProgress > div > div {
    background: linear-gradient(90deg, #00D2FF, #7A5FFF, #FF6FD8) !important;
    border-radius: 10px;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%) !important;
    border-right: 1px solid rgba(0,210,255,0.1);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 4px; background: rgba(0,210,255,0.05);
    border-radius: 10px; padding: 4px;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(0,210,255,0.15), rgba(122,95,255,0.15)) !important;
    color: #00D2FF !important;
}
</style>
"""


# ============ 主題 2：簡約（黑白灰、極簡） ============
_THEME_MINIMAL = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans TC', -apple-system, sans-serif;
}

h1 {
    color: #FAFAFA !important;
    font-weight: 300 !important;
    letter-spacing: 1px;
    border-bottom: 1px solid #333;
    padding-bottom: 0.5rem;
}
h2, h3 {
    color: #D0D0D0 !important;
    font-weight: 400 !important;
    letter-spacing: 0.5px;
}

[data-testid="stMetric"] {
    background: transparent;
    border: 1px solid #2a2a2a;
    border-radius: 2px;
    padding: 20px 24px;
    transition: border-color 0.2s ease;
}
[data-testid="stMetric"]:hover {
    border-color: #555;
}
[data-testid="stMetricLabel"] {
    color: #888 !important; font-size: 0.75rem !important;
    font-weight: 400 !important;
    text-transform: uppercase; letter-spacing: 1.5px;
}
[data-testid="stMetricValue"] {
    color: #FAFAFA !important;
    font-weight: 300 !important;
    font-size: 2rem !important;
    letter-spacing: -0.5px;
}

[data-testid="stDataFrame"] {
    border: 1px solid #2a2a2a;
    border-radius: 2px;
}
[data-testid="stDataFrame"] th {
    background: #1a1a1a !important;
    color: #AAA !important;
    font-weight: 500 !important;
    font-size: 0.8rem !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1px solid #333 !important;
}
[data-testid="stDataFrame"] tr:hover td {
    background: #1a1a1a !important;
}

.stButton > button[kind="primary"] {
    background: #FAFAFA !important;
    color: #0E0E0E !important;
    border: none !important;
    border-radius: 2px !important;
    font-weight: 500 !important;
    padding: 0.6rem 2rem !important;
    letter-spacing: 1px;
    text-transform: uppercase;
    transition: background 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    background: #CCC !important;
}
.stButton > button:not([kind="primary"]) {
    border: 1px solid #444 !important;
    border-radius: 2px !important;
    color: #CCC !important;
    background: transparent !important;
}

.stProgress > div > div {
    background: #FAFAFA !important;
    border-radius: 0 !important;
}

[data-testid="stSidebar"] {
    background: #0a0a0a !important;
    border-right: 1px solid #222;
}
[data-testid="stSidebar"] .stMarkdown hr {
    border-color: #222 !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 2rem;
    background: transparent;
    border-bottom: 1px solid #2a2a2a;
    padding: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 0 !important;
    color: #666 !important;
    font-weight: 400 !important;
    padding: 0.5rem 0 !important;
}
.stTabs [aria-selected="true"] {
    color: #FAFAFA !important;
    border-bottom: 2px solid #FAFAFA !important;
}

[data-testid="stPlotlyChart"] {
    border: 1px solid #2a2a2a;
    border-radius: 2px;
}
</style>
"""


# ============ 主題 3：炫泡（彩虹漸層、光暈、動畫） ============
_THEME_FLASHY = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Inter:wght@400;500;600&display=swap');

@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 15px rgba(255,64,179,0.3), 0 0 30px rgba(122,95,255,0.2); }
    50% { box-shadow: 0 0 25px rgba(255,64,179,0.5), 0 0 50px rgba(122,95,255,0.4); }
}
@keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-3px); }
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

h1 {
    font-family: 'Orbitron', monospace !important;
    background: linear-gradient(90deg, #FF40B3, #FFD700, #00F5FF, #7A5FFF, #FF40B3);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 3s linear infinite;
    font-weight: 900 !important;
    letter-spacing: 2px;
    text-transform: uppercase;
}
h2, h3 {
    font-family: 'Orbitron', monospace !important;
    background: linear-gradient(135deg, #FF40B3, #00F5FF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-weight: 700 !important;
    letter-spacing: 1px;
}

[data-testid="stMetric"] {
    background: linear-gradient(135deg,
        rgba(255,64,179,0.15) 0%,
        rgba(122,95,255,0.15) 50%,
        rgba(0,245,255,0.15) 100%);
    border: 2px solid transparent;
    background-clip: padding-box;
    border-radius: 20px;
    padding: 20px 24px;
    position: relative;
    animation: float 4s ease-in-out infinite;
    backdrop-filter: blur(15px);
}
[data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 20px;
    padding: 2px;
    background: linear-gradient(135deg, #FF40B3, #7A5FFF, #00F5FF);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    pointer-events: none;
}
[data-testid="stMetric"]:hover {
    animation: pulse-glow 1.5s ease-in-out infinite;
    transform: translateY(-4px) scale(1.02);
    transition: transform 0.3s ease;
}
[data-testid="stMetricLabel"] {
    color: #FFB3E0 !important;
    font-family: 'Orbitron', monospace !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 2px;
}
[data-testid="stMetricValue"] {
    background: linear-gradient(90deg, #FFD700, #FF40B3, #00F5FF);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: shimmer 4s linear infinite;
    font-weight: 900 !important;
    font-size: 2rem !important;
    font-family: 'Orbitron', monospace !important;
}

[data-testid="stDataFrame"] {
    border: 2px solid transparent;
    border-radius: 16px;
    background: linear-gradient(rgba(10,10,30,0.9), rgba(10,10,30,0.9)) padding-box,
                linear-gradient(135deg, #FF40B3, #7A5FFF, #00F5FF) border-box;
    overflow: hidden;
}
[data-testid="stDataFrame"] th {
    background: linear-gradient(135deg, rgba(255,64,179,0.25), rgba(0,245,255,0.25)) !important;
    color: #FFD700 !important;
    font-family: 'Orbitron', monospace !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}
[data-testid="stDataFrame"] tr:hover td {
    background: rgba(255,64,179,0.08) !important;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #FF40B3 0%, #7A5FFF 50%, #00F5FF 100%) !important;
    background-size: 200% auto !important;
    border: none !important;
    border-radius: 50px !important;
    font-family: 'Orbitron', monospace !important;
    font-weight: 700 !important;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 0.7rem 2.5rem !important;
    box-shadow: 0 0 20px rgba(255,64,179,0.5),
                0 0 40px rgba(122,95,255,0.3) !important;
    animation: shimmer 3s linear infinite;
    transition: all 0.3s ease !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) scale(1.05);
    box-shadow: 0 0 30px rgba(255,64,179,0.8),
                0 0 60px rgba(0,245,255,0.5) !important;
}

.stProgress > div > div {
    background: linear-gradient(90deg, #FF40B3, #FFD700, #00F5FF, #7A5FFF, #FF40B3) !important;
    background-size: 200% auto;
    animation: shimmer 2s linear infinite;
    border-radius: 20px;
    box-shadow: 0 0 15px rgba(255,64,179,0.5);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg,
        #1a0520 0%,
        #2d1053 50%,
        #051528 100%) !important;
    border-right: 2px solid;
    border-image: linear-gradient(180deg, #FF40B3, #00F5FF) 1;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: rgba(255,64,179,0.05);
    border-radius: 50px;
    padding: 6px;
    border: 1px solid rgba(255,64,179,0.2);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 50px !important;
    font-family: 'Orbitron', monospace !important;
    font-size: 0.85rem !important;
    padding: 8px 20px !important;
    color: #FFB3E0 !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #FF40B3, #7A5FFF) !important;
    color: white !important;
    box-shadow: 0 0 15px rgba(255,64,179,0.5);
}

[data-testid="stPlotlyChart"] {
    border: 2px solid transparent;
    border-radius: 20px;
    background: linear-gradient(rgba(10,10,30,0.5), rgba(10,10,30,0.5)) padding-box,
                linear-gradient(135deg, #FF40B3, #00F5FF) border-box;
    overflow: hidden;
}

/* 炫泡主題：radio/checkbox 也要亮起來 */
[data-testid="stSlider"] [role="slider"] {
    background: linear-gradient(135deg, #FF40B3, #00F5FF) !important;
    box-shadow: 0 0 15px rgba(255,64,179,0.6);
}
</style>
"""


_THEMES = {
    "科技": _THEME_TECH,
    "簡約": _THEME_MINIMAL,
    "炫泡": _THEME_FLASHY,
}
