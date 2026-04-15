"""
並行抓取工具 — 把多個獨立 IO 呼叫改成並行

典型使用情境：美股 ^SOX / TSM / 夜盤 / 日盤 / TAIEX 這 5 支原本序列抓，
各自 1-3 秒網路等待，並行後總時間趨近最慢那支。

用法:
    from utils.parallel_fetch import parallel_fetch
    results = parallel_fetch({
        "sox": (fetch_us_stock, ("^SOX", start, end)),
        "tsm": (fetch_us_stock, ("TSM", start, end)),
        "night": (fetch_night_futures, (start, end)),
    })
    sox_df = results["sox"]  # 失敗者自動回 pd.DataFrame()
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, Any, Tuple
import pandas as pd


def parallel_fetch(
    tasks: Dict[str, Tuple[Callable, tuple]],
    max_workers: int = 5,
    default: Any = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """
    並行執行多個抓資料呼叫。

    Parameters
    ----------
    tasks : dict
        {key: (callable, args_tuple)}，每個 key 會以該 callable(*args) 執行
    max_workers : int
        並行執行緒數（預設 5，足以涵蓋大盤/美股 5 支）
    default : Any
        失敗時的回傳值；預設 None 會改回空 DataFrame
    timeout : float
        單一任務逾時秒數

    Returns
    -------
    dict[str, Any]
        {key: result or default_on_failure}
    """
    if default is None:
        default = pd.DataFrame()

    results: Dict[str, Any] = {k: default for k in tasks}
    if not tasks:
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {
            ex.submit(fn, *args): key
            for key, (fn, args) in tasks.items()
        }
        for fut in as_completed(futures, timeout=timeout + 5):
            key = futures[fut]
            try:
                results[key] = fut.result(timeout=timeout)
            except Exception:
                results[key] = default
    return results
