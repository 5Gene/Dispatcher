"""Action 注册与分发门面。

对外 API::

    from dispatcher3 import action, dispatch, dispatch_async, init_actions

    @action(r"^user/[0-9]+$", priority=10)
    def handle_user(event):
        return event

    init_actions()
    result = dispatch("user/123", {"id": 123})        # 同步，直接返回结果
    future = dispatch_async("user/123", {"id": 123})  # 异步，返回 Future

语义要点
--------
* dispatch() 默认同步执行并直接返回 handler 的返回值；handler 抛出的异常
  会原样向上传播，未匹配时抛 NoMatchError。
* dispatch_async() 才走线程池。异步投递的成本约为内联执行的 14 倍，
  只在确实需要并发时才使用。
* 注册表在 init_actions() 之后冻结，运行时注册会抛 RegistryFrozenError。

日志
----
默认静默。想看每一步细节::

    from dispatcher3 import enable_logging
    enable_logging()
"""
import importlib
import logging
import os
import pkgutil
import re
import threading
import time
from typing import Any, List, Optional

from dispatcher3.dto import (
    STRATEGY_ICON,
    ActionFunc,
    ActionInfo,
    ActionMetadata,
    MatchPattern,
    MatchStrategy,
    NoMatchError,
    RegistryFrozenError,
    global_registry,
)
from dispatcher3.lock import get_executor, global_lock, shutdown_executor

logger = logging.getLogger(__name__)

# 正则元字符。用于判断 ^literal$ / ^literal.* 能否降级为字面量比较。
# 注意必须包含 '.'：旧版本遗漏了它，导致 '^user.123$' 被当成字面量
# 'user.123'，静默改变了正则语义。
_REGEX_META = frozenset(".^$*+?{}[]|()" + chr(92))

__all__ = [
    "action",
    "analyze_regex",
    "auto_import_package_modules",
    "dispatch",
    "dispatch_async",
    "init_actions",
    "is_initialized",
    "list_actions",
    "reset",
    "shutdown_executor",
]


def _brief(value: Any, limit: int = 80) -> str:
    """截断 repr，避免日志里刷出巨大的对象。"""
    try:
        text = repr(value)
    except Exception:                      # pragma: no cover - 防御性
        return "<unrepresentable>"
    if len(text) > limit:
        return text[:limit - 3] + "..."
    return text


# ============================================================================
# 正则分析
# ============================================================================
def _literal_of(text: str) -> Optional[str]:
    r"""判断一段正则源码是否等价于纯字面量，是则返回反转义后的字符串。

    允许 \. 这类"转义元字符"写法（'^a\.b$' 等价于字面量 'a.b'），
    但 \d / \w / \s 这类语义转义一律拒绝，退回完整正则。
    拿不准就返回 None —— 分类错误会静默改变路由结果，代价远大于少一次优化。
    """
    if not text:
        return text
    out = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            if index + 1 >= length:
                return None
            escaped = text[index + 1]
            if escaped not in _REGEX_META:
                return None
            out.append(escaped)
            index += 2
            continue
        if char in _REGEX_META:
            return None
        out.append(char)
        index += 1
    return "".join(out)


