# Python 单例模式详解 vs Rust 对比

## 🐛 问题根源

### Python 的模块导入机制

**问题代码**：
```python
# action_dispatch_v3.py
_registry = LayeredRegistry()  # 模块级变量
_global_lock = FastRWLock()
```

**为什么有问题**？

```python
# 场景 1：普通导入（没问题）
from dispatcher3 import dispatcher.action_dispatch_v3
# Python 会缓存模块，_registry 是同一个实例 ✅

# 场景 2：多次导入（没问题）
import dispatcher3.action_dispatch_v3 as ad1
import dispatcher3.action_dispatch_v3 as ad2
# ad1._registry 和 ad2._registry 是同一个对象 ✅

# 场景 3：reload（有问题！）
import importlib

importlib.reload(action_dispatch_v3)
# 会重新执行模块代码，创建新的 _registry！❌

# 场景 4：不同路径导入（可能有问题）
import dispatcher3.action_dispatch_v3
import py.action_dispatch_v3  # 如果路径不同
# 可能被识别为不同模块，创建多个实例！❌
```

**核心问题**：
- Python 的模块级变量在 **模块重新加载** 时会重新创建
- 如果通过不同路径导入，可能被识别为不同模块
- 在某些特殊场景（热重载、动态导入）可能创建多个实例

---

## ✅ 解决方案 1：单例模式（当前方案）

### 原理

```python
class _GlobalState:
    _instance = None  # 类变量，所有实例共享
    _lock = threading.Lock()  # 线程锁
    
    def __new__(cls):
        # __new__ 在 __init__ 之前调用，控制对象创建
        if cls._instance is None:
            with cls._lock:  # 线程安全
                if cls._instance is None:  # 双重检查
                    cls._instance = super().__new__(cls)
                    cls._instance.registry = LayeredRegistry()
                    cls._instance.global_lock = FastRWLock()
        return cls._instance  # 总是返回同一个实例
```

**关键点**：

1. **类变量 vs 实例变量**：
   ```python
   # 类变量：所有实例共享
   class A:
       _instance = None  # 类变量
   
   # 实例变量：每个实例独立
   class B:
       def __init__(self):
           self.value = 1  # 实例变量
   ```

2. **__new__ 控制对象创建**：
   ```python
   class Singleton:
       def __new__(cls):
           print("创建对象")
           return super().__new__(cls)
       
       def __init__(self):
           print("初始化对象")
   
   # 调用顺序：__new__ → __init__
   # __new__ 决定是否创建新对象
   # __init__ 初始化已创建的对象
   ```

3. **双重检查锁定**：
   ```python
   if cls._instance is None:  # 第一次检查（无锁，快）
       with cls._lock:  # 获取锁
           if cls._instance is None:  # 第二次检查（有锁，安全）
               cls._instance = ...
   ```
   
   **为什么需要两次检查**？
   ```
   线程 A                     线程 B
   检查 _instance is None ✓
   等待锁...                  检查 _instance is None ✓
   获取锁                     等待锁...
   再次检查 _instance is None ✓
   创建实例
   释放锁
                              获取锁
                              再次检查 _instance is None ✗  ← 第二次检查避免重复创建
                              直接返回已有实例
                              释放锁
   ```

### 优点

- ✅ 线程安全
- ✅ 延迟初始化（第一次使用时才创建）
- ✅ 即使模块 reload 也保持单例

### 缺点

- ⚠️ 代码复杂（~20 行）
- ⚠️ 有锁开销（首次创建时）

---

## ✅ 解决方案 2：更简单的方式

### 方式 2.1：使用模块本身作为单例（推荐）⭐⭐⭐

**原理**：Python 的模块本身就是单例

```python
# action_dispatch_v3.py

# 不使用类变量，直接使用模块级变量
# Python 保证模块只加载一次（sys.modules 缓存）

_registry = LayeredRegistry()
_global_lock = FastRWLock()

# 这样就够了！
# 只要通过同一个模块路径导入，就是同一个实例
```

**为什么可以这样**？

```python
import sys

# 导入模块
import dispatcher3.action_dispatch_v3

# Python 会把模块缓存到 sys.modules
print(sys.modules['action_dispatch_v3'])  # <module 'action_dispatch_v3'>

# 再次导入，从缓存获取，不会重新执行
import dispatcher3.action_dispatch_v3 as ad2
# ad2 和 action_dispatch_v3 是同一个模块对象
```

**结论**：
- ✅ **大多数情况下，模块级变量就够了**
- ✅ Python 的模块机制本身保证单例
- ⚠️ 唯一的问题是 `importlib.reload()`，但这在生产环境很少用

