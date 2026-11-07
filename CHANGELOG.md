# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.2.0] - 2026-10-29

破坏性重构。修复了 0.1 中的正确性缺陷、并发缺陷与打包缺陷。

### 修复（正确性）

- **正则语义被静默改写**：`analyze_regex` 的元字符集漏了 `.`，
  `^user.123$` 被当成字面量 `user.123`，导致 `userX123` 匹配不上。
  现在只要含任意元字符就退回完整正则，语义永远与 `re` 一致。
- **handler 异常被吞掉**：`_invoke_action` 用 `except Exception` 捕获后
  只 `traceback.print_exc()`，调用方拿到 `None` 却无从得知失败。
  现在异常原样传播，异步模式下通过 `Future` 抛出。
- **`NoMatchError` 从未被抛出**：旧实现只打印一行红字然后返回 `None`。
  现在正常抛出。
- **前缀层忽略 priority**：旧实现按前缀长度排序，`^api/.*`(priority=100)
  会被 `^api/v1/.*`(priority=1) 抢先命中。现在同层内 priority 优先，
  长度只作为 tie-break。
- **重复注册误报**：`DEBUG=False` 时 module 恒为 `'<prod>'`，不同模块的
  同名函数会被误判为重复。现在用 `func.__module__` + `__qualname__`，
  且无需 `inspect`（零开销）。真重复注册改为抛错而非打印警告。
- **读锁可能重复释放**：`_dispatch_thread` 的 `finally` 与 `except` 会
  各释放一次，实测 `_readers` 可降到 `-1`，计数器永久漂移。

### 修复（并发）

- **写者异常退出会让读者永久挂死**：`FastRWLock.acquire_write` 的
  `except` 分支只做 `_write_waiters -= 1`，**没有 `notify_all()`**。
  若此时有读者在等（被 `_write_waiters > 0` 门控），它们永远不会被唤醒。
  新实现先 `notify_all()` 再抛出。
- **写者线程取读锁自死锁**：`acquire_read` 见到 `_writers > 0` 就 `wait()`，
  写者线程等自己释放写锁。新实现识别"已持有写锁"并直接放行。
- **读锁 / 写锁均不可重入**：`sync=True` handler 内再 dispatch 到
  `sync=True` action 必死锁；`sync=False` handler 内嵌套 dispatch 在写者
  排队时也会死锁。新实现按线程记录重入层数。
- **读→写升级静默死锁**：旧实现先 `release_read()` 再 `acquire_write()`，
  跨线程时写者等的是自己所在线程的读锁，挂死。新实现直接抛
  `RuntimeError` 并说明原因。
- **计数漂移**：`_dispatch_thread` 的 `finally` 与 `except` 各释放一次读锁，
  实测 `_readers` 可降到 `-1`，此后锁永久失准。新实现的
  `release_read` / `release_write` 不配对会直接报错。

> **保留的语义**：`sync=True` 仍然是**全局排他**，与 `sync=False` 的
> handler 也互斥。代价是写者要等在执行的读者退出——这是排他的定义，
> 不是缺陷。为了降低这个代价，注册表里没有 `sync=True` action 时
> `dispatch` 完全不加锁。

### 修复（打包）

- **打出来的 wheel 是空的**：仓库缺少 `dispatcher3/__init__.py`，
  `find_packages()` 返回 `[]`，`pip install dispatcher3` 装不到任何代码。
- `python_requires=">=3.6"` 与 classifiers 从 3.8 起自相矛盾，统一为 `>=3.8`。
- 删除 `setup.py` 与 `publish.py` 中疑似泄露的 token blob 及注释掉的 PyPI token。
- 删除重复的发布工作流（`publish.yml` 与 `python-publish.yml` 会在同一
  release 事件上双重发布）。

### 新增

- **SUFFIX 匹配层**：`.*literal$` / `^.*literal$` 现在降级为后缀匹配，
  用 `str.endswith` 代替正则扫描。文件扩展名场景（`.*\.log$`）终于不用
  每帧跑一遍 regex。
  **层序变化**：EXACT → PREFIX → **SUFFIX** → REGEX。后缀层插在前缀层之后、
  正则层之前，因此一条后缀规则现在会赢过同 key 上的正则规则（哪怕对方
  priority 更高）——这与此前"前缀层永远赢过正则层"的规则一致，但确实改变了
  既有路由结果，升级时请检查同时存在后缀形状正则与其它正则的场景。
- **转义元字符可降级**：`^a\.b$` 这类写法现在识别为 EXACT `a.b`
  （此前一律走正则）。`\d` `\w` `\s` `\b` 等语义转义仍然留在正则层。

### 变更（破坏性）

