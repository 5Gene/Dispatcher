# 🚀 发布 Rust Crate 到 crates.io 完全指南（小白版）

## 📚 什么是 crates.io？

`crates.io` 是 Rust 的官方包仓库（类似 Python 的 PyPI，JavaScript 的 npm）。

**发布后的效果**：
```toml
# 其他人可以在 Cargo.toml 中这样使用：
[dependencies]
action-dispatch = "0.1.0"
```

---

## 🎯 第一部分：准备工作

### 步骤 1：注册 crates.io 账号

1. 访问 https://crates.io/
2. 点击右上角 **"Log in with GitHub"**（使用 GitHub 账号登录）
3. 授权 crates.io 访问你的 GitHub 账号

✅ 完成后你会看到你的用户名和头像

---

### 步骤 2：获取 API Token

1. 登录 crates.io 后，点击右上角你的头像
2. 选择 **"Account Settings"**（账号设置）
3. 找到 **"API Tokens"** 部分
4. 点击 **"New Token"**（新建 Token）
5. 输入 Token 名称（如 `my-laptop`）
6. 点击 **"Create"**（创建）
7. **⚠️ 重要**：复制显示的 Token（只会显示一次！）

Token 格式类似：`cio_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

---

### 步骤 3：配置本地 Cargo

在终端运行（将 `YOUR_TOKEN` 替换为你复制的 Token）：

```bash
cargo login cio_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

或者直接运行（会提示你输入）：

```bash
cargo login
```

✅ 看到 `Login token for 'crates.io' saved` 表示成功

**Token 保存位置**：
- Windows: `%USERPROFILE%\.cargo\credentials.toml`
- Linux/Mac: `~/.cargo/credentials.toml`

---

## 📝 第二部分：准备发布（检查清单）

### 检查 1：项目元数据

编辑 `Cargo.toml`，确保包含以下信息：

```toml
[package]
name = "action-dispatch"           # ⚠️ crate 名称（不能与已有的重复）
version = "0.1.0"                  # 版本号
edition = "2021"                   # Rust 版本
authors = ["你的名字 <your@email.com>"]
description = "高性能的基于属性宏的 Action 注册与分发系统"  # ⚠️ 必需
license = "MIT OR Apache-2.0"      # ⚠️ 必需（推荐使用这个）
repository = "https://github.com/你的用户名/action_dispatch"  # 可选但推荐
documentation = "https://docs.rs/action-dispatch"  # 可选，发布后自动生成
homepage = "https://github.com/你的用户名/action_dispatch"  # 可选
keywords = ["action", "dispatch", "macro", "async"]  # 最多5个
categories = ["asynchronous", "rust-patterns"]  # 从 crates.io 选择
readme = "README.md"               # 可选
```

**⚠️ 必需字段**：
- `name`
- `version`
- `description`（简短描述，最多100个字符）
- `license`（开源许可证）

---

### 检查 2：选择 Crate 名称

**检查名称是否可用**：

访问 `https://crates.io/crates/你的名称` 

例如：https://crates.io/crates/action-dispatch

- **404 页面** → ✅ 名称可用
- **显示 crate 信息** → ❌ 名称已被占用

**命名建议**：
- ✅ 使用连字符：`action-dispatch`（推荐）
- ✅ 小写字母
- ✅ 简短、描述性
- ❌ 不要用下划线：`action_dispatch`（不推荐）

---

### 检查 3：许可证文件

**推荐**：双许可证（最常见）

创建两个文件：

**LICENSE-MIT**:
```
MIT License

Copyright (c) 2024 你的名字

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**LICENSE-APACHE**:（访问 https://www.apache.org/licenses/LICENSE-2.0.txt 获取完整文本）

**或者**：只用一个许可证

```toml
license = "MIT"  # 或 "Apache-2.0"
```

---

### 检查 4：README.md

确保 `README.md` 包含：

```markdown
# action-dispatch

高性能的基于属性宏的 Action 注册与分发系统

## 功能特性

- ✅ 声明式注册（`#[action]` 宏）
- ✅ 正则匹配 + 优先级
- ✅ 全局同步执行模式
- ✅ 分层匹配优化
- ✅ 线程安全

## 快速开始

添加依赖：

