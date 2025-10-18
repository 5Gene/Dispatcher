"""
Python Action Dispatch - 并发测试

演示：
1. 分层匹配的性能提升
2. RwLock 的并发优势
3. sync=True 的全局排他
"""

from action_dispatch import dispatcher.action, dispatch, list_actions, get_stats, reset_stats, dispatch_with_stats
import threading
import time
from dataclasses import dataclass


@dataclass
class Event:
    id: int
    thread_name: str = ""


# ============================================================================
# 定义 Actions
# ============================================================================

# 精确匹配：O(1)
@action(regex=r"^exact/match$", priority=10)
def handle_exact(event: Event):
    pass  # 快速返回，测试匹配性能


# 前缀匹配：O(m)
@action(regex=r"^prefix/.*$", priority=5)
def handle_prefix(event: Event):
    pass


# 复杂正则：O(k)
@action(regex=r"^complex/\d+/[a-z]+$", priority=3)
def handle_complex(event: Event):
    pass


# 并发 action：sync = False
@action(regex=r"^concurrent/.*$", priority=5, sync=False)
def handle_concurrent(event: Event):
    print(f"  [并发] 线程 {event.thread_name} 开始处理 {event.id}")
    time.sleep(0.1)
    print(f"  [并发] 线程 {event.thread_name} 完成处理 {event.id}")


# 独占 action：sync = True
@action(regex=r"^exclusive/.*$", priority=10, sync=True)
def handle_exclusive(event: Event):
    print(f"  [独占] 线程 {event.thread_name} 开始独占执行 {event.id} ⚠️")
    time.sleep(0.2)
    print(f"  [独占] 线程 {event.thread_name} 完成独占执行 {event.id} ✓")


# ============================================================================
# 测试函数
# ============================================================================

def test_layered_matching():
    """测试分层匹配性能"""
    print("【测试 1】分层匹配性能")
    print("─" * 60)
    
    iterations = 10000
    
    # 测试精确匹配
    reset_stats()
    start = time.perf_counter()
    for _ in range(iterations):
        dispatch_with_stats("exact/match", Event(1))
    elapsed = time.perf_counter() - start
    stats = get_stats()
    print(f"精确匹配: {iterations} 次 dispatch")
    print(f"  总耗时: {elapsed*1000:.2f} ms")
    print(f"  平均耗时: {stats.average_time_us():.2f} μs/次")
    print()
    
    # 测试前缀匹配
    reset_stats()
    start = time.perf_counter()
    for _ in range(iterations):
        dispatch_with_stats("prefix/some/path", Event(2))
    elapsed = time.perf_counter() - start
    stats = get_stats()
    print(f"前缀匹配: {iterations} 次 dispatch")
    print(f"  总耗时: {elapsed*1000:.2f} ms")
    print(f"  平均耗时: {stats.average_time_us():.2f} μs/次")
    print()
    
    # 测试复杂正则
    reset_stats()
    start = time.perf_counter()
    for _ in range(iterations):
        dispatch_with_stats("complex/123/abc", Event(3))
    elapsed = time.perf_counter() - start
    stats = get_stats()
    print(f"复杂正则: {iterations} 次 dispatch")
    print(f"  总耗时: {elapsed*1000:.2f} ms")
    print(f"  平均耗时: {stats.average_time_us():.2f} μs/次")
    print()


def test_concurrent_execution():
    """测试并发执行（sync=False）"""
    print("【测试 2】并发执行（sync=False）")
    print("─" * 60)
    
    num_threads = 5
    start = time.perf_counter()
    
    threads = []
    for i in range(num_threads):
        t = threading.Thread(
            target=lambda idx: dispatch("concurrent/task", Event(idx, f"Thread-{idx}")),
            args=(i,)
        )
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    elapsed = time.perf_counter() - start
    print(f"\n{num_threads} 个并发任务总耗时: {elapsed*1000:.0f} ms")
    print(f"✓ 由于并发执行，总耗时约等于单个任务时间（~100ms）")
    print()


def test_exclusive_execution():
    """测试独占执行（sync=True）"""
    print("【测试 3】独占执行（sync=True）")
    print("─" * 60)
    
    num_threads = 3
    start = time.perf_counter()
    
    threads = []
    for i in range(num_threads):
        t = threading.Thread(
            target=lambda idx: dispatch("exclusive/task", Event(idx, f"Thread-{idx}")),
            args=(i,)
        )
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    elapsed = time.perf_counter() - start
    print(f"\n{num_threads} 个独占任务总耗时: {elapsed*1000:.0f} ms")
    print(f"✓ 由于串行执行，总耗时约等于 {num_threads} × 单个任务时间（~{num_threads * 200}ms）")
    print()


def test_mixed_workload():
    """测试混合负载"""
    print("【测试 4】混合负载（并发 + 独占）")
    print("─" * 60)
    
    start = time.perf_counter()
    
    threads = []
    
    # 启动 1 个独占任务
    t = threading.Thread(
        target=lambda: dispatch("exclusive/task", Event(0, "Exclusive")),
    )
    threads.append(t)
    t.start()
    
    # 稍微延迟，确保独占任务先开始
    time.sleep(0.05)
    
    # 启动 3 个并发任务（会被独占任务阻塞）
    for i in range(3):
        t = threading.Thread(
            target=lambda idx: (
                print(f"  [等待] Thread-{idx} 尝试执行，但被独占任务阻塞..."),
                dispatch("concurrent/task", Event(idx, f"Thread-{idx}"))
            ),
            args=(i,)
        )
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    elapsed = time.perf_counter() - start
    print(f"\n混合负载总耗时: {elapsed*1000:.0f} ms")
    print(f"✓ 独占任务优先执行，并发任务等待独占完成后才能执行")
    print()


# ============================================================================
# 主函数
# ============================================================================

def main():
    print("╔" + "═" * 60 + "╗")
    print("║" + " " * 15 + "Python Action Dispatch - 并发测试" + " " * 13 + "║")
    print("╚" + "═" * 60 + "╝\n")
    
    print("已注册的 actions:")
    for info in list_actions():
        print(f"  - {info.regex}: priority={info.priority}, sync={info.sync}, strategy={info.strategy}")
    print("\n")
    
    # 运行测试
    test_layered_matching()
    test_concurrent_execution()
    test_exclusive_execution()
    test_mixed_workload()
    
    print("╔" + "═" * 60 + "╗")
    print("║" + " " * 24 + "测试完成！" + " " * 24 + "║")
    print("╚" + "═" * 60 + "╝")


if __name__ == "__main__":
    main()

