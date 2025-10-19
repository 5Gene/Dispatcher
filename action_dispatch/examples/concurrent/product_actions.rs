/*!
产品相关的 action handlers

模拟产品模块的操作
*/

use action_dispatch::action;
use super::Event;
use std::thread;
use std::time::Duration;
use rand::Rng;

/// 查看产品详情
#[action(regex = r"^product/\d+$", priority = 85, sync = false)]
fn product_detail_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 📱 [product_detail] 查询产品详情 ID={}（阻塞 {}s）",
        thread_name, event.id, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [product_detail] 产品查询完成",
        thread_name
    );
}

/// 产品评论
#[action(regex = r"^product/\d+/reviews$", priority = 84, sync = false)]
fn product_reviews_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 💬 [product_reviews] 查询产品评论 ID={}（阻塞 {}s）",
        thread_name, event.id, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [product_reviews] 评论查询完成",
        thread_name
    );
}

