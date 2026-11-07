# dispatcher3

基于装饰器的 action 注册与分发。声明式注册、分层匹配、可预测的优先级规则，
运行时零依赖（仅标准库）。

```python
from dispatcher3 import action, dispatch, init_actions

@action(r"^user/[0-9]+$", priority=10)
def get_user(user_id):
    return {"id": user_id}

init_actions()
print(dispatch("user/123", 123))   # {'id': 123}
```

---

## 安装

```bash
pip install dispatcher3
```

要求 Python >= 3.8，无第三方运行时依赖。

---

## 快速开始

### 1. 声明 action

```python
from dispatcher3 import action

@action(r"^user/[0-9]+$", description="查询用户", priority=10)
def get_user(user_id):
    return {"id": user_id}

@action(r"^user/[0-9]+/update$", description="更新用户", priority=20, sync=True)
def update_user(user_id):
    return {"id": user_id, "updated": True}

@action(r"^api/v1/.*", description="v1 接口", priority=5)
def api_v1(path):
    return {"path": path}
```

### 2. 冻结注册表

```python
from dispatcher3 import init_actions

init_actions()   # 构建索引并冻结。之后不能再注册
```

冻结是有意设计：注册表在运行期只读，匹配路径因此**完全不需要加锁**。

### 3. 分发

```python
from dispatcher3 import dispatch, dispatch_async

# 同步：直接返回 handler 的返回值，异常原样抛出
result = dispatch("user/123", 123)

# 异步：返回 Future，需要并发时才用
future = dispatch_async("user/123", 123)
result = future.result(timeout=5)
```

### 4. 自动扫描包

```python
from dispatcher3 import auto_import_package_modules, init_actions

auto_import_package_modules(["myapp.handlers"])  # 只导入，触发 @action 注册
init_actions()                                    # 再冻结
```

扫描与冻结是两件事，分开调用，避免隐式副作用。

---

## API

### `action(regex, *, description="", priority=0, sync=False)`

| 参数 | 类型 | 说明 |
|---|---|---|
| `regex` | `str` | 匹配 key 的正则，唯一的位置参数 |
| `description` | `str` | 描述，仅用于 `list_actions()` |
| `priority` | `int` | 优先级，越大越优先 |
| `sync` | `bool` | `True` 表示全局排他执行 |

除 `regex` 外全部为 keyword-only。这是刻意的：旧版本
`action(regex, description, priority)` 的实现顺序与文档
`action(regex, priority, description)` 相反，位置传参会静默错位。

### `dispatch(key, event) -> Any`

同步分发，返回 handler 的返回值。

| 异常 | 场景 |
|---|---|
| `RegistryNotInitializedError` | 未调用 `init_actions()` |
| `NoMatchError` | 没有 action 匹配 `key` |
| handler 自身的异常 | 原样向上传播 |

### `dispatch_async(key, event, max_workers=None) -> Future`

提交到线程池。handler 的异常通过 `Future.result()` 重新抛出。

### 其它

| 函数 | 说明 |
|---|---|
| `init_actions()` | 构建索引并冻结注册表，幂等 |
| `is_initialized()` | 是否已冻结 |
| `reset()` | 清空并解冻，主要用于测试 |
| `list_actions()` | 按 priority 降序返回 `ActionInfo` 列表 |
| `auto_import_package_modules(names)` | 导入包下所有一级子模块 |
| `shutdown_executor(wait=True)` | 关闭异步线程池 |
| `analyze_regex(regex)` | 查看某个正则被判定成哪种策略 |

---

## 匹配优先级规则

这是最容易踩坑的地方，规则完整列在这里。

**四层短路，逐层降级：**

1. **精确匹配（EXACT）** —— 命中字典即返回，不再考察后面三层
2. **前缀匹配（PREFIX）** —— 按 `(-priority, -len(prefix))` 扫描，首个命中即返回
3. **后缀匹配（SUFFIX）** —— 按 `(-priority, -len(suffix))` 扫描，首个命中即返回
4. **正则匹配（REGEX）** —— 按 `-priority` 扫描，首个命中即返回

