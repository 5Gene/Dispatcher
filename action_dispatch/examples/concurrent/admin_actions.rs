/*!
管理员相关的 action handlers

包含关键操作，需要同步执行（sync = true）：
- admin/critical - 🔒 同步操作，会阻塞所有其他 dispatch
- admin/reports - 异步操作
*/

use action_dispatch::action;
use super::Event;
use std::thread;
use std::time::Duration;
use rand::Rng;

/// 🔒 关键管理操作（同步执行）
/// 
/// 这个 action 设置了 sync = true，会独占执行：
/// - 执行时会阻塞所有其他 dispatch 调用
/// - 其他线程必须等待这个 action 完成
#[action(regex = r"^admin/critical$", priority = 200, sync = true)]
fn admin_critical_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    
    println!("\n  ╔═══════════════════════════════════════════════════");
    println!("  ║ [{}] 🔒 [admin_critical] 开始执行（SYNC 模式）", thread_name);
    println!("  ║ ⚠️  阻塞所有其他 dispatch，独占执行 {}s", block_time);
    println!("  ╚═══════════════════════════════════════════════════\n");
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!("\n  ╔═══════════════════════════════════════════════════");
    println!("  ║ [{}] ✅ [admin_critical] 完成（释放锁）", thread_name);
    println!("  ╚═══════════════════════════════════════════════════\n");
}

/// 查看管理报表（异步）
#[action(regex = r"^admin/reports$", priority = 80, sync = false)]
fn admin_reports_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 📊 [admin_reports] 生成管理报表（阻塞 {}s）",
        thread_name, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [admin_reports] 报表生成完成",
        thread_name
    );
}

/// 用户管理
#[action(regex = r"^admin/users/.*$", priority = 79, sync = false)]
fn admin_users_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 👥 [admin_users] 管理用户 {}（阻塞 {}s）",
        thread_name, event.user, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [admin_users] 用户管理完成",
        thread_name
    );
}

