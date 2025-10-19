# 📚 静态注册原理详解

## ❓ 常见疑问

> "不是说编译期间静态注册吗？为什么还要在入口文件中手动导入模块？"

这是一个非常好的问题！让我详细解释一下。

---

## 🔍 核心概念

### 1. **静态注册 ≠ 自动导入**

`action_dispatch` 的"静态注册"是指：

```rust
#[action(regex = r"^user/.*$")]  // ← 编译时注册
fn handler(event: Event) { }      // 不需要手动调用 register() 函数
```

**对比手动注册**（其他框架常见）：

```rust
fn handler(event: Event) { }

fn main() {
    // ❌ 需要手动注册
    dispatcher.register(r"^user/.*$", handler);
}
```

**action_dispatch 的优势**：
- ✅ 使用 `#[action]` 宏，自动注册
- ✅ 无需在 `main` 中调用 `register`
- ✅ 编译时收集，运行时可用

---

### 2. **但仍需模块导入**

这是 **Rust 编译器的要求**，不是 `action_dispatch` 的限制！

```rust
// main.rs
mod user_actions;   // ← 必须导入模块
//  ^^^^^^^^^^^^^^^^
//  这行告诉 Rust 编译器："请编译 user_actions.rs"
//  如果不写，Rust 根本不会编译那个文件！
```

**原因**：
1. Rust 不会自动编译项目中的所有 `.rs` 文件
2. 只有通过 `mod` 声明的模块才会被编译
3. 只有被编译的代码，`inventory` 才能收集其中的 `#[action]`

---

## 🆚 对比其他语言

### Python（动态语言）

```python
# main.py
# ❌ 不需要显式导入

# Python 可以在运行时扫描目录，自动导入所有模块
import importlib
import os

for file in os.listdir("actions"):
    if file.endswith(".py"):
        importlib.import_module(f"actions.{file[:-3]}")
```

**Python 的特点**：
- ✅ 运行时可以扫描文件系统
- ✅ 可以动态导入模块
- ❌ 但性能较低（运行时开销）

---

### Rust（静态语言）

```rust
// main.rs
mod user_actions;    // ← 必须显式声明
mod order_actions;   // ← 必须显式声明

// ❌ Rust 不支持运行时扫描目录并编译代码
// ✅ 但性能极高（编译时确定）
```

**Rust 的特点**：
- ✅ 编译时确定所有模块
- ✅ 零运行时开销
- ✅ 类型安全
- ❌ 必须显式声明模块

---

## 🔧 inventory 的工作原理

### 第 1 步：宏展开（编译时）

```rust
// user_actions.rs
#[action(regex = r"^user/.*$")]
fn handler(event: Event) { }

// 宏展开后（简化版）：
fn handler(event: Event) { }

#[used]
#[link_section = ".action_registry"]  // ← 存储在特殊的 linker section
static ACTION_META: ActionMetadata = ActionMetadata {
    regex_str: "^user/.*$",
    func: handler_wrapper,
    // ...
};

inventory::submit!(ACTION_META);  // ← 提交给 inventory
```

**关键点**：
- 宏会生成一个静态变量 `ACTION_META`
- 这个变量会被放在特殊的 linker section 中
- `inventory::submit!` 标记这个变量

---

### 第 2 步：链接器收集（编译时）

```
链接器阶段：
┌─────────────────────────────────────────┐
│  user_actions.o                         │
│    .action_registry: [ACTION_META_1]    │ ─┐
└─────────────────────────────────────────┘  │
                                             │
┌─────────────────────────────────────────┐  │
│  order_actions.o                        │  │
│    .action_registry: [ACTION_META_2]    │ ─┤  链接器收集
└─────────────────────────────────────────┘  │  所有 action
                                             │
┌─────────────────────────────────────────┐  │
│  admin_actions.o                        │  │
│    .action_registry: [ACTION_META_3]    │ ─┘
└─────────────────────────────────────────┘

                ↓

┌─────────────────────────────────────────┐
│  最终二进制文件                          │
│  .action_registry: [                    │
│    ACTION_META_1,                       │
│    ACTION_META_2,                       │
│    ACTION_META_3,                       │
│  ]                                      │
└─────────────────────────────────────────┘
```

