"""
快取清理工具 — 刪除 mtime 超過閾值的 Parquet 檔

原本 Parquet 快取每次都會重寫，但過期的舊 hash 檔案會殘留。
跑這個可以清掉。

用法:
    python3 scripts/cache_cleanup.py --days 30       # 刪 30 天以上的
    python3 scripts/cache_cleanup.py --dry-run       # 只看不刪
"""
import argparse
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

from config.settings import CACHE_DIR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30,
                        help="刪除 mtime 超過此天數的檔案")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not CACHE_DIR.exists():
        print(f"CACHE_DIR 不存在：{CACHE_DIR}")
        return

    cutoff = datetime.now() - timedelta(days=args.days)
    cutoff_ts = cutoff.timestamp()

    total = 0
    old = []
    total_size = 0
    old_size = 0
    for f in CACHE_DIR.glob("*.parquet"):
        total += 1
        size = f.stat().st_size
        total_size += size
        if f.stat().st_mtime < cutoff_ts:
            old.append(f)
            old_size += size

    print(f"快取目錄: {CACHE_DIR}")
    print(f"全部: {total} 檔 / {total_size/1024/1024:.2f} MB")
    print(f"超過 {args.days} 天: {len(old)} 檔 / {old_size/1024/1024:.2f} MB")

    if not old:
        print("無可清除的檔案")
        return

    if args.dry_run:
        print(f"\n[DRY RUN] 會刪除這 {len(old)} 個檔:")
        for f in old[:10]:
            age_days = (datetime.now().timestamp() - f.stat().st_mtime) / 86400
            print(f"  {f.name}  ({age_days:.0f} 天前)")
        if len(old) > 10:
            print(f"  ... 還有 {len(old) - 10} 檔")
        return

    removed = 0
    for f in old:
        try:
            f.unlink()
            removed += 1
        except Exception as e:
            print(f"無法刪除 {f.name}: {e}")

    print(f"\n✅ 已刪除 {removed}/{len(old)} 檔，釋放 {old_size/1024/1024:.2f} MB")


if __name__ == "__main__":
    main()
