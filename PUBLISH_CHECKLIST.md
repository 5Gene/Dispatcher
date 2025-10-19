# 🚀 发布准备清单

## ✅ 已完成的准备工作

- ✅ 项目结构完整（Workspace）
- ✅ 代码无警告、无错误
- ✅ 所有测试通过
- ✅ 示例代码完整
- ✅ 文档详尽（~500页）
- ✅ 依赖已升级到最新

## 📋 发布前需要做的事（TODO）

### 1. 注册和配置（只需一次）

- [ ] 访问 https://crates.io/ 用 GitHub 登录
- [ ] 获取 API Token
- [ ] 运行 `cargo login YOUR_TOKEN`

### 2. 检查项目信息

编辑 `Cargo.toml`，确保包含：

```toml
[workspace.package]
version = "0.1.0"
edition = "2021"
authors = ["你的名字 <your@email.com>"]  # ← 修改这里
license = "MIT OR Apache-2.0"
repository = "https://github.com/你的用户名/action_dispatch"  # ← 修改这里
```

### 3. 检查 crate 名称是否可用

访问以下地址，看是否 404（404 = 可用）：

- https://crates.io/crates/action-dispatch
- https://crates.io/crates/action-dispatch-core
- https://crates.io/crates/action-dispatch-macro

⚠️ 如果已被占用，需要改名：
- 方案 1：`action-dispatch-rs`
- 方案 2：`rust-action-dispatch`
- 方案 3：`act-dispatch`

### 4. 创建许可证文件

项目根目录需要这两个文件：

**LICENSE-MIT**（已在文档中提供完整文本）

**LICENSE-APACHE**（访问 https://www.apache.org/licenses/LICENSE-2.0.txt）

### 5. 准备 README.md（给 crates.io 用）

确保包含：
- 项目简介
- 快速开始示例
- 功能特性
- 文档链接

### 6. 排除不必要的文件

在 `action_dispatch/Cargo.toml` 中添加：

```toml
exclude = [
    "target/",
    ".git/",
    "py/",
    "*.md",
    "build.bat",
]
```

### 7. 测试打包

```bash
cd action_dispatch_core
cargo package --dry-run

cd ../action_dispatch_macro
cargo package --dry-run

cd ../action_dispatch
cargo package --dry-run
```

✅ 全部通过后继续

---

## 🚀 发布步骤（按顺序）

### Step 1: 发布 action_dispatch_core

```bash
cd action_dispatch_core
cargo publish
```

⏰ 等待 1-2 分钟（让 crates.io 索引更新）

### Step 2: 发布 action_dispatch_macro

```bash
cd ../action_dispatch_macro
cargo publish
```

⏰ 等待 1-2 分钟

### Step 3: 发布 action_dispatch（主 crate）

```bash
cd ../action_dispatch
cargo publish
```

---

## 📝 发布后验证

1. 访问 https://crates.io/crates/action-dispatch
2. 检查版本号、描述是否正确
3. 等待 5-10 分钟，文档会出现在 https://docs.rs/action-dispatch
4. 测试安装：
   ```bash
   cargo new test_project
   cd test_project
   # 在 Cargo.toml 添加：
   # [dependencies]
   # action-dispatch = "0.1.0"
   cargo build
   ```

---

## ⚠️ 常见问题和解决方案

### 问题 1：名称已被占用

```
error: crate name `action-dispatch` is already taken
```

**解决**：
- 改名（见上面的方案）
- 或者等待（如果是废弃项目，可以联系原作者）

### 问题 2：缺少字段

```
error: missing required field `description`
```

**解决**：确保 `Cargo.toml` 包含所有必需字段

### 问题 3：依赖版本问题

```
error: dependency `action_dispatch_core` not found
```

**解决**：先发布依赖的 crate（core 和 macro），再发布主 crate

### 问题 4：文件太大

```
error: package is too large
```

**解决**：添加 `exclude` 配置，排除不必要的文件

---

## 🎯 快速发布命令（全部准备好后）

```bash
# 在项目根目录执行
cd D:\0DEV\0my\rust\action_dispatch

# 1. 发布 core
cd action_dispatch_core && cargo publish && cd ..

# 2. 等待 2 分钟
timeout /t 120

# 3. 发布 macro
cd action_dispatch_macro && cargo publish && cd ..

# 4. 等待 2 分钟
timeout /t 120

# 5. 发布主 crate
cd action_dispatch && cargo publish && cd ..

echo "发布完成！"
```

---

## 📊 当前状态

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 代码质量 | ✅ | 无警告、无错误 |
| 测试 | ✅ | 所有测试通过 |
| 文档 | ✅ | 完整详尽 |
| 示例 | ✅ | 多个示例可运行 |
| 依赖 | ✅ | 已升级到最新 |
| 账号注册 | ⏳ | **需要你完成** |
| API Token | ⏳ | **需要你完成** |
| 许可证文件 | ⏳ | **需要创建** |
| Git 仓库 | ⏳ | **推荐但可选** |

---

## 📚 下一步

1. **阅读** `HOW_TO_PUBLISH.md` 详细教程
2. **注册** crates.io 账号
3. **检查** crate 名称是否可用
4. **修改** Cargo.toml 中的作者信息
5. **创建** LICENSE 文件
6. **运行** `cargo package --dry-run` 测试
7. **发布**！

---

## 💡 提示

- 第一次发布建议使用 `0.1.0` 版本
- 发布后无法删除，只能发布新版本
- 建议先在 GitHub 上创建仓库（方便管理）
- 发布前做好备份

---

**准备好了吗？**

如果准备好了，按照 `HOW_TO_PUBLISH.md` 的步骤一步步来！

如果有任何问题，随时查看文档或询问社区。

**祝你发布顺利！** 🎉

---

**文档版本**：v1.0  
**项目状态**：已准备好发布（只差账号配置）

