"""sync=True / sync=False 的并发语义。

核心契约：sync=True 是**全局**排他 —— 与所有其它 handler 互斥，
包括 sync=False 的 handler。
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import dispatcher3.dispatcher as dispatcher_mod
from dispatcher3 import action, dispatch, init_actions
from dispatcher3.lock import global_lock


def _run_concurrently(fn, n, workers=None):
    with ThreadPoolExecutor(max_workers=workers or n) as pool:
        list(pool.map(lambda _: fn(), range(n)))


class _OverlapTracker:
    """记录是否有两个 handler 同时执行。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.active = 0
        self.peak = 0
        self.kinds = set()

    def enter(self, kind):
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.kinds.add(kind)
            return set(self.kinds)

    def leave(self, kind):
        with self._lock:
            self.active -= 1
            self.kinds.discard(kind)


# ---------------------------------------------------------------------------
# 排他性
# ---------------------------------------------------------------------------
def test_sync_true_is_globally_exclusive_against_itself():
    tracker = _OverlapTracker()

    @action(r"^exclusive$", sync=True)
    def handler(event):
        tracker.enter("sync")
        time.sleep(0.05)
        tracker.leave("sync")

    init_actions()
    _run_concurrently(lambda: dispatch("exclusive", None), 5, workers=5)
    assert tracker.peak == 1


def test_sync_true_excludes_non_sync_handler():
    """回归：sync=True 必须与 sync=False 互斥。"""
    tracker = _OverlapTracker()

    @action(r"^exclusive$", sync=True)
    def excl(event):
        tracker.enter("sync")
        time.sleep(0.25)
        tracker.leave("sync")

    @action(r"^normal$", sync=False)
    def normal(event):
        # 在 sync handler 执行期间启动，应当被挡在门外
        tracker.enter("non-sync")
        time.sleep(0.02)
        tracker.leave("non-sync")

    init_actions()

    first = threading.Thread(target=dispatch, args=("exclusive", None))
    first.start()
    time.sleep(0.05)          # 确保 sync handler 已在执行
    dispatch("normal", None)  # 必须等 sync handler 结束
    first.join(2.0)

    assert tracker.peak == 1, "sync=True 与 sync=False 同时执行了"


def test_sync_true_waits_for_in_flight_non_sync_handler():
    """全局排他的另一面：写者必须等在执行的读者退出。"""
    started = threading.Event()

    @action(r"^slow$", sync=False)
    def slow(event):
        started.set()
        time.sleep(0.4)

    @action(r"^critical$", sync=True)
    def critical(event):
        return "ok"

    init_actions()

    worker = threading.Thread(target=dispatch, args=("slow", None), daemon=True)
    worker.start()
    assert started.wait(2.0)

    start = time.perf_counter()
    assert dispatch("critical", None) == "ok"
    elapsed = time.perf_counter() - start
    worker.join(2.0)

    # 读者还要跑约 0.4s，写者必须等它
    assert elapsed >= 0.2, "写者没有等待在执行的读者，排他性不成立 (%.3fs)" % elapsed


def test_sync_false_is_concurrent():
    tracker = _OverlapTracker()

    @action(r"^concurrent$", sync=False)
    def handler(event):
        tracker.enter("non-sync")
        time.sleep(0.05)
        tracker.leave("non-sync")

    init_actions()
    _run_concurrently(lambda: dispatch("concurrent", None), 5, workers=5)
    assert tracker.peak >= 2


# ---------------------------------------------------------------------------
# 重入
# ---------------------------------------------------------------------------
def test_sync_handler_reentrancy_does_not_deadlock():
    """sync=True -> sync=True 嵌套：写锁可重入。"""
    calls = []

    @action(r"^inner$", sync=True)
    def inner(event):
        calls.append("inner")
        return "inner"

    @action(r"^outer$", sync=True)
    def outer(event):
        calls.append("outer")
        return dispatch("inner", None)

    init_actions()
    assert dispatch("outer", None) == "inner"
    assert calls == ["outer", "inner"]


def test_non_sync_reentrancy_does_not_deadlock():
    """sync=False -> sync=False 嵌套：读锁可重入。"""
    calls = []

    @action(r"^inner$", sync=False)
    def inner(event):
        calls.append("inner")
        return "inner"

    @action(r"^outer$", sync=False)
    def outer(event):
        calls.append("outer")
        return dispatch("inner", None)

    init_actions()
    assert dispatch("outer", None) == "inner"
    assert calls == ["outer", "inner"]


def test_write_then_read_is_allowed():
    """sync=True -> sync=False 嵌套：已持有更强的一致性，允许。"""

    @action(r"^inner$", sync=False)
    def inner(event):
        return "inner"

    @action(r"^outer$", sync=True)
    def outer(event):
        return dispatch("inner", None)

    init_actions()
    assert dispatch("outer", None) == "inner"


def test_read_then_write_raises_instead_of_hanging():
    """读->写升级必然死锁，必须明确报错而不是挂死。"""

    @action(r"^inner$", sync=True)
    def inner(event):
        return "inner"

    @action(r"^outer$", sync=False)
    def outer(event):
        return dispatch("inner", None)

    init_actions()
    with pytest.raises(RuntimeError, match="读->写升级"):
        dispatch("outer", None)


# ---------------------------------------------------------------------------
# 计数器完整性
# ---------------------------------------------------------------------------
def test_lock_state_is_clean_after_exceptions():
    @action(r"^boom-sync$", sync=True)
    def boom_sync(event):
        raise RuntimeError("boom")

    @action(r"^boom-normal$", sync=False)
    def boom_normal(event):
        raise RuntimeError("boom")

    @action(r"^ok$", sync=True)
    def ok(event):
        return "ok"

    init_actions()
    for _ in range(5):
        for key in ("boom-sync", "boom-normal"):
            with pytest.raises(RuntimeError):
                dispatch(key, None)

    assert global_lock.snapshot() == (0, None, 0)
    assert dispatch("ok", None) == "ok"
    assert global_lock.snapshot() == (0, None, 0)


def test_no_sync_actions_skips_lock_entirely(monkeypatch):
    """没有任何 sync=True action 时不应产生锁开销。"""
    calls = []

    class Probe:
        def acquire_read(self):
            calls.append("read+")

        def release_read(self):
            calls.append("read-")

        def acquire_write(self):
            calls.append("write+")

        def release_write(self):
            calls.append("write-")

    @action(r"^k$")
    def handler(event):
        return "k"

    init_actions()
    assert dispatcher_mod.global_registry.has_sync is False

    monkeypatch.setattr(dispatcher_mod, "global_lock", Probe())
    assert dispatch("k", None) == "k"
    assert calls == []
