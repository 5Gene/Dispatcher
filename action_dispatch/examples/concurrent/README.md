# 🔥 多文件多模块并发测试示例

这个示例展示了 `action_dispatch` 在复杂项目结构下的使用方式和并发行为。

## 📂 目录结构

```
concurrent/
├── main.rs                   # 入口文件，启动并发测试
├── user_actions.rs           # 用户模块 action (sync=false)
├── order_actions.rs          # 订单模块 action (sync=false)
├── admin_actions.rs          # 管理模块 action (包含 sync=true)
├── product_actions.rs        # 产品模块 action (sync=false)
├── api/
│   ├── mod.rs               # API 子模块
│   ├── v1.rs                # API v1 handlers (sync=false)
│   └── v2.rs                # API v2 handlers (sync=false)
└── README.md                # 本文档
```

## ✨ 功能特性

### 1. **多文件 Action 注册** ✅

- ✅ 不同业务模块的 action 定义在不同文件中
- ✅ 使用 `inventory` crate 在编译时自动收集
- ✅ 无需手动注册，自动生效

### 2. **不同包名/子模块** ✅

- ✅ `api::v1` 模块下的 action
- ✅ `api::v2` 模块下的 action
- ✅ 证明 action 可以定义在任意模块中

### 3. **同步与异步混合** ✅

- ✅ `admin/critical` - **sync=true**（独占执行）
- ✅ 其他所有 action - **sync=false**（并发执行）
- ✅ 观察同步 action 的阻塞行为

### 4. **随机阻塞时间** ✅

- ✅ 每个 action 随机阻塞 **1-10 秒**
- ✅ 模拟真实的耗时操作（数据库查询、API 调用等）
- ✅ 验证并发执行的正确性

### 5. **多线程并发调用** ✅

- ✅ 8 个线程同时调用 `dispatch`
- ✅ 测试不同 key 的匹配
- ✅ 验证线程安全性

## 🚀 运行方式

### 1. 编译并运行

```bash
cd action_dispatch
cargo run --release --example concurrent
```

### 2. 仅编译检查

```bash
cargo check --example concurrent
```

### 3. 查看详细输出

```bash
cargo run --release --example concurrent 2>&1 | tee concurrent_output.log
```

## 📊 预期输出示例

```
🚀 多文件多模块并发测试
═══════════════════════════════════════════════════════

📊 已注册 action 列表
─────────────────────────────────────────────────────

  📦 模块: user_actions
     🔓 async ^user/\d+/profile$ - user_profile_handler
     🔓 async ^user/\d+/settings$ - user_settings_handler
     🔓 async ^user/\d+/orders$ - user_orders_handler

  📦 模块: order_actions
     🔓 async ^order/[A-Z0-9]+$ - order_detail_handler
     🔓 async ^order/[A-Z0-9]+/status$ - order_status_handler
     🔓 async ^order/[A-Z0-9]+/payment$ - order_payment_handler

  📦 模块: admin_actions
     🔒 sync ^admin/critical$ - admin_critical_handler
     🔓 async ^admin/reports$ - admin_reports_handler
     🔓 async ^admin/users/.*$ - admin_users_handler

  📦 模块: api::v1
     🔓 async ^api/v1/users$ - api_v1_users_handler
     🔓 async ^api/v1/products$ - api_v1_products_handler

  📦 模块: api::v2
     🔓 async ^api/v2/users$ - api_v2_users_handler
     🔓 async ^api/v2/products/\d+$ - api_v2_product_detail_handler
     🔓 async ^api/v2/search/.*$ - api_v2_search_handler

═══════════════════════════════════════════════════════

🔥 开始并发测试（所有 dispatch 同时启动）
─────────────────────────────────────────────────────

[Worker-0] 🚀 dispatch('user/123/profile') 开始...
[Worker-1] 🚀 dispatch('user/456/settings') 开始...
[Worker-2] 🚀 dispatch('order/ORD001') 开始...
[Worker-3] 🚀 dispatch('order/ORD002/status') 开始...
[Worker-4] 🚀 dispatch('admin/critical') 开始...
[Worker-5] 🚀 dispatch('api/v1/users') 开始...
[Worker-6] 🚀 dispatch('api/v2/users') 开始...
[Worker-7] 🚀 dispatch('product/789') 开始...

  [Worker-0] 👤 [user_profile] 处理用户 user_0 的资料查询（阻塞 3s）
  [Worker-1] ⚙️  [user_settings] 修改用户 user_1 的设置（阻塞 7s）
  [Worker-2] 🛒 [order_detail] 查询订单详情 ID=2（阻塞 5s）
  [Worker-3] 📝 [order_status] 更新订单状态 ID=3（阻塞 2s）
  
  ╔═══════════════════════════════════════════════════
  ║ [Worker-4] 🔒 [admin_critical] 开始执行（SYNC 模式）
  ║ ⚠️  阻塞所有其他 dispatch，独占执行 8s
  ╚═══════════════════════════════════════════════════

  [Worker-5] 🔌 [api::v1::users] API v1 查询用户列表（阻塞 4s）
  [Worker-6] 🔌 [api::v2::users] API v2 查询用户列表（阻塞 6s）
  [Worker-7] 📱 [product_detail] 查询产品详情 ID=7（阻塞 9s）

  [Worker-3] ✅ [order_status] 订单状态更新完成
[Worker-3] ✅ dispatch('order/ORD002/status') 完成，耗时 2s

  [Worker-0] ✅ [user_profile] 用户资料查询完成
[Worker-0] ✅ dispatch('user/123/profile') 完成，耗时 3s

... (更多输出)

  ╔═══════════════════════════════════════════════════
  ║ [Worker-4] ✅ [admin_critical] 完成（释放锁）
  ╚═══════════════════════════════════════════════════

[Worker-4] ✅ dispatch('admin/critical') 完成，耗时 8s

═══════════════════════════════════════════════════════
📈 测试结果统计
═══════════════════════════════════════════════════════

总耗时: 10.234s

💡 观察要点
═══════════════════════════════════════════════════════

1. 🔒 同步 action (admin/critical) 会阻塞其他所有 dispatch
   - 如果它先执行，其他所有请求都要等待
   - 如果它后执行，它要等其他 sync=false 的执行完

2. 🔓 异步 action 可以并发执行
   - user, order, api 等 action 可以同时运行
   - 每个 action 随机阻塞 1-10s，但不影响其他异步 action

3. ✅ 所有 action 都能正确注册和执行
   - 不同文件、不同模块的 action 都被 inventory 收集
   - dispatch 能正确找到并执行对应的 handler

🎉 测试完成！
```

