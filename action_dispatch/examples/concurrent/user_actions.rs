/*!
用户相关的 action handlers

模拟用户模块的操作：
- 查看用户资料
- 修改用户设置
- 查询用户订单
*/

use action_dispatch::action;
use super::Event;
use std::thread;
use std::time::Duration;
use rand::Rng;

/// 查看用户资料
#[action(regex = r"^user/\d+/profile$", priority = 100, sync = false)]
fn user_profile_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    // 随机阻塞 1-10 秒
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 👤 [user_profile] 处理用户 {} 的资料查询（阻塞 {}s）",
        thread_name, event.user, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [user_profile] 用户资料查询完成",
        thread_name
    );
}

/// 修改用户设置
#[action(regex = r"^user/\d+/settings$", priority = 99, sync = false)]
fn user_settings_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] ⚙️  [user_settings] 修改用户 {} 的设置（阻塞 {}s）",
        thread_name, event.user, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [user_settings] 用户设置修改完成",
        thread_name
    );
}

/// 查询用户订单
#[action(regex = r"^user/\d+/orders$", priority = 98, sync = false)]
fn user_orders_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 📦 [user_orders] 查询用户 {} 的订单列表（阻塞 {}s）",
        thread_name, event.user, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [user_orders] 订单查询完成",
        thread_name
    );
}

