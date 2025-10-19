# 📋 发布检查清单

使用此清单确保发布前所有准备工作都已完成。

---

## 🔧 前置准备

- [ ] 已注册 crates.io 账号
- [ ] 已获取并配置 API Token (`cargo login`)
- [ ] 已关联 GitHub 仓库

---

## 📝 文档检查

- [ ] README.md 存在且内容完整
  - [ ] 项目简介
  - [ ] 安装方法
  - [ ] 使用示例
  - [ ] API 文档链接
  - [ ] 许可证信息

- [ ] LICENSE 文件存在
  - [ ] `LICENSE-MIT` 或 `LICENSE`
  - [ ] `LICENSE-APACHE` (如果使用 MIT OR Apache-2.0)

- [ ] 所有公开 API 都有文档注释
  - [ ] 模块级文档 (`//!`)
  - [ ] 函数文档 (`///`)
  - [ ] 结构体文档
  - [ ] 示例代码

- [ ] CHANGELOG.md 已更新
  - [ ] 列出新功能
  - [ ] 列出 Bug 修复
  - [ ] 列出破坏性变更

---

## ⚙️ Cargo.toml 检查

### Workspace Package

- [ ] `version` - 版本号正确
- [ ] `edition` - Rust edition (2021)
- [ ] `authors` - 作者信息
- [ ] `license` - 许可证 (推荐 "MIT OR Apache-2.0")
- [ ] `description` - 简短描述 (< 200 字符)
- [ ] `repository` - GitHub 仓库 URL
- [ ] `documentation` - 文档 URL (可选，默认 docs.rs)
- [ ] `homepage` - 项目主页 (可选)
- [ ] `keywords` - 关键词 (最多 5 个)
- [ ] `categories` - 分类 (从 crates.io categories 选择)
- [ ] `readme` - README 文件路径 (可选，默认 README.md)

### 依赖检查

- [ ] 所有依赖都来自 crates.io（没有 `path` 依赖）
- [ ] 依赖版本号使用合适的约束 (如 `"1.0"` 而不是 `"=1.0.0"`)
- [ ] 没有未使用的依赖

---

## 🧪 测试检查

- [ ] 所有测试通过
  ```bash
  cargo test --workspace
  ```

- [ ] 所有示例可以运行
  ```bash
  cargo run --example basic
  cargo run --example concurrent
  ```

- [ ] 文档示例可以运行
  ```bash
  cargo test --doc
  ```

- [ ] 代码格式正确
  ```bash
  cargo fmt --check
  ```

- [ ] 没有 clippy 警告
  ```bash
  cargo clippy --all-targets --all-features
  ```

- [ ] 在发布模式下编译成功
  ```bash
  cargo build --release --workspace
  ```

---

## 📦 打包检查

- [ ] 打包成功
  ```bash
  cargo package --workspace
  ```

- [ ] 检查打包内容
  ```bash
  cargo package --list
  ```

- [ ] 确认不包含敏感信息
  - [ ] 没有私钥
  - [ ] 没有密码
  - [ ] 没有 API token

- [ ] 包大小合理 (< 10 MB)
  ```bash
  ls -lh target/package/*.crate
  ```

---

## 📚 文档构建检查

- [ ] 文档构建成功
  ```bash
  cargo doc --no-deps
  ```

- [ ] 文档内容正确
  ```bash
  cargo doc --no-deps --open
  ```

- [ ] 没有文档警告
  ```bash
  cargo doc --no-deps 2>&1 | grep warning
  ```

---

## 🔍 代码质量检查

- [ ] 代码遵循 Rust API Guidelines
  - [ ] 命名约定正确
  - [ ] 错误处理适当
  - [ ] 使用合适的生命周期
  - [ ] 避免不必要的 `unsafe`

- [ ] 没有编译警告
  ```bash
  cargo build --workspace 2>&1 | grep warning
  ```

- [ ] 没有 TODO 或 FIXME
  ```bash
  grep -r "TODO\|FIXME" src/
  ```

---

## 🌐 仓库检查

- [ ] GitHub 仓库存在且公开
- [ ] README 在 GitHub 上显示正常
- [ ] LICENSE 文件在仓库根目录
- [ ] .gitignore 配置正确
- [ ] 所有更改已提交并推送
  ```bash
  git status
  git push
  ```

