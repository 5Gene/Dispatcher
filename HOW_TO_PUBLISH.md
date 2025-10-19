# 📦 如何发布 action_dispatch 到 crates.io

本文档详细说明如何将 `action_dispatch` 发布到 Rust 的官方包管理仓库 crates.io。

---

## 📋 目录

- [前置准备](#前置准备)
- [发布前检查](#发布前检查)
- [发布步骤](#发布步骤)
- [发布后验证](#发布后验证)
- [使用已发布的库](#使用已发布的库)
- [常见问题](#常见问题)
- [版本管理](#版本管理)

---

## 🔧 前置准备

### 1. 注册 crates.io 账号

1. 访问 [https://crates.io/](https://crates.io/)
2. 点击右上角 "Log in with GitHub"
3. 授权 GitHub 账号

### 2. 获取 API Token

1. 登录后，点击右上角头像
2. 选择 "Account Settings"
3. 在 "API Access" 部分，点击 "New Token"
4. 输入 token 名称（如 "action_dispatch"）
5. 点击 "Generate"
6. **复制并保存 token**（只显示一次！）

### 3. 配置 Cargo

在终端运行：

```bash
cargo login <your-token>
```

这会将 token 保存到 `~/.cargo/credentials`（或 Windows: `%USERPROFILE%\.cargo\credentials`）

---

## ✅ 发布前检查

### 1. 检查 Cargo.toml

确保所有必要信息都已填写：

```toml
[workspace.package]
version = "0.1.0"               # ✅ 版本号
edition = "2021"                # ✅ Rust 版本
authors = ["Your Name <you@example.com>"]  # ✅ 作者信息
license = "MIT OR Apache-2.0"   # ✅ 许可证
repository = "https://github.com/username/action_dispatch"  # ✅ 仓库地址
description = "通用的基于属性宏的 Action 注册与分发系统"  # ✅ 描述
keywords = ["action", "dispatch", "macro", "event", "handler"]  # ✅ 关键词
categories = ["rust-patterns", "asynchronous"]  # ✅ 分类
```

**重要字段说明**：

- **version**: 遵循 [Semantic Versioning](https://semver.org/)
  - `0.1.0` = 初始版本
  - `0.2.0` = 新功能，向后兼容
  - `1.0.0` = 稳定版本
  - `1.1.0` = 新功能
  - `1.0.1` = Bug 修复

- **license**: 推荐使用 `MIT OR Apache-2.0`（Rust 社区标准）

- **keywords**: 最多 5 个，帮助用户搜索

- **categories**: 从 [crates.io categories](https://crates.io/categories) 选择

### 2. 添加 README.md

确保根目录有 `README.md`，它会显示在 crates.io 页面上。

```bash
# 检查 README
ls README.md
```

### 3. 添加 LICENSE 文件

```bash
# MIT License
touch LICENSE-MIT

# Apache License
touch LICENSE-APACHE
```

### 4. 检查依赖

确保所有依赖都来自 crates.io（不能有本地路径依赖）：

```toml
# ✅ 正确
[dependencies]
regex = "1.11"
once_cell = "1.20"

# ❌ 错误（发布时不能有 path）
[dependencies]
my_local_crate = { path = "../my_local_crate" }
```

### 5. 运行测试

```bash
# 运行所有测试
cargo test --workspace

# 运行示例
cargo run --example basic
cargo run --example concurrent
```

### 6. 检查文档

```bash
# 生成文档
cargo doc --no-deps --open

# 检查文档是否完整
```

### 7. 检查打包

```bash
# 模拟打包（不会真的发布）
cargo package --workspace
```

这会创建 `.crate` 文件在 `target/package/` 目录。

---

## 🚀 发布步骤

### 步骤 1：发布 `action_dispatch_core`

```bash
cd action_dispatch_core
cargo publish
```

**等待发布成功**（通常需要几分钟）。

---

### 步骤 2：发布 `action_dispatch_macro`

```bash
cd ../action_dispatch_macro
cargo publish
```

**等待发布成功**。

---

### 步骤 3：更新 `action_dispatch` 的依赖

修改 `action_dispatch/Cargo.toml`：

```toml
[dependencies]
# 从 path 改为 version
action_dispatch_core = { version = "0.1.0" }
action_dispatch_macro = { version = "0.1.0" }
```

---

### 步骤 4：发布 `action_dispatch`

```bash
cd ../action_dispatch
cargo publish
```

---

### 完整发布脚本（自动化）

创建 `publish.sh`（Linux/macOS）或 `publish.bat`（Windows）：

```bash
#!/bin/bash
set -e

echo "🚀 开始发布 action_dispatch"

# 1. 发布 core
echo "\n📦 发布 action_dispatch_core..."
cd action_dispatch_core
cargo publish
echo "✅ action_dispatch_core 发布成功"

# 等待 crates.io 索引更新
echo "\n⏳ 等待 crates.io 索引更新（60秒）..."
sleep 60

# 2. 发布 macro
echo "\n📦 发布 action_dispatch_macro..."
cd ../action_dispatch_macro
cargo publish
echo "✅ action_dispatch_macro 发布成功"

# 等待 crates.io 索引更新
echo "\n⏳ 等待 crates.io 索引更新（60秒）..."
sleep 60

# 3. 发布 main
echo "\n📦 发布 action_dispatch..."
cd ../action_dispatch
cargo publish
echo "✅ action_dispatch 发布成功"

echo "\n🎉 所有包发布完成！"
echo "📝 访问 https://crates.io/crates/action_dispatch 查看"
```

运行：

```bash
chmod +x publish.sh
./publish.sh
```

---

## ✅ 发布后验证

### 1. 检查 crates.io

访问：
- https://crates.io/crates/action_dispatch
- https://crates.io/crates/action_dispatch_core
- https://crates.io/crates/action_dispatch_macro

确认：
- ✅ 版本号正确
- ✅ README 显示正常
- ✅ 文档链接可用

### 2. 检查文档

访问：
- https://docs.rs/action_dispatch

等待文档构建完成（通常 5-10 分钟）。

### 3. 测试安装

创建一个新项目测试：

```bash
cargo new test_action_dispatch
cd test_action_dispatch
```

修改 `Cargo.toml`：

```toml
[dependencies]
action_dispatch = "0.1.0"
```

创建测试代码：

```rust
use action_dispatch::{action, dispatch};

#[derive(Clone)]
struct Event {
    id: u64,
}

#[action(regex = r"^test$")]
fn test_handler(event: Event) {
    println!("测试成功！Event ID: {}", event.id);
}

fn main() {
    dispatch("test", Event { id: 123 }).unwrap();
}
```

运行：

```bash
cargo run
```

如果输出 `测试成功！Event ID: 123`，说明发布成功！✅

---

## 🎯 使用已发布的库

### 基本使用

在你的项目中添加依赖：

```toml
[dependencies]
action_dispatch = "0.1.0"
```

然后运行：

```bash
cargo build
```

### 在多文件项目中使用

```rust
// src/actions/user.rs
use action_dispatch::action;

#[derive(Clone)]
pub struct Event {
    pub id: u64,
}

#[action(regex = r"^user/.*$")]
pub fn user_handler(event: Event) {
    println!("处理用户请求");
}

// src/actions/mod.rs
pub mod user;

// src/main.rs
use action_dispatch::dispatch;

mod actions;  // ← 导入 actions 模块

fn main() {
    let event = actions::user::Event { id: 123 };
    dispatch("user/profile", event).unwrap();
}
```

**关键点**：
- ✅ 必须 `mod actions;` 导入模块
- ✅ 只要模块被导入，`#[action]` 就会自动注册
- ✅ 无需手动调用注册函数

---

## ❓ 常见问题

### Q1: 发布失败：验证错误

**错误信息**：
```
error: failed to verify package tarball
```

**解决方案**：
```bash
# 清理并重试
cargo clean
cargo package
cargo publish
```

---

### Q2: 依赖冲突

**错误信息**：
```
error: failed to select a version for `xxx`
```

**解决方案**：
- 检查 `Cargo.toml` 中的版本约束
- 使用 `cargo update` 更新依赖
- 参考 [crates.io](https://crates.io/) 查找兼容版本

---

### Q3: 文档构建失败

访问 https://docs.rs/action_dispatch 显示构建失败。

**解决方案**：
- 检查文档注释是否有语法错误
- 本地运行 `cargo doc` 检查
- 查看 docs.rs 的构建日志

---

### Q4: 如何撤销发布？

**注意**：crates.io **不允许删除已发布的版本**！

但可以：
1. **Yank（撤回）** 某个版本：
   ```bash
   cargo yank --vers 0.1.0
   ```
   - 不会删除包
   - 但新项目不会使用这个版本
   - 已依赖的项目仍可使用

2. **发布新版本** 修复问题：
   ```bash
   # 修改 version = "0.1.1"
   cargo publish
   ```

---

### Q5: 如何更新文档？

修改代码后重新发布即可：

```bash
# 1. 修改 version = "0.1.1"
# 2. 重新发布
cargo publish
```

docs.rs 会自动重新构建文档。

---

## 📊 版本管理

### Semantic Versioning（语义化版本）

格式：`MAJOR.MINOR.PATCH`

- **MAJOR**：不兼容的 API 变更
  - `0.1.0` → `1.0.0`：API 重大变更
  
- **MINOR**：向后兼容的新功能
  - `1.0.0` → `1.1.0`：添加新功能
  
- **PATCH**：向后兼容的 Bug 修复
  - `1.0.0` → `1.0.1`：修复 bug

### 版本号示例

```toml
# 0.x.x 版本（开发阶段）
0.1.0  # 初始版本
0.1.1  # Bug 修复
0.2.0  # 新功能（可能不兼容）
0.3.0  # 更多新功能

# 1.x.x 版本（稳定版本）
1.0.0  # 第一个稳定版本
1.0.1  # Bug 修复
1.1.0  # 新功能（向后兼容）
1.2.0  # 更多新功能
2.0.0  # 重大变更（不兼容 1.x）
```

### 更新版本号

修改 `Cargo.toml`：

```toml
[workspace.package]
version = "0.1.1"  # ← 更新这里
```

然后重新发布。

---

## 📚 相关资源

- [crates.io 官方文档](https://doc.rust-lang.org/cargo/reference/publishing.html)
- [Semantic Versioning](https://semver.org/)
- [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)
- [crates.io 政策](https://crates.io/policies)

---

## ✅ 发布检查清单

使用 [PUBLISH_CHECKLIST.md](PUBLISH_CHECKLIST.md) 确保所有步骤都完成。

---

## 🎉 恭喜！

如果你完成了所有步骤，你的库现在已经：
- ✅ 发布到 crates.io
- ✅ 任何人都可以使用
- ✅ 文档自动生成在 docs.rs
- ✅ 成为 Rust 生态系统的一部分！

**下一步**：
- 在 GitHub README 添加 badges
- 在社区分享你的项目
- 收集用户反馈，持续改进

**Happy Publishing!** 🚀