def analyze_regex(regex_str: str) -> MatchPattern:
    r"""分析正则并选择代价最低的匹配策略。

    只有能证明等价时才降级，否则一律走完整正则，保证语义不变。

    - EXACT:  ^literal$
    - PREFIX: ^literal.* / ^literal.*$
    - SUFFIX: .*literal$ / ^.*literal$
    - REGEX:  其它情况

    literal 里允许出现 \. 这类转义元字符（会被反转义），但不允许
    \d / \w / 字符类 / 量词 / 分组 / 分支等真正的正则语法。

    Raises:
        ValueError: 正则无法编译。
    """
    # 精确：^literal$
    if len(regex_str) >= 2 and regex_str.startswith("^") and regex_str.endswith("$"):
        literal = _literal_of(regex_str[1:-1])
        if literal is not None:
            logger.debug("🔍 %-24r → 🎯 EXACT  字面量=%r", regex_str, literal)
            return MatchPattern(MatchStrategy.EXACT, literal)

    # 前缀：^literal.* / ^literal.*$
    if regex_str.startswith("^"):
        if regex_str.endswith(".*$"):
            raw = regex_str[1:-3]
        elif regex_str.endswith(".*"):
            raw = regex_str[1:-2]
        else:
            raw = None
        if raw is not None:
            literal = _literal_of(raw)
            if literal is not None:
                logger.debug("🔍 %-24r → 🧭 PREFIX 前缀=%r", regex_str, literal)
                return MatchPattern(MatchStrategy.PREFIX, literal)

    # 后缀：.*literal$ / ^.*literal$
    body = regex_str[1:] if regex_str.startswith("^") else regex_str
    if body.startswith(".*") and body.endswith("$"):
        raw = body[2:-1]
        if raw:
            literal = _literal_of(raw)
            if literal is not None:
                logger.debug("🔍 %-24r → 🏁 SUFFIX 后缀=%r", regex_str, literal)
                return MatchPattern(MatchStrategy.SUFFIX, literal)

    try:
        compiled = re.compile(regex_str)
    except re.error as exc:
        logger.error("💥 正则编译失败 %r: %s", regex_str, exc)
        raise ValueError("非法正则 %r: %s" % (regex_str, exc)) from exc

    logger.debug("🔍 %-24r → 🌀 REGEX （含正则语法，走完整正则）", regex_str)
    return MatchPattern(MatchStrategy.REGEX, regex_str, compiled)


def action(regex: str, *, description: str = "", priority: int = 0,
           sync: bool = False):
    """把函数注册为 action。

    Args:
        regex: 匹配 key 的正则表达式。
        description: 描述信息，仅用于 list_actions()。
        priority: 优先级，数值越大越优先。
        sync: True 表示该 handler 全局排他执行。

    所有参数除 regex 外均为 keyword-only，避免旧版本
    action(regex, description, priority) 与文档
    action(regex, priority, description) 的歧义。
    """

    def decorator(func: ActionFunc) -> ActionFunc:
        code = getattr(func, "__code__", None)
        module = getattr(func, "__module__", "<unknown>")
        qualname = getattr(func, "__qualname__", func.__name__)
        line = code.co_firstlineno if code is not None else 0
        # 只留文件名：清单里 app.py:42 比 pkg.sub.mod:42 更好认
        filename = (os.path.basename(code.co_filename)
                    if code is not None else "<unknown>")

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("🎬 定义 action %s  (%s:%d)  priority=%d sync=%s%s",
                         qualname, filename, line, priority, sync,
                         ("  " + description) if description else "")

        metadata = ActionMetadata(
            func=func,
            regex_str=regex,
            priority=priority,
            description=description,
            sync=sync,
            match_pattern=analyze_regex(regex),
            # __module__ / __code__ 都是现成属性，无需 inspect，零额外开销
            module=module,
            line=line,
            qualname=qualname,
            filename=filename,
        )
        global_registry.register(metadata)
        return func

    return decorator


def init_actions() -> None:
    """构建索引并冻结注册表。必须在 dispatch 之前调用。"""
    logger.debug("⚙️  init_actions()")
    global_registry.finalize()


def is_initialized() -> bool:
    """注册表是否已冻结。"""
    return global_registry.is_finalized()


def reset() -> None:
    """清空注册表并解除冻结。主要用于测试。"""
    global_registry.reset()


def auto_import_package_modules(package_names: List[str]) -> List[str]:
    """导入若干包下的全部一级子模块，触发其中的 @action 注册。

    只负责导入，不负责 finalize —— 调用方仍需显式调用 init_actions()，
    这样"扫描"和"冻结"两件事不会纠缠在一起。

    Returns:
        成功导入的模块全名列表。
    """
    imported: List[str] = []
    for package_name in package_names:
        logger.info("📦 扫描包 %r", package_name)
        try:
            package = importlib.import_module(package_name)
        except ImportError:
            logger.error("   ✗ 无法导入包 %r", package_name, exc_info=True)
            continue
        paths = getattr(package, "__path__", None)
        if paths is None:
            logger.error("   ✗ %r 不是一个包", package_name)
            continue
        for _, modname, _ in pkgutil.iter_modules(paths):
            full_name = "%s.%s" % (package_name, modname)
            try:
                importlib.import_module(full_name)
                imported.append(full_name)
                logger.info("   ✓ %s", full_name)
            except ImportError:
                logger.error("   ✗ %s 导入失败", full_name, exc_info=True)
    logger.info("📦 扫描完成，成功导入 %d 个模块", len(imported))
    return imported