## 🔍 关键观察点

### 1. **Action 自动注册** ✅

不同文件、不同模块的 action 都能自动注册：

```rust
// user_actions.rs
#[action(regex = r"^user/\d+/profile$")]
fn user_profile_handler(event: Event) { }

// api/v1.rs
#[action(regex = r"^api/v1/users$")]
fn api_v1_users_handler(event: Event) { }
```

**无需手动调用注册函数！** `inventory` crate 在编译时自动收集。

---

### 2. **同步 Action 的行为** 🔒

```rust
// admin_actions.rs
#[action(regex = r"^admin/critical$", sync = true)]
fn admin_critical_handler(event: Event) {
    // 这个 action 会独占执行
    // 阻塞所有其他 dispatch 调用
}
```

**效果**：
- ✅ 执行时获取写锁（独占）
- ✅ 其他线程的 dispatch 必须等待
- ✅ 保证关键操作的原子性

---

### 3. **异步 Action 的行为** 🔓

```rust
// user_actions.rs
#[action(regex = r"^user/\d+/profile$", sync = false)]
fn user_profile_handler(event: Event) {
    // 这个 action 可以并发执行
}

// order_actions.rs
#[action(regex = r"^order/.*$", sync = false)]
fn order_handler(event: Event) {
    // 与 user_profile_handler 可以同时执行
}
```

**效果**：
- ✅ 执行时只获取读锁（共享）
- ✅ 多个 sync=false 的 action 可以并发
- ✅ 高性能

---

### 4. **不同模块的 Action** 📦

```rust
// 主模块
mod user_actions;    // user/...
mod order_actions;   // order/...

// 子模块
mod api {
    pub mod v1;      // api/v1/...
    pub mod v2;      // api/v2/...
}
```

**证明**：action 可以定义在**任意位置**，只要：
1. 使用 `#[action(...)]` 宏
2. 模块被引入（`mod xxx;`）

---

## 🎯 测试场景

### 场景 1：异步 Action 并发执行

```
时间轴：
t=0s   | Worker-0: user/123/profile (3s)
       | Worker-1: order/ORD001 (5s)      } 并发执行
       | Worker-2: api/v1/users (4s)      }
       
t=3s   | Worker-0 完成
t=4s   | Worker-2 完成
t=5s   | Worker-1 完成

总耗时: ~5s (而不是 3+5+4=12s)
```

---

### 场景 2：同步 Action 阻塞

