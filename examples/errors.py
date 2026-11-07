"""错误场景全集 —— 每一种失败路径都演示一遍。

运行::

    python -m examples.errors
"""
from dispatcher3 import (
    NoMatchError,
    RegistryFrozenError,
    RegistryNotInitializedError,
    action,
    dispatch,
    init_actions,
    reset,
)


def demo_not_initialized():
    print("=" * 72)
    print("一、忘记 init_actions()")
    print("=" * 72)
    reset()

    @action(r"^k$")
    def handler(event):
        return "k"

    try:
        dispatch("k", None)
    except RegistryNotInitializedError as exc:
        print("  RegistryNotInitializedError:", exc)
    print()


def demo_no_match():
    print("=" * 72)
    print("二、没有 action 匹配")
    print("=" * 72)
    reset()

    @action(r"^known$")
    def handler(event):
        return "known"

    init_actions()
    try:
        dispatch("unknown", None)
    except NoMatchError as exc:
        print("  NoMatchError:", exc)
    print()


def demo_handler_exception():
    print("=" * 72)
    print("三、handler 自己抛异常（异常原样传播，不会被吞）")
    print("=" * 72)
    reset()

    @action(r"^boom$")
    def boom(event):
        raise ValueError("业务炸了")

    init_actions()
    try:
        dispatch("boom", None)
    except ValueError as exc:
        print("  ValueError:", exc)
    print()


def demo_invalid_regex():
    print("=" * 72)
    print("四、非法正则（在定义时就失败，不会拖到运行时）")
    print("=" * 72)
    reset()
    try:
        @action(r"^[unclosed$")
        def broken(event):
            pass
    except ValueError as exc:
        print("  ValueError:", exc)
    print()


def demo_register_after_freeze():
    print("=" * 72)
    print("五、冻结后注册")
    print("=" * 72)
    reset()

    @action(r"^a$")
    def first(event):
        return "a"

    init_actions()
    try:
        @action(r"^b$")
        def late(event):
            return "b"
    except RegistryFrozenError as exc:
        print("  RegistryFrozenError:", exc)
    print()


def demo_duplicate():
    print("=" * 72)
    print("六、同模块同名函数重复注册")
    print("=" * 72)
    reset()

    def handler(event):
        return 1

    action(r"^a$")(handler)

    def handler(event):  # noqa: F811 - 故意同名
        return 2

    try:
        action(r"^b$")(handler)
    except RegistryFrozenError as exc:
        print("  RegistryFrozenError:", exc)
    print()


def demo_read_to_write():
    print("=" * 72)
    print("七、sync=False handler 内 dispatch 到 sync=True")
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
    print()


def demo_async_exception():
    print("=" * 72)
    print("八、异步模式下 handler 异常通过 Future 抛出")
    print("=" * 72)
    from dispatcher3 import dispatch_async, shutdown_executor

    reset()

    @action(r"^async-boom$")
    def async_boom(event):
        raise KeyError("异步里也会炸")

    init_actions()
    future = dispatch_async("async-boom", None)
    try:
        future.result(timeout=5)
    except KeyError as exc:
        print("  KeyError:", exc)
    shutdown_executor()
    print()


def main():
    demo_not_initialized()
    demo_no_match()
    demo_handler_exception()
    demo_invalid_regex()
    demo_register_after_freeze()
    demo_duplicate()
    demo_read_to_write()
    demo_async_exception()


if __name__ == "__main__":
    main()