**建议**：
```python
# 如果你的应用不会使用 reload，那么：
_registry = LayeredRegistry()  # 这样就够了
_global_lock = FastRWLock()

# 无需复杂的单例模式！
```

### 方式 2.2：使用 functools.lru_cache ⭐⭐

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_global_state():
    """获取全局状态（缓存为单例）"""
    class State:
        def __init__(self):
            self.registry = LayeredRegistry()
            self.global_lock = FastRWLock()
    return State()

# 使用
_state = get_global_state()
_registry = _state.registry
_global_lock = _state.global_lock
```

**优点**：
- ✅ 简单（3 行）
- ✅ 线程安全（lru_cache 内部有锁）
- ✅ 自动单例

### 方式 2.3：使用元类 ⭐

```python
class SingletonMeta(type):
    """单例元类"""
    _instances = {}
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class GlobalState(metaclass=SingletonMeta):
    """使用元类的单例"""
    def __init__(self):
        self.registry = LayeredRegistry()
        self.global_lock = FastRWLock()


# 使用
_state = GlobalState()  # 总是返回同一个实例
_registry = _state.registry
```

### 方式 2.4：使用 Borg 模式 ⭐

```python
class GlobalState:
    """Borg 模式：共享状态而非共享实例"""
    _shared_state = {}
    
    def __init__(self):
        self.__dict__ = self._shared_state
        if not hasattr(self, 'registry'):
            self.registry = LayeredRegistry()
            self.global_lock = FastRWLock()


# 使用
_state = GlobalState()  # 可以创建多个实例
_registry = _state.registry  # 但所有实例共享状态
```

---

## 🦀 Rust 版本有这类问题吗？

### 答案：**没有！** ✅

### Rust 的解决方案

**Rust 代码**：
```rust
// action_dispatch_core/src/lib.rs

use once_cell::sync::Lazy;

// 全局静态变量
static ACTION_REGISTRY: Lazy<LayeredRegistry> = Lazy::new(|| {
    // 构建注册表
    LayeredRegistry::new(...)
});

static GLOBAL_DISPATCH_LOCK: RwLock<()> = RwLock::new(());
```

### 为什么 Rust 不需要单例模式？

#### 1. **真正的静态变量**

**Python**：

```python
# 模块级变量（本质是模块对象的属性）
_registry = LayeredRegistry()  # 可能被重新创建

# 运行时初始化
import dispatcher3.action_dispatch  # 执行代码，创建对象
```

**Rust**：
```rust
// 真正的静态变量（编译期确定）
static ACTION_REGISTRY: Lazy<...> = Lazy::new(...);

// 编译后是内存中的固定地址
// 0x123456: ACTION_REGISTRY
// 程序启动到结束，地址不变
```

**区别**：
- Python：模块级变量是运行时创建的对象
- Rust：静态变量是编译期分配的内存地址

#### 2. **Lazy 初始化保证单次**

```rust
use once_cell::sync::Lazy;

static REGISTRY: Lazy<Registry> = Lazy::new(|| {
    println!("初始化一次");
    Registry::new()
});

// 第一次访问
let r1 = &*REGISTRY;  // 输出：初始化一次

// 再次访问
let r2 = &*REGISTRY;  // 无输出，直接返回

// r1 和 r2 是同一个对象的引用
assert_eq!(r1 as *const _, r2 as *const _);
```

**原理**：
- `Lazy<T>` 内部使用 `Once` 保证只初始化一次
- 线程安全（使用原子操作和锁）
- 一旦初始化，永不改变

#### 3. **无法 "重新加载" 模块**

**Python**：
```python
import importlib
importlib.reload(module)  # 可以重新加载！
```

**Rust**：
```rust
// Rust 编译后是二进制文件
// 无法 "重新加载" 代码
// 要更新代码必须重新编译并重启程序
```

#### 4. **编译期保证**

**Rust 的类型系统**：
```rust
// 如果尝试创建多个实例，编译错误
static REGISTRY1: Registry = Registry::new();  // ❌ 编译错误
static REGISTRY2: Registry = Registry::new();  // Registry::new() 不是 const fn

// 必须使用 Lazy
static REGISTRY: Lazy<Registry> = Lazy::new(|| Registry::new());  // ✅

