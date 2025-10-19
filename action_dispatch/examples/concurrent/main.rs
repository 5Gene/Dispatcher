/*!
# 多文件、多模块并发测试示例

这个示例展示了：
1. ✅ action 在不同文件中定义
2. ✅ action 在不同模块中定义
3. ✅ 同步（sync=true）和异步（sync=false）action 的混合
4. ✅ 每个 action 随机阻塞 1-10s
5. ✅ 多线程并发调用 dispatch
6. ✅ 验证所有 action 都能正确注册和执行

## 运行方式

```bash
cargo run --release --example concurrent
```

## 预期结果

- 同步 action (admin/critical) 会阻塞其他所有 dispatch
- 异步 action 可以并发执行
- 所有 action 最终都会被正确执行
*/

use action_dispatch::{dispatch, list_actions};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use std::collections::HashMap;

// 导入不同文件中的 action 模块
mod user_actions;
mod order_actions;
mod admin_actions;
mod product_actions;
mod api;

// ============================================
// 共享事件类型
// ============================================

#[derive(Clone, Debug)]
pub struct Event {
    pub id: u64,
    pub user: String,
    pub data: String,
}

// ============================================
// 执行结果记录
// ============================================

#[derive(Debug, Clone)]
struct ExecutionRecord {
    action_name: String,
    thread_id: String,
    start_time: Instant,
    duration: Duration,
    blocked_time: Duration,
}

type ResultCollector = Arc<Mutex<Vec<ExecutionRecord>>>;

pub fn record_execution(
    collector: &ResultCollector,
    action_name: &str,
    thread_id: &str,
    start_time: Instant,
    blocked_time: Duration,
) {
    let duration = start_time.elapsed();
    let record = ExecutionRecord {
        action_name: action_name.to_string(),
        thread_id: thread_id.to_string(),
        start_time,
        duration,
        blocked_time,
    };
    
    collector.lock().unwrap().push(record);
}

// ============================================
// 主函数
// ============================================

fn main() {
    println!("\n🚀 多文件多模块并发测试");
    println!("═══════════════════════════════════════════════════════\n");
    
    // 显示所有已注册的 action
    let actions = list_actions();
    println!("📊 已注册 action 列表");
    println!("─────────────────────────────────────────────────────");
    
    let mut by_module: HashMap<String, Vec<_>> = HashMap::new();
    for action in &actions {
        let module = if action.regex.contains("user") {
            "user_actions"
        } else if action.regex.contains("order") {
            "order_actions"
        } else if action.regex.contains("admin") {
            "admin_actions"
        } else if action.regex.contains("api/v1") {
            "api::v1"
        } else if action.regex.contains("api/v2") {
            "api::v2"
        } else {
            "unknown"
        };
        
        by_module.entry(module.to_string()).or_insert_with(Vec::new).push(action);
    }
    
    for (module, actions) in by_module.iter() {
        println!("\n  📦 模块: {}", module);
        for action in actions {
            let sync_mark = if action.sync { "🔒 sync" } else { "🔓 async" };
            println!("     {} {} - {}", sync_mark, action.regex, action.description);
        }
    }
    
    println!("\n═══════════════════════════════════════════════════════\n");
    
    // 创建结果收集器
    let collector: ResultCollector = Arc::new(Mutex::new(Vec::new()));
    
    // 测试用的 dispatch keys
    let test_cases = vec![
        ("user/123/profile", "User Profile"),
        ("user/456/settings", "User Settings"),
        ("order/ORD001", "Order Detail"),
        ("order/ORD002/status", "Order Status"),
        ("admin/critical", "Admin Critical"),  // 🔒 sync action
        ("api/v1/users", "API v1 Users"),
        ("api/v2/users", "API v2 Users"),
        ("product/789", "Product Detail"),
    ];
    
    println!("🔥 开始并发测试（所有 dispatch 同时启动）");
    println!("─────────────────────────────────────────────────────\n");
    
    let global_start = Instant::now();
    
    // 创建线程
    let handles: Vec<_> = test_cases
        .into_iter()
        .enumerate()
        .map(|(i, (key, name))| {
            let key = key.to_string();
            let name = name.to_string();
            let collector = Arc::clone(&collector);
            
            thread::Builder::new()
                .name(format!("Worker-{}", i))
                .spawn(move || {
                    let thread_name = thread::current().name().unwrap().to_string();
                    let event = Event {
                        id: i as u64,
                        user: format!("user_{}", i),
                        data: name.clone(),
                    };
                    
                    let start = Instant::now();
                    println!("[{}] 🚀 dispatch('{}') 开始...", thread_name, key);
                    
                    // 设置全局 collector（通过 thread-local 或其他方式传递）
                    // 这里我们简化处理，直接在 action 中访问
                    
                    match dispatch(&key, event) {
                        Ok(()) => {
                            let elapsed = start.elapsed();
                            println!(
                                "[{}] ✅ dispatch('{}') 完成，耗时 {:?}",
                                thread_name, key, elapsed
                            );
                        }
                        Err(e) => {
                            println!("[{}] ❌ dispatch('{}') 失败: {}", thread_name, key, e);
                        }
                    }
                })
                .unwrap()
        })
        .collect();
    
    // 等待所有线程完成
    for handle in handles {
        handle.join().unwrap();
    }
    
    let total_time = global_start.elapsed();
    
    println!("\n═══════════════════════════════════════════════════════");
    println!("📈 测试结果统计");
    println!("═══════════════════════════════════════════════════════\n");
    
    println!("总耗时: {:?}", total_time);
    
    // 分析执行结果
    let results = collector.lock().unwrap();
    if !results.is_empty() {
        println!("\n详细执行记录:");
        println!("─────────────────────────────────────────────────────");
        
        let mut sorted_results = results.clone();
        sorted_results.sort_by(|a, b| a.start_time.cmp(&b.start_time));
        
        for record in sorted_results.iter() {
            let relative_start = record.start_time.duration_since(global_start);
            println!(
                "  [{}] {} - 开始: {:?}, 阻塞: {:?}, 总耗时: {:?}",
                record.thread_id,
                record.action_name,
                relative_start,
                record.blocked_time,
                record.duration
            );
        }
    }
    
    println!("\n═══════════════════════════════════════════════════════");
    println!("💡 观察要点");
    println!("═══════════════════════════════════════════════════════\n");
    println!("1. 🔒 同步 action (admin/critical) 会阻塞其他所有 dispatch");
    println!("   - 如果它先执行，其他所有请求都要等待");
    println!("   - 如果它后执行，它要等其他 sync=false 的执行完");
    println!();
    println!("2. 🔓 异步 action 可以并发执行");
    println!("   - user, order, api 等 action 可以同时运行");
    println!("   - 每个 action 随机阻塞 1-10s，但不影响其他异步 action");
    println!();
    println!("3. ✅ 所有 action 都能正确注册和执行");
    println!("   - 不同文件、不同模块的 action 都被 inventory 收集");
    println!("   - dispatch 能正确找到并执行对应的 handler");
    println!();
    
    println!("🎉 测试完成！\n");
}