# ============================================================================
# 分发
# ============================================================================
def dispatch(key: str, event: Any) -> Any:
    """同步分发事件并返回 handler 的返回值。

    Raises:
        RegistryNotInitializedError: 未调用 init_actions()。
        NoMatchError: 没有 action 匹配 key。
    """
    trace = logger.isEnabledFor(logging.DEBUG)
    if trace:
        logger.debug("🎺 dispatch(%r)  thread=%s  event=%s",
                     key, threading.current_thread().name, _brief(event))

    metadata = global_registry.resolve(key)
    if metadata is None:
        logger.debug("   ❌ 没有 action 匹配 %r", key)
        raise NoMatchError("没有匹配 %r 的 action" % (key,))

    if trace:
        pattern = metadata.match_pattern
        logger.debug("   %s %s命中 %s  [%s, priority=%d, sync=%s]",
                     STRATEGY_ICON[pattern.strategy.name],
                     {"EXACT": "精确", "PREFIX": "前缀", "REGEX": "正则"}[pattern.strategy.name],
                     metadata.qualname, metadata.regex_str,
                     metadata.priority, metadata.sync)

    if metadata.sync:
        # 写锁：与所有其它 handler 互斥（含 sync=False）
        global_lock.acquire_write(trace)
        try:
            return _call(metadata, event, trace)
        finally:
            global_lock.release_write(trace)

    if global_registry.has_sync:
        # 存在 sync=True 的 action 时，读者必须登记，否则写者等不到它们退出
        global_lock.acquire_read(trace)
        try:
            return _call(metadata, event, trace)
        finally:
            global_lock.release_read(trace)

    # 没有任何 sync=True 的 action：不会出现写者，读锁纯属开销
    if trace:
        logger.debug("   🚀 无锁快路径（注册表里没有 sync=True 的 action）")
    return _call(metadata, event, trace)


def dispatch_async(key: str, event: Any, max_workers: Optional[int] = None):
    """异步分发，返回 concurrent.futures.Future。

    handler 的异常会通过 Future 抛给调用方（result() 时重新抛出）。
    """
    logger.debug("📮 dispatch_async(%r) 提交到线程池", key)
    return get_executor(max_workers).submit(dispatch, key, event)


def _call(metadata: ActionMetadata, event: Any, trace: bool) -> Any:
    # 关闭日志时热路径上只有这一次布尔判断
    if not trace:
        return metadata.func(event)

    logger.debug("   ▶️  执行 %s(%s)", metadata.qualname, _brief(event))
    start = time.perf_counter()
    try:
        result = metadata.func(event)
    except BaseException as exc:
        elapsed = (time.perf_counter() - start) * 1000
        logger.debug("   💥 %s 抛出 %s: %s  (耗时 %.3fms)",
                     metadata.qualname, type(exc).__name__, exc, elapsed)
        raise
    elapsed = (time.perf_counter() - start) * 1000
    logger.debug("   ✅ 完成 %s  耗时 %.3fms  返回 %s",
                 metadata.qualname, elapsed, _brief(result))
    return result


# ============================================================================
# 内省
# ============================================================================
def list_actions() -> List[ActionInfo]:
    """按 priority 降序列出全部已注册 action。"""
    return [
        ActionInfo(
            regex=meta.regex_str,
            priority=meta.priority,
            description=meta.description,
            sync=meta.sync,
            strategy=meta.match_pattern.strategy.name.lower(),
            module=meta.module,
            filename=meta.filename,
            line=meta.line,
        )
        for meta in global_registry.list_all()
    ]