**关键点**：
- 链接器会收集所有 `.action_registry` section 中的数据
- 合并成一个统一的列表
- 这发生在编译时，不是运行时！

---

### 第 3 步：运行时访问

```rust
// main.rs
fn main() {
    // inventory::iter() 直接访问编译时生成的列表
    for meta in inventory::iter::<ActionMetadata>() {
        println!("找到 action: {}", meta.regex_str);
    }
}
```

**关键点**：
- `inventory::iter()` 访问链接器收集的数据
- 零运行时开销
- 不需要扫描文件系统

---

## ⚠️ 为什么必须 `mod xxx;`？

### 问题：如果不写 `mod user_actions;`

```rust
// main.rs
// mod user_actions;  ← 注释掉

fn main() {
    dispatch("user/123", event)?;  // ❌ 找不到 handler！
}
```

**原因**：

```
Rust 编译过程：
┌──────────────────────────────────────────────────┐
│  第 1 步：解析 main.rs                           │
│    - 看到 mod user_actions; → 编译 user_actions.rs │
│    - 没看到？→ 跳过 user_actions.rs              │
└──────────────────────────────────────────────────┘
                ↓
┌──────────────────────────────────────────────────┐
│  第 2 步：编译各个模块                           │
│    - main.rs → main.o                            │
│    - user_actions.rs → user_actions.o  (如果导入) │
│    - order_actions.rs → order_actions.o (如果导入) │
└──────────────────────────────────────────────────┘
                ↓
┌──────────────────────────────────────────────────┐
│  第 3 步：链接                                   │
│    只链接被编译的模块！                           │
│    如果 user_actions.rs 没被编译，                │
│    里面的 ACTION_META 根本不存在！               │
└──────────────────────────────────────────────────┘
```

**结论**：
- 没有 `mod user_actions;`
- → `user_actions.rs` 不会被编译
- → `ACTION_META` 不会生成
- → `inventory` 无法收集
- → `dispatch("user/123")` 找不到 handler

---

## 💡 最佳实践

### 方案 1：集中管理模块（推荐）✅

创建一个专门的模块文件来管理所有 action：

```rust
// actions/mod.rs
pub mod user;
pub mod order;
pub mod admin;
pub mod api {
    pub mod v1;
    pub mod v2;
}

// main.rs
mod actions;  // ← 只需一行！

fn main() {
    dispatch("user/123", event)?;  // ✅ 所有 action 都可用
}
```

**优点**：
- ✅ 入口文件只需一行 `mod actions;`
- ✅ 所有 action 模块在 `actions/mod.rs` 中集中管理
- ✅ 清晰的项目结构

---

### 方案 2：使用 build.rs 自动生成（高级）⚡

```rust
// build.rs
use std::fs;
use std::io::Write;

fn main() {
    let action_dir = "src/actions";
    let mut mod_file = fs::File::create("src/actions/mod.rs").unwrap();
    
    // 扫描 actions 目录
    for entry in fs::read_dir(action_dir).unwrap() {
        let entry = entry.unwrap();
        let name = entry.file_name().into_string().unwrap();
        
        if name.ends_with(".rs") && name != "mod.rs" {
            let module_name = name.trim_end_matches(".rs");
            writeln!(mod_file, "pub mod {};", module_name).unwrap();
        }
    }
}
```

**优点**：
- ✅ 完全自动化
- ✅ 添加新文件无需修改代码

**缺点**：
- ❌ 增加构建复杂度
- ❌ IDE 自动补全可能有问题

---

### 方案 3：按业务模块组织（平衡）⚖️

