"""打开详细日志，看 dispatch 的每一步。

运行::

    python -m examples.logging_demo

日志分两个级别：

* INFO  —— 初始化摘要、包扫描结果、线程池生命周期
* DEBUG —— 每次 dispatch 的命中策略、加锁、执行、耗时、返回值
"""
import time

from dispatcher3 import (
    action,
    disable_logging,
    dispatch,
    enable_logging,
    init_actions,
    reset,
)


def main():
    enable_logging()          # 默认就是 DEBUG，能看到每一步
    reset()

    print(">>> 1. 定义 action（日志里能看到每个正则被判定成哪种策略）")

    @action(r"^user/[0-9]+$", description="按 ID 查用户", priority=10)
    def get_user(uid):
        time.sleep(0.01)
        return {"id": uid, "name": "user-%s" % uid}

    @action(r"^api/v1/.*", description="v1 接口", priority=5)
    def api_v1(path):
        return {"path": path}

    @action(r"^critical/.*", description="关键操作", priority=100, sync=True)
    def critical(event):
        return {"event": event, "exclusive": True}

    @action(r"^broken$", description="会抛异常")
    def broken(event):
        raise ValueError("我就是想炸一下")

    print()
    print(">>> 2. init_actions() —— 输出完整的 action 清单（INFO）")
    init_actions()

    print()
    print(">>> 3. 精确/前缀/正则 三种命中")
    print("  返回:", dispatch("user/7", 7))
    print("  返回:", dispatch("api/v1/users", "api/v1/users"))

    print()
    print(">>> 4. sync=True 走写锁，日志里能看到全局排他")
    print("  返回:", dispatch("critical/deploy", "deploy"))

    print()
    print(">>> 5. handler 抛异常（异常传播，日志里记了耗时）")
    try:
        dispatch("broken", None)
    except ValueError as exc:
        print("  捕获:", exc)

    print()
    print(">>> 6. 未命中")
    try:
        dispatch("nothing/here", None)
    except Exception as exc:
        print("  捕获:", type(exc).__name__)

    print()
    print(">>> 7. 多个线程抢锁 —— 能看到谁在等、等了多久")
    run_contention_demo()

    print()
    print(">>> 8. 关掉日志，之后完全静默")
    disable_logging()
    print("  返回:", dispatch("queue-read", None))


def run_contention_demo():
    import threading

    # 注册表已冻结，先清空再注册一批专门制造竞争用的 action
    reset()
    go = threading.Event()

    @action(r"^hold$", description="占住写锁", sync=True)
    def hold(event):
        go.set()
        time.sleep(0.15)
        return "hold"

    @action(r"^queue-write$", description="排队抢写锁", sync=True)
    def queue_write(event):
        time.sleep(0.05)
        return "write"

    @action(r"^queue-read$", description="排队抢读锁", sync=False)
    def queue_read(event):
        time.sleep(0.02)
        return "read"

    init_actions()

    holder = threading.Thread(target=dispatch, args=("hold", None), name="Worker-1")
    holder.start()
    go.wait(2.0)
    go.clear()

    writer = threading.Thread(target=dispatch, args=("queue-write", None), name="Worker-2")
    reader = threading.Thread(target=dispatch, args=("queue-read", None), name="Worker-3")
    writer.start()
    reader.start()

    for thread in (holder, writer, reader):
        thread.join(5.0)

    print("  说明：⏳ 是开始等待，🔄 是被唤醒但还要继续等，")
    print("        拿到锁的那条会带上实际等待耗时。")


if __name__ == "__main__":
    main()
