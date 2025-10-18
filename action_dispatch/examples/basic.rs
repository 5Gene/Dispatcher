/*!
基础示例：演示 action 的注册和分发
*/

use action_dispatch::{action, dispatch};

#[derive(Clone, Debug)]
struct MyEvent {
    id: u64,
    message: String,
}

// 低优先级的普通 action
#[action(
    regex = r"test/.*",
    priority = 1,
    description = "测试处理器"
)]
fn handle_test(event: MyEvent) {
    println!("[TEST] 收到事件: id={}, message={}", event.id, event.message);
}

// 使用引用传递的 action（适合大事件，零拷贝）
#[action(
    regex = r"large/.*",
    priority = 5,
    by_ref = true,
    description = "大事件处理器（引用传递）"
)]
fn handle_large_event(event: &MyEvent) {
    println!("[LARGE - by_ref] 处理大事件: id={} (零拷贝)", event.id);
}

// 高优先级的用户 action
#[action(
    regex = r"user/\d+/read",
    priority = 10,
    description = "读取用户信息"
)]
fn handle_user_read(event: MyEvent) {
    println!("[USER READ] 读取用户 {}: {}", event.id, event.message);
}

// 最高优先级的更新 action，启用全局同步
#[action(
    regex = r"user/\d+/update",
    priority = 100,
    sync = true,
    description = "更新用户信息（全局同步）"
)]
fn handle_user_update(event: MyEvent) {
    println!(
        "[USER UPDATE - SYNC] 开始更新用户 {}: {}",
        event.id, event.message
    );
    std::thread::sleep(std::time::Duration::from_millis(500));
    println!("[USER UPDATE - SYNC] 完成更新用户 {}", event.id);
}

fn main() {
    println!("=== 基础示例 ===\n");

    // 列出所有已注册的 action
    println!("已注册的 actions:");
    for action in action_dispatch::list_actions() {
        println!(
            "  - regex: {:?}, priority: {}, sync: {}, by_ref: {}, desc: {}",
            action.regex, action.priority, action.sync, action.by_ref, action.description
        );
    }
    println!();

    // 测试分发
    println!("开始分发事件:\n");

    // 1. 测试匹配
    println!("1. 分发到 test/something");
    dispatch(
        "test/something",
        MyEvent {
            id: 1,
            message: "测试消息".to_string(),
        },
    )
    .unwrap();
    println!();

    // 2. 测试用户读取
    println!("2. 分发到 user/123/read");
    dispatch(
        "user/123/read",
        MyEvent {
            id: 123,
            message: "读取请求".to_string(),
        },
    )
    .unwrap();
    println!();

    // 3. 测试用户更新（全局同步）
    println!("3. 分发到 user/456/update（全局同步模式）");
    dispatch(
        "user/456/update",
        MyEvent {
            id: 456,
            message: "更新请求".to_string(),
        },
    )
    .unwrap();
    println!();

    // 4. 测试引用传递（by_ref）
    println!("4. 分发到 large/event（引用传递，零拷贝）");
    dispatch(
        "large/event",
        MyEvent {
            id: 789,
            message: "大事件".to_string(),
        },
    )
    .unwrap();
    println!();

    // 5. 测试无匹配
    println!("5. 分发到 unknown/key（预期失败）");
    match dispatch(
        "unknown/key",
        MyEvent {
            id: 999,
            message: "未知请求".to_string(),
        },
    ) {
        Ok(_) => println!("成功"),
        Err(e) => println!("失败: {}", e),
    }

    println!("\n=== 示例完成 ===");
}

