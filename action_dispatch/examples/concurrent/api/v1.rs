/*!
API v1 handlers

旧版本 API 的 action handlers
*/

use action_dispatch::action;
use crate::Event;
use std::thread;
use std::time::Duration;
use rand::Rng;

/// API v1 - 用户列表
#[action(regex = r"^api/v1/users$", priority = 70, sync = false)]
fn api_v1_users_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 🔌 [api::v1::users] API v1 查询用户列表（阻塞 {}s）",
        thread_name, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [api::v1::users] API v1 请求完成",
        thread_name
    );
}

/// API v1 - 产品列表
#[action(regex = r"^api/v1/products$", priority = 69, sync = false)]
fn api_v1_products_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 🔌 [api::v1::products] API v1 查询产品列表（阻塞 {}s）",
        thread_name, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [api::v1::products] API v1 请求完成",
        thread_name
    );
}