**层内规则：**

| 层 | 排序 | 同分时 |
|---|---|---|
| EXACT | priority 降序 | 保留先注册者 |
| PREFIX | priority 降序，其次前缀长度降序 | 更长前缀优先 |
| SUFFIX | priority 降序，其次后缀长度降序 | 更长后缀优先 |
| REGEX | priority 降序 | 保持注册顺序（稳定排序） |

**注意：层间不做 priority 比较。** 一个精确匹配的 `priority=1` 会赢过
一个前缀匹配的 `priority=999`。这是刻意的——精确匹配是 O(1) 字典查找，
如果为了比较优先级还要扫前缀层，精确匹配的收益就没了。需要更高优先级时，
请用同一层的规则表达。

### 示例

```python
@action(r"^api/.*", priority=100)
def generic(event): ...

@action(r"^api/v1/.*", priority=1)
def specific(event): ...

dispatch("api/v1/users", None)   # -> generic  (同层，priority 高者胜)
```

```python
@action(r"^api/v1/.*", priority=5)
def specific(event): ...

@action(r"^api/v1/users/.*", priority=5)
def deeper(event): ...

dispatch("api/v1/users/1", None)   # -> deeper  (同层同优先级，更长前缀胜)
```

### 正则会被降级吗

只有当**能证明等价**时才降级为字面量比较：

| 写法 | 策略 | 说明 |
|---|---|---|
| `^user/123$` | EXACT | 中间无正则元字符 |
| `^api/v1/.*` | PREFIX | 提取前缀 `api/v1/` |
| `^api/v1/.*$` | PREFIX | 同上 |
| `.*\.log$` | SUFFIX | 提取后缀 `.log` |
| `^.*\.json$` | SUFFIX | 同上 |
| `^a\.b$` | EXACT | 转义元字符等价于字面量 `a.b` |
| `^user/[0-9]+$` | REGEX | 含字符类 |
| `^user.123$` | REGEX | 含未转义的 `.` |
| `.*abc` | REGEX | 没有 `$`，是"包含"不是后缀 |

