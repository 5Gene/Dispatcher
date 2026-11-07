"""可复现的基准测试。

运行::

    python benchmarks/bench.py

测的是**端到端**延迟（调用返回到拿到结果），不是仅测 dispatch() 提交
函数的耗时 —— 0.1 的文档只测了提交开销，报出的 5.6 us 比真实端到端
低了约 3 倍。

分别测量两种配置，因为它们的加锁成本不同：

* 无 sync=True action：不会出现写者，dispatch 完全不加锁
* 有 sync=True action：读者必须登记（读锁），否则写者等不到它们退出
"""
import os
import statistics
import sys
import time

# 允许直接 python benchmarks/bench.py 运行，无需先 pip install
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dispatcher3
from dispatcher3 import (
    action,
    dispatch,
    dispatch_async,
    init_actions,
    reset,
    shutdown_executor,
)


def bench(label, fn, n=20000, repeat=5):
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        for _ in range(n):
            fn()
        samples.append((time.perf_counter() - start) / n * 1e6)
    print("  %-24s best=%6.2f us  median=%6.2f us"
          % (label, min(samples), statistics.median(samples)))


def build_registry(include_sync):
    reset()

    @action(r"^exact/key$")
    def exact(event):
        return event

    @action(r"^api/v1/.*")
    def prefix(event):
        return event

    @action(r"^user/[0-9]+$")
    def regex(event):
        return event

    if include_sync:
        @action(r"^exclusive$", sync=True)
        def exclusive(event):
            return event

    init_actions()


def main():
    print("dispatcher3 %s / Python %s"
          % (dispatcher3.__version__, sys.version.split()[0]))

    print()
    print("配置 A：无 sync=True action（dispatch 不加锁）")
    build_registry(include_sync=False)
    bench("精确匹配 EXACT", lambda: dispatch("exact/key", None))
    bench("前缀匹配 PREFIX", lambda: dispatch("api/v1/users", None))
    bench("正则匹配 REGEX", lambda: dispatch("user/123", None))

    print()
    print("配置 B：存在 sync=True action（读路径加读锁）")
    build_registry(include_sync=True)
    bench("精确匹配 EXACT", lambda: dispatch("exact/key", None))
    bench("前缀匹配 PREFIX", lambda: dispatch("api/v1/users", None))
    bench("正则匹配 REGEX", lambda: dispatch("user/123", None))
    bench("sync=True 排他", lambda: dispatch("exclusive", None))

    print()
    print("异步投递（submit + Future.result）:")
    bench("dispatch_async + result",
          lambda: dispatch_async("exact/key", None).result(), n=5000)

    print()
    print("读锁成本 ≈ 配置 B - 配置 A。全局排他要求读者登记，这是必要代价。")

    shutdown_executor()


if __name__ == "__main__":
    main()
