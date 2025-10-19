use action_dispatch::{action, dispatch, set_single_thread_mode, is_single_thread_mode};
use std::thread;
use std::time::{Duration, Instant};

#[derive(Clone)]
struct Task {
    id: u64,
    name: String,
}

// 普通 action，默认可并发
#[action(regex = r"^task/normal$", priority = 0, description = "普通任务")]
fn handle_normal_task(task: Task) {
    println!("🟢 [线程 {:?}] 处理普通任务: {} - {}", 
             thread::current().id(), task.id, task.name);
    thread::sleep(Duration::from_millis(100)); // 模拟工作
}

// 关键 action，强制串行
#[action(regex = r"^task/critical$", priority = 10, sync = true, description = "关键任务")]
fn handle_critical_task(task: Task) {
    println!("🔴 [线程 {:?}] 处理关键任务: {} - {} (独占执行)", 
             thread::current().id(), task.id, task.name);
    thread::sleep(Duration::from_millis(100));
}

fn benchmark(mode: &str, single_thread: bool, task_count: usize) {
    println!("\n==================================================");
    println!("🧪 测试模式: {}", mode);
    println!("单线程模式: {}", if single_thread { "✅ 启用" } else { "❌ 禁用" });
    println!("==================================================\n");
    
    set_single_thread_mode(single_thread);
    
    let start = Instant::now();
    
    let handles: Vec<_> = (0..task_count)
        .map(|i| {
            thread::spawn(move || {
                let task = Task {
                    id: i as u64,
                    name: format!("任务{}", i),
                };
                
                if i % 3 == 0 {
                    dispatch("task/critical", task.clone()).unwrap();
                } else {
                    dispatch("task/normal", task.clone()).unwrap();
                }
            })
        })
        .collect();
    
    for handle in handles {
        handle.join().unwrap();
    }
    
    let elapsed = start.elapsed();
    println!("\n⏱️  耗时: {:?}", elapsed);
}

fn main() {
    println!("\n🚀 Action Dispatch - 并发控制演示\n");
    
    // 测试 1: 多线程模式（默认）
    benchmark("多线程模式 (默认)", false, 10);
    
    // 等待一下
    thread::sleep(Duration::from_millis(500));
    
    // 测试 2: 单线程模式
    benchmark("单线程模式 (强制串行)", true, 10);
    
    // 测试 3: 查询当前模式
    println!("\n==================================================");
    println!("📊 当前配置:");
    println!("==================================================");
    println!("单线程模式: {}", if is_single_thread_mode() { "✅" } else { "❌" });
    println!();
    
    // 测试 4: 动态切换
    println!("==================================================");
    println!("🔄 动态切换测试");
    println!("==================================================\n");
    
    set_single_thread_mode(false);
    println!("切换到多线程模式: {}", is_single_thread_mode());
    
    set_single_thread_mode(true);
    println!("切换到单线程模式: {}", is_single_thread_mode());
    
    set_single_thread_mode(false);
    println!("切换回多线程模式: {}", is_single_thread_mode());
    
    println!("\n✅ 测试完成！\n");
    
    // 性能对比总结
    println!("==================================================");
    println!("📈 性能说明:");
    println!("==================================================");
    println!("• 多线程模式: sync=false 的 action 可并发执行");
    println!("  → 性能最优，适用于生产环境");
    println!();
    println!("• 单线程模式: 所有 dispatch 串行执行");
    println!("  → 适用于调试、嵌入式系统、单核 CPU");
    println!();
    println!("• sync=true 的 action: 始终独占执行");
    println!("  → 不受全局配置影响");
    println!();
}

