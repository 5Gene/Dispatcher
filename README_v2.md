# Action Dispatch - Python v2 (改进版)

## ⚠️ 重要更新

**原始 v1 版本存在问题**：不是真正的静态注册，允许运行时动态注册。

**v2 版本改进**：
- ✅ 显式初始化机制
- ✅ 冻结机制防止运行时修改
- ✅ 更好的错误检测
- ✅ 注册位置追踪

**推荐使用 v2 版本！**

---

## 快速开始

### 安装

```bash
# 只需 Python 3.7+，无需额外依赖
cd action_dispatch/py
```

### 基础使用

```python
from action_dispatch_v2 import dispatcher.action, dispatch, init_actions
from dataclasses import dataclass

@dataclass
class Event:
    id: int
    message: str

# 1. 定义 actions（模块顶层）
@action(regex=r"^user/\d+$", priority=10)
def handle_user(event: Event):
    print(f"用户操作: {event.id}")

@action(regex=r"^critical/.*$", priority=100, sync=True)
def handle_critical(event: Event):
    print(f"关键操作: {event.id} (独占执行)")

# 2. 显式初始化（必须！）
if __name__ == '__main__':
    init_actions()  # 冻结注册表
    
    # 3. 正常使用
    dispatch("user/123", Event(123, "test"))
    dispatch("critical/op", Event(999, "important"))
```

---

## 核心改进

### 改进 1：显式初始化

```python
# ❌ v1：无需初始化，任何时候都可以注册
from action_dispatch import dispatcher.action, dispatch

@action(regex=r"user/.*")
def handler(event): pass

dispatch("user/123", event)  # 直接使用（危险）

# ✅ v2：必须显式初始化
from action_dispatch_v2 import dispatcher.action, dispatch, init_actions

@action(regex=r"user/.*")
def handler(event): pass

init_actions()  # 显式初始化并冻结
dispatch("user/123", event)  # 之后才能使用
```

### 改进 2：冻结机制

```python
# v1：可以运行时注册
def some_function():
    @action(regex=r"runtime/.*")  # ❌ 允许！
    def runtime_handler(event):
        pass

# v2：运行时注册被阻止
init_actions()  # 冻结

try:
    @action(regex=r"runtime/.*")
    def runtime_handler(event):
        pass
except RegistryFrozenError:
    print("✓ 正确地阻止了运行时注册")
```

### 改进 3：位置追踪

```python
# v2 显示注册位置
from action_dispatch_v2 import list_actions

for info in list_actions():
    print(f"{info.regex}")
    print(f"  定义于: {info.module}:{info.line}")  # ← 显示位置

# 输出：
# ^user/\d+$
#   定义于: myapp.handlers:42
```

---

## API 文档

### @action 装饰器

```python
@action(
    regex: str,           # 必需：匹配正则
    priority: int = 0,    # 可选：优先级
    description: str = "", # 可选：描述
    sync: bool = False    # 可选：是否全局排他
)
```

**⚠️ 重要约束**：
1. **只能在模块顶层使用**
2. **不要在函数内使用**
3. **不要在条件语句中使用**
4. **不要在初始化后使用**

### init_actions()

显式初始化注册表并冻结。

```python
def init_actions():
    """
    初始化并冻结注册表
    
    调用后：
    - 构建分层索引
    - 冻结注册表
    - 之后无法添加新 action
    """
```

**必须在任何 dispatch() 调用前调用！**

### init_actions_auto()

自动导入模块并初始化。

```python
def init_actions_auto(module_names: Optional[List[str]] = None):
    """
    自动导入指定模块并初始化
    
    参数：
        module_names: 要导入的模块列表
    
    示例：
        init_actions_auto(['myapp.handlers', 'myapp.api'])
    """
```

### dispatch()

事件分发函数（与 v1 相同）。

```python
def dispatch(key: str, event: Any) -> None:
    """
    分发事件到匹配的 action
    
    异常：
        NoMatchError: 没有匹配的 action
        RegistryNotInitializedError: 未调用 init_actions()
    """
```

---

## 使用模式

### 模式 1：单文件应用

```python
# app.py
from action_dispatch_v2 import dispatcher.action, dispatch, init_actions

@action(regex=r"^user/.*$")
def handle_user(event):
    print(f"User: {event}")

if __name__ == '__main__':
    init_actions()  # 初始化
    dispatch("user/123", {"id": 123})
```

### 模式 2：多模块应用

```python
# handlers/user.py
from action_dispatch_v2 import dispatcher.action

@action(regex=r"^user/.*$", priority=10)
def handle_user(event):
    print(f"User: {event}")

# handlers/order.py
from action_dispatch_v2 import dispatcher.action

@action(regex=r"^order/.*$", priority=5)
def handle_order(event):
    print(f"Order: {event}")

# main.py
from action_dispatch_v2 import init_actions_auto, dispatch

def main():
    # 自动导入并初始化
    init_actions_auto([
        'handlers.user',
        'handlers.order',
    ])
    
    # 正常使用
    dispatch("user/123", {"id": 123})
    dispatch("order/456", {"id": 456})

if __name__ == '__main__':
    main()
```

### 模式 3：显式导入

