# 🔥 并发测试示例使用指南

## 📂 示例位置

```
action_dispatch/action_dispatch/examples/concurrent/
```

## 🎯 示例目的

展示 `action_dispatch` 在复杂项目结构下的能力：

1. ✅ **多文件定义** - action 在不同文件中定义
2. ✅ **多模块支持** - 包括子模块（`api::v1`, `api::v2`）
3. ✅ **混合同步/异步** - 包含 `sync=true` 和 `sync=false` 的 action
4. ✅ **并发执行测试** - 多线程同时调用 dispatch
5. ✅ **随机阻塞** - 每个 action 随机阻塞 1-10 秒，模拟真实场景

---

## 🚀 快速开始

### 1. 运行示例

```bash
cd action_dispatch
cargo run --release --example concurrent
```

### 2. 查看源码

```bash
# 查看完整目录结构
tree action_dispatch/examples/concurrent/

# 或在 Windows 中
dir /s action_dispatch\examples\concurrent\
```

---

## 📊 文件结构

```
concurrent/
├── main.rs                   # 🚪 入口文件
│   ├── 导入所有模块
│   ├── 启动并发测试
│   └── 显示执行结果
│
├── user_actions.rs           # 👤 用户模块 (sync=false)
│   ├── user/xxx/profile
│   ├── user/xxx/settings
│   └── user/xxx/orders
│
├── order_actions.rs          # 🛒 订单模块 (sync=false)
│   ├── order/XXX
│   ├── order/XXX/status
│   └── order/XXX/payment
│
├── admin_actions.rs          # 🔒 管理模块 (包含 sync=true)
│   ├── admin/critical        ← 🔒 SYNC (阻塞其他所有 dispatch)
│   ├── admin/reports
│   └── admin/users/...
│
├── product_actions.rs        # 📱 产品模块 (sync=false)
│   ├── product/xxx
│   └── product/xxx/reviews
│
├── api/                      # 🔌 API 子模块
│   ├── mod.rs
│   ├── v1.rs                 # api/v1/...
│   └── v2.rs                 # api/v2/...
│
└── README.md                 # 📖 详细文档
```

---

## 🔑 关键特性展示

### 1. **多文件自动注册**

```rust
// user_actions.rs
#[action(regex = r"^user/\d+/profile$")]
fn user_profile(event: Event) { }

// order_actions.rs
#[action(regex = r"^order/.*$")]
fn order_handler(event: Event) { }

// main.rs
mod user_actions;   // ← 只需导入模块
mod order_actions;  // ← action 自动注册！

fn main() {
    // 无需手动注册，直接使用
    dispatch("user/123/profile", event).unwrap();
    dispatch("order/ORD001", event).unwrap();
}
```

**原理**：`inventory` crate 在编译时自动收集所有 `#[action]` 标记的函数。

---

### 2. **子模块支持**

```rust
// api/v1.rs
use action_dispatch::action;
use crate::Event;  // 注意使用 crate::

#[action(regex = r"^api/v1/users$")]
fn api_v1_users(event: Event) { }

// main.rs
mod api;  // ← api 是一个子模块

fn main() {
    dispatch("api/v1/users", event).unwrap();  // ✅ 可以工作
}
```

**证明**：action 可以定义在**任意深度**的模块中！

---

### 3. **同步 Action (sync=true)**

```rust
// admin_actions.rs
#[action(regex = r"^admin/critical$", sync = true)]
//                                     ^^^^^^^^^^^^^ 独占执行
fn admin_critical(event: Event) {
    println!("🔒 独占执行，阻塞所有其他 dispatch");
    thread::sleep(Duration::from_secs(5));
}
```

**效果**：
- 执行时获取**写锁**（独占）
- 其他所有 dispatch 必须等待
- 适合关键操作（修改全局状态等）

---

### 4. **异步 Action (sync=false)**

```rust
// user_actions.rs
#[action(regex = r"^user/.*$", sync = false)]
//                               ^^^^^^^^^^^^^ 可并发
fn user_handler(event: Event) {
    println!("🔓 可以并发执行");
}

// order_actions.rs
#[action(regex = r"^order/.*$", sync = false)]
fn order_handler(event: Event) {
    println!("🔓 与 user_handler 可以同时执行");
}
```

**效果**：
- 执行时只获取**读锁**（共享）
- 多个 `sync=false` 的 action 可以**并发执行**
- 高性能

---

### 5. **并发测试**

```rust
// main.rs
fn main() {
    let test_cases = vec![
        "user/123/profile",
        "order/ORD001",
        "admin/critical",  // ← sync=true，会阻塞
        "api/v1/users",
    ];
    
    // 同时启动 4 个线程
    let handles: Vec<_> = test_cases
        .into_iter()
        .map(|key| {
            thread::spawn(move || {
                dispatch(key, event).unwrap();
            })
        })
        .collect();
    
    for h in handles {
        h.join().unwrap();
    }
}
```

---

## 📈 预期输出

