"""
GitHub Gist 持久化儲存
用一個 Gist 存所有使用者的庫存，每個使用者一個檔案
需要在 Streamlit Secrets 設定 GITHUB_TOKEN (需 gist scope)
"""
import json
import requests
import streamlit as st

GIST_API = "https://api.github.com/gists"
GIST_DESC = "tw-stock-screener-portfolios"


def _get_token() -> str:
    try:
        return st.secrets.get("GITHUB_TOKEN", "")
    except Exception:
        return ""


def _headers():
    return {
        "Authorization": f"token {_get_token()}",
        "Accept": "application/vnd.github.v3+json",
    }


def _find_gist_id() -> str:
    """搜尋已存在的庫存 Gist（用 description 辨識）"""
    # 先看 session cache
    if "gist_id" in st.session_state:
        return st.session_state["gist_id"]

    # 也可以直接在 Secrets 指定
    try:
        gid = st.secrets.get("GIST_ID", "")
        if gid:
            st.session_state["gist_id"] = gid
            return gid
    except Exception:
        pass

    # 搜尋自己的 Gists
    try:
        resp = requests.get(
            GIST_API, headers=_headers(),
            params={"per_page": 100}, timeout=15
        )
        resp.raise_for_status()
        for g in resp.json():
            if g.get("description") == GIST_DESC:
                st.session_state["gist_id"] = g["id"]
                return g["id"]
    except Exception:
        pass

    return ""


def _create_gist() -> str:
    """建立新的庫存 Gist"""
    payload = {
        "description": GIST_DESC,
        "public": False,
        "files": {
            "_index.json": {
                "content": json.dumps({"created": "auto", "app": "tw-stock-screener"})
            }
        }
    }
    try:
        resp = requests.post(GIST_API, headers=_headers(),
                             json=payload, timeout=15)
        resp.raise_for_status()
        gid = resp.json()["id"]
        st.session_state["gist_id"] = gid
        return gid
    except Exception:
        return ""


def _file_name(username: str) -> str:
    safe = "".join(c for c in username if c.isalnum() or c in "_-")
    return f"portfolio_{safe}.json"


def is_available() -> bool:
    """檢查 Gist 儲存是否可用"""
    return bool(_get_token())


def load(username: str) -> list:
    """從 Gist 讀取使用者庫存"""
    if not _get_token():
        return []

    gist_id = _find_gist_id()
    if not gist_id:
        return []

    try:
        resp = requests.get(f"{GIST_API}/{gist_id}",
                            headers=_headers(), timeout=15)
        resp.raise_for_status()
        files = resp.json().get("files", {})
        fname = _file_name(username)
        if fname in files:
            content = files[fname].get("content", "[]")
            data = json.loads(content)
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def save(username: str, data: list) -> bool:
    """儲存使用者庫存到 Gist"""
    if not _get_token():
        return False

    gist_id = _find_gist_id()
    if not gist_id:
        gist_id = _create_gist()
    if not gist_id:
        return False

    fname = _file_name(username)
    payload = {
        "files": {
            fname: {
                "content": json.dumps(data, ensure_ascii=False, indent=2)
            }
        }
    }
    try:
        resp = requests.patch(f"{GIST_API}/{gist_id}",
                              headers=_headers(), json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception:
        return False
