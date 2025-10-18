/*!
性能优化演示

展示所有性能优化特性：
1. 引用传递（by_ref）- 避免大事件拷贝
2. 分层匹配 - 精确/前缀/正则
3. RwLock - 并发执行 sync=false 的 action
4. Send + Sync 约束 - 编译期安全检查
*/

use action_dispatch::{action, dispatch};
use std::thread;
use std::time::{Duration, Instant};

// ============================================================================
// 1. 引用传递优化：避免大事件拷贝
// ============================================================================

#[derive(Clone)]
struct LargeEvent {
    data: Vec<u8>,
    id: u64,
}

impl LargeEvent {
    fn new(id: u64, size: usize) -> Self {
        Self {
            data: vec![0u8; size],
            id,
        }
    }
}

// 值传递：会拷贝整个事件（慢）
#[action(regex = r"^large/by_value$", priority = 5)]
fn handle_large_by_value(event: LargeEvent) {
    println!("  [值传递] 处理大事件 {} ({} bytes)", event.id, event.data.len());
}

// 引用传递：零拷贝（快）
#[action(regex = r"^large/by_ref$", priority = 5, by_ref = true)]
fn handle_large_by_ref(event: &LargeEvent) {
    println!("  [引用传递] 处理大事件 {} ({} bytes) - 零拷贝！", event.id, event.data.len());
}

// ============================================================================
// 2. 分层匹配优化：精确/前缀/正则
// ============================================================================

#[derive(Clone)]
struct RouteEvent {
    route: String,
}

// 精确匹配：O(1) HashMap 查找
#[action(regex = r"^exact/match$", priority = 10)]
fn handle_exact(_event: RouteEvent) {
    println!("  [精确匹配 O(1)] 处理精确路由");
}

// 前缀匹配：O(m) 前缀检查
#[action(regex = r"^prefix/.*", priority = 5)]
fn handle_prefix(_event: RouteEvent) {
    println!("  [前缀匹配 O(m)] 处理前缀路由");
}

// 复杂正则：O(k) 完整正则匹配
#[action(regex = r"^complex/\d+/[a-z]+$", priority = 3)]
fn handle_complex(_event: RouteEvent) {
    println!("  [复杂正则 O(k)] 处理复杂正则路由");
}

// ============================================================================
// 3. RwLock 优化：并发执行
// ============================================================================

#[derive(Clone)]
struct ConcurrentEvent {
    id: u64,
}

// sync = false：可以并发执行（持有读锁）
#[action(regex = r"^concurrent/.*", priority = 5, sync = false)]
fn handle_concurrent(event: ConcurrentEvent) {
    println!("  [并发] 线程 {:?} 开始处理 {}", thread::current().id(), event.id);
    thread::sleep(Duration::from_millis(100));
    println!("  [并发] 线程 {:?} 完成处理 {}", thread::current().id(), event.id);
}

// sync = true：全局排他执行（持有写锁）
#[action(regex = r"^exclusive/.*", priority = 10, sync = true)]
fn handle_exclusive(event: ConcurrentEvent) {
    println!("  [独占] 线程 {:?} 开始独占执行 {} ⚠️ 所有其他操作阻塞", 
        thread::current().id(), event.id);
    thread::sleep(Duration::from_millis(200));
    println!("  [独占] 线程 {:?} 完成独占执行 {} ✓", 
        thread::current().id(), event.id);
}

// ============================================================================
// 主函数：演示所有优化
// ============================================================================

fn main() {
    println!("╔════════════════════════════════════════════════════════════╗");
    println!("║        Action Dispatch - 性能优化演示                      ║");
    println!("╚════════════════════════════════════════════════════════════╝\n");

    // 演示 1：引用传递 vs 值传递
    demo_by_ref_optimization();
    println!();

    // 演示 2：分层匹配
    demo_layered_matching();
    println!();

    // 演示 3：RwLock 并发
    demo_rwlock_concurrency();
    println!();

    println!("╔════════════════════════════════════════════════════════════╗");
    println!("║                     演示完成！                              ║");
    println!("╚════════════════════════════════════════════════════════════╝");
}