```
🚀 多文件多模块并发测试
═══════════════════════════════════════════════════════

📊 已注册 action 列表
─────────────────────────────────────────────────────

  📦 模块: user_actions
     🔓 async ^user/\d+/profile$
     🔓 async ^user/\d+/settings$
     ...

  📦 模块: admin_actions
     🔒 sync ^admin/critical$          ← 注意这里是 sync
     🔓 async ^admin/reports$
     ...

═══════════════════════════════════════════════════════

🔥 开始并发测试
─────────────────────────────────────────────────────

[Worker-0] 🚀 dispatch('user/123/profile') 开始...
[Worker-1] 🚀 dispatch('order/ORD001') 开始...
[Worker-2] 🚀 dispatch('admin/critical') 开始...

  [Worker-0] 👤 [user_profile] 处理用户查询（阻塞 3s）
  [Worker-1] 🛒 [order_detail] 查询订单详情（阻塞 5s）
  
  ╔═══════════════════════════════════════════════════
  ║ [Worker-2] 🔒 [admin_critical] 开始执行（SYNC 模式）
  ║ ⚠️  阻塞所有其他 dispatch，独占执行 8s
  ╚═══════════════════════════════════════════════════

... (Worker-0 和 Worker-1 可以并发)

  ╔═══════════════════════════════════════════════════
  ║ [Worker-2] ✅ [admin_critical] 完成（释放锁）
  ╚═══════════════════════════════════════════════════

[Worker-0] ✅ dispatch 完成
[Worker-1] ✅ dispatch 完成
[Worker-2] ✅ dispatch 完成

═══════════════════════════════════════════════════════
📈 测试结果统计
═══════════════════════════════════════════════════════

总耗时: 10.234s

💡 观察要点
═══════════════════════════════════════════════════════

1. 🔒 同步 action 会阻塞其他所有 dispatch
2. 🔓 异步 action 可以并发执行
3. ✅ 所有 action 都能正确注册和执行
```

---

## 🔍 核心观察点

### 1. Action 自动注册 ✅

运行 `list_actions()` 可以看到：
- ✅ `user_actions.rs` 中的 action
- ✅ `order_actions.rs` 中的 action
- ✅ `admin_actions.rs` 中的 action
- ✅ `api/v1.rs` 中的 action
- ✅ `api/v2.rs` 中的 action

**全部自动注册，无需手动调用！**

---

### 2. 同步 Action 的阻塞行为 🔒

当 `admin/critical` (sync=true) 执行时：
- ⏸️  其他所有 dispatch 都被阻塞
- 🔒 独占执行
- ⏱️  总时间 = 所有任务串行执行的时间

---

### 3. 异步 Action 的并发行为 🔓

多个 `sync=false` 的 action：
- ✅ 可以同时执行
- ⚡ 总时间 ≈ 最长任务的时间
- 🚀 高性能

---

## 🧪 如何修改测试

### 添加新的 Action

创建新文件 `notification_actions.rs`：

```rust
use action_dispatch::action;
use super::Event;
use std::thread;
use std::time::Duration;

#[action(regex = r"^notification/\d+$", sync = false)]
fn notification_handler(event: Event) {
    println!("📬 处理通知");
    thread::sleep(Duration::from_secs(2));
}
```

在 `main.rs` 中导入：

```rust
mod notification_actions;  // ← 添加这行
```

在测试用例中添加：

```rust
let test_cases = vec![
    // ... 现有的
    ("notification/123", "Notification"),  // ← 添加这行
];
```

运行即可看到新 action！

---

### 测试更多同步 Action

将某个 action 改为 `sync = true`：

```rust
#[action(regex = r"^order/.*$", sync = true)]
//                               ^^^^^^^^^^^^ 改为 true
fn order_handler(event: Event) { }
```

观察：现在 `order` 相关的 dispatch 也会独占执行！

---

### 修改阻塞时间

```rust
// 当前：随机 1-10 秒
let block_time = rand::thread_rng().gen_range(1..=10);

// 改为：随机 1-3 秒（更快）
let block_time = rand::thread_rng().gen_range(1..=3);

// 改为：固定 5 秒（便于观察）
let block_time = 5;
```

---

## ✅ 验证清单

运行示例后，你应该能看到：

- [x] 所有 action 都被列出（来自不同文件、不同模块）
- [x] `admin/critical` 标记为 `🔒 sync`
- [x] 其他 action 标记为 `🔓 async`
- [x] 多个线程同时启动
- [x] 异步 action 可以并发执行
- [x] 同步 action 会阻塞其他 dispatch
- [x] 所有 dispatch 最终都成功完成

---

## 📚 相关文档

- **详细说明**：`examples/concurrent/README.md`
- **多线程机制**：`DISPATCH_EXPLAINED.md`
- **性能分析**：`PERFORMANCE.md`
- **Aho-Corasick 优化**：`AHO_CORASICK_EXPLAINED.md`

---

## 🎓 学习要点

### 1. inventory 自动收集

```rust
#[action(...)]  // ← 只要有这个宏
fn handler() { }

// 编译时自动收集，运行时可用
dispatch("key", event);  // ✅ 自动找到
```

### 2. 模块系统

```rust
mod module_a;        // ✅ 导入后，里面的 action 自动注册
// mod module_b;     // ❌ 不导入，action 不会注册
```

### 3. sync 标志

```rust
sync = false  // 默认，高性能，可并发
sync = true   // 独占执行，用于关键操作
```

---

## 🎯 下一步

1. **运行示例**：`cargo run --release --example concurrent`
2. **修改代码**：添加自己的 action
3. **调整参数**：测试不同的并发场景
4. **理解原理**：阅读相关文档

---

**Happy Coding!** 🎉🚀