```rust
// src/
//   main.rs
//   user/
//     mod.rs        ← pub mod profile; pub mod settings;
//     profile.rs    ← #[action] ...
//     settings.rs   ← #[action] ...
//   order/
//     mod.rs        ← pub mod detail; pub mod payment;
//     detail.rs     ← #[action] ...
//     payment.rs    ← #[action] ...

// main.rs
mod user;   // ← user/mod.rs 会自动导入 profile 和 settings
mod order;  // ← order/mod.rs 会自动导入 detail 和 payment

fn main() {
    dispatch("user/profile", event)?;  // ✅
    dispatch("order/detail", event)?;  // ✅
}
```

**优点**：
- ✅ 符合 Rust 惯例
- ✅ 清晰的业务模块划分
- ✅ 每个业务模块内部集中管理

---

## 🆚 Python vs Rust 对比

### Python（动态导入）

```python
# Python 可以这样做：
import os
import importlib

# 运行时扫描目录
for file in os.listdir("actions"):
    if file.endswith(".py"):
        # 运行时动态导入
        importlib.import_module(f"actions.{file[:-3]}")

# 所有 @action 装饰的函数自动注册
dispatch("user/123", event)
```

**成本**：
- 运行时开销（每次启动都要扫描）
- 可能导入不需要的模块
- 类型安全较弱

---

### Rust（静态声明）

```rust
// Rust 必须这样做：
mod user_actions;
mod order_actions;
// ... 明确声明需要哪些模块

fn main() {
    // 编译时已确定所有 action
    dispatch("user/123", event)?;
}
```

**优势**：
- ✅ 零运行时开销
- ✅ 编译时确定所有模块
- ✅ 完整的类型检查
- ✅ 不会意外导入不相关的代码

---

## 🎯 结论

### 为什么需要 `mod xxx;`？

1. **Rust 编译器要求** - 不是 action_dispatch 的限制
2. **必须告诉编译器哪些文件需要编译**
3. **只有被编译的代码，inventory 才能收集**

---

### "静态注册"的真正含义

✅ **是静态的**：
- 编译时确定所有 action
- 运行时无需注册函数
- 零运行时开销

✅ **但需要模块声明**：
- 通过 `mod` 告诉编译器编译哪些文件
- 这是 Rust 模块系统的基本要求
- 一次声明，永久生效

---

### 最佳实践总结

| 方案 | 复杂度 | 推荐度 | 适用场景 |
|------|--------|--------|---------|
| **集中管理** | ⭐ | ⭐⭐⭐⭐⭐ | 大多数项目 |
| **build.rs 自动生成** | ⭐⭐⭐⭐ | ⭐⭐⭐ | 动态插件系统 |
| **业务模块组织** | ⭐⭐ | ⭐⭐⭐⭐ | 大型项目 |

---

### 推荐结构

```rust
// 推荐的项目结构
src/
  main.rs           // mod actions; 一行搞定！
  lib.rs           // 库代码
  actions/
    mod.rs         // 集中管理所有 action 模块
    user.rs
    order.rs
    admin.rs
    api/
      mod.rs
      v1.rs
      v2.rs
```

```rust
// actions/mod.rs
pub mod user;
pub mod order;
pub mod admin;
pub mod api;

// main.rs
mod actions;  // ← 只需这一行！

fn main() {
    // 所有 action 都可用
    dispatch("user/123", event)?;
    dispatch("order/456", event)?;
    dispatch("admin/critical", event)?;
    dispatch("api/v1/users", event)?;
}
```

---

## 📚 延伸阅读

- [Rust 模块系统](https://doc.rust-lang.org/book/ch07-00-managing-growing-projects-with-packages-crates-and-modules.html)
- [inventory crate 文档](https://docs.rs/inventory/)
- [Rust 链接器 sections](https://doc.rust-lang.org/reference/linkage.html)

---

**总结**：需要 `mod` 声明是 Rust 的设计，不是缺陷，这带来了编译时的类型安全和零运行时开销！✨

