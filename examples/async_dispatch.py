"""异步分发 —— Future、并发、异常、关闭线程池。

运行::

    python -m examples.async_dispatch
"""
import time

from dispatcher3 import (
    action,
    dispatch,
    dispatch_async,
    init_actions,
    reset,
    shutdown_executor, enable_logging,
)


def main():
    reset()

    @action(r"^job/[0-9]+$", description="耗时任务", priority=1)
    def slow_job(job_id):
        time.sleep(0.2)
        return "job-%s done" % job_id

    @action(r"^fail$", description="异步里抛异常")
    def fail(event):
        raise RuntimeError("异步任务失败")

    @action(r"^noop$", description="空转，用于对比两种投递方式的成本")
    def noop(event):
        return None

    init_actions()

    print("=" * 72)
    print("一、并发执行 5 个 0.2s 的任务")
    print("=" * 72)
    start = time.perf_counter()
    futures = [dispatch_async("job/%d" % i, i) for i in range(5)]
    results = [f.result(timeout=10) for f in futures]
    elapsed = time.perf_counter() - start
    for result in results:
        print("  ", result)
    print("  总耗时 %.2fs（串行需要 1.0s）" % elapsed)
    print()

    print("=" * 72)
    print("二、异常通过 Future 抛出")
    print("=" * 72)
    future = dispatch_async("fail", None)
    try:
        future.result(timeout=5)
    except RuntimeError as exc:
        print("  RuntimeError:", exc)
    print()

    print("=" * 72)
    print("三、dispatch_async 与 dispatch 的成本对比")
    print("=" * 72)
    n = 20000
    start = time.perf_counter()
    for _ in range(n):
        dispatch("noop", None)
    inline = (time.perf_counter() - start) / n * 1e6
    start = time.perf_counter()
    for _ in range(2000):
        dispatch_async("noop", None).result()
    pooled = (time.perf_counter() - start) / 2000 * 1e6
    print("  dispatch        : %6.1f us/次" % inline)
    print("  dispatch_async  : %6.1f us/次" % pooled)
    print("  异步的固定开销与 handler 做什么无关，只在需要并发时用")
    print()

    print("=" * 72)
    print("四、关闭线程池（之后再调用会重新创建）")
    print("=" * 72)
    shutdown_executor()
    print("  已关闭，再次 dispatch_async ->", dispatch_async("job/9", 9).result(timeout=10))
    shutdown_executor()


if __name__ == "__main__":
    enable_logging()
    main()
