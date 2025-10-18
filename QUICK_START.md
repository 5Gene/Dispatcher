# 快速开始指南

## 🚀 5 分钟上手 Action Dispatch

### 第一步：创建事件类型

```rust
#[derive(Clone)]
struct MyEvent {
    user_id: u64,
    message: String,
}
```

**注意**：事件类型必须实现 `Clone`，因为可能需要在内部传递。

### 第二步：定义 Action Handler

```rust
use action_dispatch::action;

// 普通 action - 支持并发
#[action(regex = r"user/\d+/read", priority = 5)]
fn handle_read(event: MyEvent) {
    println!("读取用户: {}", event.user_id);
}

// 关键 action - 全局排他
#[action(regex = r"user/\d+/update", priority = 10, sync = true)]
fn handle_update(event: MyEvent) {
    println!("更新用户: {}", event.user_id);
    // 这个函数执行时，所有其他 dispatch 都会被阻塞
}
```

### 第三步：分发事件

```rust
use action_dispatch::dispatch;

fn main() {
    // 分发事件
    dispatch("user/123/read", MyEvent {
        user_id: 123,
        message: "读取请求".to_string(),
    }).unwrap();
    
    dispatch("user/456/update", MyEvent {
        user_id: 456,
        message: "更新请求".to_string(),
    }).unwrap();
}
```

### 第四步：处理错误

```rust
use action_dispatch::{dispatch, DispatchError};

match dispatch("unknown/key", event) {
    Ok(()) => println!("成功"),
    Err(DispatchError::NoMatch) => println!("没有匹配的 handler"),
    Err(DispatchError::Poisoned) => println!("锁被污染"),
}
```

## 📝 常见模式

### 模式 1：按优先级路由

```rust
// 特殊用户（高优先级）
#[action(regex = r"user/admin/.*", priority = 100)]
fn handle_admin(event: MyEvent) {
    println!("管理员操作");
}

// 普通用户（低优先级）
#[action(regex = r"user/.*/.*", priority = 1)]
fn handle_normal_user(event: MyEvent) {
    println!("普通用户操作");
}

// 当 key = "user/admin/delete" 时，
// handle_admin 会被执行（优先级更高）
```

### 模式 2：关键操作保护

```rust
// 数据库迁移 - 需要全局排他
#[action(regex = r"system/migrate", priority = 1000, sync = true)]
fn handle_migration(event: MyEvent) {
    println!("开始数据库迁移（阻塞所有操作）");
    // 执行迁移...
    println!("迁移完成");
}

// 普通查询 - 可以并发
#[action(regex = r"system/query", priority = 1, sync = false)]
fn handle_query(event: MyEvent) {
    println!("执行查询");
}
```

### 模式 3：多线程并发

```rust
use std::thread;

fn main() {
    let handles: Vec<_> = (0..10).map(|i| {
        thread::spawn(move || {
            dispatch("user/123/read", MyEvent {
                user_id: i,
                message: format!("线程 {}", i),
            }).unwrap();
        })
    }).collect();

    for h in handles {
        h.join().unwrap();
    }
}
```

## ⚙️ 编译与运行

### 编译项目

```bash
# 开发模式
cargo build --all

# 发布模式（推荐）
cargo build --all --release
```

### 运行示例

```bash
# 基础示例
cargo run --example basic

# 并发示例
cargo run --example concurrent

# 简单测试
cargo run --example simple_test
```

### 运行测试

```bash
# 运行所有测试
cargo test --all

# 运行特定测试
cargo test test_basic_dispatch

# 显示输出
cargo test -- --nocapture
```

## 🔍 调试技巧

### 列出所有注册的 Action

```rust
use action_dispatch::list_actions;

fn main() {
    println!("已注册的 actions:");
    for action in list_actions() {
        println!("  regex: {}", action.regex);
        println!("  priority: {}", action.priority);
        println!("  sync: {}", action.sync);
        println!("  description: {}", action.description);
        println!();
    }
}
```

