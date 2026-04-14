"""
策略參數設定頁面
"""
import streamlit as st

st.set_page_config(page_title="策略設定", page_icon="⚙️", layout="wide")
from utils.theme import inject_custom_css, render_theme_selector
render_theme_selector()
inject_custom_css()
from utils.auth import require_auth
require_auth()
st.title("⚙️ 策略參數設定")

st.markdown("""
調整各策略的技術參數。修改後回到主頁面重新執行分析即可套用。
""")

# 讀取目前設定值
import config.settings as cfg

# 均線參數
st.markdown("### 📊 突破均線")
col1, col2 = st.columns(2)
with col1:
    ma_periods = st.multiselect(
        "均線週期",
        options=[5, 10, 20, 30, 60, 120, 240],
        default=cfg.MA_PERIODS,
        help="選擇要偵測的均線週期"
    )
with col2:
    breakout_lookback = st.number_input(
        "突破回溯天數",
        min_value=1, max_value=10, value=3,
        help="幾天內突破均線算「剛突破」"
    )

st.markdown("---")

# 量價參數
st.markdown("### 📈 量價齊揚")
col3, col4 = st.columns(2)
with col3:
    vol_ma_period = st.number_input(
        "均量天數",
        min_value=5, max_value=60, value=cfg.VOLUME_MA_PERIOD,
        help="計算平均成交量的天數"
    )
with col4:
    vol_surge = st.slider(
        "量能放大倍數門檻",
        min_value=1.0, max_value=5.0, value=cfg.VOLUME_SURGE_RATIO, step=0.1,
        help="當日量 / 均量超過此倍數視為放量"
    )

st.markdown("---")

# RSI 參數
st.markdown("### 💪 相對強弱")
col5, col6 = st.columns(2)
with col5:
    rsi_period = st.number_input(
        "RSI 週期",
        min_value=5, max_value=30, value=cfg.RSI_PERIOD
    )
with col6:
    rsi_bullish_range = st.slider(
        "RSI 強勢區間",
        min_value=0, max_value=100, value=(55, 70),
        help="此區間內的 RSI 給予最高分"
    )

st.markdown("---")

# 法人籌碼參數
st.markdown("### 🏦 法人籌碼")
col7, col8 = st.columns(2)
with col7:
    inst_lookback = st.number_input(
        "法人回溯天數",
        min_value=5, max_value=60, value=cfg.INSTITUTIONAL_LOOKBACK,
        help="統計法人買賣超的天數"
    )
with col8:
    st.markdown("**法人權重**")
    trust_weight = st.slider("投信權重", 0.0, 1.0, 0.45, 0.05)
    foreign_weight = st.slider("外資權重", 0.0, 1.0, 0.40, 0.05)
    dealer_weight = st.slider("自營商權重", 0.0, 1.0, 0.15, 0.05)

st.markdown("---")

# 套用設定
if st.button("💾 套用設定", type="primary"):
    # 直接更新 config 模組的值，所有策略會自動讀取
    cfg.MA_PERIODS = ma_periods
    cfg.RSI_PERIOD = rsi_period
    cfg.VOLUME_MA_PERIOD = vol_ma_period
    cfg.VOLUME_SURGE_RATIO = vol_surge
    cfg.INSTITUTIONAL_LOOKBACK = inst_lookback
    # RSI 強勢區間 & 法人權重 — 存到 config 供策略讀取
    cfg.RSI_BULLISH_LOW = rsi_bullish_range[0]
    cfg.RSI_BULLISH_HIGH = rsi_bullish_range[1]
    cfg.INST_TRUST_WEIGHT = trust_weight
    cfg.INST_FOREIGN_WEIGHT = foreign_weight
    cfg.INST_DEALER_WEIGHT = dealer_weight

    # 也存到 session state，讓跨頁面時保留
    st.session_state["custom_settings"] = {
        "ma_periods": ma_periods,
        "breakout_lookback": breakout_lookback,
        "rsi_period": rsi_period,
        "rsi_bullish_range": rsi_bullish_range,
        "vol_ma_period": vol_ma_period,
        "vol_surge": vol_surge,
        "inst_lookback": inst_lookback,
        "inst_weights": {
            "trust": trust_weight,
            "foreign": foreign_weight,
            "dealer": dealer_weight
        }
    }
    st.success("設定已套用！回到主頁面重新分析即可生效。")

# 頁面載入時自動恢復上次的設定
if "custom_settings" in st.session_state:
    s = st.session_state["custom_settings"]
    cfg.MA_PERIODS = s.get("ma_periods", cfg.MA_PERIODS)
    cfg.RSI_PERIOD = s.get("rsi_period", cfg.RSI_PERIOD)
    cfg.VOLUME_MA_PERIOD = s.get("vol_ma_period", cfg.VOLUME_MA_PERIOD)
    cfg.VOLUME_SURGE_RATIO = s.get("vol_surge", cfg.VOLUME_SURGE_RATIO)
    cfg.INSTITUTIONAL_LOOKBACK = s.get("inst_lookback", cfg.INSTITUTIONAL_LOOKBACK)
    rsi_range = s.get("rsi_bullish_range", (55, 70))
    cfg.RSI_BULLISH_LOW = rsi_range[0]
    cfg.RSI_BULLISH_HIGH = rsi_range[1]
    iw = s.get("inst_weights", {})
    cfg.INST_TRUST_WEIGHT = iw.get("trust", 0.45)
    cfg.INST_FOREIGN_WEIGHT = iw.get("foreign", 0.40)
    cfg.INST_DEALER_WEIGHT = iw.get("dealer", 0.15)

st.markdown("---")
with st.expander("📖 參數說明", expanded=False):
    st.markdown("""
    ### 參數說明

    | 參數 | 預設值 | 說明 |
    |------|--------|------|
    | 均線週期 | 5, 10, 20, 60 | 常用的短中長期均線 |
    | RSI 週期 | 14 | Wilder 原始設定 |
    | 均量天數 | 20 | 約一個月的交易日 |
    | 量能倍數 | 1.5x | 高於此值視為放量 |
    | 法人回溯 | 20天 | 約一個月的買賣超統計 |
    | 投信權重 | 45% | 投信為台股最具指標性的法人 |

    > **注意**：設定修改後需要回到主頁面重新點擊「開始分析」才會生效。
    > 設定只在這次使用期間有效，重新整理頁面會恢復預設值。
    """)
