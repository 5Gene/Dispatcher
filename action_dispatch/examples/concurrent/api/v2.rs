/*!
API v2 handlers

新版本 API 的 action handlers
*/

use action_dispatch::action;
use crate::Event;
use std::thread;
use std::time::Duration;
use rand::Rng;

/// API v2 - 用户列表
#[action(regex = r"^api/v2/users$", priority = 60, sync = false)]
fn api_v2_users_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 🔌 [api::v2::users] API v2 查询用户列表（阻塞 {}s）",
        thread_name, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [api::v2::users] API v2 请求完成",
        thread_name
    );
}

/// API v2 - 产品详情
#[action(regex = r"^api/v2/products/\d+$", priority = 59, sync = false)]
fn api_v2_product_detail_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 🔌 [api::v2::product] API v2 查询产品详情 ID={}（阻塞 {}s）",
        thread_name, event.id, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [api::v2::product] API v2 请求完成",
        thread_name
    );
}

/// API v2 - 搜索
#[action(regex = r"^api/v2/search/.*$", priority = 58, sync = false)]
fn api_v2_search_handler(event: Event) {
    let thread_name = thread::current().name().unwrap_or("unknown").to_string();
    
    let block_time = rand::thread_rng().gen_range(1..=10);
    println!(
        "  [{}] 🔍 [api::v2::search] API v2 搜索: {}（阻塞 {}s）",
        thread_name, event.data, block_time
    );
    
    thread::sleep(Duration::from_secs(block_time));
    
    println!(
        "  [{}] ✅ [api::v2::search] API v2 搜索完成",
        thread_name
    );
}