### 测试正则表达式

```rust
use regex::Regex;

fn test_regex() {
    let re = Regex::new(r"user/\d+/read").unwrap();
    
    assert!(re.is_match("user/123/read"));
    assert!(!re.is_match("user/abc/read"));
}
```

## ⚠️ 常见问题

### Q1: 为什么 dispatch 返回 NoMatch？

**答**：检查以下几点：
1. 正则表达式是否正确
2. key 是否符合预期格式
3. action 是否已注册（使用 `list_actions()` 查看）

### Q2: 如何避免死锁？

**答**：不要在 `sync = true` 的 handler 中再次调用 `dispatch`：

```rust
// ❌ 错误 - 会死锁
#[action(regex = r"task1", sync = true)]
fn bad_handler(event: MyEvent) {
    dispatch("task2", event).unwrap(); // 死锁！
}

// ✅ 正确 - 使用 sync = false
#[action(regex = r"task1", sync = false)]
fn good_handler(event: MyEvent) {
    dispatch("task2", event).unwrap(); // OK
}
```

### Q3: 多个 action 匹配同一个 key 怎么办？

**答**：优先级最高的会被执行：

```rust
#[action(regex = r"user/.*", priority = 1)]
fn low_priority(event: MyEvent) { /* 不会执行 */ }

#[action(regex = r"user/.*", priority = 10)]
fn high_priority(event: MyEvent) { /* 会执行 */ }

// dispatch("user/123", event) 会执行 high_priority
```

### Q4: 如何让所有 action 都可以处理？

**答**：当前设计只会执行优先级最高的一个。如果需要多个 handler 都执行，可以：

1. 在一个 handler 内部调用其他函数
2. 使用事件总线模式（不同的系统）
3. 修改 dispatch 逻辑（需要自行实现）

### Q5: 性能如何？

**答**：性能特点：

- ✅ 编译期注册，零运行时开销
- ✅ 正则匹配缓存，高效
- ✅ `sync = false` 时，锁竞争最小
- ⚠️ `sync = true` 时，会阻塞所有操作
- ⚠️ action 数量过多会影响匹配速度

典型性能：
- 匹配 + 分发（无锁竞争）：~1-5 μs
- 锁获取（无竞争）：~10-50 ns
- 锁竞争：~100-500 ns

## 📚 下一步

- 查看 [README.md](README.md) 了解完整文档
- 阅读 [examples/](action_dispatch/examples/) 目录下的示例
- 查看 [tests/](action_dispatch/tests/) 目录下的测试用例
- 探索源码：[action_dispatch_core/src/lib.rs](action_dispatch_core/src/lib.rs)

## 🎓 进阶主题

### 自定义错误类型

```rust
use action_dispatch::DispatchError;

#[derive(Debug)]
enum MyError {
    Dispatch(DispatchError),
    Custom(String),
}

impl From<DispatchError> for MyError {
    fn from(e: DispatchError) -> Self {
        MyError::Dispatch(e)
    }
}

fn my_dispatch(key: &str, event: MyEvent) -> Result<(), MyError> {
    dispatch(key, event)?;
    Ok(())
}
```

### 性能监控

```rust
use std::time::Instant;

#[action(regex = r"monitored/.*", priority = 5)]
fn monitored_handler(event: MyEvent) {
    let start = Instant::now();
    
    // 执行业务逻辑...
    
    let elapsed = start.elapsed();
    println!("Handler 执行时间: {:?}", elapsed);
}
```

### 条件编译

```rust
// 开发环境：详细日志
#[cfg(debug_assertions)]
#[action(regex = r"debug/.*", priority = 100)]
fn debug_handler(event: MyEvent) {
    println!("[DEBUG] {:?}", event);
}

// 生产环境：简化处理
#[cfg(not(debug_assertions))]
#[action(regex = r"debug/.*", priority = 100)]
fn production_handler(_event: MyEvent) {
    // 不做任何事
}
```

---

**祝您使用愉快！🦀**

