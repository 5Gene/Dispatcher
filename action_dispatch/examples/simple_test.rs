/*!
简单测试：快速验证系统是否正常工作
*/

use action_dispatch::{action, dispatch};

#[derive(Clone)]
struct Event {
    value: i32,
}

#[action(regex = r"test", priority = 0)]
fn test_handler(event: Event) {
    println!("收到事件: value = {}", event.value);
}

fn main() {
    println!("开始测试...");
    
    match dispatch("test", Event { value: 42 }) {
        Ok(_) => println!("✓ 测试成功！"),
        Err(e) => println!("✗ 测试失败: {:?}", e),
    }
}

