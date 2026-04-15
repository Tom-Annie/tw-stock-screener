"""測試 utils/parallel_fetch.parallel_fetch"""
import time
import pandas as pd

from utils.parallel_fetch import parallel_fetch


def test_empty_tasks():
    assert parallel_fetch({}) == {}


def test_basic_parallel():
    def ok(x):
        return x * 2
    out = parallel_fetch({
        "a": (ok, (1,)),
        "b": (ok, (2,)),
    })
    assert out == {"a": 2, "b": 4}


def test_failure_returns_default():
    def boom(_):
        raise RuntimeError("fail")
    out = parallel_fetch({"x": (boom, (1,))})
    assert isinstance(out["x"], pd.DataFrame) and out["x"].empty


def test_custom_default():
    def boom():
        raise RuntimeError("fail")
    out = parallel_fetch({"x": (boom, ())}, default="FALLBACK")
    assert out["x"] == "FALLBACK"


def test_actually_parallel():
    """兩個各睡 0.3s 的任務並行總時間應 <0.5s"""
    def slow(s):
        time.sleep(s)
        return s
    start = time.time()
    parallel_fetch({
        "a": (slow, (0.3,)),
        "b": (slow, (0.3,)),
        "c": (slow, (0.3,)),
    })
    elapsed = time.time() - start
    assert elapsed < 0.6, f"elapsed={elapsed}s 看起來沒並行"


def test_partial_failure_isolation():
    def ok():
        return "OK"
    def boom():
        raise ValueError()
    out = parallel_fetch({"a": (ok, ()), "b": (boom, ())})
    assert out["a"] == "OK"
    assert isinstance(out["b"], pd.DataFrame) and out["b"].empty
