"""
Python 版本性能对比：v2 vs v3

对比项：
1. 精确匹配（单次 + 重复）
2. 前缀匹配
3. 复杂正则匹配
4. 并发性能
5. 内存占用
"""

import time
import threading
from dataclasses import dataclass


@dataclass
class Event:
    id: int
    data: str = "test"


def benchmark_version(version_name: str, action_decorator, dispatch_func, init_func):
    """基准测试一个版本"""
    
    print(f"\n{'='*70}")
    print(f" 测试版本: {version_name}")
    print(f"{'='*70}\n")
    
    # 定义 actions
    @action_decorator(regex=r"^exact/match$", priority=10)
    def handle_exact(event):
        pass
    
    @action_decorator(regex=r"^prefix/.*$", priority=5)
    def handle_prefix(event):
        pass
    
    @action_decorator(regex=r"^complex/\d+/[a-z]+$", priority=3)
    def handle_complex(event):
        pass
    
    @action_decorator(regex=r"^concurrent/.*$", priority=5, sync=False)
    def handle_concurrent(event):
        pass
    
    # 初始化
    init_func()
    
    event = Event(123)
    
    results = {}
    
    # ========================================================================
    # 测试 1：精确匹配（冷启动）
    # ========================================================================
    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        dispatch_func("exact/match", event)
    elapsed = time.perf_counter() - start
    
    avg_us = elapsed * 1000000 / iterations
    results['exact_cold'] = avg_us
    print(f"1. 精确匹配（冷启动）: {iterations} 次")
    print(f"   平均耗时: {avg_us:.2f} μs/次")
    print()
    
    # ========================================================================
    # 测试 2：精确匹配（热点key，测试缓存）
    # ========================================================================
    iterations = 10000
    start = time.perf_counter()
    for _ in range(iterations):
        dispatch_func("exact/match", event)  # 相同的 key
    elapsed = time.perf_counter() - start
    
    avg_us = elapsed * 1000000 / iterations
    results['exact_hot'] = avg_us
    print(f"2. 精确匹配（热点 key）: {iterations} 次")
    print(f"   平均耗时: {avg_us:.2f} μs/次")
    print()
    
    # ========================================================================
    # 测试 3：前缀匹配
    # ========================================================================
    iterations = 5000
    start = time.perf_counter()
    for i in range(iterations):
        dispatch_func(f"prefix/{i}", event)  # 不同的 key
    elapsed = time.perf_counter() - start
    
    avg_us = elapsed * 1000000 / iterations
    results['prefix'] = avg_us
    print(f"3. 前缀匹配: {iterations} 次")
    print(f"   平均耗时: {avg_us:.2f} μs/次")
    print()
    
    # ========================================================================
    # 测试 4：复杂正则
    # ========================================================================
    iterations = 2000
    start = time.perf_counter()
    for i in range(iterations):
        dispatch_func(f"complex/{i}/abc", event)
    elapsed = time.perf_counter() - start
    
    avg_us = elapsed * 1000000 / iterations
    results['regex'] = avg_us
    print(f"4. 复杂正则: {iterations} 次")
    print(f"   平均耗时: {avg_us:.2f} μs/次")
    print()
    
    # ========================================================================
    # 测试 5：并发（10线程）
    # ========================================================================
    num_threads = 10
    iterations_per_thread = 100
    
    def worker():
        for i in range(iterations_per_thread):
            dispatch_func("concurrent/task", event)
    
    start = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - start
    
    total_ops = num_threads * iterations_per_thread
    ops_per_sec = total_ops / elapsed
    results['concurrent'] = ops_per_sec
    print(f"5. 并发测试（{num_threads} 线程）:")
    print(f"   总操作: {total_ops}")
    print(f"   总耗时: {elapsed*1000:.0f} ms")
    print(f"   吞吐量: {ops_per_sec:.0f} ops/s")
    print()
    
    return results


