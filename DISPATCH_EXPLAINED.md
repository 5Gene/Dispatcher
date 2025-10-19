# 🧵 dispatch 多线程机制详解

## 📖 目录

- [核心概念](#核心概念)
- [多线程场景演示](#多线程场景演示)
- [代码逐步分析](#代码逐步分析)
- [两种执行模式](#两种执行模式)
- [RwLock 工作原理](#rwlock-工作原理)
- [为什么这么设计](#为什么这么设计)
- [实际应用示例](#实际应用示例)
- [常见问题](#常见问题)

---

## 核心概念

### dispatch 不创建线程！

**重要**：`dispatch` 函数本身**不会创建任何线程**。它的作用是：

1. ✅ **提供线程安全的接口**：使用 `RwLock` 保护共享数据
2. ✅ **允许并发调用**：多个线程可以同时调用 `dispatch`
3. ✅ **智能并发控制**：根据 `sync` 标志决定并发还是独占

### 核心机制：RwLock（读写锁）

```rust
// action_dispatch_core/src/lib.rs:47
static GLOBAL_DISPATCH_LOCK: Lazy<RwLock<()>> = Lazy::new(|| RwLock::new(()));
```

**RwLock 特性**：

| 锁类型 | 并发性 | 使用场景 |
|-------|-------|---------|
| **读锁（Read Lock）** | 多个线程可同时持有 | `sync = false` 的 action |
| **写锁（Write Lock）** | 只有一个线程可持有 | `sync = true` 的 action |

---

## 多线程场景演示

### 场景 1：多个线程并发调用 dispatch

```rust
use std::thread;
use std::time::Duration;
use action_dispatch::{action, dispatch};

#[derive(Clone)]
struct Event { id: u64 }

#[action(regex = r"^task/.*", sync = false)]  // sync = false (默认)
fn handle_task(event: Event) {
    println!("[线程 {:?}] 开始处理任务 {}", thread::current().id(), event.id);
    thread::sleep(Duration::from_millis(100));  // 模拟耗时操作
    println!("[线程 {:?}] 完成任务 {}", thread::current().id(), event.id);
}

fn main() {
    println!("=== 启动 3 个并发线程 ===");
    let start = std::time::Instant::now();
    
    // 创建 3 个线程，同时调用 dispatch
    let handles: Vec<_> = (1..=3)
        .map(|i| {
            thread::spawn(move || {
                dispatch(&format!("task/{}", i), Event { id: i }).unwrap();
            })
        })
        .collect();
    
    for h in handles {
        h.join().unwrap();
    }
    
    println!("总耗时: {:?}", start.elapsed());
    // 输出: 总耗时: ~100ms (并发执行)
}
```

### 输出示例：

```
=== 启动 3 个并发线程 ===
[线程 ThreadId(2)] 开始处理任务 1
[线程 ThreadId(3)] 开始处理任务 2  ← 同时开始！
[线程 ThreadId(4)] 开始处理任务 3  ← 同时开始！
[线程 ThreadId(2)] 完成任务 1
[线程 ThreadId(3)] 完成任务 2
[线程 ThreadId(4)] 完成任务 3
总耗时: ~100ms  ← 并发执行，不是 300ms
```

### 执行时间轴：

```
时间轴 (sync = false)：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

t=0ms   | 线程1: dispatch("task/1")
        |   → 获取读锁 ✅
        |   → 开始执行 handler
        |
        | 线程2: dispatch("task/2")
        |   → 获取读锁 ✅ (同时持有！)
        |   → 开始执行 handler
        |
        | 线程3: dispatch("task/3")
        |   → 获取读锁 ✅ (同时持有！)
        |   → 开始执行 handler
        |
        | 🚀 三个线程并发执行
        |
t=100ms | 线程1: 完成，释放读锁
        | 线程2: 完成，释放读锁
        | 线程3: 完成，释放读锁

总耗时: ~100ms (并发)
```

---

## 代码逐步分析

### dispatch 函数签名（第 399 行）

```rust
pub fn dispatch<T>(key: &str, event: T) -> Result<(), DispatchError>
where
    T: 'static + Send + Sync,  // 必须是线程安全的类型
```

**泛型约束**：
- `'static`：event 必须拥有所有数据（不能有借用）
- `Send`：可以在线程间传递
- `Sync`：可以被多个线程同时访问

---

### 第 1 步：获取读锁（403-406 行）

```rust
// 1. 先获取读锁进行匹配（允许并发）
let read_guard = GLOBAL_DISPATCH_LOCK
    .read()
    .map_err(|_: PoisonError<RwLockReadGuard<()>>| DispatchError::Poisoned)?;
```

**目的**：保护 `ACTION_REGISTRY` 的读取操作

**多线程行为**：

```rust
// 多个线程可以同时获取读锁
线程1: GLOBAL_DISPATCH_LOCK.read()  → ✅ 成功获取读锁
线程2: GLOBAL_DISPATCH_LOCK.read()  → ✅ 成功获取读锁（同时持有）
线程3: GLOBAL_DISPATCH_LOCK.read()  → ✅ 成功获取读锁（同时持有）
// ... 可以有更多线程
```

**为什么用读锁？**
- `ACTION_REGISTRY` 是只读的（一旦初始化就不再修改）
- 多个线程可以安全地并发查询
- 性能优化：读操作不需要互斥

---

### 第 2 步：查找匹配的 handler（408-420 行）

```rust
// 2. 在读锁保护下进行匹配
// 分层匹配：精确匹配 O(1) -> 前缀匹配 O(m) -> 复杂正则 O(k)
let handler = ACTION_REGISTRY.find(key);

// 3. 检查是否找到匹配
let handler = match handler {
    Some(h) => h,
    None => {
        // 没有匹配，释放锁并返回错误
        drop(read_guard);  // 显式释放读锁
        return Err(DispatchError::NoMatch);
    }
};
```

**线程安全性**：
- ✅ 多个线程同时查询 `ACTION_REGISTRY`
- ✅ 不会发生数据竞争（registry 是只读的）
- ✅ 每个线程拿到自己的 `&ActionHandler` 引用

---

### 第 3 步：决定执行策略（422-463 行）

这是**多线程机制的核心**！

```rust
// 4. 根据全局并发配置和 sync 标志决定执行策略
let ptr = &event as *const T as *const ();
let force_single = FORCE_SINGLE_THREAD.load(Ordering::Relaxed);

if handler.sync || force_single {
    // ========================================
    // 情况 A：需要独占执行
    // ========================================
    
    // 先释放读锁
    drop(read_guard);
    
    // 获取写锁（独占，阻塞其他所有 dispatch）
    let _write_guard = GLOBAL_DISPATCH_LOCK
        .write()
        .map_err(|_: PoisonError<RwLockWriteGuard<()>>| DispatchError::Poisoned)?;
    
    // 在写锁保护下执行（独占执行）
    unsafe { handler.call(ptr) };
    
    // 根据 by_ref 决定是否需要 forget
    if !handler.by_ref {
        std::mem::forget(event);
    }
    
    // _write_guard 自动 drop，释放写锁
} else {
    // ========================================
    // 情况 B：允许并发执行
    // ========================================
    
    // 保持读锁，直接执行（多个线程可并发）
    unsafe { handler.call(ptr) };
    
    if !handler.by_ref {
        std::mem::forget(event);
    }
    
    // read_guard 自动 drop，释放读锁
}
```

---

## 两种执行模式

### 模式 A：独占执行（sync = true）

#### 触发条件

```rust
if handler.sync || force_single {
    // 进入独占模式
}
```

- `handler.sync = true`：action 级别要求独占
- `force_single = true`：全局配置强制单线程

#### 执行流程

```rust
// 426-447 行
drop(read_guard);                                  // 1. 释放读锁
let _write_guard = GLOBAL_DISPATCH_LOCK.write()?;  // 2. 获取写锁 🔒
unsafe { handler.call(ptr) };                      // 3. 独占执行
// _write_guard 自动 drop                          // 4. 释放写锁
```

#### 多线程行为

```rust
#[action(regex = r"^critical", sync = true)]
fn critical_handler(event: Event) {
    println!("开始关键操作");
    thread::sleep(Duration::from_millis(100));
    println!("完成关键操作");
}

// 3 个线程同时调用
fn main() {
    let start = Instant::now();
    let handles: Vec<_> = (0..3).map(|_| {
        thread::spawn(|| {
            dispatch("critical", Event { id: 1 }).unwrap();
        })
    }).collect();
    
    for h in handles { h.join().unwrap(); }
    println!("总耗时: {:?}", start.elapsed());
    // 输出: 总耗时: ~300ms (串行执行)
}
```

#### 时间轴

```
时间轴 (sync = true)：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

t=0ms   | 线程1: dispatch("critical")
        |   → 获取读锁 ✅
        |   → 匹配成功
        |   → 发现 sync = true
        |   → 释放读锁
        |   → 获取写锁 ✅ 🔒 (独占)
        |   → 执行 handler...
        |
        | 线程2: dispatch("critical")
        |   → 获取读锁 ✅
        |   → 匹配成功
        |   → 释放读锁
        |   → 尝试获取写锁... ⏳ (阻塞，等待线程1)
        |
        | 线程3: dispatch("critical")
        |   → 获取读锁 ✅
        |   → 匹配成功
        |   → 释放读锁
        |   → 尝试获取写锁... ⏳ (阻塞，等待)
        |
t=100ms | 线程1: 完成，释放写锁 🔓
        |
        | 线程2: 获取写锁 ✅ 🔒 (独占)
        |   → 执行 handler...
        |
t=200ms | 线程2: 完成，释放写锁 🔓
        |
        | 线程3: 获取写锁 ✅ 🔒 (独占)
        |   → 执行 handler...
        |
t=300ms | 线程3: 完成，释放写锁 🔓

总耗时: ~300ms (串行执行)
```

---

### 模式 B：并发执行（sync = false）

#### 触发条件

```rust
else {
    // sync = false 且 force_single = false
    // 进入并发模式
}
```

#### 执行流程

```rust
// 448-463 行
// 保持读锁执行（不释放！）
unsafe { handler.call(ptr) };
// read_guard 自动 drop，释放读锁
```

**关键点**：
- ✅ **不释放读锁**，直接执行 handler
- ✅ 多个线程可以**同时持有读锁**
- ✅ 多个 handler **并发执行**

#### 多线程行为

```rust
#[action(regex = r"^task", sync = false)]  // sync = false (默认)
fn task_handler(event: Event) {
    println!("开始任务");
    thread::sleep(Duration::from_millis(100));
    println!("完成任务");
}

// 3 个线程同时调用
fn main() {
    let start = Instant::now();
    let handles: Vec<_> = (0..3).map(|_| {
        thread::spawn(|| {
            dispatch("task", Event { id: 1 }).unwrap();
        })
    }).collect();
    
    for h in handles { h.join().unwrap(); }
    println!("总耗时: {:?}", start.elapsed());
    // 输出: 总耗时: ~100ms (并发执行)
}
```

#### 时间轴

```
时间轴 (sync = false)：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

t=0ms   | 线程1: dispatch("task")
        |   → 获取读锁 ✅
        |   → 匹配成功
        |   → sync = false
        |   → 保持读锁，执行 handler 🚀
        |
        | 线程2: dispatch("task")
        |   → 获取读锁 ✅ (同时持有)
        |   → 匹配成功
        |   → sync = false
        |   → 保持读锁，执行 handler 🚀
        |
        | 线程3: dispatch("task")
        |   → 获取读锁 ✅ (同时持有)
        |   → 匹配成功
        |   → sync = false
        |   → 保持读锁，执行 handler 🚀
        |
        | 🎉 三个 handler 并发执行
        |
t=100ms | 线程1: 完成，释放读锁
        | 线程2: 完成，释放读锁
        | 线程3: 完成，释放读锁

总耗时: ~100ms (并发执行)
```

---

## RwLock 工作原理

### 锁的规则

```
┌─────────────────────────────────────────────────┐
│       GLOBAL_DISPATCH_LOCK (RwLock<()>)         │
├─────────────────────────────────────────────────┤
│                                                 │
│  读锁（Read Lock）          写锁（Write Lock）  │
│  ━━━━━━━━━━━━━━             ━━━━━━━━━━━━━━━    │
│  • 共享锁                    • 独占锁            │
│  • 多个线程可同时持有         • 只有一个线程      │
│  • 用于读操作                • 用于写操作        │
│  • 不阻塞其他读锁            • 阻塞所有其他锁    │
│                                                 │
│  并发规则：                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━    │
│                                                 │
│  ✅ 读锁 + 读锁 = 允许 (并发)                   │
│  ❌ 读锁 + 写锁 = 阻塞 (互斥)                   │
│  ❌ 写锁 + 写锁 = 阻塞 (互斥)                   │
│  ❌ 写锁 + 读锁 = 阻塞 (互斥)                   │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 锁的生命周期

#### 读锁（共享）

```rust
// 获取读锁
let read_guard = GLOBAL_DISPATCH_LOCK.read()?;

// ... 持有读锁期间，可以并发执行 ...

// 离开作用域，自动释放
drop(read_guard);  // 或者自动 drop
```

**并发示例**：

```rust
线程1: let guard1 = LOCK.read();  // ✅ 成功
线程2: let guard2 = LOCK.read();  // ✅ 成功（同时持有）
线程3: let guard3 = LOCK.read();  // ✅ 成功（同时持有）

// 三个线程同时持有读锁，可以并发读取
```

#### 写锁（独占）

```rust
// 获取写锁
let write_guard = GLOBAL_DISPATCH_LOCK.write()?;

// ... 持有写锁期间，独占执行 ...

// 离开作用域，自动释放
drop(write_guard);  // 或者自动 drop
```

**互斥示例**：

```rust
线程1: let guard1 = LOCK.write();  // ✅ 成功（独占）

线程2: let guard2 = LOCK.read();   // ⏳ 阻塞（等待线程1释放）
线程3: let guard3 = LOCK.write();  // ⏳ 阻塞（等待线程1释放）

// 只有线程1可以执行，线程2和3必须等待
```

---

## 为什么这么设计？

### 问题：如果用 Mutex 会怎样？

```rust
// 假设使用 Mutex（互斥锁）
static LOCK: Mutex<()> = Mutex::new(());

pub fn dispatch<T>(key: &str, event: T) -> Result<(), DispatchError> {
    let _guard = LOCK.lock().unwrap();  // 独占锁
    
    let handler = ACTION_REGISTRY.find(key);
    unsafe { handler.call(&event) };
    
    // _guard drop，释放锁
    Ok(())
}
```

#### Mutex 的问题

**所有 dispatch 都串行执行**，即使 `sync = false` 也无法并发：

```rust
#[action(regex = r"^task", sync = false)]  // sync = false 没用！
fn task_handler(event: Event) {
    thread::sleep(Duration::from_millis(100));
}

// 3 个线程
线程1: dispatch("task") → 获取 Mutex → 执行 (100ms) → 释放
线程2: dispatch("task") → ⏳ 等待线程1... → 执行 (100ms) → 释放
线程3: dispatch("task") → ⏳ 等待线程2... → 执行 (100ms) → 释放

总耗时: 300ms (强制串行)
```

#### 性能对比（10 个线程，每个 100ms）

| 实现方案 | sync=false 行为 | sync=false 耗时 | sync=true 耗时 |
|---------|---------------|----------------|---------------|
| **Mutex** | ❌ 强制串行 | ~1000ms | ~1000ms |
| **RwLock** | ✅ 可并发 | **~100ms** 🚀 | ~1000ms |

---

### RwLock 的优势

#### ✅ 灵活的并发控制

```rust
// sync = false（默认）：高性能并发
#[action(regex = r"^api/.*", sync = false)]
fn api_handler(event: Event) {
    // 读数据库、调用其他服务
    // → 多个请求可以并发处理 🚀
}

// sync = true：需要独占时也支持
#[action(regex = r"^admin/critical", sync = true)]
fn critical_handler(event: Event) {
    // 修改全局状态、写数据库
    // → 独占执行，保证安全 🔒
}
```

#### ✅ 读写分离的性能优化

```rust
dispatch 执行过程：
1. 获取读锁 → 匹配 handler (快速，可并发)
2. 根据 sync 标志决定：
   - sync = false → 保持读锁执行 (并发)
   - sync = true  → 升级为写锁执行 (独占)
```

#### ✅ 最小化锁竞争

- **读操作**（匹配 handler）：多个线程并发，无竞争
- **写操作**（sync=true 的 handler）：仅在必要时独占

---

## 实际应用示例

### 示例 1：HTTP 服务器

```rust
use std::thread;
use std::sync::Arc;
use action_dispatch::{action, dispatch};

#[derive(Clone)]
struct HttpRequest {
    method: String,
    path: String,
    body: String,
}

// GET 请求：只读操作，可并发
#[action(regex = r"^GET /api/users", sync = false)]
fn handle_get_users(req: HttpRequest) {
    println!("[{}] 查询用户列表", thread::current().name().unwrap());
    let users = database::query_users();  // 读数据库
    send_response(users);
}

#[action(regex = r"^GET /api/products", sync = false)]
fn handle_get_products(req: HttpRequest) {
    println!("[{}] 查询商品列表", thread::current().name().unwrap());
    let products = database::query_products();  // 读数据库
    send_response(products);
}

// POST 请求：写操作，但不同资源可以并发
#[action(regex = r"^POST /api/users", sync = false)]
fn handle_create_user(req: HttpRequest) {
    // 创建用户（数据库有行锁，可以并发）
    database::insert_user(&req.body);
}

// 关键操作：必须独占
#[action(regex = r"^POST /admin/reset-database", sync = true)]
fn handle_reset_database(req: HttpRequest) {
    println!("⚠️ 开始重置数据库（独占模式）");
    database::reset_all();  // 删除所有数据
    println!("✅ 数据库重置完成");
}

fn main() {
    // 模拟 10 个并发 HTTP 请求
    let handles: Vec<_> = (0..10)
        .map(|i| {
            thread::Builder::new()
                .name(format!("Worker-{}", i))
                .spawn(move || {
                    let req = HttpRequest {
                        method: "GET".into(),
                        path: "/api/users".into(),
                        body: "".into(),
                    };
                    dispatch("GET /api/users", req).unwrap();
                })
                .unwrap()
        })
        .collect();
    
    for h in handles {
        h.join().unwrap();
    }
    
    println!("✅ 所有请求处理完成");
}
```

**输出示例**：

```
[Worker-0] 查询用户列表
[Worker-1] 查询用户列表  ← 并发执行
[Worker-2] 查询用户列表  ← 并发执行
[Worker-3] 查询用户列表  ← 并发执行
...
✅ 所有请求处理完成
总耗时: ~100ms (而不是 1000ms)
```

---

### 示例 2：游戏服务器

```rust
#[derive(Clone)]
struct GameEvent {
    player_id: u64,
    action: String,
}

// 普通游戏操作：可并发
#[action(regex = r"^player/\d+/move", sync = false)]
fn handle_move(event: GameEvent) {
    // 更新玩家位置（每个玩家独立，可并发）
    update_player_position(event.player_id);
}

#[action(regex = r"^player/\d+/attack", sync = false)]
fn handle_attack(event: GameEvent) {
    // 计算伤害（每个战斗独立，可并发）
    calculate_damage(event.player_id);
}

// 全局事件：必须独占
#[action(regex = r"^server/save-world", sync = true)]
fn handle_save_world(event: GameEvent) {
    println!("🌍 开始保存游戏世界（所有其他操作暂停）");
    save_all_player_data();
    save_world_state();
    println!("✅ 游戏世界保存完成");
}

#[action(regex = r"^server/restart", sync = true)]
fn handle_restart(event: GameEvent) {
    println!("⚠️ 服务器重启（独占模式）");
    shutdown_all_connections();
    restart_server();
}
```

**运行效果**：

```
时间轴：
t=0s    | 100个玩家同时移动/攻击 → 并发处理 ✅
t=1s    | 触发 save-world
        | → 获取写锁，阻塞所有其他操作
        | → 保存所有数据 (5秒)
t=6s    | → 释放写锁
        | 100个玩家继续移动/攻击 → 并发处理 ✅
```

---

### 示例 3：数据处理管道

```rust
use std::sync::mpsc;

#[derive(Clone)]
struct DataChunk {
    id: usize,
    data: Vec<u8>,
}

// 数据转换：可并发
#[action(regex = r"^transform/.*", sync = false)]
fn transform_data(chunk: DataChunk) {
    println!("转换数据块 {}", chunk.id);
    let transformed = expensive_transformation(&chunk.data);
    send_to_next_stage(transformed);
}

// 数据聚合：必须独占（需要全局状态）
#[action(regex = r"^aggregate/.*", sync = true)]
fn aggregate_results(chunk: DataChunk) {
    println!("聚合数据块 {} (独占)", chunk.id);
    GLOBAL_AGGREGATOR.add(chunk.data);
}

fn main() {
    // 处理 1000 个数据块
    let handles: Vec<_> = (0..1000)
        .map(|i| {
            thread::spawn(move || {
                let chunk = DataChunk {
                    id: i,
                    data: vec![0; 1024],
                };
                
                // 转换阶段：1000 个块并发处理
                dispatch(&format!("transform/{}", i), chunk.clone()).unwrap();
            })
        })
        .collect();
    
    for h in handles {
        h.join().unwrap();
    }
}
```

**性能对比**：

| 阶段 | sync 标志 | 1000 块耗时 |
|------|----------|-----------|
| 转换（transform） | `false` | ~100ms（并发） |
| 聚合（aggregate） | `true` | ~10s（串行） |

---

## 常见问题

### Q1: dispatch 会创建线程吗？

**答：不会！**

```rust
// dispatch 本身不创建线程
dispatch("key", event).unwrap();

// 线程由用户创建
thread::spawn(|| {
    dispatch("key", event).unwrap();
});
```

---

### Q2: 读锁和写锁有什么区别？

**答：**

| 特性 | 读锁 | 写锁 |
|------|------|------|
| **并发性** | ✅ 多个线程可同时持有 | ❌ 只有一个线程可持有 |
| **用途** | 读取共享数据 | 修改共享数据 |
| **性能** | 🚀 高（无竞争） | 🐌 低（串行化） |
| **触发条件** | `sync = false` | `sync = true` |

---

### Q3: 为什么需要先获取读锁，再升级为写锁？

**答：优化性能！**

```rust
// 1. 先获取读锁进行匹配（快速，可并发）
let read_guard = LOCK.read()?;
let handler = find(key);  // O(1) ~ O(log n)

// 2. 根据 sync 标志决定
if handler.sync {
    // 只有需要独占时才升级为写锁
    drop(read_guard);
    let write_guard = LOCK.write()?;
    // ...
}
```

**好处**：
- ✅ 匹配阶段可以并发（多个线程同时查询）
- ✅ 只有 `sync=true` 的 action 才独占
- ✅ 最小化锁竞争

**如果直接用写锁**：
- ❌ 所有 dispatch 都串行（包括匹配阶段）
- ❌ 性能大幅下降

---

### Q4: sync = false 的 action 可以并发，那数据安全吗？

**答：安全！**

**原因 1**：每个 dispatch 调用的 `event` 是独立的

```rust
// 线程1
dispatch("task", Event { id: 1 });  // event1

// 线程2
dispatch("task", Event { id: 2 });  // event2 (不同的对象)

// event1 和 event2 是两个独立的对象，不会冲突
```

**原因 2**：如果 handler 内部访问共享数据，需要自己加锁

```rust
use std::sync::Mutex;

static COUNTER: Mutex<u64> = Mutex::new(0);

#[action(regex = r"^increment", sync = false)]  // 可以并发
fn increment_counter(event: Event) {
    // handler 内部自己加锁
    let mut counter = COUNTER.lock().unwrap();
    *counter += 1;
}
```

**原因 3**：如果确实需要全局独占，用 `sync = true`

```rust
#[action(regex = r"^critical", sync = true)]  // 独占执行
fn critical_operation(event: Event) {
    // 整个 handler 独占执行，不需要额外加锁
    GLOBAL_STATE.update();
}
```

---

### Q5: 什么时候应该用 sync = true？

**使用场景**：

1. **修改全局状态**
   ```rust
   #[action(regex = r"^update-config", sync = true)]
   fn update_config(event: ConfigEvent) {
       GLOBAL_CONFIG.write().unwrap().update(event);
   }
   ```

2. **需要严格顺序**
   ```rust
   #[action(regex = r"^log/.*", sync = true)]
   fn write_log(event: LogEvent) {
       // 确保日志按顺序写入
       LOG_FILE.write(event);
   }
   ```

3. **资源独占**
   ```rust
   #[action(regex = r"^device/write", sync = true)]
   fn write_device(event: DeviceEvent) {
       // 硬件设备一次只能一个操作
       DEVICE.write(event.data);
   }
   ```

**不需要 sync = true 的场景**：

1. **只读操作**
   ```rust
   #[action(regex = r"^query/.*", sync = false)]  // 可并发
   fn query_data(event: QueryEvent) {
       let result = DATABASE.read().query(event.sql);
   }
   ```

2. **独立的状态修改**
   ```rust
   #[action(regex = r"^user/\d+/update", sync = false)]  // 可并发
   fn update_user(event: UserEvent) {
       // 每个用户独立，数据库有行锁
       DATABASE.update_user(event.user_id, event.data);
   }
   ```

---

### Q6: 如何调试多线程问题？

**方法 1：启用单线程模式**

```rust
fn main() {
    // 调试时强制单线程
    action_dispatch::set_single_thread_mode(true);
    
    // 所有 dispatch 都串行执行，更容易复现和调试
    dispatch("key", event).unwrap();
}
```

**方法 2：添加日志**

```rust
#[action(regex = r"^task/.*")]
fn handle_task(event: Event) {
    println!("[{:?}] 开始处理 task", thread::current().id());
    // ...
    println!("[{:?}] 完成处理 task", thread::current().id());
}
```

**方法 3：使用 `list_actions` 检查注册状态**

```rust
fn main() {
    for action in action_dispatch::list_actions() {
        println!("Action: {} (sync={})", action.regex, action.sync);
    }
}
```

---

### Q7: 性能最佳实践

#### ✅ 推荐做法

1. **默认使用 sync = false**
   ```rust
   #[action(regex = r"^.*")]  // 默认就是 sync = false
   fn handler(event: Event) { }
   ```

2. **只在必要时使用 sync = true**
   ```rust
   #[action(regex = r"^critical", sync = true)]
   fn critical_handler(event: Event) { }
   ```

3. **handler 内部尽量短小快速**
   ```rust
   #[action(regex = r"^task/.*")]
   fn quick_handler(event: Event) {
       // ✅ 快速处理
       process(event);
   }
   
   // 如果有耗时操作，考虑异步
   #[action(regex = r"^slow-task/.*")]
   fn slow_handler(event: Event) {
       // ✅ 发送到后台线程处理
       THREAD_POOL.spawn(|| {
           expensive_operation(event);
       });
   }
   ```

#### ❌ 避免

1. **不要在 handler 中递归调用 dispatch**
   ```rust
   #[action(regex = r"^A", sync = true)]
   fn handler_a(event: Event) {
       dispatch("B", event);  // ❌ 死锁！
   }
   
   #[action(regex = r"^B", sync = true)]
   fn handler_b(event: Event) {
       dispatch("A", event);  // ❌ 死锁！
   }
   ```

2. **不要过度使用 sync = true**
   ```rust
   #[action(regex = r"^.*", sync = true)]  // ❌ 所有操作都串行
   fn handler(event: Event) { }
   ```

---

## 总结

### 核心要点

1. **dispatch 不创建线程**，只是提供线程安全的接口
2. **RwLock 实现智能并发控制**：
   - 读锁（sync=false）→ 并发执行
   - 写锁（sync=true）→ 独占执行
3. **性能优化**：读写分离，最小化锁竞争

### 使用建议

| 场景 | 推荐配置 | 性能 |
|------|---------|------|
| 只读操作 | `sync = false` | 🚀 并发 |
| 独立的写操作 | `sync = false` | 🚀 并发 |
| 全局状态修改 | `sync = true` | 🔒 串行 |
| 调试模式 | `set_single_thread_mode(true)` | 🔒 串行 |

### 性能对比

| 配置 | 10 线程耗时 | QPS |
|------|-----------|-----|
| **Mutex（所有串行）** | ~1000ms | 10 |
| **RwLock + sync=false** | **~100ms** | **100** |
| **RwLock + sync=true** | ~1000ms | 10 |

---

**现在理解了吗？** 🎉

`dispatch` 通过 **RwLock** 实现了灵活的多线程支持：
- ✅ 默认高性能并发（sync=false）
- ✅ 需要时可独占执行（sync=true）
- ✅ 线程安全，无数据竞争
- ✅ 性能优秀，最小化锁竞争

