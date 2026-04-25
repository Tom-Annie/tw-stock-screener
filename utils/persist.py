"""
跨頁面持久化 widget 狀態 — 解決 Streamlit 多頁 app 切頁時 widget key
被清掉導致設定 reset 的問題。

模式:
  - persist key(一般 session_state key,Streamlit 不會 cross-page 清除)
  - widget key(綁 widget 的 key,可能被 streamlit 視為 page-scoped)
  - 渲染前 persist → widget,on_change 時 widget → persist

用法:
    from utils.persist import persist_state
    persist_state("my_setting", default=10)
    val = st.selectbox("選項", [5,10,30], key="my_setting")
"""
import streamlit as st


_PREFIX = "_persist_"


def persist_state(key: str, default=None):
    """
    保證 key 跨頁不被清除。在每頁渲染 widget 之前呼叫。

    內部維護一個 `_persist_<key>` 鏡像;
    若 widget key 已存在(同頁互動)→ 同步寫回鏡像;
    若 widget key 不存在(剛換頁)→ 從鏡像復原。
    """
    mirror_key = _PREFIX + key

    if mirror_key not in st.session_state:
        st.session_state[mirror_key] = default

    if key in st.session_state:
        # 同頁互動 — widget 已存在,以 widget 為準同步到鏡像
        st.session_state[mirror_key] = st.session_state[key]
    else:
        # 剛換頁進來 — widget 不存在,從鏡像復原
        st.session_state[key] = st.session_state[mirror_key]


def make_persist_callback(key: str):
    """產生 on_change callback,把 widget 值寫回鏡像"""
    mirror_key = _PREFIX + key

    def _cb():
        if key in st.session_state:
            st.session_state[mirror_key] = st.session_state[key]
    return _cb


__all__ = ["persist_state", "make_persist_callback"]
