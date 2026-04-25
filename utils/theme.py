"""
UI 風格主題：科技、簡約、炫泡
在 sidebar 提供切換按鈕
"""
import streamlit as st

_DEFAULT_THEME = "科技"


def _get_current_theme() -> str:
    return st.session_state.get("ui_theme", _DEFAULT_THEME)


def render_theme_selector():
    """在 sidebar 渲染主題切換器（radio）

    重要:同時使用 `key=` 和 `index=` 是 Streamlit 多頁應用的陷阱
    — 換頁後 `index` 會覆蓋 session_state,造成主題重置。
    正確做法:先用 `if key not in session_state` 補預設值,
    然後 widget 只用 `key=`,讓 session_state 當唯一真實來源。
    """
    options = list(_THEMES.keys())
    if "ui_theme" not in st.session_state or \
            st.session_state["ui_theme"] not in options:
        st.session_state["ui_theme"] = _DEFAULT_THEME
    return st.sidebar.radio(
        "🎨 介面風格",
        options=options,
        horizontal=True,
        key="ui_theme",
    )


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


# ============ 主題 2：賽博龐克（霓虹綠粉 + 掃描線） ============
_THEME_CYBERPUNK = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Share+Tech+Mono&display=swap');

@keyframes scanline {
    0% { transform: translateY(-100%); }
    100% { transform: translateY(100vh); }
}
@keyframes glitch {
    0%, 100% { text-shadow: 2px 0 #FF0080, -2px 0 #00FFC8; }
    25% { text-shadow: -2px 0 #FF0080, 2px 0 #00FFC8; }
    50% { text-shadow: 2px 2px #FF0080, -2px -2px #00FFC8; }
    75% { text-shadow: -2px 2px #FF0080, 2px -2px #00FFC8; }
}
@keyframes neon-flicker {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.85; }
}

html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; }
code, .stCode, pre { font-family: 'Share Tech Mono', monospace !important; color: #00FFC8 !important; }

[data-testid="stAppViewContainer"]::before {
    content: '';
    position: fixed; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #00FFC8, transparent);
    animation: scanline 6s linear infinite;
    pointer-events: none; z-index: 9999;
    box-shadow: 0 0 12px #00FFC8;
}

h1 {
    font-family: 'Rajdhani', sans-serif !important;
    color: #00FFC8 !important;
    font-weight: 700 !important;
    text-transform: uppercase;
    letter-spacing: 3px;
    animation: glitch 3s infinite;
    text-shadow: 0 0 10px #00FFC8, 0 0 20px #00FFC8;
}
h2, h3 {
    color: #FF0080 !important;
    font-weight: 600 !important;
    letter-spacing: 2px;
    text-transform: uppercase;
    text-shadow: 0 0 8px rgba(255,0,128,0.6);
    border-left: 3px solid #00FFC8;
    padding-left: 10px;
}

[data-testid="stMetric"] {
    background: rgba(10,0,20,0.7);
    border: 1px solid #FF0080;
    border-radius: 0;
    padding: 18px 22px;
    position: relative;
    box-shadow: 0 0 15px rgba(255,0,128,0.3), inset 0 0 15px rgba(0,255,200,0.1);
    clip-path: polygon(0 0, 100% 0, 100% calc(100% - 12px), calc(100% - 12px) 100%, 0 100%);
}
[data-testid="stMetric"]:hover {
    border-color: #00FFC8;
    box-shadow: 0 0 25px rgba(0,255,200,0.6);
}
[data-testid="stMetricLabel"] {
    color: #FF0080 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 2px;
}
[data-testid="stMetricValue"] {
    color: #00FFC8 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 1.9rem !important;
    text-shadow: 0 0 10px #00FFC8;
    animation: neon-flicker 4s infinite;
}

[data-testid="stDataFrame"] {
    border: 1px solid #FF0080;
    border-radius: 0;
    box-shadow: 0 0 10px rgba(255,0,128,0.3);
}
[data-testid="stDataFrame"] th {
    background: linear-gradient(90deg, #2a0515, #15052a) !important;
    color: #00FFC8 !important;
    font-family: 'Share Tech Mono', monospace !important;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    border-bottom: 2px solid #FF0080 !important;
}
[data-testid="stDataFrame"] tr:hover td {
    background: rgba(255,0,128,0.08) !important;
    color: #00FFC8 !important;
}

.stButton > button[kind="primary"] {
    background: transparent !important;
    color: #00FFC8 !important;
    border: 2px solid #00FFC8 !important;
    border-radius: 0 !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 3px;
    text-transform: uppercase;
    padding: 0.6rem 2rem !important;
    box-shadow: 0 0 15px rgba(0,255,200,0.4), inset 0 0 15px rgba(0,255,200,0.1) !important;
    clip-path: polygon(10px 0, 100% 0, calc(100% - 10px) 100%, 0 100%);
    transition: all 0.2s ease !important;
}
.stButton > button[kind="primary"]:hover {
    background: #00FFC8 !important;
    color: #0a0015 !important;
    box-shadow: 0 0 25px #00FFC8 !important;
}

.stProgress > div > div {
    background: linear-gradient(90deg, #FF0080, #00FFC8) !important;
    border-radius: 0 !important;
    box-shadow: 0 0 10px #00FFC8;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0015 0%, #15052a 100%) !important;
    border-right: 2px solid #FF0080;
    box-shadow: inset -5px 0 15px rgba(255,0,128,0.2);
}

.stTabs [aria-selected="true"] {
    background: rgba(0,255,200,0.1) !important;
    color: #00FFC8 !important;
    border-bottom: 2px solid #00FFC8 !important;
}
</style>
"""


# ============ 主題 3：駭客終端（純黑螢光綠、Matrix 雨） ============
_THEME_MATRIX = """
<style>
@import url('https://fonts.googleapis.com/css2?family=VT323&family=Share+Tech+Mono&display=swap');

@keyframes matrix-rain {
    0% { background-position: 0 0; }
    100% { background-position: 0 1000px; }
}
@keyframes terminal-blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}
@keyframes scan {
    0%, 100% { background-position: 0 0; }
    50% { background-position: 0 4px; }
}

html, body {
    background: #000000 !important;
    font-family: 'Share Tech Mono', monospace !important;
    color: #00FF41 !important;
}
[data-testid="stAppViewContainer"] {
    background: #000000 !important;
    background-image:
        repeating-linear-gradient(0deg,
            rgba(0,255,65,0.03) 0px,
            rgba(0,255,65,0.03) 1px,
            transparent 1px,
            transparent 3px);
}
[data-testid="stAppViewContainer"]::after {
    content: '';
    position: fixed; inset: 0;
    background:
        radial-gradient(ellipse at top, transparent 0%, rgba(0,0,0,0.4) 100%);
    pointer-events: none; z-index: 1;
}

* { font-family: 'Share Tech Mono', monospace !important; color: #00FF41 !important; }

h1 {
    font-family: 'VT323', monospace !important;
    color: #00FF41 !important;
    font-weight: 400 !important;
    font-size: 3rem !important;
    letter-spacing: 2px;
    text-shadow: 0 0 5px #00FF41, 0 0 10px #00FF41;
}
h1::before { content: '> '; color: #00FF41; animation: terminal-blink 1s infinite; }
h1::after { content: '_'; animation: terminal-blink 1s infinite; }

h2, h3 {
    color: #00FF41 !important;
    font-family: 'VT323', monospace !important;
    font-weight: 400 !important;
    font-size: 1.8rem !important;
    text-shadow: 0 0 5px #00FF41;
}
h2::before, h3::before { content: '[+] '; opacity: 0.7; }

[data-testid="stMetric"] {
    background: rgba(0,15,0,0.6);
    border: 1px solid #00FF41;
    border-radius: 0;
    padding: 14px 18px;
    box-shadow: 0 0 8px rgba(0,255,65,0.3), inset 0 0 20px rgba(0,255,65,0.05);
}
[data-testid="stMetric"]:hover {
    box-shadow: 0 0 18px rgba(0,255,65,0.6);
    background: rgba(0,30,0,0.7);
}
[data-testid="stMetricLabel"] {
    color: #00AA2A !important;
    font-size: 0.8rem !important;
    text-transform: uppercase;
}
[data-testid="stMetricLabel"]::before { content: '$ '; opacity: 0.6; }
[data-testid="stMetricValue"] {
    color: #00FF41 !important;
    font-family: 'VT323', monospace !important;
    font-weight: 400 !important;
    font-size: 2.2rem !important;
    text-shadow: 0 0 8px #00FF41;
}

[data-testid="stDataFrame"] {
    border: 1px solid #00FF41;
    border-radius: 0;
    background: #000 !important;
}
[data-testid="stDataFrame"] th {
    background: #001a05 !important;
    color: #00FF41 !important;
    text-transform: uppercase;
    border-bottom: 1px solid #00FF41 !important;
}
[data-testid="stDataFrame"] td { color: #00CC33 !important; }
[data-testid="stDataFrame"] tr:hover td {
    background: #001a05 !important;
    color: #00FF41 !important;
}

.stButton > button {
    background: #000 !important;
    color: #00FF41 !important;
    border: 1px solid #00FF41 !important;
    border-radius: 0 !important;
    font-family: 'Share Tech Mono', monospace !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    box-shadow: 0 0 8px rgba(0,255,65,0.3) !important;
}
.stButton > button:hover {
    background: #00FF41 !important;
    color: #000 !important;
    box-shadow: 0 0 15px #00FF41 !important;
}
.stButton > button[kind="primary"]::before { content: '> '; }

.stProgress > div > div {
    background: #00FF41 !important;
    box-shadow: 0 0 8px #00FF41;
    border-radius: 0 !important;
}

[data-testid="stSidebar"] {
    background: #000 !important;
    border-right: 1px solid #00FF41;
    box-shadow: inset -3px 0 10px rgba(0,255,65,0.2);
}

input, textarea, select {
    background: #000 !important;
    color: #00FF41 !important;
    border: 1px solid #00FF41 !important;
    border-radius: 0 !important;
    font-family: 'Share Tech Mono', monospace !important;
}

.stTabs [aria-selected="true"] {
    background: rgba(0,255,65,0.1) !important;
    color: #00FF41 !important;
    border-bottom: 2px solid #00FF41 !important;
}
</style>
"""


# ============ 主題 4：血月（深紅黑 + 金） ============
_THEME_BLOODMOON = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;800&family=Crimson+Text:wght@400;600&display=swap');

@keyframes blood-pulse {
    0%, 100% { box-shadow: 0 0 15px rgba(180,20,20,0.4), inset 0 0 30px rgba(180,20,20,0.1); }
    50% { box-shadow: 0 0 35px rgba(220,30,30,0.7), inset 0 0 40px rgba(180,20,20,0.2); }
}
@keyframes gold-shimmer {
    0%, 100% { text-shadow: 0 0 8px rgba(212,175,55,0.5); }
    50% { text-shadow: 0 0 20px rgba(255,215,80,0.9), 0 0 35px rgba(212,175,55,0.4); }
}

html, body, [class*="css"] { font-family: 'Crimson Text', serif; }

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse at top, rgba(80,10,10,0.4) 0%, transparent 60%),
        radial-gradient(ellipse at bottom, rgba(40,0,0,0.6) 0%, transparent 70%),
        #0a0000 !important;
}

h1 {
    font-family: 'Cinzel', serif !important;
    color: #D4AF37 !important;
    font-weight: 800 !important;
    letter-spacing: 4px;
    text-transform: uppercase;
    text-align: center;
    animation: gold-shimmer 3s ease-in-out infinite;
    border-top: 2px solid #8B0000;
    border-bottom: 2px solid #8B0000;
    padding: 1rem 0;
    background: linear-gradient(180deg, rgba(80,0,0,0.3), transparent, rgba(80,0,0,0.3));
}
h2, h3 {
    font-family: 'Cinzel', serif !important;
    color: #D4AF37 !important;
    font-weight: 600 !important;
    letter-spacing: 2px;
    text-transform: uppercase;
    text-shadow: 0 0 8px rgba(212,175,55,0.4);
    border-left: 4px solid #8B0000;
    padding-left: 12px;
}

[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(60,0,0,0.8) 0%, rgba(20,0,0,0.9) 100%);
    border: 1px solid #8B0000;
    border-radius: 4px;
    padding: 18px 22px;
    animation: blood-pulse 4s ease-in-out infinite;
    position: relative;
}
[data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, #D4AF37, transparent);
}
[data-testid="stMetric"]:hover {
    border-color: #D4AF37;
    transform: scale(1.02);
    transition: all 0.3s ease;
}
[data-testid="stMetricLabel"] {
    color: #D4AF37 !important;
    font-family: 'Cinzel', serif !important;
    font-size: 0.8rem !important;
    text-transform: uppercase;
    letter-spacing: 2px;
}
[data-testid="stMetricValue"] {
    color: #FFD700 !important;
    font-family: 'Cinzel', serif !important;
    font-weight: 800 !important;
    font-size: 2rem !important;
    text-shadow: 0 0 12px rgba(255,215,0,0.6), 0 2px 4px rgba(0,0,0,0.8);
}

[data-testid="stDataFrame"] {
    border: 1px solid #8B0000;
    border-radius: 4px;
    box-shadow: 0 0 15px rgba(139,0,0,0.4);
}
[data-testid="stDataFrame"] th {
    background: linear-gradient(135deg, #3a0000, #1a0000) !important;
    color: #D4AF37 !important;
    font-family: 'Cinzel', serif !important;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    border-bottom: 2px solid #8B0000 !important;
}
[data-testid="stDataFrame"] td { color: #E8D099 !important; }
[data-testid="stDataFrame"] tr:hover td {
    background: rgba(139,0,0,0.2) !important;
    color: #FFD700 !important;
}

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #8B0000 0%, #4a0000 100%) !important;
    color: #D4AF37 !important;
    border: 2px solid #D4AF37 !important;
    border-radius: 4px !important;
    font-family: 'Cinzel', serif !important;
    font-weight: 600 !important;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 0.7rem 2.2rem !important;
    box-shadow: 0 0 15px rgba(139,0,0,0.5), inset 0 1px 0 rgba(212,175,55,0.3) !important;
    transition: all 0.3s ease !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #B22222 0%, #6a0000 100%) !important;
    box-shadow: 0 0 25px rgba(220,20,60,0.7) !important;
    transform: translateY(-2px);
}

.stProgress > div > div {
    background: linear-gradient(90deg, #8B0000, #D4AF37, #8B0000) !important;
    border-radius: 2px;
    box-shadow: 0 0 10px rgba(139,0,0,0.6);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a0000 0%, #0a0000 100%) !important;
    border-right: 2px solid #8B0000;
    box-shadow: inset -5px 0 20px rgba(139,0,0,0.3);
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(139,0,0,0.4), rgba(212,175,55,0.2)) !important;
    color: #D4AF37 !important;
    border-bottom: 2px solid #D4AF37 !important;
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
    "炫泡": _THEME_FLASHY,
    "賽博龐克": _THEME_CYBERPUNK,
    "駭客": _THEME_MATRIX,
    "血月": _THEME_BLOODMOON,
}
