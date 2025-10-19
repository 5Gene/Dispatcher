# 📚 模块导入总结

## ❓ 问题

> "为什么需要在入口文件中手动导入 action 模块？不是说是编译期间静态注册的吗？"

---

## ✅ 简短回答

**是静态注册**，但**仍需模块导入**。

- ✅ **静态注册** = 使用 `#[action]` 宏，无需手动调用注册函数
- ✅ **模块导入** = 告诉 Rust 编译器编译哪些文件

这是 **Rust 编译器的要求**，不是 `action_dispatch` 的限制。

---

## 🔑 关键概念

### Rust 不会自动编译所有 `.rs` 文件

```rust
// main.rs
mod user_actions;   // ✅ Rust 会编译 user_actions.rs
// mod order_actions;  // ❌ 被注释掉，不会编译 order_actions.rs
```

**没有 `mod` 声明 = 文件不会被编译 = action 无法注册**

---

## 💡 对比其他语言

### Python（可以运行时扫描）

```python
import os
for file in os.listdir("actions"):
    if file.endswith(".py"):
        __import__(f"actions.{file[:-3]}")
```

### Rust（必须编译时声明）

```rust
mod user_actions;    // 必须显式声明
mod order_actions;   // 必须显式声明
```

**原因**：
- Python 是解释型，可以运行时动态导入
- Rust 是编译型，必须编译时确定所有模块

---

## 🎯 最佳实践：集中管理模块

### 推荐结构

```
src/
  main.rs           # mod actions; 一行搞定！
  actions/
    mod.rs          # 集中管理所有 action 模块
    user.rs
    order.rs
    admin.rs
    api/
      mod.rs
      v1.rs
      v2.rs
```

### actions/mod.rs

```rust
// actions/mod.rs
pub mod user;
pub mod order;
pub mod admin;
pub mod api;
```

### main.rs

```rust
// main.rs
mod actions;  // ← 只需这一行！

fn main() {
    // 所有 action 都可用
    dispatch("user/123", event)?;
    dispatch("order/456", event)?;
}
```

**优点**：
- ✅ 入口文件只需一行
- ✅ 所有模块在 `actions/mod.rs` 中集中管理
- ✅ 清晰的项目结构

---

## 📖 详细解释

参见：[STATIC_REGISTRATION_EXPLAINED.md](STATIC_REGISTRATION_EXPLAINED.md)

包含：
- ✅ inventory 工作原理
- ✅ 为什么必须 `mod xxx;`
- ✅ Python vs Rust 对比
- ✅ 多种项目结构方案
- ✅ 完整的技术细节

---

## 📦 发布文档

已还原：
- ✅ [HOW_TO_PUBLISH.md](HOW_TO_PUBLISH.md) - 详细发布指南
- ✅ [PUBLISH_CHECKLIST.md](PUBLISH_CHECKLIST.md) - 发布检查清单

---

## 🎉 总结

1. **需要 `mod` 是 Rust 的设计**，不是缺陷
2. **这带来了编译时的类型安全和零运行时开销**
3. **使用集中管理模块的方式，只需一行 `mod actions;`**

**Happy Coding!** 🚀