// 而且，静态变量名称冲突会在编译期发现
static REGISTRY: ... = ...;
static REGISTRY: ... = ...;  // ❌ 编译错误：重复定义
```

### Rust vs Python 对比表

| 维度 | Python | Rust |
|------|--------|------|
| **变量类型** | 运行时对象 | 编译期静态变量 |
| **初始化** | 模块加载时 | 首次访问时（Lazy） |
| **是否唯一** | ⚠️ 取决于导入路径 | ✅ 绝对唯一 |
| **线程安全** | ⚠️ 需要手动保证 | ✅ 编译期保证 |
| **重新加载** | ✅ 支持（可能破坏单例） | ❌ 不支持 |
| **内存地址** | 运行时分配 | 编译期固定 |
| **需要单例模式** | ⚠️ 某些场景需要 | ✅ 不需要 |

---

## 📊 性能对比

### Python 单例模式开销

```python
# 方案 1：当前方案（双重检查锁）
def __new__(cls):
    if cls._instance is None:  # ~10 ns
        with cls._lock:  # ~100 ns（首次）
            if cls._instance is None:
                cls._instance = ...  # ~1000 ns
    return cls._instance  # ~10 ns

# 首次创建：~1200 ns
# 后续访问：~20 ns
```

```python
# 方案 2：模块级变量（无单例模式）
_registry = LayeredRegistry()  # 模块加载时创建

# 访问：~5 ns（直接属性访问）
```

```python
# 方案 3：lru_cache
@lru_cache(maxsize=1)
def get_state():
    return State()

# 首次：~500 ns
# 后续：~50 ns（缓存查找）
```

### Rust 静态变量开销

```rust
static REGISTRY: Lazy<Registry> = Lazy::new(|| Registry::new());

// 首次访问：~100 ns（原子操作 + 初始化）
// 后续访问：~1 ns（直接内存访问）
```

**对比**：
- Python 模块变量：~5 ns
- Python 单例模式：~20 ns
- Rust 静态变量：**~1 ns** ⭐

---

## 💡 最佳实践建议

### Python 项目

**场景 1：普通应用（99% 的情况）**

```python
# 直接使用模块级变量，无需单例模式
_registry = LayeredRegistry()
_global_lock = FastRWLock()
```

**推荐理由**：
- ✅ 简单
- ✅ Python 模块机制已保证唯一
- ✅ 性能最好（~5 ns）

**场景 2：需要支持 reload**

```python
# 使用单例模式
class _GlobalState:
    _instance = None
    # ...
```

**推荐理由**：
- ✅ 即使 reload 也保持单例
- ✅ 线程安全
- ⚠️ 略复杂，但可靠

**场景 3：追求简洁**

```python
# 使用 lru_cache
@lru_cache(maxsize=1)
def get_state():
    class State:
        def __init__(self):
            self.registry = LayeredRegistry()
    return State()

_state = get_state()
```

**推荐理由**：
- ✅ 简洁（3 行）
- ✅ 线程安全
- ✅ 自动单例

### Rust 项目

```rust
// 直接使用静态变量 + Lazy
use once_cell::sync::Lazy;

static REGISTRY: Lazy<Registry> = Lazy::new(|| {
    Registry::new()
});

// 无需任何单例模式！
```

**推荐理由**：
- ✅ 编译期保证唯一
- ✅ 线程安全
- ✅ 性能极致
- ✅ 零运行时开销

---

## 🎯 总结

### 问题根源

- Python：模块级变量在某些场景（reload、不同路径导入）可能不唯一
- Rust：静态变量编译期确定，永远唯一

### 解决方案

**Python**：
1. **推荐**：直接用模块级变量（99% 场景够用）
2. 需要 reload：单例模式
3. 追求简洁：lru_cache

**Rust**：
- 直接用 `static` + `Lazy`（无需单例模式）

### 性能

| 方案 | 访问开销 | 复杂度 |
|------|---------|-------|
| Python 模块变量 | ~5 ns | ⭐ 简单 |
| Python 单例 | ~20 ns | ⭐⭐⭐ 复杂 |
| Python lru_cache | ~50 ns | ⭐⭐ 中等 |
| Rust static | **~1 ns** | ⭐ 简单 |

### 建议

**当前实现（单例模式）**：
- ✅ 保留（已实现，线程安全，支持 reload）
- ⚠️ 但大多数场景不需要这么复杂

**更简单的替代**：
- 如果不需要 reload：直接用模块级变量
- 如果追求简洁：使用 lru_cache

**Rust 版本**：
- ✅ 完美（无需任何额外工作）
- ✅ 性能最优
- ✅ 编译期保证

---

**文档版本**：v1.0  
**最后更新**：2024年

**结论**：Python 需要考虑单例问题，Rust 不需要。当前实现（单例模式）是保守但可靠的选择。

