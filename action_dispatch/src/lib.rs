/*!
# Action Dispatch

一个通用的基于属性宏的 Action 注册与分发系统

## 特性

- ✅ **声明式注册**：使用 `#[action(...)]` 属性宏标记处理函数
- ✅ **正则匹配**：支持正则表达式匹配 key
- ✅ **优先级控制**：支持设置 action 优先级
- ✅ **类型安全**：编译期类型检查，无需序列化
- ✅ **线程安全**：完全线程安全，支持多线程并发
- ✅ **全局同步模式**：支持全局排他执行，阻塞所有其他 dispatch
- ✅ **零成本抽象**：编译期注册，运行时几乎无开销

## 核心概念

### 全局同步锁（Global Sync Lock）

系统维护一个全局互斥锁，所有 `dispatch` 调用都会竞争此锁：

- **`sync = false`（默认）**：拿锁 → 匹配 → 释放锁 → 执行
  - 支持多个 action 并发执行
  
- **`sync = true`**：拿锁 → 匹配 → 不释放锁 → 执行 → 完成后释放
  - 该 action 执行期间，所有其他 dispatch 请求都会被阻塞
  - 适用于关键操作，如数据库迁移、配置更新等

## 快速开始

```rust
use action_dispatch::{action, dispatch};

#[derive(Clone)]
struct MyEvent {
    user_id: u64,
    action: String,
}

// 普通 action，支持并发
#[action(regex = r"user/\d+/read", priority = 5, sync = false)]
fn handle_read(event: MyEvent) {
    println!("读取用户 {}", event.user_id);
}

// 关键 action，全局同步执行
#[action(regex = r"user/\d+/update", priority = 10, sync = true)]
fn handle_update(event: MyEvent) {
    println!("更新用户 {}（阻塞所有其他操作）", event.user_id);
    std::thread::sleep(std::time::Duration::from_secs(2));
}

fn main() {
    // 直接分发事件（首次调用会自动初始化注册表）
    dispatch("user/123/read", MyEvent {
        user_id: 123,
        action: "read".to_string(),
    }).unwrap();

    dispatch("user/456/update", MyEvent {
        user_id: 456,
        action: "update".to_string(),
    }).unwrap();
}
```

## 多线程示例

```rust
use action_dispatch::{action, dispatch};
use std::thread;

#[derive(Clone)]
struct Event { id: u64 }

#[action(regex = r"normal/.*", sync = false)]
fn handle_normal(event: Event) {
    println!("并发执行: {}", event.id);
}

#[action(regex = r"critical/.*", sync = true)]
fn handle_critical(event: Event) {
    println!("独占执行: {}", event.id);
    thread::sleep(std::time::Duration::from_secs(1));
}

fn main() {
    let handles: Vec<_> = (0..10).map(|i| {
        thread::spawn(move || {
            if i % 2 == 0 {
                dispatch("normal/task", Event { id: i }).unwrap();
            } else {
                dispatch("critical/task", Event { id: i }).unwrap();
            }
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }
}
```

## 参数说明

### `#[action(...)]` 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `regex` | `&str` | ✅ | - | 匹配 key 的正则表达式 |
| `priority` | `i32` | ❌ | `0` | 优先级，数值越大优先级越高 |
| `description` | `&str` | ❌ | `""` | 描述信息 |
| `sync` | `bool` | ❌ | `false` | 是否启用全局同步执行模式 |

### 函数签名要求

- 必须是自由函数（不在 impl 块中）
- 必须恰好有一个参数：`fn(T)` 或 `fn(&T)`
- 所有 action 必须使用相同的事件类型 `T`
- 返回值不限

## 性能特点

- **编译期注册**：使用 `inventory` crate 在编译期收集所有 handler
- **零动态分配**：action 列表在程序启动时初始化，之后只读
- **高效匹配**：使用编译后的正则表达式，支持缓存
- **最小锁竞争**：`sync = false` 的 action 快速释放锁

## 错误处理

```rust
use action_dispatch::{dispatch, DispatchError};

match dispatch("unknown/key", event) {
    Ok(()) => println!("分发成功"),
    Err(DispatchError::NoMatch) => println!("没有匹配的 action"),
    Err(DispatchError::Poisoned) => println!("锁已被污染"),
}
```

## 并发控制

### 全局单线程模式

可以配置全局并发策略，强制所有 dispatch 串行执行：

```rust
use action_dispatch::set_single_thread_mode;

fn main() {
    // 启用单线程模式（调试/嵌入式系统）
    set_single_thread_mode(true);
    
    // 即使在多线程环境中，所有 dispatch 也会串行执行
    dispatch("key1", event1).unwrap();
    dispatch("key2", event2).unwrap();
}
```

### 使用场景

| 场景 | 配置 | 说明 |
|------|------|------|
| 生产环境 | `set_single_thread_mode(false)` | 默认，启用并发 |
| 调试模式 | `set_single_thread_mode(true)` | 简化并发问题排查 |
| 嵌入式系统 | `set_single_thread_mode(true)` | 单核 CPU 无需并发 |
| 性能测试 | 动态切换 | 对比单/多线程性能 |

### 查询当前模式

```rust
use action_dispatch::is_single_thread_mode;

if is_single_thread_mode() {
    println!("当前为单线程模式");
} else {
    println!("当前为多线程模式");
}
```

## 调试工具

```rust
use action_dispatch::list_actions;

// 列出所有已注册的 action
for action in list_actions() {
    println!("Action: {} (优先级: {}, sync: {})", 
             action.regex, action.priority, action.sync);
}
```

## 注意事项

1. **避免死锁**：`sync = true` 的 action 中不要再调用 `dispatch`
2. **性能考虑**：谨慎使用 `sync = true`，会阻塞所有其他操作
3. **类型一致性**：所有 action 必须使用相同的事件类型
4. **正则性能**：复杂的正则表达式可能影响匹配速度

## License

MIT OR Apache-2.0
*/

// Re-export 核心功能
pub use action_dispatch_core::{
    dispatch, 
    list_actions, 
    set_single_thread_mode, 
    is_single_thread_mode,
    ActionInfo, 
    DispatchError,
};

// Re-export 宏
pub use action_dispatch_macro::action;

// 确保下游 crate 可以使用 inventory
#[doc(hidden)]
pub use action_dispatch_core::inventory;

