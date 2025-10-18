# Action Dispatch

> 一个通用的、高性能的、基于属性宏的 Action 注册与分发系统

[![Rust](https://img.shields.io/badge/rust-1.70%2B-orange.svg)](https://www.rust-lang.org/)
[![License](https://img.shields.io/badge/license-MIT%2FApache--2.0-blue.svg)](LICENSE)

## ✨ 特性

- 🎯 **声明式注册**：使用 `#[action(...)]` 属性宏标记处理函数，自动注册
- 🔍 **正则匹配**：支持正则表达式匹配 key，灵活强大
- 📊 **优先级控制**：支持设置 action 优先级，高优先级优先匹配
- 🔒 **全局同步模式**：支持全局排他执行，阻塞所有其他 dispatch（可选）
- 🛡️ **类型安全**：编译期类型检查，无需序列化/反序列化
- 🚀 **高性能**：编译期注册，运行时零开销抽象
- 🔧 **线程安全**：完全线程安全，支持多线程并发调用
- 📝 **易于调试**：提供调试接口，查询所有已注册 action

## 🎯 核心概念

### 全局同步锁（Global Sync Lock）

系统维护一个全局互斥锁，所有 `dispatch` 调用都会竞争此锁：

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| `sync = false` (默认) | 拿锁 → 匹配 → **释放锁** → 执行 | 普通操作，支持并发 |
| `sync = true` | 拿锁 → 匹配 → **持有锁** → 执行 → 释放锁 | 关键操作，需要全局排他 |

**设计思想**：

- 所有 dispatch 请求入口串行化（竞争同一把锁）
- `sync = false` 的 action 快速释放锁 → 允许并发
- `sync = true` 的 action 持有锁直到完成 → 阻塞所有其他操作

## 🚀 快速开始

### 安装

将以下内容添加到 `Cargo.toml`：

```toml
[dependencies]
action_dispatch = { path = "./action_dispatch" }
```

### 基础示例

```rust
use action_dispatch::{action, dispatch};

#[derive(Clone)]
struct MyEvent {
    user_id: u64,
    action: String,
}

// 普通 action，支持并发执行
#[action(regex = r"user/\d+/read", priority = 5, sync = false)]
fn handle_read(event: MyEvent) {
    println!("读取用户: {}", event.user_id);
}

// 关键 action，全局同步执行
#[action(regex = r"user/\d+/update", priority = 10, sync = true)]
fn handle_update(event: MyEvent) {
    println!("更新用户: {}（阻塞所有其他操作）", event.user_id);
    std::thread::sleep(std::time::Duration::from_secs(2));
}

fn main() {
    // 分发事件
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

## 📚 详细文档

### `#[action(...)]` 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `regex` | `&str` | ✅ | - | 匹配 key 的正则表达式 |
| `priority` | `i32` | ❌ | `0` | 优先级，数值越大优先级越高 |
| `description` | `&str` | ❌ | `""` | 描述信息，用于调试和文档 |
| `sync` | `bool` | ❌ | `false` | 是否启用全局同步执行模式 |

### 函数签名要求

被 `#[action]` 标记的函数必须满足：

1. **必须是自由函数**（不在 impl 块中）
2. **恰好一个参数**：`fn(T)` 或 `fn(&T)`
3. **所有 action 使用相同的事件类型 `T`**
4. **返回值不限**（可以是任意类型或 `()`）

### 分发函数

```rust
pub fn dispatch<T>(key: &str, event: T) -> Result<(), DispatchError>
where
    T: 'static + Send + Sync
```

**执行流程**：

1. 获取全局锁（阻塞直到成功）
2. 在锁保护下遍历所有 action，找到第一个匹配且优先级最高的
3. 若无匹配，释放锁并返回 `Err(DispatchError::NoMatch)`
4. 若匹配成功：
   - `sync = false`: 立即释放锁 → 执行函数（支持并发）
   - `sync = true`: 保持持有锁 → 执行函数 → 完成后释放（全局排他）

### 错误处理

```rust
use action_dispatch::{dispatch, DispatchError};

match dispatch("some/key", event) {
    Ok(()) => println!("分发成功"),
    Err(DispatchError::NoMatch) => println!("没有匹配的 action"),
    Err(DispatchError::Poisoned) => println!("锁已被污染"),
}
```

### 调试工具

```rust
use action_dispatch::list_actions;

// 列出所有已注册的 action
for action in list_actions() {
    println!(
        "regex: {}, priority: {}, sync: {}, description: {}",
        action.regex, action.priority, action.sync, action.description
    );
}
```

## 🎭 示例

### 运行基础示例

```bash
cd action_dispatch
cargo run --example basic
```

### 运行并发示例

```bash
cargo run --example concurrent
```

并发示例展示了：

1. **场景 1**：多个 `sync = false` 的 action 并发执行
2. **场景 2**：`sync = true` 的 action 阻塞后续操作
3. **场景 3**：关键操作（`sync = true`）阻塞所有其他 dispatch

## ⚡ 性能特点

- **编译期注册**：使用 `inventory` crate 在编译期收集所有 handler
- **零动态分配**：action 列表在程序启动时初始化，之后只读
- **高效匹配**：使用预编译的正则表达式，支持内部缓存
- **最小锁竞争**：`sync = false` 的 action 快速释放锁，减少竞争
- **类型擦除**：使用原始指针实现零成本类型擦除

### 性能基准（参考）

| 操作 | 耗时 | 说明 |
|------|------|------|
| 匹配 + 分发（sync=false） | ~1-5 μs | 正则匹配 + 函数调用 |
| 获取全局锁 | ~10-50 ns | 无竞争情况下 |
| 全局锁竞争 | ~100-500 ns | 有竞争但快速释放 |

> ⚠️ 实际性能取决于：正则表达式复杂度、action 数量、锁竞争程度

## 🔧 高级用法

### 多个正则匹配同一 key

当多个 action 的正则表达式都匹配同一个 key 时，**优先级最高的 action 会被执行**：

```rust
#[action(regex = r"user/.*", priority = 1)]
fn handle_user_general(event: MyEvent) {
    // 通用处理
}

#[action(regex = r"user/admin/.*", priority = 10)]
fn handle_user_admin(event: MyEvent) {
    // 管理员处理（优先级更高，会被优先匹配）
}
```

### 复杂正则表达式

```rust
#[action(regex = r"^api/v[12]/users/\d+/(profile|settings)$", priority = 5)]
fn handle_api_request(event: MyEvent) {
    // 匹配: api/v1/users/123/profile
    // 匹配: api/v2/users/456/settings
    // 不匹配: api/v3/users/789/profile
}
```

### 与异步运行时集成

虽然当前版本使用 `std::sync::Mutex`，但可以轻松扩展为异步版本：

```rust
// 未来版本可能支持
#[action_async(regex = r"async/task", sync = true)]
async fn handle_async(event: MyEvent) {
    tokio::time::sleep(Duration::from_secs(1)).await;
}
```

## ⚠️ 注意事项

### 避免死锁

**不要在 `sync = true` 的 action 中再次调用 `dispatch`**：

```rust
#[action(regex = r"task/.*", sync = true)]
fn bad_handler(event: MyEvent) {
    // ❌ 错误：会导致死锁！
    dispatch("another/task", event).unwrap();
}
```

**解决方案**：

1. 使用 `sync = false`（如果不需要全局排他）
2. 重构逻辑，避免嵌套调用
3. 使用异步版本（未来支持）

### 性能考虑

1. **谨慎使用 `sync = true`**：会阻塞所有其他 dispatch，影响吞吐量
2. **正则表达式优化**：复杂的正则会影响匹配速度，尽量简化
3. **减少 action 数量**：action 越多，匹配遍历越慢
4. **避免长时间执行**：handler 应该快速完成，或使用异步

### 类型一致性

所有 action 必须使用相同的事件类型：

```rust
// ❌ 错误：不同的事件类型
#[action(regex = r"type1/.*")]
fn handler1(event: EventA) { }

#[action(regex = r"type2/.*")]
fn handler2(event: EventB) { } // 编译错误！
```

**解决方案**：使用 enum 或 trait object 统一类型。

## 🧪 测试

运行所有测试：

```bash
cd action_dispatch
cargo test --all
```

测试覆盖：

- ✅ 基础分发功能
- ✅ 优先级匹配
- ✅ 并发安全性
- ✅ 全局同步锁行为
- ✅ 错误处理
- ✅ 正则表达式匹配

## 📂 项目结构

```
action_dispatch/
├── Cargo.toml                    # Workspace 配置
├── README.md                     # 本文档
├── action_dispatch/              # 主 crate
│   ├── Cargo.toml
│   ├── src/
│   │   └── lib.rs               # Re-export 所有功能
│   ├── examples/
│   │   ├── basic.rs             # 基础示例
│   │   └── concurrent.rs        # 并发示例
│   └── tests/
│       └── integration_test.rs  # 集成测试
├── action_dispatch_core/         # 核心运行时
│   ├── Cargo.toml
│   └── src/
│       └── lib.rs               # 注册表、锁、dispatch 函数
└── action_dispatch_macro/        # 属性宏
    ├── Cargo.toml
    └── src/
        └── lib.rs               # #[action] 宏实现
```

## 🛠️ 开发

### 构建项目

```bash
cargo build --all
```

### 运行示例

```bash
cargo run --example basic
cargo run --example concurrent
```

### 格式化代码

```bash
cargo fmt --all
```

### Lint 检查

```bash
cargo clippy --all -- -D warnings
```

## 📖 设计文档

### 架构概览

```
┌─────────────────────────────────────────────────┐
│                   用户代码                        │
│  #[action(...)] fn handler(event: T) { }       │
└─────────────────┬───────────────────────────────┘
                  │ (编译期)
                  ▼
┌─────────────────────────────────────────────────┐
│            action_dispatch_macro                │
│  解析注解 → 生成 inventory::submit! 代码         │
└─────────────────┬───────────────────────────────┘
                  │ (链接期)
                  ▼
┌─────────────────────────────────────────────────┐
│            action_dispatch_core                 │
│  ┌─────────────────────────────────────┐       │
│  │  全局注册表 (ACTION_REGISTRY)        │       │
│  │  - Vec<&'static ActionHandler>      │       │
│  │  - 按优先级排序                      │       │
│  └─────────────────────────────────────┘       │
│  ┌─────────────────────────────────────┐       │
│  │  全局分发锁 (GLOBAL_DISPATCH_LOCK)   │       │
│  │  - Mutex<()>                        │       │
│  └─────────────────────────────────────┘       │
└─────────────────┬───────────────────────────────┘
                  │ (运行时)
                  ▼
┌─────────────────────────────────────────────────┐
│         dispatch(key, event)                    │
│  1. 获取全局锁                                   │
│  2. 匹配 key（正则 + 优先级）                    │
│  3. 决定是否释放锁（根据 sync）                  │
│  4. 执行 handler                                │
│  5. 返回结果                                     │
└─────────────────────────────────────────────────┘
```

### 类型擦除技术

为了支持不同的函数签名统一注册，我们使用了类型擦除：

```rust
// 用户函数: fn(MyEvent)
// 擦除为: fn(*const ())
// 执行时: 通过原始指针还原类型
```

这是一个 **零成本抽象**，不涉及动态分配或虚函数表。

## 📜 许可证

本项目采用双许可证：

- MIT License ([LICENSE-MIT](LICENSE-MIT))
- Apache License 2.0 ([LICENSE-APACHE](LICENSE-APACHE))

您可以选择其中任意一种许可证使用本项目。

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md)（待添加）。

## 📮 联系

- Issues: [GitHub Issues](https://github.com/example/action_dispatch/issues)
- Discussions: [GitHub Discussions](https://github.com/example/action_dispatch/discussions)

## 🙏 致谢

本项目使用了以下优秀的开源库：

- [inventory](https://github.com/dtolnay/inventory) - 编译期收集
- [regex](https://github.com/rust-lang/regex) - 正则表达式
- [once_cell](https://github.com/matklad/once_cell) - 全局静态变量
- [syn](https://github.com/dtolnay/syn) - Rust 语法解析
- [quote](https://github.com/dtolnay/quote) - 过程宏代码生成

---

**Happy coding! 🦀**

