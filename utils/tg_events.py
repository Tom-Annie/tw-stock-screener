"""
TG 事件偵測 — 從每日歷史 parquet 算出值得推播的「轉折事件」

典型事件:
- 首次進 S 級（composite > 80）
- 連 3 日 TOP 20
- 從 TOP 20 跌出（退出）
- 分數大幅跳升（+15 分以上）

每日掃描結束後呼叫 detect_events(today_ranked, history_dir) 即可拿到事件列表。
"""
from pathlib import Path
from typing import List, Dict
import pandas as pd


def _load_prev(history_dir: Path, today_date: str,
               n_days: int = 5) -> List[pd.DataFrame]:
    """載入 today_date 之前的 N 個歷史檔（最新到舊）"""
    files = sorted(history_dir.glob("*.parquet"), reverse=True)
    out = []
    for f in files:
        if f.stem >= today_date:
            continue
        try:
            df = pd.read_parquet(f)
            df._date = f.stem  # 臨時屬性
            out.append(df)
        except Exception:
            continue
        if len(out) >= n_days:
            break
    return out


def detect_events(today: pd.DataFrame, history_dir: Path,
                  today_date: str,
                  top_n: int = 20,
                  jump_threshold: float = 15.0) -> Dict[str, list]:
    """
    回傳 {
        'new_s': [{stock_id, name, score}, ...],         # 今天首次進 S 級
        'streak_top': [{stock_id, name, days}, ...],      # 連續 top_n 天數 >=3
        'exits': [{stock_id, name}, ...],                 # 從 TOP 20 跌出
        'jumps': [{stock_id, name, from_score, to_score, delta}, ...]  # 分數跳升
    }
    """
    events = {"new_s": [], "streak_top": [], "exits": [], "jumps": []}

    if today is None or today.empty:
        return events

    prev_list = _load_prev(history_dir, today_date, n_days=5)
    if not prev_list:
        return events

    prev_latest = prev_list[0]

    today_by_id = {r["stock_id"]: r for _, r in today.iterrows()}
    prev_by_id = {r["stock_id"]: r for _, r in prev_latest.iterrows()}

    # 1. 首次進 S（今天 grade=S 且昨天 grade != S）
    today_s = today[today.get("grade", "") == "S"]
    yesterday_s_ids = set(prev_latest[prev_latest.get("grade", "") == "S"]["stock_id"]) \
        if "grade" in prev_latest.columns else set()
    for _, r in today_s.iterrows():
        if r["stock_id"] not in yesterday_s_ids:
            events["new_s"].append({
                "stock_id": r["stock_id"],
                "name": r.get("name", ""),
                "score": round(float(r.get("composite_score", 0)), 1),
            })

    # 2. 連續 N 天 top_n（包含今天）
    today_top_ids = set(today.nlargest(top_n, "composite_score")["stock_id"]) \
        if "composite_score" in today.columns else set()
    for sid in today_top_ids:
        streak = 1
        for prev_df in prev_list:
            if "composite_score" not in prev_df.columns:
                break
            prev_top = set(prev_df.nlargest(top_n, "composite_score")["stock_id"])
            if sid in prev_top:
                streak += 1
            else:
                break
        if streak >= 3:
            r = today_by_id.get(sid, {})
            events["streak_top"].append({
                "stock_id": sid,
                "name": r.get("name", "") if hasattr(r, "get") else "",
                "days": streak,
            })

    # 3. 退出 TOP 20（昨天在今天不在）
    prev_top_ids = set(prev_latest.nlargest(top_n, "composite_score")["stock_id"]) \
        if "composite_score" in prev_latest.columns else set()
    exit_ids = prev_top_ids - today_top_ids
    for sid in exit_ids:
        r = prev_by_id.get(sid)
        events["exits"].append({
            "stock_id": sid,
            "name": r.get("name", "") if r is not None else "",
        })

    # 4. 分數跳升（+jump_threshold 以上）
    if "composite_score" in today.columns and "composite_score" in prev_latest.columns:
        for sid, r in today_by_id.items():
            prev_r = prev_by_id.get(sid)
            if prev_r is None:
                continue
            to_s = float(r.get("composite_score", 0))
            from_s = float(prev_r.get("composite_score", 0))
            delta = to_s - from_s
            if delta >= jump_threshold:
                events["jumps"].append({
                    "stock_id": sid,
                    "name": r.get("name", ""),
                    "from_score": round(from_s, 1),
                    "to_score": round(to_s, 1),
                    "delta": round(delta, 1),
                })

    return events


def format_events_for_tg(events: Dict[str, list], date_str: str = "") -> str:
    """格式化事件字典為 TG HTML 訊息（無事件回傳空字串）"""
    has_any = any(events.get(k) for k in ("new_s", "streak_top", "jumps", "exits"))
    if not has_any:
        return ""

    header = "🔔 <b>策略轉折事件</b>"
    if date_str:
        header += f" — {date_str}"
    lines = [header, ""]

    if events.get("new_s"):
        lines.append("🔥 <b>新進 S 級</b>")
        for e in events["new_s"][:10]:
            lines.append(f"  • {e['stock_id']} {e['name']}  {e['score']} 分")
        lines.append("")

    if events.get("jumps"):
        lines.append("🚀 <b>分數大跳升</b>")
        jumps = sorted(events["jumps"], key=lambda x: -x["delta"])[:10]
        for e in jumps:
            lines.append(
                f"  • {e['stock_id']} {e['name']}  "
                f"{e['from_score']} → {e['to_score']} ({e['delta']:+})"
            )
        lines.append("")

    if events.get("streak_top"):
        lines.append("⭐ <b>連日 TOP 20</b>")
        streaks = sorted(events["streak_top"], key=lambda x: -x["days"])[:10]
        for e in streaks:
            lines.append(f"  • {e['stock_id']} {e['name']}  連 {e['days']} 日")
        lines.append("")

    if events.get("exits"):
        exits = events["exits"][:10]
        ids_str = ", ".join(f"{e['stock_id']} {e['name']}" for e in exits)
        lines.append(f"📤 <b>退出 TOP 20:</b> {ids_str}")

    return "\n".join(lines)