- [ ] 打上版本 tag
  ```bash
  git tag v0.1.0
  git push --tags
  ```

---

## 🚀 发布步骤

### 第一步：发布 action_dispatch_core

- [ ] 切换到 core 目录
  ```bash
  cd action_dispatch_core
  ```

- [ ] 发布
  ```bash
  cargo publish
  ```

- [ ] 等待发布成功（等待 60 秒让 crates.io 索引更新）

---

### 第二步：发布 action_dispatch_macro

- [ ] 切换到 macro 目录
  ```bash
  cd ../action_dispatch_macro
  ```

- [ ] 发布
  ```bash
  cargo publish
  ```

- [ ] 等待发布成功（等待 60 秒）

---

### 第三步：更新 action_dispatch 依赖

- [ ] 修改 `action_dispatch/Cargo.toml`，将 path 依赖改为 version：
  ```toml
  [dependencies]
  action_dispatch_core = "0.1.0"
  action_dispatch_macro = "0.1.0"
  ```

---

### 第四步：发布 action_dispatch

- [ ] 切换到主目录
  ```bash
  cd ../action_dispatch
  ```

- [ ] 发布
  ```bash
  cargo publish
  ```

- [ ] 等待发布成功

---

## ✅ 发布后验证

- [ ] 访问 crates.io 页面
  - [ ] https://crates.io/crates/action_dispatch
  - [ ] https://crates.io/crates/action_dispatch_core
  - [ ] https://crates.io/crates/action_dispatch_macro

- [ ] 确认版本号正确

- [ ] 确认 README 显示正常

- [ ] 等待文档构建完成（5-10 分钟）
  - [ ] https://docs.rs/action_dispatch

- [ ] 测试安装
  ```bash
  cargo new test_project
  cd test_project
  # 添加依赖
  cargo add action_dispatch
  # 创建测试代码
  cargo run
  ```

---

## 📢 发布后宣传

- [ ] 在 GitHub Release 中发布版本
  - [ ] 添加 CHANGELOG
  - [ ] 附上文档链接

- [ ] 在社区分享
  - [ ] Reddit: r/rust
  - [ ] Rust 论坛
  - [ ] Twitter/X
  - [ ] 中文社区（Rust.cc 等）

- [ ] 更新 GitHub README badges
  ```markdown
  [![Crates.io](https://img.shields.io/crates/v/action_dispatch.svg)](https://crates.io/crates/action_dispatch)
  [![Documentation](https://docs.rs/action_dispatch/badge.svg)](https://docs.rs/action_dispatch)
  [![License](https://img.shields.io/crates/l/action_dispatch.svg)](https://github.com/username/action_dispatch#license)
  ```

---

## 📊 发布记录

| 版本 | 发布日期 | 主要变更 | crates.io | docs.rs |
|------|---------|---------|-----------|---------|
| 0.1.0 | YYYY-MM-DD | 初始版本 | [链接](https://crates.io/crates/action_dispatch/0.1.0) | [链接](https://docs.rs/action_dispatch/0.1.0) |
| 0.1.1 | YYYY-MM-DD | Bug 修复 | [链接](https://crates.io/crates/action_dispatch/0.1.1) | [链接](https://docs.rs/action_dispatch/0.1.1) |

---

## 🔄 下次发布前

- [ ] 更新 `version` 字段
- [ ] 更新 CHANGELOG.md
- [ ] 重新运行此检查清单

---

## ❌ 如果发布失败

### 常见错误处理

1. **验证失败**
   ```bash
   cargo clean
   cargo package
   ```

2. **依赖冲突**
   ```bash
   cargo update
   cargo tree
   ```

3. **文档错误**
   ```bash
   cargo doc --no-deps
   # 修复错误后重试
   ```

4. **Token 过期**
   ```bash
   cargo login <new-token>
   ```

---

## 📝 备注

- crates.io **不允许删除**已发布的版本
- 可以使用 `cargo yank` 撤回版本
- 发布后通常需要 5-10 分钟等待文档构建

---

## ✨ 完成！

如果所有检查都通过了，恭喜你成功发布了一个 Rust crate！🎉

记得：
- 监控用户反馈
- 及时修复 bug
- 持续改进文档
- 定期发布新版本

**Happy Publishing!** 🚀

