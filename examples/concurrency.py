"""并发语义 —— sync=True 全局排他、sync=False 并发、各种重入。

运行::

    python -m examples.concurrency
"""
import threading
import time

from dispatcher3 import action, dispatch, init_actions, reset


class ConcurrencyProbe:
    """记录同时在执行的 handler 数量。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.active = 0
        self.peak = 0

    def __enter__(self):
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)

    def __exit__(self, *exc):
        with self._lock:
            self.active -= 1


def run_threads(fn, n):
    threads = [threading.Thread(target=fn) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def demo_sync_exclusive():
    print("=" * 72)
    print("一、sync=True：全局排他（含与非 sync 互斥）")
    print("=" * 72)
    reset()
    probe = ConcurrencyProbe()

    @action(r"^exclusive$", sync=True)
    def exclusive(event):
        with probe:
            time.sleep(0.03)

    @action(r"^normal$", sync=False)
    def normal(event):
        with probe:
            time.sleep(0.03)

    init_actions()

    run_threads(lambda: dispatch("exclusive", None), 5)
    print("  5 个 sync=True 并发提交 -> 峰值并发 %d（应为 1）" % probe.peak)

    probe.peak = 0
    run_threads(lambda: dispatch("normal", None), 5)
    print("  5 个 sync=False 并发提交 -> 峰值并发 %d（应大于 1）" % probe.peak)

    probe.peak = 0

    def mixed_sync():
        for _ in range(10):
            dispatch("exclusive", None)

    def mixed_normal():
        for _ in range(10):
            dispatch("normal", None)

    a = threading.Thread(target=mixed_sync)
    b = threading.Thread(target=mixed_normal)
    a.start()
    b.start()
    a.join()
    b.join()
    print("  sync 与 non-sync 混跑 -> 峰值并发 %d（应为 1，全局排他）" % probe.peak)
    print()


def demo_reentrancy():
    print("=" * 72)
    print("二、重入规则")
    print("=" * 72)
    reset()
    trace = []

    @action(r"^inner$")
    def inner(event):
        trace.append("inner")
        return "inner"

    @action(r"^outer-sync$", sync=True)
    def outer_sync(event):
        trace.append("outer-sync")
        return dispatch("inner", None)

    @action(r"^outer-normal$", sync=False)
    def outer_normal(event):
        trace.append("outer-normal")
        return dispatch("inner", None)

    init_actions()

    print("  sync=True  -> sync=False :", dispatch("outer-sync", None), trace)
    trace.clear()
    print("  sync=False -> sync=False :", dispatch("outer-normal", None), trace)
    print("  读锁、写锁都按线程记层数，嵌套 dispatch 不会自死锁")
    print()


def demo_sync_to_sync():
    print("=" * 72)
    print("三、sync=True -> sync=True 重入（写锁重入）")
    print("=" * 72)
    reset()

    @action(r"^level2$", sync=True)
    def level2(event):
        return "level2"

    @action(r"^level1$", sync=True)
    def level1(event):
        return "level1 -> " + dispatch("level2", None)

    init_actions()
    print("  ->", dispatch("level1", None))
    print()


def demo_read_to_write_blocked():
    print("=" * 72)
    print("四、sync=False -> sync=True（读->写升级，必须报错）")
    print("=" * 72)
    reset()

    @action(r"^inner$", sync=True)
    def inner(event):
        return "inner"

    @action(r"^outer$", sync=False)
    def outer(event):
        return dispatch("inner", None)

    init_actions()
    try:
        dispatch("outer", None)
    except RuntimeError as exc:
        print("  RuntimeError:", exc)
        print("  说明：写者会等自己持有的读锁释放，必然死锁。明确报错优于挂死。")
    print()


def demo_async_pool():
    print("=" * 72)
    print("五、dispatch_async 并发执行")
    print("=" * 72)
    from dispatcher3 import dispatch_async, shutdown_executor

    reset()

    @action(r"^job$", sync=False)
    def job(event):
        time.sleep(0.1)
        return "done"

    init_actions()
    start = time.perf_counter()
    futures = [dispatch_async("job", None) for _ in range(5)]
    results = [f.result(timeout=10) for f in futures]
    elapsed = time.perf_counter() - start
    print("  5 个 0.1s 的任务 ->", results, "总耗时 %.2fs" % elapsed)
    shutdown_executor()
    print()


def main():
    demo_sync_exclusive()
    demo_reentrancy()
    demo_sync_to_sync()
    demo_read_to_write_blocked()
    demo_async_pool()


if __name__ == "__main__":
    main()
