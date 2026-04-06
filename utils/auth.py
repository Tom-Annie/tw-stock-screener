"""
共用密碼驗證 — 所有頁面都呼叫 require_auth()
支援多組密碼：Secrets 裡設 APP_PASSWORD (單組) 或 APP_PASSWORDS (多組，逗號分隔)
"""
import streamlit as st


def _get_valid_passwords() -> list:
    """取得所有有效密碼"""
    passwords = []

    # 單組密碼
    single = st.secrets.get("APP_PASSWORD", "")
    if single:
        passwords.append(single.strip())

    # 多組密碼 (逗號分隔)
    multi = st.secrets.get("APP_PASSWORDS", "")
    if multi:
        for pw in multi.split(","):
            pw = pw.strip()
            if pw and pw not in passwords:
                passwords.append(pw)

    return passwords


def require_auth():
    """
    檢查密碼，未通過則 st.stop()。
    密碼設在 Streamlit Secrets：
      - APP_PASSWORD = "密碼"         (單組)
      - APP_PASSWORDS = "密碼1,密碼2"  (多組，逗號分隔)
    """
    valid_passwords = _get_valid_passwords()
    if not valid_passwords:
        return  # 沒設密碼就不擋

    if st.session_state.get("authenticated"):
        return

    st.title("🔒 請輸入密碼")
    password = st.text_input("密碼", type="password", key="auth_pw")
    if st.button("登入"):
        if password in valid_passwords:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("密碼錯誤")
    st.stop()
