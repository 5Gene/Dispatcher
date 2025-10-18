/*!
并发示例：演示全局同步锁的效果

这个示例创建多个线程，分别执行：
- sync = false 的 action（支持并发）
- sync = true 的 action（全局排他）

观察输出，验证同步机制是否正确工作。
*/

use action_dispatch::{action, dispatch};
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;
use std::time::{Duration, Instant};

#[derive(Clone, Debug)]
struct Event {
    id: u64,
    thread_name: String,
}

// 并发计数器：统计正在执行的 action 数量
static CONCURRENT_READ_COUNT: AtomicU64 = AtomicU64::new(0);
static CONCURRENT_WRITE_COUNT: AtomicU64 = AtomicU64::new(0);

// 读操作：sync = false，支持并发
#[action(
    regex = r"user/\d+/read",
    priority = 5,
    sync = false,
    description = "读取用户（并发）"
)]
fn handle_read(event: Event) {
    let count = CONCURRENT_READ_COUNT.fetch_add(1, Ordering::SeqCst) + 1;
    let start = Instant::now();
    
    println!(
        "[READ START ] 线程 {}: 开始读取用户 {} (当前并发读取数: {})",
        event.thread_name, event.id, count
    );

    // 模拟耗时操作
    thread::sleep(Duration::from_millis(300));

    let elapsed = start.elapsed();
    CONCURRENT_READ_COUNT.fetch_sub(1, Ordering::SeqCst);
    
    println!(
        "[READ END   ] 线程 {}: 完成读取用户 {} (耗时: {:?})",
        event.thread_name, event.id, elapsed
    );
}

// 更新操作：sync = true，全局排他
#[action(
    regex = r"user/\d+/update",
    priority = 10,
    sync = true,
    description = "更新用户（全局同步）"
)]
fn handle_update(event: Event) {
    let count = CONCURRENT_WRITE_COUNT.fetch_add(1, Ordering::SeqCst) + 1;
    let start = Instant::now();
    
    println!(
        "[UPDATE START] 线程 {}: 开始更新用户 {} ⚠️  全局锁已持有 (当前并发更新数: {})",
        event.thread_name, event.id, count
    );

    // 模拟耗时操作
    thread::sleep(Duration::from_secs(2));

    let elapsed = start.elapsed();
    CONCURRENT_WRITE_COUNT.fetch_sub(1, Ordering::SeqCst);
    
    println!(
        "[UPDATE END  ] 线程 {}: 完成更新用户 {} ✓ 全局锁已释放 (耗时: {:?})",
        event.thread_name, event.id, elapsed
    );
}

// 关键操作：sync = true，高优先级
#[action(
    regex = r"system/critical",
    priority = 100,
    sync = true,
    description = "系统关键操作"
)]
fn handle_critical(event: Event) {
    let start = Instant::now();
    
    println!(
        "[CRITICAL START] 线程 {}: 🚨 开始执行关键操作 id={} （阻塞所有其他操作）",
        event.thread_name, event.id
    );

    thread::sleep(Duration::from_secs(3));

    let elapsed = start.elapsed();
    
    println!(
        "[CRITICAL END  ] 线程 {}: ✓ 关键操作完成 id={} (耗时: {:?})",
        event.thread_name, event.id, elapsed
    );
}

fn main() {
    println!("=== 并发示例 ===\n");
    println!("演示全局同步锁的效果：");
    println!("- sync = false 的 action 可以并发执行");
    println!("- sync = true 的 action 会阻塞所有其他 dispatch\n");

    let start_time = Instant::now();

    // 场景 1：多个并发读取
    println!("【场景 1】启动 3 个并发读取线程...\n");
    let handles1: Vec<_> = (0..3)
        .map(|i| {
            thread::spawn(move || {
                dispatch(
                    "user/100/read",
                    Event {
                        id: 100 + i,
                        thread_name: format!("读取-{}", i),
                    },
                )
                .unwrap();
            })
        })
        .collect();

    // 等待所有读取完成
    for h in handles1 {
        h.join().unwrap();
    }

    println!("\n【场景 1 完成】所有读取操作已完成\n");
    println!("---\n");

    // 场景 2：混合并发读取和全局同步更新
    println!("【场景 2】混合测试：2 个读取 + 1 个更新（sync=true）\n");
    
    let mut handles2 = vec![];

    // 启动 1 个更新（sync = true）
    handles2.push(thread::spawn(|| {
        thread::sleep(Duration::from_millis(50)); // 稍微延迟，让读取先开始
        dispatch(
            "user/200/update",
            Event {
                id: 200,
                thread_name: "更新-0".to_string(),
            },
        )
        .unwrap();
    }));

    // 启动 2 个读取（sync = false）
    for i in 0..2 {
        handles2.push(thread::spawn(move || {
            dispatch(
                "user/200/read",
                Event {
                    id: 200 + i,
                    thread_name: format!("读取-{}", i),
                },
            )
            .unwrap();
        }));
    }

    for h in handles2 {
        h.join().unwrap();
    }

    println!("\n【场景 2 完成】混合操作已完成\n");
    println!("---\n");

    // 场景 3：关键操作阻塞所有其他操作
    println!("【场景 3】关键操作测试：1 个关键操作 + 3 个读取\n");
    
    let mut handles3 = vec![];

    // 先启动关键操作
    handles3.push(thread::spawn(|| {
        dispatch(
            "system/critical",
            Event {
                id: 999,
                thread_name: "关键操作".to_string(),
            },
        )
        .unwrap();
    }));

    // 稍微延迟后启动读取（这些会被阻塞）
    thread::sleep(Duration::from_millis(100));
    
    for i in 0..3 {
        handles3.push(thread::spawn(move || {
            println!(
                "[等待中...] 线程 读取-{}: 尝试分发读取请求，但被关键操作阻塞",
                i
            );
            dispatch(
                "user/300/read",
                Event {
                    id: 300 + i,
                    thread_name: format!("读取-{}", i),
                },
            )
            .unwrap();
        }));
    }

    for h in handles3 {
        h.join().unwrap();
    }

    println!("\n【场景 3 完成】关键操作及后续读取已完成\n");

    let total_time = start_time.elapsed();
    println!("=== 总耗时: {:?} ===", total_time);
    
    println!("\n观察要点：");
    println!("1. 场景 1 中的 3 个读取应该几乎同时执行（并发）");
    println!("2. 场景 2 中的更新会阻塞后续的读取");
    println!("3. 场景 3 中的关键操作会阻塞所有其他操作（包括读取）");
}

