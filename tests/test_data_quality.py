"""測試 utils/data_quality.check_scan_quality"""
import pandas as pd
import pytest

from utils.data_quality import check_scan_quality, SCORE_COLS, format_issues_for_tg


def _healthy_df(n: int = 50) -> pd.DataFrame:
    """合成一個品質正常的 ranked DataFrame"""
    import numpy as np
    rng = np.random.default_rng(42)
    data = {"stock_id": [f"{i:04d}" for i in range(n)]}
    for col in SCORE_COLS:
        data[col] = rng.uniform(20, 90, n).round(1)
    return pd.DataFrame(data)


def test_healthy_returns_empty():
    assert check_scan_quality(_healthy_df()) == []


def test_empty_df():
    assert "掃描結果為空" in check_scan_quality(pd.DataFrame())[0]


def test_none():
    assert "掃描結果為空" in check_scan_quality(None)[0]


def test_too_few_rows():
    df = _healthy_df(5)
    issues = check_scan_quality(df, min_rows=20)
    assert any("樣本過少" in x for x in issues)


def test_stuck_constant_catches_margin_bug():
    """模擬先前 margin=10 的 bug"""
    df = _healthy_df()
    df["margin_analysis_score"] = 10.0  # 所有股票同分
    issues = check_scan_quality(df)
    assert any("margin_analysis_score" in x and "同分" in x for x in issues)


def test_stuck_constant_catches_shareholder_abnormal():
    """shareholder 卡在非中性分（例如 80）時應告警"""
    df = _healthy_df()
    df["shareholder_score"] = 80.0
    issues = check_scan_quality(df)
    assert any("shareholder_score" in x and "同分" in x for x in issues)


def test_shareholder_constant_50_ok():
    """shareholder=50（中性）或 0（權重=0）時允許"""
    df = _healthy_df()
    df["shareholder_score"] = 50.0
    issues = check_scan_quality(df)
    assert not any("shareholder_score" in x and "同分" in x for x in issues)


def test_all_nan():
    df = _healthy_df()
    df["ma_breakout_score"] = float("nan")
    issues = check_scan_quality(df)
    assert any("ma_breakout_score" in x and "全部 NaN" in x for x in issues)


def test_high_nan_ratio():
    df = _healthy_df()
    df.loc[:40, "volume_price_score"] = float("nan")  # 80%+ NaN
    issues = check_scan_quality(df)
    assert any("volume_price_score" in x and "NaN 比例" in x for x in issues)


def test_out_of_range():
    df = _healthy_df()
    df.loc[0, "us_market_score"] = 150
    issues = check_scan_quality(df)
    assert any("越界" in x for x in issues)


def test_missing_column():
    df = _healthy_df()
    df = df.drop(columns=["enhanced_technical_score"])
    issues = check_scan_quality(df)
    assert any("缺欄位" in x for x in issues)


def test_format_issues_empty():
    assert format_issues_for_tg([]) == ""


def test_format_issues_with_date():
    msg = format_issues_for_tg(["X 壞了", "Y 低變異"], "2026-04-15")
    assert "2026-04-15" in msg
    assert "X 壞了" in msg
    assert "Y 低變異" in msg
