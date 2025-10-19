/*!
订单相关的 action handlers

模拟订单模块的操作：
- 查看订单详情
- 修改订单状态
- 订单支付
*/

use action_dispatch::action;
use super::Event;
use std::thread;
use std::time::Duration;
use rand::Rng;

/// 查看订单详情
#[action(regex = r"^order/[A-Z0-9]+$", priority = 90, sync = false)]
fn order_detail_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 🛒 [order_detail] 查询订单详情 ID={}（阻塞 {}s）",
        thread_name, event.id, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [order_detail] 订单详情查询完成",
        thread_name
    );
}

/// 修改订单状态
#[action(regex = r"^order/[A-Z0-9]+/status$", priority = 89, sync = false)]
fn order_status_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 📝 [order_status] 更新订单状态 ID={}（阻塞 {}s）",
        thread_name, event.id, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [order_status] 订单状态更新完成",
        thread_name
    );
}

/// 订单支付
#[action(regex = r"^order/[A-Z0-9]+/payment$", priority = 88, sync = false)]
fn order_payment_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 💰 [order_payment] 处理订单支付 ID={}（阻塞 {}s）",
        thread_name, event.id, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [order_payment] 订单支付完成",
        thread_name
    );
}