\`\`\`toml
[dependencies]
action-dispatch = "0.1.0"
\`\`\`

使用示例：

\`\`\`rust
use action_dispatch::{action, dispatch};

#[derive(Clone)]
struct Event { id: u64 }

#[action(regex = r"^user/\\d+$", priority = 10)]
fn handle_user(event: Event) {
    println!("处理用户: {}", event.id);
}

fn main() {
    dispatch("user/123", Event { id: 123 }).unwrap();
}
\`\`\`

## 文档

完整文档：https://docs.rs/action-dispatch

## 许可证

MIT OR Apache-2.0
```

---

### 检查 5：排除不必要的文件

在 `Cargo.toml` 中添加：

```toml
[package]
# ...
exclude = [
    "target/",
    ".git/",
    ".vscode/",
    ".idea/",
    "*.swp",
    "*.swo",
    "*.md",      # 排除多余的 markdown 文件
    "build.bat",
    "py/",       # 排除 Python 版本
]
```

或者指定只包含哪些文件（更精确）：

```toml
[package]
# ...
include = [
    "src/**/*",
    "Cargo.toml",
    "README.md",
    "LICENSE-MIT",
    "LICENSE-APACHE",
]
```

---

## 🚀 第三部分：发布步骤

### 步骤 1：测试编译

```bash
# 清理并重新编译
cd D:\0DEV\0my\rust\action_dispatch
cargo clean
cargo build --all --release

# 运行测试
cargo test --all

# 运行示例
cargo run --example basic
```

✅ 确保所有都通过

---

### 步骤 2：打包测试（Dry Run）

```bash
# 只打包，不发布（测试）
cargo package --dry-run
```

这会：
1. 检查 `Cargo.toml` 必需字段
2. 构建 `.crate` 包
3. 显示将要包含的文件
4. **不会实际上传**

**检查输出**：
```
   Packaging action-dispatch v0.1.0
   Verifying action-dispatch v0.1.0
   Compiling action-dispatch v0.1.0
    Finished dev [unoptimized + debuginfo] target(s)
```

✅ 如果成功，继续下一步

❌ 如果失败，查看错误信息并修复

---

### 步骤 3：实际打包

```bash
# 生成 .crate 文件
cargo package
```

包会保存在：`target/package/action-dispatch-0.1.0.crate`

---

### 步骤 4：发布到 crates.io 🎉

```bash
# 发布！
cargo publish
```

**这会**：
1. 上传 `.crate` 包到 crates.io
2. 编译检查
3. 生成文档（https://docs.rs/）

**输出示例**：
```
    Updating crates.io index
   Uploading action-dispatch v0.1.0
```

✅ **成功！** 看到 `Uploaded` 消息

⚠️ **注意**：一旦发布，**无法删除**（只能发布新版本）

---

### 步骤 5：验证发布

1. 访问 `https://crates.io/crates/action-dispatch`
2. 检查信息是否正确
3. 等待 5-10 分钟，文档会出现在 `https://docs.rs/action-dispatch`

---

## 🔄 第四部分：更新版本

### 语义化版本（SemVer）

格式：`主版本.次版本.修订号`

| 变更类型 | 版本号变化 | 示例 |
|---------|-----------|------|
| **破坏性变更** | 主版本 +1 | 0.1.0 → 1.0.0 |
| **新增功能** | 次版本 +1 | 0.1.0 → 0.2.0 |
| **Bug 修复** | 修订号 +1 | 0.1.0 → 0.1.1 |

### 发布新版本步骤

1. **修改代码**
2. **更新版本号**：
   ```toml
   [package]
   version = "0.1.1"  # 或 0.2.0 或 1.0.0
   ```
3. **更新 CHANGELOG**（可选但推荐）
4. **提交 Git**：
   ```bash
   git add .
   git commit -m "Release v0.1.1"
   git tag v0.1.1
   git push origin main --tags
   ```
5. **重新发布**：
   ```bash
   cargo publish
   ```

---

## 📦 第五部分：使用你的 Crate

### 在其他项目中使用

**Cargo.toml**:
```toml
[dependencies]
action-dispatch = "0.1.0"
```

**main.rs**:
```rust
use action_dispatch::{action, dispatch};

#[derive(Clone)]
struct Event { id: u64 }

#[action(regex = r"^user/\d+$", priority = 10)]
fn handle_user(event: Event) {
    println!("用户 ID: {}", event.id);
}

fn main() {
    dispatch("user/123", Event { id: 123 }).unwrap();
}
```

