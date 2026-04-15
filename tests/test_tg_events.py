"""測試 utils/tg_events.detect_events / format_events_for_tg"""
import pandas as pd
from pathlib import Path

from utils.tg_events import detect_events, format_events_for_tg


def _make_df(rows):
    """rows: list of (stock_id, name, composite, grade)"""
    return pd.DataFrame(rows, columns=["stock_id", "name",
                                        "composite_score", "grade"])


def _seed_history(tmp_path: Path, date: str, rows):
    f = tmp_path / f"{date}.parquet"
    _make_df(rows).to_parquet(f, index=False)
    return f


def test_empty_today():
    events = detect_events(pd.DataFrame(), Path("/nonexistent"), "2026-04-15")
    assert events == {"new_s": [], "streak_top": [], "exits": [], "jumps": []}


def test_no_history(tmp_path):
    today = _make_df([("2330", "台積電", 85, "S")])
    events = detect_events(today, tmp_path, "2026-04-15")
    assert events["new_s"] == []  # 沒歷史無法比對


def test_new_s_detected(tmp_path):
    _seed_history(tmp_path, "2026-04-14", [
        ("2330", "台積電", 70, "A"),
        ("2454", "聯發科", 60, "B"),
    ])
    today = _make_df([
        ("2330", "台積電", 85, "S"),  # 首次進 S
        ("2454", "聯發科", 60, "B"),
    ])
    events = detect_events(today, tmp_path, "2026-04-15")
    assert len(events["new_s"]) == 1
    assert events["new_s"][0]["stock_id"] == "2330"


def test_jump_detected(tmp_path):
    _seed_history(tmp_path, "2026-04-14", [("2330", "台積電", 50, "C")])
    today = _make_df([("2330", "台積電", 70, "A")])
    events = detect_events(today, tmp_path, "2026-04-15", jump_threshold=15)
    assert len(events["jumps"]) == 1
    assert events["jumps"][0]["delta"] == 20.0


def test_no_jump_when_below_threshold(tmp_path):
    _seed_history(tmp_path, "2026-04-14", [("2330", "台積電", 60, "B")])
    today = _make_df([("2330", "台積電", 70, "A")])
    events = detect_events(today, tmp_path, "2026-04-15", jump_threshold=15)
    assert events["jumps"] == []


def test_exit_top_n(tmp_path):
    _seed_history(tmp_path, "2026-04-14", [
        ("A", "a", 90, "S"), ("B", "b", 80, "S"), ("C", "c", 70, "A"),
    ])
    today = _make_df([
        ("A", "a", 90, "S"), ("B", "b", 80, "S"), ("D", "d", 75, "A"),
    ])
    events = detect_events(today, tmp_path, "2026-04-15", top_n=2)
    # Top 2 yesterday: A, B. Top 2 today: A, B. No exit at top=2
    assert events["exits"] == []
    # At top=3: yesterday A,B,C; today A,B,D. C exited.
    events2 = detect_events(today, tmp_path, "2026-04-15", top_n=3)
    exit_ids = {e["stock_id"] for e in events2["exits"]}
    assert "C" in exit_ids


def test_streak_top(tmp_path):
    for d in ["2026-04-10", "2026-04-11", "2026-04-12", "2026-04-13", "2026-04-14"]:
        _seed_history(tmp_path, d, [
            ("2330", "台積電", 85, "S"), ("2454", "聯發科", 75, "A"),
        ])
    today = _make_df([("2330", "台積電", 88, "S"), ("2454", "聯發科", 78, "A")])
    events = detect_events(today, tmp_path, "2026-04-15", top_n=20)
    assert all(e["days"] >= 3 for e in events["streak_top"])


def test_format_empty():
    assert format_events_for_tg({"new_s": [], "streak_top": [],
                                  "exits": [], "jumps": []}) == ""


def test_format_has_content():
    msg = format_events_for_tg({
        "new_s": [{"stock_id": "2330", "name": "台積電", "score": 85}],
        "jumps": [{"stock_id": "2454", "name": "聯發科",
                   "from_score": 50, "to_score": 70, "delta": 20}],
        "streak_top": [],
        "exits": [],
    }, "2026-04-15")
    assert "2026-04-15" in msg
    assert "2330" in msg
    assert "2454" in msg
    assert "S 級" in msg
