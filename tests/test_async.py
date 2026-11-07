"""dispatch_async 的 Future 语义。"""
import time

import pytest

from dispatcher3 import action, dispatch, dispatch_async, init_actions


def test_async_returns_future_with_result():
    @action(r"^a$")
    def handler(event):
        return event * 2

    init_actions()
    future = dispatch_async("a", 21)
    assert future.result(timeout=5) == 42


def test_async_surfaces_handler_exception():
    @action(r"^boom$")
    def handler(event):
        raise ValueError("boom")

    init_actions()
    future = dispatch_async("boom", None)
    with pytest.raises(ValueError, match="boom"):
        future.result(timeout=5)


def test_async_runs_concurrently():
    @action(r"^sleep$", sync=False)
    def handler(event):
        time.sleep(0.2)
        return "done"

    init_actions()
    start = time.perf_counter()
    futures = [dispatch_async("sleep", None) for _ in range(5)]
    assert [f.result(timeout=5) for f in futures] == ["done"] * 5
    assert time.perf_counter() - start < 0.8


def test_sync_dispatch_does_not_use_thread_pool():
    """dispatch() 必须内联执行，不能依赖线程池。"""
    import threading

    caller = threading.get_ident()
    seen = {}

    @action(r"^whoami$")
    def handler(event):
        seen["tid"] = threading.get_ident()
        return "ok"

    init_actions()
    dispatch("whoami", None)
    assert seen["tid"] == caller