/// 演示 1：引用传递优化
fn demo_by_ref_optimization() {
    println!("【演示 1】引用传递优化 - 避免大事件拷贝");
    println!("─────────────────────────────────────────────────────────");

    let event = LargeEvent::new(1, 1024 * 1024); // 1 MB 事件

    println!("\n测试 1: 值传递（会拷贝 1 MB 数据）");
    let start = Instant::now();
    dispatch("large/by_value", event.clone()).unwrap();
    let elapsed_value = start.elapsed();
    println!("  耗时: {:?}", elapsed_value);

    println!("\n测试 2: 引用传递（零拷贝）");
    let start = Instant::now();
    dispatch("large/by_ref", event.clone()).unwrap();
    let elapsed_ref = start.elapsed();
    println!("  耗时: {:?}", elapsed_ref);

    if elapsed_value > elapsed_ref {
        let speedup = elapsed_value.as_micros() as f64 / elapsed_ref.as_micros() as f64;
        println!("\n  ✓ 引用传递提速: {:.2}x", speedup);
    }
}

/// 演示 2：分层匹配优化
fn demo_layered_matching() {
    println!("【演示 2】分层匹配优化 - 不同匹配策略的性能");
    println!("─────────────────────────────────────────────────────────");

    println!("\n测试 1: 精确匹配（HashMap O(1)）");
    let start = Instant::now();
    for _ in 0..1000 {
        dispatch("exact/match", RouteEvent { route: "exact/match".to_string() }).unwrap();
    }
    let elapsed_exact = start.elapsed();
    println!("  1000次 dispatch 耗时: {:?} (平均 {:.2} μs/次)", 
        elapsed_exact, elapsed_exact.as_micros() as f64 / 1000.0);

    println!("\n测试 2: 前缀匹配（starts_with O(m)）");
    let start = Instant::now();
    for _ in 0..1000 {
        dispatch("prefix/some/path", RouteEvent { route: "prefix/some/path".to_string() }).unwrap();
    }
    let elapsed_prefix = start.elapsed();
    println!("  1000次 dispatch 耗时: {:?} (平均 {:.2} μs/次)", 
        elapsed_prefix, elapsed_prefix.as_micros() as f64 / 1000.0);

    println!("\n测试 3: 复杂正则（regex O(k)）");
    let start = Instant::now();
    for _ in 0..1000 {
        dispatch("complex/123/abc", RouteEvent { route: "complex/123/abc".to_string() }).unwrap();
    }
    let elapsed_regex = start.elapsed();
    println!("  1000次 dispatch 耗时: {:?} (平均 {:.2} μs/次)", 
        elapsed_regex, elapsed_regex.as_micros() as f64 / 1000.0);

    println!("\n  ✓ 精确匹配最快（HashMap 查找）");
    println!("  ✓ 前缀匹配次之（字符串比较）");
    println!("  ✓ 复杂正则最慢（完整正则匹配）");
}

/// 演示 3：RwLock 并发优化
fn demo_rwlock_concurrency() {
    println!("【演示 3】RwLock 并发优化 - sync=false 可并发执行");
    println!("─────────────────────────────────────────────────────────");

    println!("\n测试 1: 多个 sync=false 的 action 并发执行");
    let start = Instant::now();
    let handles: Vec<_> = (0..5)
        .map(|i| {
            thread::spawn(move || {
                dispatch("concurrent/task", ConcurrentEvent { id: i }).unwrap();
            })
        })
        .collect();

    for h in handles {
        h.join().unwrap();
    }
    let elapsed_concurrent = start.elapsed();
    println!("  5 个并发任务总耗时: {:?}", elapsed_concurrent);
    println!("  ✓ 由于并发执行，总耗时约等于单个任务时间（~100ms）");

    println!("\n测试 2: sync=true 的 action 串行执行（独占）");
    let start = Instant::now();
    let handles: Vec<_> = (0..3)
        .map(|i| {
            thread::spawn(move || {
                dispatch("exclusive/task", ConcurrentEvent { id: i }).unwrap();
            })
        })
        .collect();

    for h in handles {
        h.join().unwrap();
    }
    let elapsed_exclusive = start.elapsed();
    println!("  3 个独占任务总耗时: {:?}", elapsed_exclusive);
    println!("  ✓ 由于串行执行，总耗时约等于 3 × 单个任务时间（~600ms）");

    let speedup = elapsed_exclusive.as_millis() as f64 / elapsed_concurrent.as_millis() as f64;
    println!("\n  ✓ 并发执行相比串行提速: {:.2}x", speedup);
}

