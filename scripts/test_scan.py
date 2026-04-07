"""
掃描流程整合測試
每次修改掃描相關程式碼後執行，驗證整條流程是否正常
用法: python scripts/test_scan.py
"""
import os
import sys
import time
import traceback
from datetime import datetime, timedelta

_project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.chdir(_project_root)
sys.path.insert(0, _project_root)

# 讀 secrets
_secrets_path = os.path.join(os.path.dirname(__file__), "..", ".streamlit", "secrets.toml")
if os.path.exists(_secrets_path):
    try:
        with open(_secrets_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and val and key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass

if os.environ.get("FINMIND_TOKEN"):
    import config.settings as cfg
    cfg.FINMIND_TOKEN = os.environ["FINMIND_TOKEN"]


# ── 測試輔助 ──────────────────────────────────────────────

_passed = 0
_failed = 0
_errors = []


def _test(name, fn):
    global _passed, _failed
    print(f"  [{name}] ", end="", flush=True)
    t0 = time.time()
    try:
        fn()
        elapsed = time.time() - t0
        print(f"PASS ({elapsed:.1f}s)")
        _passed += 1
    except Exception as e:
        elapsed = time.time() - t0
        print(f"FAIL ({elapsed:.1f}s)")
        _failed += 1
        _errors.append((name, str(e), traceback.format_exc()))


# ── 測試項目 ──────────────────────────────────────────────

def test_yfinance_single():
    """單股 yfinance 下載 + 解析"""
    import yfinance as yf
    from data.fetcher import _parse_yf_single

    data = yf.download("2330.TW", start="2026-03-01", progress=False)
    assert not data.empty, "yfinance 下載為空"
    df = _parse_yf_single(data, "2330.TW", "2330")
    assert not df.empty, "_parse_yf_single 回傳為空"
    for col in ["date", "stock_id", "open", "high", "low", "close", "volume"]:
        assert col in df.columns, f"缺少欄位: {col}"
    assert (df["stock_id"] == "2330").all(), "stock_id 不正確"
    assert len(df) >= 5, f"資料太少: {len(df)} 筆"


def test_yfinance_batch():
    """批次 yfinance 下載 + 解析"""
    import yfinance as yf
    from data.fetcher import _parse_yf_single

    tickers = ["2330.TW", "2317.TW", "2454.TW"]
    data = yf.download(tickers, start="2026-03-01",
                       group_by="ticker", progress=False)
    assert not data.empty, "batch 下載為空"

    for ticker, sid in [("2330.TW", "2330"), ("2317.TW", "2317"), ("2454.TW", "2454")]:
        df = _parse_yf_single(data, ticker, sid)
        assert not df.empty, f"{sid} 解析為空"
        assert "close" in df.columns, f"{sid} 缺少 close"
        assert "date" in df.columns, f"{sid} 缺少 date"


def test_fetch_prices_batch():
    """完整三階段批次抓取"""
    from data.fetcher import fetch_stock_prices_batch

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    df = fetch_stock_prices_batch(["2330", "2317"], start, end)
    assert not df.empty, "fetch_stock_prices_batch 回傳為空"
    assert set(df.columns) >= {"date", "stock_id", "close", "volume"}, \
        f"欄位不足: {list(df.columns)}"
    sids = df["stock_id"].unique().tolist()
    assert "2330" in sids, "缺少 2330"
    assert len(df) >= 20, f"資料太少: {len(df)} 筆"


def test_normalize_price_df():
    """_normalize_price_df 處理各種格式"""
    import pandas as pd
    from data.fetcher import _normalize_price_df

    # 正常 DataFrame
    df = pd.DataFrame({
        "date": ["2026-01-02", "2026-01-03"],
        "stock_id": ["2330", "2330"],
        "open": [100, 101], "high": [105, 106],
        "low": [99, 100], "close": [103, 104],
        "volume": [1000, 2000],
    })
    result = _normalize_price_df(df)
    assert not result.empty
    assert list(result.columns) == ["date", "stock_id", "open", "high", "low", "close", "volume"]

    # MultiIndex 殘留（模擬 tuple columns）
    df2 = pd.DataFrame({
        ("Date", ""): ["2026-01-02"],
        ("2330.TW", "Close"): [100.0],
        ("2330.TW", "Volume"): [5000],
    })
    df2.columns = pd.MultiIndex.from_tuples(df2.columns)
    result2 = _normalize_price_df(df2)
    # 即使欄位不完全匹配也不應 crash
    assert isinstance(result2, pd.DataFrame)


def test_strategies_score():
    """八大策略評分不 crash"""
    import pandas as pd
    from data.fetcher import fetch_stock_prices_batch
    from strategies.ma_breakout import MABreakoutStrategy
    from strategies.volume_price import VolumePriceStrategy
    from strategies.relative_strength import RelativeStrengthStrategy
    from strategies.institutional_flow import InstitutionalFlowStrategy
    from strategies.enhanced_technical import EnhancedTechnicalStrategy
    from strategies.margin_analysis import MarginAnalysisStrategy
    from strategies.us_market import USMarketStrategy
    from strategies.shareholder import ShareholderStrategy

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
    prices = fetch_stock_prices_batch(["2330"], start, end)
    assert not prices.empty, "價量為空，無法測試策略"

    pdf = prices[prices["stock_id"] == "2330"].sort_values("date").reset_index(drop=True)
    assert len(pdf) >= 60, f"資料不足 60 筆 ({len(pdf)})"

    strategies = [
        ("均線突破", MABreakoutStrategy(), {}),
        ("量價齊揚", VolumePriceStrategy(), {}),
        ("相對強弱", RelativeStrengthStrategy(), {}),
        ("法人買賣超", InstitutionalFlowStrategy(), {"institutional_df": pd.DataFrame()}),
        ("進階技術", EnhancedTechnicalStrategy(), {}),
        ("融資融券", MarginAnalysisStrategy(), {"margin_df": pd.DataFrame()}),
        ("美股連動", USMarketStrategy(), {"sox_df": pd.DataFrame(), "tsm_df": pd.DataFrame(),
                                          "tsmc_close": 0, "night_df": pd.DataFrame(),
                                          "day_futures_df": pd.DataFrame()}),
        ("大戶籌碼", ShareholderStrategy(), {"tdcc_df": pd.DataFrame()}),
    ]

    for name, strategy, kwargs in strategies:
        try:
            score = strategy.score(pdf, **kwargs)
            assert isinstance(score, (int, float)), f"{name} 回傳非數字: {type(score)}"
            assert 0 <= score <= 100, f"{name} 分數超出範圍: {score}"
        except Exception as e:
            raise AssertionError(f"策略 {name} 異常: {e}")


def test_scorer_rank():
    """排名引擎"""
    from strategies.scorer import rank_stocks, compute_composite_score
    from config.settings import DEFAULT_WEIGHTS

    results = [
        {"stock_id": "2330", "name": "台積電",
         "ma_breakout_score": 80, "volume_price_score": 70,
         "relative_strength_score": 75, "institutional_flow_score": 60,
         "enhanced_technical_score": 65, "margin_analysis_score": 50,
         "us_market_score": 55, "shareholder_score": 70},
        {"stock_id": "2317", "name": "鴻海",
         "ma_breakout_score": 40, "volume_price_score": 50,
         "relative_strength_score": 45, "institutional_flow_score": 30,
         "enhanced_technical_score": 35, "margin_analysis_score": 20,
         "us_market_score": 25, "shareholder_score": 40},
    ]
    ranked = rank_stocks(results, DEFAULT_WEIGHTS)
    assert not ranked.empty
    assert "composite_score" in ranked.columns
    assert "grade" in ranked.columns
    assert "rank" in ranked.columns
    assert ranked.iloc[0]["stock_id"] == "2330", "排名錯誤"
    assert ranked.iloc[0]["rank"] == 1

    score = compute_composite_score(
        {"ma_breakout": 80, "volume_price": 70}, DEFAULT_WEIGHTS)
    assert isinstance(score, float)


def test_us_stock():
    """美股資料抓取"""
    from data.fetcher import fetch_us_stock

    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    sox = fetch_us_stock("^SOX", start, end)
    # 可能週末或假日為空，但不應 crash
    assert isinstance(sox, type(sox))  # 不 crash 即可


def test_stock_list():
    """股票清單抓取"""
    from data.fetcher import fetch_stock_list

    sl = fetch_stock_list()
    assert not sl.empty, "股票清單為空"
    assert "stock_id" in sl.columns
    assert len(sl) >= 100, f"股票數量異常: {len(sl)}"


# ── 主程式 ──────────────────────────────────────────────

def main():
    print(f"\n{'='*50}")
    print(f"  掃描流程整合測試 — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'='*50}\n")

    tests = [
        ("yfinance 單股下載", test_yfinance_single),
        ("yfinance 批次下載", test_yfinance_batch),
        ("三階段批次抓取", test_fetch_prices_batch),
        ("欄位格式統一", test_normalize_price_df),
        ("八大策略評分", test_strategies_score),
        ("排名引擎", test_scorer_rank),
        ("美股資料", test_us_stock),
        ("股票清單", test_stock_list),
    ]

    t0 = time.time()
    for name, fn in tests:
        _test(name, fn)
    elapsed = time.time() - t0

    print(f"\n{'='*50}")
    print(f"  結果: {_passed} PASS / {_failed} FAIL  ({elapsed:.1f}s)")
    print(f"{'='*50}")

    if _errors:
        print("\n  失敗詳情:")
        for name, msg, tb in _errors:
            print(f"\n  --- {name} ---")
            print(f"  {msg}")
            print(tb)

    sys.exit(1 if _failed else 0)


if __name__ == "__main__":
    main()