def main():
    print("\n" + "█" * 70)
    print(" " * 18 + "Python 性能对比：v2 vs v3")
    print("█" * 70 + "\n")
    
    # ========================================================================
    # 测试 v2
    # ========================================================================
    print("\n" + "▶" * 35 + " 测试 v2 " + "◀" * 35)
    
    import dispatcher.action_dispatch_v2 as v2
    
    results_v2 = benchmark_version(
        "v2 (基础版)",
        v2.action,
        v2.dispatch,
        v2.init_actions
    )
    
    # ========================================================================
    # 测试 v3
    # ========================================================================
    print("\n" + "▶" * 35 + " 测试 v3 " + "◀" * 35)
    
    import dispatcher.action_dispatch_v3 as v3
    
    results_v3 = benchmark_version(
        "v3 (优化版)",
        v3.action,
        v3.dispatch,
        v3.init_actions
    )
    
    # ========================================================================
    # 对比结果
    # ========================================================================
    print("\n" + "=" * 70)
    print(" " * 26 + "性能对比总结")
    print("=" * 70 + "\n")
    
    print(f"{'测试项':<20} {'v2':<15} {'v3':<15} {'提升':<10}")
    print("-" * 70)
    
    # 精确匹配（冷启动）
    v2_val = results_v2['exact_cold']
    v3_val = results_v3['exact_cold']
    speedup = v2_val / v3_val
    print(f"{'精确匹配（冷启动）':<20} {v2_val:<15.2f} {v3_val:<15.2f} {speedup:<10.2f}x")
    
    # 精确匹配（热点）
    v2_val = results_v2['exact_hot']
    v3_val = results_v3['exact_hot']
    speedup = v2_val / v3_val
    print(f"{'精确匹配（热点）':<20} {v2_val:<15.2f} {v3_val:<15.2f} {speedup:<10.2f}x ⭐")
    
    # 前缀匹配
    v2_val = results_v2['prefix']
    v3_val = results_v3['prefix']
    speedup = v2_val / v3_val
    print(f"{'前缀匹配':<20} {v2_val:<15.2f} {v3_val:<15.2f} {speedup:<10.2f}x")
    
    # 复杂正则
    v2_val = results_v2['regex']
    v3_val = results_v3['regex']
    speedup = v2_val / v3_val
    print(f"{'复杂正则':<20} {v2_val:<15.2f} {v3_val:<15.2f} {speedup:<10.2f}x")
    
    # 并发
    v2_val = results_v2['concurrent']
    v3_val = results_v3['concurrent']
    speedup = v3_val / v2_val
    print(f"{'并发吞吐量':<20} {v2_val:<15.0f} {v3_val:<15.0f} {speedup:<10.2f}x")
    
    print("-" * 70)
    
    # 计算综合提升
    improvements = [
        results_v2['exact_cold'] / results_v3['exact_cold'],
        results_v2['exact_hot'] / results_v3['exact_hot'],
        results_v2['prefix'] / results_v3['prefix'],
        results_v2['regex'] / results_v3['regex'],
        results_v3['concurrent'] / results_v2['concurrent'],
    ]
    avg_improvement = sum(improvements) / len(improvements)
    
    print(f"\n{'综合性能提升:':<20} {avg_improvement:.2f}x")
    
    # 显示缓存统计（v3）
    cache_info = v3.get_cache_stats()
    if cache_info:
        print(f"\nv3 缓存统计:")
        print(f"  命中: {cache_info.hits}")
        print(f"  未命中: {cache_info.misses}")
        print(f"  命中率: {cache_info.hits/(cache_info.hits+cache_info.misses)*100:.1f}%")
    
    print("\n" + "=" * 70)
    
    # 评估
    if avg_improvement >= 3.0:
        rating = "⭐⭐⭐ 优秀"
    elif avg_improvement >= 2.0:
        rating = "⭐⭐ 良好"
    elif avg_improvement >= 1.5:
        rating = "⭐ 一般"
    else:
        rating = "⚠️ 提升不明显"
    
    print(f"\n性能提升评级: {rating}")
    print(f"平均提升倍数: {avg_improvement:.2f}x\n")
    
    print("=" * 70)


if __name__ == "__main__":
    main()