- **`dispatch()` 改为同步执行并直接返回 handler 的返回值**，不再返回
  `Future`。异步入口独立为 `dispatch_async()`。
  收益：端到端延迟 16.7 us → 0.2 us（无 `sync=True` action 时，约 80x）
  或 → 1.0 us（有 `sync=True` action 时，读锁成本，约 17x）。
- **模块路径变更**：`dispatcher3.action_dispatch_v3` → `dispatcher3.dispatcher`。
  推荐直接 `from dispatcher3 import ...`。
- **`action()` 的参数改为 keyword-only**（`regex` 除外）。
  旧签名 `action(regex, description, priority)` 与文档写的
  `action(regex, priority, description)` 顺序相反，位置传参会静默错位。
- **`init_actions()` 与 `auto_import_package_modules()` 拆开**：
  后者只导入模块，不再隐式冻结注册表。
- 公开函数去掉下划线前缀：`_init_actions` → `init_actions`，
  `_init_actions_auto` 移除（功能并入 `auto_import_package_modules`）。

### 变更（性能）

- **无 sync action 时跳过加锁**：`has_sync` 在 `init_actions()` 时算好，
  没有 `sync=True` 的 action 就不会出现写者，读锁纯属开销。
  精确匹配 2.2 us → 0.2 us（该配置下）。
- **读锁改为纯计数实现**：去掉旧 `FastRWLock` 的"快速路径"假象
  （它仍在 mutex 内判断），也去掉锁内的 `print` 与 `key` 参数。
- **删除 LRU 缓存**：只挂在非精确路径上，而精确路径在调用 `find()` 之前
  就返回了，实测 `hits=0/misses=0`。且 `lru_cache` 内部有锁，在热路径上
  制造全局争用点，抵消了读写锁的意义。dispatch 的 key 通常是事件级唯一的，
  天然低复用，缓存本就是错配。
- 移除 `inspect.currentframe()`：改用 `func.__module__` /
  `func.__code__.co_firstlineno`，真实位置信息 + 零开销。
- 移除热路径上的 `print`：改为 `logging`，默认不输出。旧版本每次 dispatch
  打两行 emoji，在生产环境是噪音，在无 tty 环境下是阻塞源。

### 新增

- **初始化清单**：`init_actions()` 输出一张完整的 action 表格（INFO），
  整块用双横线包裹，列出每个 action 的策略、优先级、sync、匹配键（含降级结果）、
  处理器、定义位置、描述，附分层统计与图例。按显示宽度对齐，中文/emoji 不会把表挤歪。
  位置列只显示文件名（`app.py:42`），不用模块全名——`ActionInfo` 新增
  `filename` 字段，`module` 保留用于重复注册检测。
- **详细日志**：`enable_logging()` / `disable_logging()`。默认静默
  （热路径只多一次布尔判断），打开后能看到每一步：正则降级判定、注册到哪一层、
  冻结摘要、命中策略、加锁/解锁、执行耗时、返回值、异常。全部带 emoji。
  日志分两级：INFO 是初始化摘要与扫描结果，DEBUG 是每次 dispatch 的细节。
  **等锁可见**：`⏳ 等待中`（实时输出，不是事后补记）、`🔄 被唤醒但条件不满足`、
  拿到锁时附带实际等待毫秒数；每条都带线程名与当前写者。
  锁内不做 I/O —— 消息先在锁内收集，出锁后才输出，避免阻塞的日志流把分发器拖死。
- **8 个可运行示例**（`examples/`）：匹配规则、并发语义、错误全集、异步、
  包扫描、内省、日志演示，以及 `run_all` 依次跑完。
- `tests/test_logging.py`：10 个用例锁定日志行为（默认静默、各级别内容、
  handler 不重复叠加）。
- `reset()`：清空并解冻注册表。没有它就无法在同一个进程里写测试——
  这也是 0.1 一个测试都没有的原因。
- `shutdown_executor()`：显式关闭异步线程池。
- `tests/`：61 个 pytest 用例，覆盖正则分类、注册表、分发、并发语义、
  异步、打包与性能冒烟。
- `benchmarks/bench.py`：可复现的端到端基准。
- `examples/`：可运行示例（取代原来无法运行的 `test/`）。
- CI 矩阵：3 OS × 5 Python 版本，且构建后会验证 wheel 里确实有代码。

### 移除

- `FastRWLock`（读路径不再需要锁）
- `TIME_OUT_TIME` 常量（定义了但唯一使用处被注释掉）
- `test/` 目录（重命名为 `examples/`，原文件 `acion1.py` 拼写错误且依赖
  已失效的导入路径）

---

## [0.1] - 2024

初始版本。仅作为历史记录保留，存在上述全部缺陷，请勿使用。