```
时间轴：
t=0s   | Worker-0: user/123 (async, 3s) 开始
       | Worker-1: admin/critical (sync, 8s) 等待读锁释放
       
t=3s   | Worker-0 完成，释放读锁
       | Worker-1 获取写锁，开始执行 (独占)
       
t=3s   | Worker-2: order/ORD001 (async) ⏳ 被阻塞
       
t=11s  | Worker-1 完成，释放写锁
       | Worker-2 获取读锁，开始执行
       
t=16s  | Worker-2 完成

总耗时: ~16s (串行化)
```

---

### 场景 3：混合场景

```
多个异步 action + 1 个同步 action：

异步 action 们可以并发，但遇到同步 action 时：
1. 正在执行的异步 action 会先完成
2. 同步 action 独占执行
3. 之后的异步 action 继续并发
```

---

## 📚 代码结构说明

### 入口文件 (`main.rs`)

```rust
// 导入各个模块
mod user_actions;
mod order_actions;
mod admin_actions;
mod api;

fn main() {
    // 列出所有已注册的 action
    let actions = list_actions();
    
    // 并发调用 dispatch
    let handles: Vec<_> = test_cases
        .into_iter()
        .map(|(key, name)| {
            thread::spawn(move || {
                dispatch(key, event).unwrap();
            })
        })
        .collect();
    
    // 等待所有线程完成
    for handle in handles {
        handle.join().unwrap();
    }
}
```

### Action 文件 (`user_actions.rs` 等)

```rust
use action_dispatch::action;
use super::Event;  // 使用共享的 Event 类型

#[action(regex = r"^user/\d+/profile$", sync = false)]
fn user_profile_handler(event: Event) {
    // 随机阻塞 1-10s
    let block_time = rand::thread_rng().gen_range(1..=10);
    thread::sleep(Duration::from_secs(block_time));
}
```

### 子模块 (`api/v1.rs`)

```rust
use action_dispatch::action;
use crate::Event;  // 注意使用 crate::

#[action(regex = r"^api/v1/users$", sync = false)]
fn api_v1_users_handler(event: Event) {
    // ...
}
```

---

## 🧪 如何修改测试

### 1. 添加更多 Action

在任意文件中添加：

```rust
#[action(regex = r"^your/pattern$", sync = false)]
fn your_handler(event: Event) {
    println!("Your action executed!");
}
```

### 2. 修改阻塞时间

修改 `rand::thread_rng().gen_range(1..=10)` 的范围。

### 3. 添加更多测试 Key

在 `main.rs` 的 `test_cases` 中添加：

```rust
let test_cases = vec![
    // ... 现有的
    ("your/test/key", "Your Test"),
];
```

### 4. 测试更多同步 Action

将 `sync = false` 改为 `sync = true`：

```rust
#[action(regex = r"^critical/.*$", sync = true)]
fn critical_handler(event: Event) { }
```

---

## ✅ 验证清单

运行示例后，应该能观察到：

- [x] 所有 action 都被正确注册（从不同文件、不同模块）
- [x] `list_actions()` 能列出所有 action
- [x] 异步 action 可以并发执行（总时间 < 单个时间之和）
- [x] 同步 action 会阻塞其他 dispatch
- [x] 每个 action 都被正确匹配和执行
- [x] 多线程安全，无数据竞争

---

## 🎓 学习要点

### 1. **inventory crate 的作用**

```rust
// 编译时自动收集所有带 #[action] 的函数
// 无需手动注册！

// 在不同文件中定义
#[action(...)]
fn handler1() { }

#[action(...)]
fn handler2() { }

// 自动可用
dispatch("key", event);  // 自动找到匹配的 handler
```

---

### 2. **模块系统与 Action**

```rust
// main.rs
mod user_actions;  // ✅ 必须导入，才能注册
// mod hidden;     // ❌ 不导入，不会注册

// 子模块也可以
mod api {
    pub mod v1;    // ✅ 会注册
    mod v2;        // ✅ 也会注册（pub 不影响 action 注册）
}
```

---

### 3. **sync 标志的重要性**

```rust
sync = false  // 默认，推荐
  → 高性能，可并发
  → 适合读操作、独立操作

sync = true   // 谨慎使用
  → 独占执行，低并发
  → 适合写全局状态、关键操作
```

---

## 🚀 下一步

1. **运行示例**，观察输出
2. **修改代码**，添加自己的 action
3. **调整参数**，测试不同的并发场景
4. **查看文档**：
   - `AHO_CORASICK_EXPLAINED.md` - Aho-Corasick 优化详解
   - `DISPATCH_EXPLAINED.md` - 多线程机制详解
   - `PERFORMANCE.md` - 性能分析

---

**Happy Coding!** 🎉

