# 🏗️ 按业务模块组织 Action 的最佳实践

## 📋 目录

- [概述](#概述)
- [目录结构](#目录结构)
- [工作原理](#工作原理)
- [完整示例](#完整示例)
- [优缺点分析](#优缺点分析)
- [适用场景](#适用场景)
- [与其他方案对比](#与其他方案对比)
- [实战建议](#实战建议)

---

## 概述

**按业务模块组织**是一种将相关的 action handlers 按业务领域分组的项目结构方式。

### 核心思想

每个业务模块有自己的子目录，包含：
- `mod.rs` - 模块声明文件
- 多个 action handler 文件
- 共享的类型定义

---

## 目录结构

### 完整结构

```
src/
├── main.rs                    # 入口文件
├── lib.rs                     # 库文件（可选）
│
├── user/                      # 用户业务模块
│   ├── mod.rs                 # 用户模块声明
│   ├── profile.rs             # 用户资料相关 action
│   ├── settings.rs            # 用户设置相关 action
│   ├── authentication.rs      # 用户认证相关 action
│   └── types.rs               # 用户相关类型定义
│
├── order/                     # 订单业务模块
│   ├── mod.rs                 # 订单模块声明
│   ├── create.rs              # 创建订单 action
│   ├── query.rs               # 查询订单 action
│   ├── payment.rs             # 订单支付 action
│   ├── shipping.rs            # 订单发货 action
│   └── types.rs               # 订单相关类型定义
│
├── product/                   # 产品业务模块
│   ├── mod.rs                 # 产品模块声明
│   ├── catalog.rs             # 产品目录 action
│   ├── detail.rs              # 产品详情 action
│   ├── inventory.rs           # 库存管理 action
│   └── types.rs               # 产品相关类型定义
│
└── admin/                     # 管理业务模块
    ├── mod.rs                 # 管理模块声明
    ├── users.rs               # 用户管理 action
    ├── reports.rs             # 报表管理 action
    ├── settings.rs            # 系统设置 action
    └── types.rs               # 管理相关类型定义
```

---

## 工作原理

### 第 1 步：入口文件导入顶层模块

```rust
// src/main.rs
mod user;     // 导入 user 模块
mod order;    // 导入 order 模块
mod product;  // 导入 product 模块
mod admin;    // 导入 admin 模块

fn main() {
    // 所有模块的 action 都已注册
    use action_dispatch::dispatch;
    
    dispatch("user/profile/123", event)?;
    dispatch("order/create", event)?;
    dispatch("product/detail/456", event)?;
    dispatch("admin/users/list", event)?;
}
```

**关键点**：
- ✅ 入口文件只需声明顶层业务模块
- ✅ 每个业务模块 4 行
- ✅ 清晰的模块边界

---

### 第 2 步：每个模块的 mod.rs 管理内部文件

```rust
// src/user/mod.rs
pub mod profile;          // 导出 user/profile.rs
pub mod settings;         // 导出 user/settings.rs
pub mod authentication;   // 导出 user/authentication.rs
pub mod types;            // 导出类型定义

// 可选：重新导出常用类型
pub use types::{UserEvent, UserProfile, UserSettings};
```

**关键点**：
- ✅ `mod.rs` 是模块的"入口"
- ✅ 声明并导出子文件
- ✅ 可以重新导出类型，简化导入

---

### 第 3 步：具体的 action handler 文件

```rust
// src/user/profile.rs
use action_dispatch::action;
use super::types::UserEvent;  // 使用同模块的类型

/// 查看用户资料
#[action(regex = r"^user/profile/\d+$", priority = 100)]
pub fn view_profile(event: UserEvent) {
    println!("查看用户 {} 的资料", event.user_id);
}

/// 编辑用户资料
#[action(regex = r"^user/profile/\d+/edit$", priority = 99)]
pub fn edit_profile(event: UserEvent) {
    println!("编辑用户 {} 的资料", event.user_id);
}
```

**关键点**：
- ✅ 每个文件关注单一职责
- ✅ 使用 `super::types` 导入同模块类型
- ✅ 相关的 action 在同一文件

---

## 完整示例

### 示例 1：用户模块

#### 文件结构
```
user/
├── mod.rs
├── profile.rs
├── settings.rs
├── authentication.rs
└── types.rs
```

#### user/mod.rs
```rust
//! 用户业务模块
//! 
//! 包含所有与用户相关的 action handlers

pub mod profile;
pub mod settings;
pub mod authentication;
pub mod types;

// 重新导出常用类型
pub use types::{UserEvent, UserProfile, UserSettings};
```

#### user/types.rs
```rust
//! 用户模块的类型定义

/// 用户事件
#[derive(Clone, Debug)]
pub struct UserEvent {
    pub user_id: u64,
    pub action: String,
    pub data: serde_json::Value,
}

/// 用户资料
#[derive(Clone, Debug)]
pub struct UserProfile {
    pub id: u64,
    pub name: String,
    pub email: String,
}

/// 用户设置
#[derive(Clone, Debug)]
pub struct UserSettings {
    pub user_id: u64,
    pub theme: String,
    pub language: String,
}
```

#### user/profile.rs
```rust
//! 用户资料相关的 action handlers

use action_dispatch::action;
use super::types::UserEvent;

/// 查看用户资料
#[action(regex = r"^user/profile/\d+$", priority = 100)]
pub fn view_profile(event: UserEvent) {
    println!("查看用户资料: {}", event.user_id);
    // 业务逻辑...
}

/// 编辑用户资料
#[action(regex = r"^user/profile/\d+/edit$", priority = 99)]
pub fn edit_profile(event: UserEvent) {
    println!("编辑用户资料: {}", event.user_id);
    // 业务逻辑...
}

/// 上传用户头像
#[action(regex = r"^user/profile/\d+/avatar$", priority = 98)]
pub fn upload_avatar(event: UserEvent) {
    println!("上传头像: {}", event.user_id);
    // 业务逻辑...
}
```

#### user/settings.rs
```rust
//! 用户设置相关的 action handlers

use action_dispatch::action;
use super::types::UserEvent;

/// 查看用户设置
#[action(regex = r"^user/settings/\d+$", priority = 90)]
pub fn view_settings(event: UserEvent) {
    println!("查看设置: {}", event.user_id);
    // 业务逻辑...
}

/// 更新用户设置
#[action(regex = r"^user/settings/\d+/update$", priority = 89)]
pub fn update_settings(event: UserEvent) {
    println!("更新设置: {}", event.user_id);
    // 业务逻辑...
}
```

#### user/authentication.rs
```rust
//! 用户认证相关的 action handlers

use action_dispatch::action;
use super::types::UserEvent;

/// 用户登录
#[action(regex = r"^user/login$", priority = 200, sync = true)]
pub fn login(event: UserEvent) {
    println!("用户登录: {}", event.user_id);
    // 关键操作，使用 sync = true
}

/// 用户登出
#[action(regex = r"^user/logout$", priority = 199)]
pub fn logout(event: UserEvent) {
    println!("用户登出: {}", event.user_id);
}

/// 密码重置
#[action(regex = r"^user/reset-password$", priority = 198, sync = true)]
pub fn reset_password(event: UserEvent) {
    println!("密码重置: {}", event.user_id);
    // 关键操作，使用 sync = true
}
```

---

### 示例 2：订单模块

#### 文件结构
```
order/
├── mod.rs
├── create.rs
├── query.rs
├── payment.rs
├── shipping.rs
└── types.rs
```

#### order/mod.rs
```rust
//! 订单业务模块

pub mod create;
pub mod query;
pub mod payment;
pub mod shipping;
pub mod types;

pub use types::{OrderEvent, Order, OrderStatus};
```

#### order/types.rs
```rust
//! 订单模块的类型定义

#[derive(Clone, Debug)]
pub struct OrderEvent {
    pub order_id: String,
    pub user_id: u64,
    pub action: String,
}

#[derive(Clone, Debug)]
pub struct Order {
    pub id: String,
    pub user_id: u64,
    pub total: f64,
    pub status: OrderStatus,
}

#[derive(Clone, Debug)]
pub enum OrderStatus {
    Pending,
    Paid,
    Shipped,
    Completed,
    Cancelled,
}
```

#### order/create.rs
```rust
//! 订单创建相关的 action handlers

use action_dispatch::action;
use super::types::OrderEvent;

/// 创建订单
#[action(regex = r"^order/create$", priority = 100)]
pub fn create_order(event: OrderEvent) {
    println!("创建订单: {}", event.order_id);
    // 业务逻辑...
}

/// 订单草稿
#[action(regex = r"^order/draft$", priority = 99)]
pub fn draft_order(event: OrderEvent) {
    println!("保存订单草稿: {}", event.order_id);
    // 业务逻辑...
}
```

#### order/payment.rs
```rust
//! 订单支付相关的 action handlers

use action_dispatch::action;
use super::types::OrderEvent;

/// 订单支付
#[action(regex = r"^order/\w+/pay$", priority = 90, sync = true)]
pub fn pay_order(event: OrderEvent) {
    println!("订单支付: {}", event.order_id);
    // 关键操作，使用 sync = true
}

/// 支付回调
#[action(regex = r"^order/\w+/payment-callback$", priority = 89)]
pub fn payment_callback(event: OrderEvent) {
    println!("支付回调: {}", event.order_id);
    // 业务逻辑...
}

/// 退款
#[action(regex = r"^order/\w+/refund$", priority = 88, sync = true)]
pub fn refund_order(event: OrderEvent) {
    println!("订单退款: {}", event.order_id);
    // 关键操作，使用 sync = true
}
```

---

### 示例 3：主入口文件

```rust
// src/main.rs
use action_dispatch::{dispatch, list_actions};

// 导入所有业务模块
mod user;
mod order;
mod product;
mod admin;

fn main() {
    println!("🚀 启动 Action Dispatch 系统");
    
    // 列出所有已注册的 action
    println!("\n📊 已注册的 action:");
    for action in list_actions() {
        println!("  - {} (优先级: {})", action.regex, action.priority);
    }
    
    // 测试各个模块的 action
    test_user_actions();
    test_order_actions();
    test_product_actions();
    test_admin_actions();
}

fn test_user_actions() {
    println!("\n🧪 测试用户模块");
    
    let event = user::UserEvent {
        user_id: 123,
        action: "view".to_string(),
        data: serde_json::json!({}),
    };
    
    dispatch("user/profile/123", event.clone()).unwrap();
    dispatch("user/settings/123", event.clone()).unwrap();
    dispatch("user/login", event).unwrap();
}

fn test_order_actions() {
    println!("\n🧪 测试订单模块");
    
    let event = order::OrderEvent {
        order_id: "ORD001".to_string(),
        user_id: 123,
        action: "create".to_string(),
    };
    
    dispatch("order/create", event.clone()).unwrap();
    dispatch("order/ORD001/pay", event).unwrap();
}

fn test_product_actions() {
    println!("\n🧪 测试产品模块");
    // ...
}

fn test_admin_actions() {
    println!("\n🧪 测试管理模块");
    // ...
}
```

---

## 优缺点分析

### ✅ 优点

#### 1. **清晰的业务边界**

```
user/      ← 用户相关的所有东西都在这里
order/     ← 订单相关的所有东西都在这里
product/   ← 产品相关的所有东西都在这里
```

- ✅ 每个模块独立
- ✅ 职责明确
- ✅ 易于理解

---

#### 2. **符合 Rust 惯例**

```rust
// 标准的 Rust 模块组织方式
mod user {
    pub mod profile;
    pub mod settings;
}
```

- ✅ Rust 社区认可的结构
- ✅ IDE 支持好
- ✅ 自动补全完善

---

#### 3. **易于协作**

```
团队分工：
- Alice 负责 user/
- Bob 负责 order/
- Charlie 负责 product/

冲突最小化！
```

- ✅ 减少文件冲突
- ✅ 并行开发
- ✅ 代码审查更容易

---

#### 4. **便于重构**

```rust
// 移动整个模块很简单
// 重命名模块也很简单

// 之前
mod user;

// 之后
mod users;  // 只需改一行
```

- ✅ 模块内部重构不影响外部
- ✅ 重命名模块只需改入口
- ✅ 移动文件保持结构

---

#### 5. **类型共享方便**

```rust
// order/types.rs
pub struct OrderEvent { ... }
pub struct Order { ... }

// order/create.rs
use super::types::{OrderEvent, Order};  // 简单

// order/payment.rs
use super::types::{OrderEvent, Order};  // 简单
```

- ✅ 同模块类型共享方便
- ✅ 使用 `super::types` 即可
- ✅ 避免循环依赖

---

### ❌ 缺点

#### 1. **需要多个 mod.rs 文件**

```
每个模块都需要一个 mod.rs：
user/mod.rs
order/mod.rs
product/mod.rs
admin/mod.rs
```

- ⚠️ 增加文件数量
- ⚠️ 每次添加文件都要更新 mod.rs

---

#### 2. **入口文件需要声明所有顶层模块**

```rust
// src/main.rs
mod user;     // 需要手动添加
mod order;    // 需要手动添加
mod product;  // 需要手动添加
mod admin;    // 需要手动添加
```

- ⚠️ 添加新模块需要改 main.rs
- ⚠️ 不如"集中管理"方案简洁

---

#### 3. **跨模块导入稍微复杂**

```rust
// 从 order 模块导入 user 模块的类型
use crate::user::types::UserEvent;  // 需要 crate::

// 而不是
use super::types::UserEvent;  // 这只能用于同模块
```

- ⚠️ 跨模块导入路径较长
- ⚠️ 需要理解 `crate::`, `super::`, `self::`

---

## 适用场景

### ✅ 非常适合

#### 1. **中大型项目**

```
> 50 个 action handlers
明确的业务模块划分
多人协作开发
```

**原因**：
- ✅ 清晰的模块边界
- ✅ 减少文件冲突
- ✅ 易于维护

---

#### 2. **微服务架构**

```
每个模块对应一个微服务：
user/ → 用户服务
order/ → 订单服务
product/ → 产品服务
```

**原因**：
- ✅ 模块独立性强
- ✅ 容易拆分成独立服务
- ✅ API 边界清晰

---

#### 3. **团队协作**

```
多人团队，各自负责不同业务模块
```

**原因**：
- ✅ 减少代码冲突
- ✅ 清晰的职责划分
- ✅ 并行开发效率高

---

### ⚠️ 可能不适合

#### 1. **小型项目**

```
< 20 个 action handlers
只有少量业务模块
```

**问题**：
- ❌ 过度设计
- ❌ 增加不必要的复杂度

**建议**：使用**集中管理**方案（方案 1）

---

#### 2. **快速原型**

```
需要快速迭代
业务边界不清晰
```

**问题**：
- ❌ 频繁重构模块结构
- ❌ 增加开发成本

**建议**：先使用简单结构，稳定后再重构

---

## 与其他方案对比

### 方案对比表

| 特性 | 方案 1: 集中管理 | 方案 2: 自动生成 | **方案 3: 业务模块** |
|------|-----------------|-----------------|-------------------|
| **入口文件** | `mod actions;` 一行 | `mod actions;` 一行 | 每个模块一行 |
| **复杂度** | ⭐ 低 | ⭐⭐⭐⭐ 高 | ⭐⭐ 中 |
| **符合 Rust 惯例** | ⭐⭐⭐⭐ 很好 | ⭐⭐ 一般 | ⭐⭐⭐⭐⭐ 完美 |
| **业务边界** | ⭐⭐⭐ 较清晰 | ⭐⭐⭐ 较清晰 | ⭐⭐⭐⭐⭐ 非常清晰 |
| **协作友好** | ⭐⭐⭐ 好 | ⭐⭐⭐ 好 | ⭐⭐⭐⭐⭐ 非常好 |
| **IDE 支持** | ⭐⭐⭐⭐ 很好 | ⭐⭐⭐ 好 | ⭐⭐⭐⭐⭐ 完美 |
| **维护成本** | ⭐⭐⭐⭐ 低 | ⭐⭐ 较高 | ⭐⭐⭐ 中 |
| **适合规模** | 小到中 | 中到大 | **中到大** |

---

### 详细对比

#### vs 方案 1（集中管理）

**方案 1 结构**：
```
actions/
  mod.rs      ← 所有模块集中在这里
  user.rs
  order.rs
  product.rs
```

**方案 3 结构**：
```
user/
  mod.rs      ← 用户模块的声明
  profile.rs
  settings.rs
order/
  mod.rs      ← 订单模块的声明
  create.rs
  payment.rs
```

| 对比项 | 方案 1 | 方案 3 |
|--------|--------|--------|
| 入口复杂度 | ✅ 一行 | ⚠️ 多行 |
| 模块独立性 | ⚠️ 较弱 | ✅ 很强 |
| 子文件组织 | ⚠️ 扁平 | ✅ 分层 |
| 团队协作 | ⚠️ 易冲突 | ✅ 少冲突 |

**结论**：
- 小项目 → 方案 1
- 大项目 → **方案 3** ✅

---

#### vs 方案 2（自动生成）

**方案 2 结构**：
```
actions/
  mod.rs      ← build.rs 自动生成
  user.rs
  order.rs
  ...
```

**方案 3 结构**：
```
user/
  mod.rs      ← 手动维护，但清晰
  profile.rs
  settings.rs
```

| 对比项 | 方案 2 | 方案 3 |
|--------|--------|--------|
| 自动化程度 | ✅ 全自动 | ⚠️ 半手动 |
| 构建复杂度 | ⚠️ 高（需要 build.rs） | ✅ 低（标准 Rust） |
| IDE 支持 | ⚠️ 可能有问题 | ✅ 完美 |
| 可控性 | ⚠️ 较弱 | ✅ 完全可控 |

**结论**：
- 需要完全自动化 → 方案 2
- 追求稳定性和标准 → **方案 3** ✅

---

## 实战建议

### 1. **何时选择方案 3**

选择业务模块组织方式，如果你的项目满足：

✅ **项目规模 > 50 个 action handlers**
✅ **有清晰的业务模块划分**
✅ **多人协作开发**
✅ **需要长期维护**
✅ **追求标准 Rust 结构**

---

### 2. **迁移策略**

#### 从方案 1 迁移到方案 3

**第 1 步**：创建模块目录
```bash
mkdir src/user
mkdir src/order
mkdir src/product
```

**第 2 步**：移动文件
```bash
mv src/actions/user*.rs src/user/
mv src/actions/order*.rs src/order/
mv src/actions/product*.rs src/product/
```

**第 3 步**：创建 mod.rs
```bash
# 在每个目录创建 mod.rs
touch src/user/mod.rs
touch src/order/mod.rs
touch src/product/mod.rs
```

**第 4 步**：更新入口
```rust
// 之前
mod actions;

// 之后
mod user;
mod order;
mod product;
```

---

### 3. **命名约定**

#### 模块名

```rust
// ✅ 好的命名
mod user;      // 清晰、简洁
mod order;
mod product;

// ❌ 避免
mod user_module;     // 冗余的 _module
mod users_actions;   // 冗余的 _actions
```

#### 文件名

```rust
// ✅ 好的命名
profile.rs       // 动词或名词
authentication.rs
settings.rs

// ❌ 避免
user_profile.rs  // 冗余的 user_ 前缀（已经在 user/ 目录下）
```

---

### 4. **类型组织**

#### 推荐：每个模块有自己的 types.rs

```
user/
  types.rs      ← UserEvent, UserProfile, etc.
  profile.rs
  settings.rs

order/
  types.rs      ← OrderEvent, Order, OrderStatus, etc.
  create.rs
  payment.rs
```

**好处**：
- ✅ 类型定义集中
- ✅ 避免循环依赖
- ✅ 易于查找

---

### 5. **跨模块依赖**

#### 如果 order 需要使用 user 的类型

```rust
// order/payment.rs
use crate::user::types::UserEvent;  // ✅ 跨模块导入

#[action(regex = r"^order/.*$")]
fn process_order(order_event: OrderEvent) {
    // 可能需要查询用户信息
    let user_event = UserEvent { ... };
    // ...
}
```

**建议**：
- ✅ 最小化跨模块依赖
- ✅ 考虑提取共享类型到单独模块（如 `common/types.rs`）

---

## 总结

### 方案 3 的核心价值

1. **清晰的业务边界** - 每个模块独立
2. **符合 Rust 惯例** - 标准的模块组织方式
3. **易于协作** - 减少文件冲突
4. **便于维护** - 模块内部重构不影响外部
5. **IDE 友好** - 完美的自动补全和导航

### 适用场景

- ✅ 中大型项目（> 50 个 action handlers）
- ✅ 多人团队协作
- ✅ 清晰的业务模块划分
- ✅ 长期维护的项目

### 与其他方案对比

- **vs 方案 1（集中管理）**：更强的模块独立性
- **vs 方案 2（自动生成）**：更稳定和标准

---

**方案 3 是追求工程化和可维护性的最佳选择！** 🏗️✨