**运行**:
```bash
cargo build
cargo run
```

✅ 完成！

---

## 🐛 常见问题

### 问题 1：`name already taken`

**错误**：
```
error: crate name `action-dispatch` is already taken
```

**解决**：
- 改用其他名称，如 `action-dispatch-rs`
- 或联系原作者（如果是废弃项目）

---

### 问题 2：缺少必需字段

**错误**：
```
error: missing required field `description`
```

**解决**：在 `Cargo.toml` 中添加：
```toml
description = "你的 crate 描述"
license = "MIT OR Apache-2.0"
```

---

### 问题 3：文件太大

**错误**：
```
error: package is too large (> 10MB)
```

**解决**：
1. 检查 `target/` 目录是否被包含（应该排除）
2. 添加 `.gitignore` 和 `exclude` 配置
3. 移除大文件（测试数据、图片等）

---

### 问题 4：依赖冲突

**错误**：
```
error: cyclic dependency
```

**解决**：
- 检查 `Cargo.toml` 依赖关系
- 不要循环引用

---

### 问题 5：API Token 过期

**错误**：
```
error: authentication failed
```

**解决**：
```bash
# 重新登录
cargo login
```

---

## 📊 发布检查清单

在发布前，确认以下所有项：

- [ ] ✅ 已注册 crates.io 账号
- [ ] ✅ 已配置 `cargo login`
- [ ] ✅ 检查 crate 名称可用
- [ ] ✅ `Cargo.toml` 包含所有必需字段
- [ ] ✅ 添加 LICENSE 文件
- [ ] ✅ README.md 完整
- [ ] ✅ 代码无警告、无错误
- [ ] ✅ 所有测试通过
- [ ] ✅ 示例可运行
- [ ] ✅ 排除不必要的文件
- [ ] ✅ `cargo package --dry-run` 成功
- [ ] ✅ 代码已提交 Git
- [ ] ✅ 打上版本 tag

---

## 🎯 快速命令参考

```bash
# 1. 登录
cargo login

# 2. 测试打包
cargo package --dry-run

# 3. 实际打包
cargo package

# 4. 发布
cargo publish

# 5. 发布新版本
# 修改 Cargo.toml version
cargo publish

# 6. 撤回版本（不推荐，不会删除）
cargo yank --vers 0.1.0

# 7. 取消撤回
cargo yank --vers 0.1.0 --undo
```

---

## 📚 进阶技巧

### 1. 发布工作区（Workspace）

你的项目是工作区（多个 crate）：

```bash
# 逐个发布（按依赖顺序）
cd action_dispatch_core
cargo publish

cd ../action_dispatch_macro
cargo publish

cd ../action_dispatch
cargo publish
```

### 2. 使用 cargo-release

```bash
# 安装
cargo install cargo-release

# 自动化发布（更新版本号、打 tag、发布）
cargo release patch  # 0.1.0 → 0.1.1
cargo release minor  # 0.1.0 → 0.2.0
cargo release major  # 0.1.0 → 1.0.0
```

### 3. GitHub Actions 自动发布

创建 `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions-rs/toolchain@v1
        with:
          toolchain: stable
      - run: cargo publish --token ${{ secrets.CARGO_TOKEN }}
```

---

## 🎉 总结

### 发布流程（5 步）

1. **准备**：注册账号、配置 token
2. **检查**：元数据、许可证、README
3. **测试**：`cargo package --dry-run`
4. **发布**：`cargo publish`
5. **验证**：访问 crates.io

### 关键命令

```bash
cargo login               # 登录（只需一次）
cargo package --dry-run  # 测试打包
cargo publish            # 发布
```

### 重要提醒

⚠️ **发布前三思**：
- 版本号无法修改
- crate 无法删除
- 只能发布新版本

✅ **发布后**：
- 全世界都可以使用你的 crate
- 自动生成文档（docs.rs）
- 出现在 crates.io 搜索中

---

## 📞 需要帮助？

- **官方文档**：https://doc.rust-lang.org/cargo/reference/publishing.html
- **crates.io 指南**：https://doc.crates.io/
- **Rust 社区**：https://users.rust-lang.org/

---

**祝发布顺利！** 🚀

有任何问题随时查看这份文档，或访问官方资源。

---

**文档版本**：v1.0  
**适用对象**：Rust 初学者  
**最后更新**：2024年

