"""
格式化工具
"""


def format_volume(vol: int) -> str:
    """格式化成交量 (張)"""
    if vol >= 100_000_000:
        return f"{vol / 100_000_000:.1f}億"
    elif vol >= 10_000:
        return f"{vol / 10_000:.0f}萬"
    elif vol >= 1_000:
        return f"{vol / 1_000:.1f}千"
    return str(vol)


def format_money(amount: float) -> str:
    """格式化金額"""
    if abs(amount) >= 100_000_000:
        return f"{amount / 100_000_000:.2f}億"
    elif abs(amount) >= 10_000:
        return f"{amount / 10_000:.0f}萬"
    return f"{amount:,.0f}"


def grade_color(grade: str) -> str:
    """等級對應的顏色"""
    return {
        "S": "#FF6B6B",
        "A": "#FFA726",
        "B": "#66BB6A",
        "C": "#42A5F5",
        "D": "#BDBDBD",
    }.get(grade, "#FFFFFF")


def score_emoji(score: float) -> str:
    """分數對應的 emoji"""
    if score >= 80:
        return "🔥"
    elif score >= 65:
        return "✅"
    elif score >= 50:
        return "⚡"
    elif score >= 30:
        return "⚠️"
    return "❌"