判断依据是"去掉锚点后的字符串里是否含有任何正则元字符
（`\` `.` `^` `$` `*` `+` `?` `{` `}` `[` `]` `|` `(` `)`）"。
只要含一个就退回完整正则，**语义永远不变**。

唯一的例外是**转义元字符**：`\.` `\*` `\(` 这类写法等价于字面量，
会被反转义后降级（`^a\.b$` → EXACT `a.b`）。而 `\d` `\w` `\s` `\b`
这类**语义转义**一律拒绝，留在正则层。

> 旧版本（0.1）的元字符集漏了 `.`，导致 `^user.123$` 被当成字面量
> `user.123`，静默改变了正则语义。已在 0.2.0 修复。

---

## 并发模型

一把全局读写锁：

| 模式 | 加锁 | 行为 |
|---|---|---|
| `sync=False`（默认） | 读锁 | 与其它 `sync=False` 并发；与 `sync=True` 互斥 |
| `sync=True` | 写锁 | 全局排他，与**所有** handler 互斥 |

> 注册表里没有任何 `sync=True` 的 action 时，`dispatch` 完全不加锁
> （`has_sync` 在 `init_actions()` 时算好）。这是常见情况下的快路径。

### 为什么读者也要加锁

"全局排他"要求写者能等到在执行的 `sync=False` handler 全部退出，前提是
它们必须登记自己是读者。所以「读路径无锁」和「全局排他」不可兼得，只能二选一。

本库选择全局排他。代价是每次 dispatch 多约 0.7 us，收益是 `sync=True`
真的能保护共享状态。反过来削弱它，会把一次确定的等待变成一场静默的数据竞争——
后者更糟，因为它在测试里大概率不出现。

### 重入规则

| 场景 | 结果 |
|---|---|
| `sync=False` → `sync=False` | 允许（读锁重入） |
| `sync=True` → `sync=True` | 允许（写锁重入） |
| `sync=True` → `sync=False` | 允许（已持有更强的一致性） |
| `sync=False` → `sync=True` | 抛 `RuntimeError` |

最后一条是刻意的：读→写升级必然死锁（写者等自己持有的读锁释放），
明确报错远好于静默挂死。

---

## 日志

默认完全静默，热路径上只有一次布尔判断。想看每一步细节：

```python
from dispatcher3 import enable_logging

enable_logging()      # 默认 DEBUG，输出到 stderr
```

输出示例：

```
21:15:00.539 DEBUG dispatcher3.dispatcher │ 🎬 定义 action get_user  (app.py:7)  priority=10 sync=False  按 ID 查用户
21:15:00.539 DEBUG dispatcher3.dispatcher │ 🔍 '^user/[0-9]+$'          → 🌀 REGEX （含元字符，走完整正则）
21:15:00.540 DEBUG dispatcher3.dto        │    🌀 正则层 +1  共 1 条
21:15:00.540 INFO  dispatcher3.dto        │ 🔒 注册表已冻结
21:15:00.540 INFO  dispatcher3.dto        │    🎯 精确 1 | 🧭 前缀 1 | 🌀 正则 1 | ⚡ sync 1
21:15:00.540 DEBUG dispatcher3.dispatcher │ 🎺 dispatch('user/7')  thread=MainThread  event=7
21:15:00.540 DEBUG dispatcher3.dispatcher │    🌀 正则命中 get_user  [^user/[0-9]+$, priority=10, sync=False]
21:15:00.540 DEBUG dispatcher3.lock       │ 🔐 读锁 +1 (readers=1)
21:15:00.540 DEBUG dispatcher3.dispatcher │    ▶️  执行 get_user(7)
21:15:00.540 DEBUG dispatcher3.dispatcher │    ✅ 完成 get_user  耗时 0.001ms  返回 {'id': 7}
21:15:00.540 DEBUG dispatcher3.lock       │ 🔓 读锁 -1 (readers=0)
```

### 初始化清单

`init_actions()` 会输出一张完整的 action 清单（INFO 级别），整块用双横线包裹，
每个 action 的策略、优先级、sync 属性、匹配键、处理器、定义位置、描述都在里面：

```
🔒 注册表冻结   共 5 个 action
   🎯 精确 2   🧭 前缀 1   🌀 正则 2   │   ⚡ sync 2   · 并发 3   │   🔐 读路径加读锁
════════════════════════════════════════════════════════════════════════════════════════════════════
  #   策略     优先级 匹配键                               处理器                 位置               sync  描述
────────────────────────────────────────────────────────────────────────────────────────────────────
  1   EXACT    100    ^health$ -> 'health'                 health                 app.py:6           ·     健康检查
  2   EXACT    50     ^order/refund$ -> 'order/refund'     OrderService.refund    app.py:19          ⚡    退款
  3   REGEX    20     ^user/[0-9]+/update$                 update_user            app.py:12          ⚡    更新用户
  4   REGEX    10     ^user/[0-9]+$                        get_user               app.py:9           ·     按 ID 查用户
  5   PREFIX   5      ^api/v1/.* -> prefix 'api/v1/'       api_v1                 app.py:15          ·     v1 接口
────────────────────────────────────────────────────────────────────────────────────────────────────
   🎯 精确：字典 O(1)      🧭 前缀：线性，priority 优先，其次更长前缀
   🌀 正则：线性，priority 优先      ⚡ sync=True 全局排他      · sync=False 可并发
════════════════════════════════════════════════════════════════════════════════════════════════════
```

几个细节：

- **整块一次性输出**，不会和其它线程的日志交错
- **匹配键列同时给出原始正则和降级结果**（`-> 'health'` / `-> prefix 'api/v1/'`），
  一眼看出这个 action 走的是字典还是线性扫描
- **处理器列左截断**：`Class.method` 这类长名字保留尾部，不会把函数名砍掉
- **对齐列只用 ASCII**：emoji 和中文的终端宽度在不同环境不一致，混进定宽列会整表错位，
  所以 emoji 只出现在汇总行、图例和行尾
- 排序是 priority 降序，和 `list_actions()` 一致

### 图标对照

| 图标 | 含义 |
|---|---|
| 🎬 | 定义 action |
| 🔍 | 正则分析（降级成哪种策略） |
| 🎯 🧭 🏁 🌀 | 精确层 / 前缀层 / 后缀层 / 正则层 |
| 🔒 ⚙️ 🧹 | 冻结 / 初始化 / 清空注册表 |
| 🎺 📮 | 同步 dispatch / 异步投递 |
| 🔐 🔑 🔓 ♻️ | 读锁 / 写锁 / 释放 / 重入 |
| ⏳ 🔄 | 开始等锁 / 被唤醒但仍需继续等 |
| ▶️ ✅ 💥 | 开始执行 / 完成 / 抛异常 |
| 🚀 | 无锁快路径 |
| ❌ | 未命中 |
| 📦 | 包扫描 |

### 等锁日志

线程抢锁时能看到**谁在等、在等谁、等了多久**。等待是实时输出的，
不是等完之后补一条：

```
DEBUG dispatcher3.dispatcher │ 🎺 dispatch('hold')  thread=Worker-1  event=None
DEBUG dispatcher3.lock       │ 🔑 写锁已获取（无竞争）thread=Worker-1
DEBUG dispatcher3.dispatcher │ 🎺 dispatch('queue-write')  thread=Worker-2  event=None
DEBUG dispatcher3.lock       │ ⏳ 写锁等待中… thread=Worker-2  当前写者=Worker-1  在读=0  排队写者=0
DEBUG dispatcher3.dispatcher │ 🎺 dispatch('queue-read')  thread=Worker-3  event=None
DEBUG dispatcher3.lock       │ ⏳ 读锁等待中… thread=Worker-3  当前写者=Worker-1  在读=0  排队写者=1
DEBUG dispatcher3.lock       │ 🔓 写锁释放  thread=Worker-1  → 唤醒等待者
DEBUG dispatcher3.lock       │ 🔑 写锁已获取，全局排他中  thread=Worker-2  等待 150.045ms
DEBUG dispatcher3.lock       │ 🔄 读锁被唤醒但条件不满足，继续等  thread=Worker-3（写者=Worker-2）
DEBUG dispatcher3.lock       │ 🔓 写锁释放  thread=Worker-2  → 唤醒等待者
DEBUG dispatcher3.lock       │ 🔐 读锁 +1 (readers=1) thread=Worker-3  等待 200.824ms
```

关键点：

- **实时**：`⏳` 在真正 `wait()` 之前就输出，长等待期间你能看到现场
- **写者优先**：`Worker-3` 被唤醒后发现又有写者在排队，于是 `🔄` 继续等
- **耗时**：拿到锁的那条带实际等待毫秒数，可以直接定位热点竞争
- **无竞争不打扰**：正常路径只有一行 `🔑 写锁已获取（无竞争）`

> 实现上，等待路径会**先完全释放锁**再打日志，然后重新取锁去 `wait()`。
> 临界区内绝不做 I/O——否则一个阻塞的日志流会把整个分发器拖死。

### 级别划分

| 级别 | 内容 |
|---|---|
| INFO | 冻结摘要、包扫描结果、线程池生命周期 |
| DEBUG | 每次 dispatch 的命中策略、加锁、执行、耗时、返回值 |
| WARNING | 默认级别，正常情况下无输出 |

不想用内置 handler 时，自己控制即可：

```python
import logging
logging.getLogger("dispatcher3").setLevel(logging.DEBUG)
```

`disable_logging()` 会移除内置 handler，并把级别复位为 `NOTSET`（继承 root）。

### 日志不出来？先看这三条

**1. `enable_logging()` 只管 `dispatcher3.*`，不管你自己的 logger**

```python
enable_logging()

logger = logging.getLogger(__name__)   # 比如 myapp
logger.debug("看不到这行")              # ← 它不属于 dispatcher3
```

自己的 logger 要自己配置：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**2. 没有配置过 logging 时，Python 默认级别是 WARNING**

不调 `enable_logging()` 也不调 `basicConfig()`，`logger.debug()` 就是什么都不做。
这是 logging 的默认行为，不是库的问题。

**3. 级别开成 INFO 就看不到逐次分发**

`enable_logging(level=logging.INFO)` 只留初始化摘要和扫描结果，
每次 dispatch 的细节是 DEBUG，会被过滤掉。

### 与你已有的 logging 配置共存

如果 root logger 已经有 handler（`basicConfig` / `dictConfig` / pytest 等），
`enable_logging()` **不会**再装自己的 handler，只把级别调开，让日志走你的
handler —— 既不会打架，也不会重复输出。

```python
logging.basicConfig(level=logging.DEBUG, filename="app.log")
enable_logging()      # 日志会进 app.log，而不是 stderr
```

### 异步注意事项

`dispatch_async` 使用固定大小线程池（默认 15）。**不要在 worker 内部
同步等待另一个 `dispatch_async`**：

```python
@action(r"^outer$")
def outer(event):
    # ❌ 池被占满时这里会一直等下去
    return dispatch_async("inner", event).result()
```

需要这种链路时用同步的 `dispatch()`：

```python
@action(r"^outer$")
def outer(event):
    return dispatch("inner", event)   # ✅ 直接内联执行
```

---

## 性能

Python 3.14 / Windows，端到端延迟（含匹配 + 执行 + 返回），取 5 轮最小值：

| 场景 | 无 `sync=True` action | 有 `sync=True` action |
|---|---|---|
| 精确匹配 EXACT | **~0.2 us** | ~1.0 us |
| 前缀匹配 PREFIX | **~0.2 us** | ~1.1 us |
| 正则匹配 REGEX | **~0.4 us** | ~1.3 us |
| `sync=True` 排他 | — | ~0.95 us |
| `dispatch_async` + `result()` | 14–16 us | 14–16 us |

两列差的就是读锁的成本（约 0.7 us）。注册表里有 `sync=True` 的 action 时，
所有 `sync=False` 的 dispatch 也必须登记为读者，否则写者等不到它们退出。
没有 `sync=True` 的 action 则完全不加锁。

完整数据与复现方式见 [BENCHMARK.md](BENCHMARK.md)。数值随机器与 Python
版本浮动，重要的是量级关系。

自己复现：

```bash
python benchmarks/bench.py
```

### 与 0.1 对比

| 指标 | 0.1 | 0.2（无 sync） | 0.2（有 sync） |
|---|---|---|---|
| 端到端精确匹配 | 16.7 us | ~0.2 us（**约 80x**） | ~1.0 us（**约 17x**） |
| 读锁重入 / 写锁重入 | 死锁 | 支持 | 支持 |
| 写者异常退出后读者 | 永久挂死 | 正常 | 正常 |

> 0.1 的文档宣称精确匹配 5.6 us，但那个数字只测了 `dispatch()` 提交函数
> 的耗时（本机 3.89 us），没有测实际交付。用户要拿到结果必须再调
> `.result()`，真实端到端是 16.7 us。

### 为什么异步比同步贵十几倍

`submit` + `Future` + 条件变量唤醒 + 线程切换，在 Python 里固定成本约
14 us，与你的 handler 做什么无关。同步调用没有这些开销。

**结论：默认用 `dispatch()`。只有需要真并发（I/O 密集、多路并行）时才用
`dispatch_async()`。** 一个 CPU 密集的 handler 放进线程池不会变快，
只会更慢（GIL）。

---

## 多平台支持

| 维度 | 状态 |
|---|---|
| OS | Windows / Linux / macOS —— 纯标准库，无 OS 相关代码 |
| Python | 3.8+；CI 覆盖 3.9–3.13 |
| 运行时 | CPython。PyPy 未验证 |
| CI | 3 OS × 5 Python 版本矩阵（`.github/workflows/ci.yml`） |

> 说明：CI 矩阵是在 0.2.0 中加入的，**尚未在真实 GitHub Actions 上跑过**。
> 在此之前"跨平台"只是推断，不是验证过的结论。

---

## 开发

```bash
pip install -e ".[dev]"

python -m pytest tests -q          # 测试（76 个用例）
python benchmarks/bench.py         # 基准
python -m examples.run_all         # 跑全部示例
```

目录结构：

```
dispatcher3/
  __init__.py     公开 API
  dispatcher.py   装饰器、正则分析、dispatch 门面
  dto.py          数据模型 + 分层注册表
  lock.py         sync 锁 + 异步线程池
  log.py          日志开关
tests/            pytest 用例
examples/         可运行示例
benchmarks/       基准脚本
```

### 示例清单

每个示例都可用 `python -m examples.<name>` 单独运行。

| 示例 | 覆盖内容 |
|---|---|
| `basic` | 最小可用示例 |
| `matching` | 三种匹配层、同层 priority、前缀长度 tie-break、层间短路、正则降级判定 |
| `concurrency` | sync 全局排他、sync=False 并发、读锁/写锁重入、读→写报错、异步并发 |
| `errors` | 未初始化、未命中、handler 异常、非法正则、冻结后注册、重复注册、读→写、异步异常 |
| `async_dispatch` | Future、并发执行、异常传递、两种投递成本对比、线程池关闭 |
| `auto_import` | 包扫描自动注册 |
| `introspection` | list_actions、注册表分层视图、锁状态 |
| `logging_demo` | 打开详细日志看每一步 |
| `run_all` | 子进程依次跑全部示例 |

---

## 从 0.1 迁移

0.2.0 是破坏性版本，改动清单见 [CHANGELOG.md](CHANGELOG.md)。最需要
注意的三点：

```python
# 1. dispatch 现在是同步的，直接返回结果
# 0.1
dispatch("key", event).result()
# 0.2
dispatch("key", event)

# 2. 异常不再被吞掉
# 0.1: handler 抛异常 -> 打印 traceback，返回 None
# 0.2: handler 抛异常 -> 原样抛出

# 3. 模块路径变了
# 0.1
from dispatcher3.action_dispatch_v3 import action, dispatch
# 0.2
from dispatcher3 import action, dispatch
```

**保持不变**：`sync=True` 依然是全局排他，与 `sync=False` 的 handler 也互斥。
依赖它保护共享状态的代码不需要改。变的只是锁本身——原来的实现在
写者异常退出、以及任何重入场景下都会死锁。

---

## 已知限制

- 层间不比较 priority（见上文"匹配优先级规则"），这是性能与可预测性的取舍
- 前缀/正则层是线性扫描，规则数到数百条时建议改用精确匹配或前缀分层
- 不支持运行时注册；这是特性不是缺陷
- 异步线程池大小固定，无背压，突发流量会堆积在队列里
- `sync=True` 是**全局**锁，不按 key 分段。不同 key 的排他任务也会互相排队；
  需要细粒度并发时应把粒度放到 handler 内部自己控制
- `sync=False` handler 内不能 dispatch 到 `sync=True` 的 action（读→写升级
  会死锁，库会直接抛 `RuntimeError`）

---

## 许可证

MIT