```python
# main.py
from action_dispatch_v2 import init_actions, dispatch

# 导入所有 handler 模块
from handlers import user, order, payment

def main():
    # 初始化（所有模块已导入）
    init_actions()
    
    # 正常使用
    dispatch("user/123", {"id": 123})

if __name__ == '__main__':
    main()
```

---

## 错误处理

### 错误 1：忘记初始化

```python
@action(regex=r"user/.*")
def handle_user(event):
    pass

# ❌ 忘记调用 init_actions()
dispatch("user/123", event)

# 异常：RegistryNotInitializedError
# 注册表未初始化！请先调用 init_actions()
```

### 错误 2：运行时注册

```python
init_actions()  # 冻结

# ❌ 尝试在初始化后注册
@action(regex=r"late/.*")
def late_handler(event):
    pass

# 异常：RegistryFrozenError
# 注册表已冻结，不允许运行时注册 action
```

### 错误 3：在函数内定义

```python
# ❌ 错误：在函数内定义
def create_handlers():
    @action(regex=r"...")
    def handler(event):
        pass

# 问题：只有调用 create_handlers() 时才注册
# 如果在 init_actions() 之后调用，会抛出 RegistryFrozenError
```

---

## 最佳实践

### ✅ 推荐

```python
# 1. 所有 action 在模块顶层
@action(regex=r"^user/.*$")
def handle_user(event):
    pass

@action(regex=r"^order/.*$")
def handle_order(event):
    pass

# 2. 主程序入口初始化
if __name__ == '__main__':
    init_actions()  # 只调用一次
    main()          # 开始业务逻辑

# 3. 按优先级组织
@action(regex=r"^critical/.*$", priority=100, sync=True)
def handle_critical(event):  # 高优先级
    pass

@action(regex=r"^normal/.*$", priority=10)
def handle_normal(event):   # 普通优先级
    pass
```

### ❌ 避免

```python
# ❌ 不要在函数内定义
def init_handlers():
    @action(regex=r"...")
    def handler(event):
        pass

# ❌ 不要条件定义
if DEBUG:
    @action(regex=r"debug/.*")
    def debug_handler(event):
        pass

# ❌ 不要在初始化后注册
init_actions()
@action(regex=r"late/.*")  # RegistryFrozenError
def late_handler(event):
    pass

# ❌ 不要多次初始化
init_actions()
init_actions()  # 会被忽略（已冻结）
```

---

## 与 v1 对比

| 特性 | v1 | v2 |
|------|----|----|
| 静态注册 | ❌ 伪静态 | ⚠️ 半静态 |
| 防运行时修改 | ❌ 无保护 | ✅ 冻结机制 |
| 显式初始化 | ❌ | ✅ |
| 位置追踪 | ❌ | ✅ |
| 重复注册检测 | ❌ | ✅ |
| 错误信息 | ⚠️ 基本 | ✅ 详细 |
| 适用场景 | 原型 | 生产 |

**迁移指南**：参见 `VERSION_COMPARISON.md`

---

## 运行测试

```bash
# 基础测试
python action_dispatch_v2.py

# 预期输出
# ============================================================
# Action Dispatch v2 - 改进版测试
# ============================================================
# 
# 🔧 正在初始化 action 注册表...
#    发现 3 个 action
#    精确匹配: 0 个
#    前缀匹配: 2 个
#    正则匹配: 1 个
# ✅ 注册表初始化完成并已冻结
# 
# [测试输出...]
# 
# ✓ 正确地阻止了运行时注册
```

---

## 文档

- `STATIC_REGISTRATION_ISSUE.md` - 问题分析与解决方案
- `VERSION_COMPARISON.md` - v1 vs v2 详细对比
- `README.md` - v1 文档（不推荐）
- `README_v2.md` - 本文档

---

## 性能

与 v1 相同：
- 精确匹配：~15 μs
- 前缀匹配：~20 μs
- 复杂正则：~50 μs

冻结机制无性能影响（只在初始化时检查）。

---

## 限制

### Python 语言的固有限制

1. **无真正的编译期**：无法像 Rust 那样在编译期注册
2. **依赖开发者规范**：需要遵守最佳实践
3. **模块导入顺序**：可能影响注册顺序

### v2 的限制

1. 需要显式调用 `init_actions()`
2. 无法完全阻止模块导入时的动态行为
3. 多次调用 `init_actions()` 会被忽略（已冻结）

---

## 总结

### Python v2 vs Rust

| 维度 | Python v2 | Rust |
|------|-----------|------|
| 静态注册 | ⚠️ 半静态 | ✅ 完全静态 |
| 类型安全 | ⚠️ 类型提示 | ✅ 编译期 |
| 性能 | B+ (15-50 μs) | A++ (0.1-10 μs) |
| 易用性 | ✅ 高 | ⚠️ 中等 |
| 开发速度 | ✅ 快 | ⚠️ 较慢 |
| 可靠性 | ⚠️ 中等 | ✅ 极高 |

### 使用建议

- **生产环境（高可靠）**：使用 **Rust**
- **生产环境（Python栈）**：使用 **Python v2**
- **原型开发**：使用 **Python v2**（更安全）
- **学习研究**：两者都研究

---

**版本**：2.0  
**状态**：✅ 生产可用（需遵守规范）  
**推荐**：⭐⭐⭐⭐（相比 v1：⭐⭐）

---

**感谢用户发现原始版本的问题！v2 是 Python 限制下的最佳解决方案。** 🙏

