"""性能冒烟测试。

不做精确断言（CI 机器差异大），只保证不出现数量级退化：
内联 dispatch 必须显著快于经线程池的异步分发。
"""
import time

from dispatcher3 import action, dispatch, dispatch_async, init_actions


def _measure(fn, n):
    start = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - start) / n * 1e6


def test_inline_dispatch_is_fast():
    @action(r"^user/[0-9]+$")
    def handler(event):
        return event

    @action(r"^exact/key$")
    def exact(event):
        return event

    init_actions()

    per_call = _measure(lambda: dispatch("exact/key", None), 20000)
    # 宽松上限，只拦截数量级退化
    assert per_call < 50, "精确匹配 %.2f us/次，疑似退化" % per_call

    regex_call = _measure(lambda: dispatch("user/123", None), 5000)
    assert regex_call < 200, "正则匹配 %.2f us/次，疑似退化" % regex_call


def test_async_dispatch_costs_more_than_inline():
    @action(r"^k$")
    def handler(event):
        return event

    init_actions()

    inline = _measure(lambda: dispatch("k", None), 5000)
    pooled = _measure(lambda: dispatch_async("k", None).result(), 2000)
    assert pooled > inline, "异步投递应当比内联更贵 (inline=%.2f, pooled=%.2f)" % (inline, pooled)
