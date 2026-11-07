"""数据模型与 action 注册表。

本模块只包含不可变的数据载体和一个可重置的注册表，不含任何分发逻辑。
热路径上的两个类（MatchPattern / ActionMetadata）使用 __slots__ 以避免
__dict__ 开销；仅用于调试展示的 ActionInfo 使用 dataclass 以保持可读性。
"""
import logging
import re
import threading
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

ActionFunc = Callable[[Any], Any]

# 每一层匹配策略的图标，日志和报错里共用
STRATEGY_ICON = {
    "EXACT": "🎯",
    "PREFIX": "🧭",
    "SUFFIX": "🏁",
    "REGEX": "🌀",
}

# 注册表清单的横线。上下用双横线包裹，内部用单横线分隔。
RULE_WIDTH = 100
DOUBLE_RULE = "═" * RULE_WIDTH
SINGLE_RULE = "─" * RULE_WIDTH

# 定宽列的宽度：#, 策略, 优先级, 匹配键, 处理器, 位置, sync
_COLUMN_WIDTHS = (3, 8, 6, 36, 22, 18, 4)
_HANDLER_COLUMN = 4


def _display_width(text: str) -> int:
    """终端显示宽度。中文和 emoji 占两列，直接 len() 会错位。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in text)


def _pad(text: str, width: int) -> str:
    """按显示宽度右补空格。"""
    return text + " " * max(0, width - _display_width(text))


def _format_row(cells) -> str:
    """把一行单元格按显示宽度对齐；最后一列（描述）不参与定宽。

    处理器列用左截断：嵌套函数/方法的 qualname 很长，真正有用的函数名在
    末尾，从右边砍会把名字砍没。
    """
    fixed = cells[:len(_COLUMN_WIDTHS)]
    tail = cells[len(_COLUMN_WIDTHS):]
    parts = []
    for index, (cell, width) in enumerate(zip(fixed, _COLUMN_WIDTHS)):
        cut = _cut_left if index == _HANDLER_COLUMN else _cut
        parts.append(_pad(cut(cell, width), width))
    row = "  " + " ".join(parts)
    if tail:
        row += "  " + _cut(tail[0], 60)
    return row.rstrip()


def _cut_left(text: str, width: int) -> str:
    """按显示宽度左截断，保留尾部（用于 qualname 这类点分名称）。"""
    if _display_width(text) <= width:
        return text
    out = []
    used = 0
    for ch in reversed(text):
        ch_width = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + ch_width > width - 1:
            break
        out.append(ch)
        used += ch_width
    return "…" + "".join(reversed(out))


def _cut(text: str, width: int) -> str:
    """按显示宽度截断，超出部分用省略号。"""
    if _display_width(text) <= width:
        return text
    out = []
    used = 0
    for ch in text:
        ch_width = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if used + ch_width > width - 1:
            break
        out.append(ch)
        used += ch_width
    return "".join(out) + "…"


# ============================================================================
# 异常
# ============================================================================
class DispatchError(Exception):
    """分发错误基类。"""


class NoMatchError(DispatchError):
    """没有任何 action 匹配给定的 key。"""


class RegistryNotInitializedError(DispatchError):
    """注册表尚未 finalize，无法分发。"""


class RegistryFrozenError(DispatchError):
    """注册表已冻结，禁止运行时注册。"""


# ============================================================================
# 匹配策略
# ============================================================================
class MatchStrategy(Enum):
    """匹配策略。"""

    EXACT = 1   # 字典命中，O(1)
    PREFIX = 2  # 前缀列表顺序扫描
    SUFFIX = 3  # 后缀列表顺序扫描
    REGEX = 4   # 正则顺序扫描


class MatchPattern:
    """正则的分析结果：策略 + 提取出的字面量/编译后的 pattern。"""

    __slots__ = ("strategy", "pattern", "regex")

    def __init__(self, strategy: MatchStrategy, pattern: str,
                 regex: Optional["re.Pattern"] = None) -> None:
        self.strategy = strategy
        self.pattern = pattern
        self.regex = regex

    def __repr__(self) -> str:
        return "MatchPattern(%s, %r)" % (self.strategy.name, self.pattern)


class ActionMetadata:
    """单个 action 的注册信息。"""

    __slots__ = ("func", "regex_str", "priority", "description",
                 "sync", "match_pattern", "module", "filename", "line", "qualname")

    def __init__(self, func: ActionFunc, regex_str: str, priority: int,
                 description: str, sync: bool, match_pattern: MatchPattern,
                 module: str, line: int, qualname: str,
                 filename: str = "<unknown>") -> None:
        self.func = func
        self.regex_str = regex_str
        self.priority = priority
        self.description = description
        self.sync = sync
        self.match_pattern = match_pattern
        self.module = module
        # 只保留文件名，清单里展示 app.py:42 比 pkg.sub.mod:42 更好认
        self.filename = filename
        self.line = line
        self.qualname = qualname

    @property
    def ident(self) -> str:
        """用于重复注册检测的唯一标识。"""
        return "%s:%s" % (self.module, self.qualname)

    def __repr__(self) -> str:
        return "ActionMetadata(%r, strategy=%s, priority=%d, sync=%s)" % (
            self.regex_str, self.match_pattern.strategy.name, self.priority, self.sync)


# ============================================================================
# 注册表
# ============================================================================
class LayeredRegistry:
    """分层注册表：精确匹配走字典，前缀/正则走排序后的列表。

    匹配优先级规则（三层短路）：

    1. 精确匹配（EXACT）命中即返回，不再考察其它层；
    2. 否则按 (-priority, -len(prefix)) 顺序扫描前缀层，首个命中即返回；
    3. 否则按 (-priority, -len(suffix)) 顺序扫描后缀层，首个命中即返回；
    4. 否则按 -priority 顺序扫描正则层，首个命中即返回。

    同一层内 priority 高者优先；前缀层同优先级时更长的前缀优先。
    该规则在 README 中有完整说明。
    """

    __slots__ = ("exact_matches", "prefix_matches", "suffix_matches",
                 "regex_matches", "all_actions", "has_sync",
                 "_finalized", "_seen", "_lock")

    def __init__(self) -> None:
        self.exact_matches: Dict[str, ActionMetadata] = {}
        self.prefix_matches: List[Tuple[str, ActionMetadata]] = []
        self.suffix_matches: List[Tuple[str, ActionMetadata]] = []
        self.regex_matches: List[ActionMetadata] = []
        self.all_actions: List[ActionMetadata] = []
        # 是否存在 sync=True 的 action。若为 False，dispatch 完全不需要加锁。
        self.has_sync = False
        self._finalized = False
        self._seen: Set[str] = set()
        self._lock = threading.RLock()

    # -- 注册 ---------------------------------------------------------------
    def register(self, metadata: ActionMetadata) -> None:
        """注册一个 action。注册表冻结后调用会抛 RegistryFrozenError。"""
        with self._lock:
            if self._finalized:
                raise RegistryFrozenError(
                    "注册表已冻结，禁止运行时注册: %s (定义于 %s:%d)"
                    % (metadata.qualname, metadata.module, metadata.line)
                )

            if metadata.ident in self._seen:
                raise RegistryFrozenError(
                    "重复注册: %s (定义于 %s:%d)"
                    % (metadata.ident, metadata.module, metadata.line)
                )
            self._seen.add(metadata.ident)
            self.all_actions.append(metadata)

            pattern = metadata.match_pattern
            icon = STRATEGY_ICON[pattern.strategy.name]
            if pattern.strategy is MatchStrategy.EXACT:
                current = self.exact_matches.get(pattern.pattern)
                if current is None:
                    self.exact_matches[pattern.pattern] = metadata
                    logger.debug("   %s 精确层 +1  字面量=%r  共 %d 条",
                                 icon, pattern.pattern, len(self.exact_matches))
                elif metadata.priority > current.priority:
                    logger.debug("   %s 精确层覆盖  %r  priority %d > %d",
                                 icon, pattern.pattern, metadata.priority,
                                 current.priority)
                    self.exact_matches[pattern.pattern] = metadata
                else:
                    logger.debug("   %s 精确层跳过  %r  priority %d <= %d（保留先注册者）",
                                 icon, pattern.pattern, metadata.priority,
                                 current.priority)
            elif pattern.strategy is MatchStrategy.PREFIX:
                self.prefix_matches.append((pattern.pattern, metadata))
                logger.debug("   %s 前缀层 +1  前缀=%r  共 %d 条",
                             icon, pattern.pattern, len(self.prefix_matches))
            elif pattern.strategy is MatchStrategy.SUFFIX:
                self.suffix_matches.append((pattern.pattern, metadata))
                logger.debug("   %s 后缀层 +1  后缀=%r  共 %d 条",
                             icon, pattern.pattern, len(self.suffix_matches))
            else:
                self.regex_matches.append(metadata)
                logger.debug("   %s 正则层 +1  共 %d 条", icon, len(self.regex_matches))

    # -- 冻结 / 重置 --------------------------------------------------------
    def finalize(self) -> None:
        """构建索引并冻结注册表。重复调用是幂等的。

        冻结时会输出一张完整的 action 清单（INFO 级别），包含每个 action 的
        匹配策略、优先级、sync 属性、匹配键、处理器、定义位置和描述。
        """
        with self._lock:
            if self._finalized:
                return
            # 前缀层：priority 优先，其次更长前缀优先
            self.prefix_matches.sort(key=lambda item: (-item[1].priority, -len(item[0])))
            # 后缀层：规则同前缀层
            self.suffix_matches.sort(key=lambda item: (-item[1].priority, -len(item[0])))
            # 正则层：priority 优先，同优先级保持注册顺序（sort 稳定）
            self.regex_matches.sort(key=lambda meta: -meta.priority)
            # 冻结后不再变化，dispatch 据此决定是否需要走读锁
            self.has_sync = any(meta.sync for meta in self.all_actions)
            self._finalized = True
            report = self._build_report()

        # 整块一次性输出，避免和其它线程的日志交错
        logger.info(report)

    def _build_report(self) -> str:
        """生成注册表清单。整块用双横线包裹。

        对齐列只用 ASCII —— emoji 和中文的终端宽度在不同环境下不一致，
        混进定宽列会导致整张表错位。emoji 放在汇总行、图例和行尾。
        """
        actions = self.list_all()
        total = len(actions)
        sync_count = sum(1 for meta in actions if meta.sync)

        lines = [DOUBLE_RULE]
        lines.append("🔒 注册表冻结   共 %d 个 action" % total)
        lines.append(
            "   🎯 精确 %d   🧭 前缀 %d   🏁 后缀 %d   🌀 正则 %d   │   "
            "⚡ sync %d   · 并发 %d   │   %s"
            % (len(self.exact_matches), len(self.prefix_matches),
               len(self.suffix_matches), len(self.regex_matches),
               sync_count, total - sync_count,
               "🔐 读路径加读锁" if self.has_sync else "🚀 读路径无锁")
        )
        lines.append(DOUBLE_RULE)

        if not total:
            lines.append("   （空）注册表里没有任何 action")
            lines.append(DOUBLE_RULE)
            return "\n".join(lines)

        lines.append(_format_row(
            ["#", "策略", "优先级", "匹配键", "处理器", "位置", "sync", "描述"]))
        lines.append(SINGLE_RULE)

        for index, meta in enumerate(actions, 1):
            pattern = meta.match_pattern
            if pattern.strategy is MatchStrategy.EXACT:
                key = "%s -> %r" % (meta.regex_str, pattern.pattern)
            elif pattern.strategy is MatchStrategy.PREFIX:
                key = "%s -> prefix %r" % (meta.regex_str, pattern.pattern)
            elif pattern.strategy is MatchStrategy.SUFFIX:
                key = "%s -> suffix %r" % (meta.regex_str, pattern.pattern)
            else:
                key = meta.regex_str

            lines.append(_format_row([
                str(index),
                pattern.strategy.name,
                str(meta.priority),
                key,
                meta.qualname,
                "%s:%d" % (meta.filename, meta.line),
                "⚡" if meta.sync else "·",
                meta.description or "-",
            ]))

        lines.append(SINGLE_RULE)
        lines.append("   🎯 精确：字典 O(1)      🧭 前缀：线性，priority 优先，其次更长前缀")
        lines.append("   🏁 后缀：线性，priority 优先，其次更长后缀      🌀 正则：线性，priority 优先")
        lines.append("   ⚡ sync=True 全局排他      · sync=False 可并发")
        lines.append(DOUBLE_RULE)
        return "\n".join(lines)

    def reset(self) -> None:
        """清空注册表并解除冻结。主要用于测试。"""
        with self._lock:
            self.exact_matches.clear()
            self.prefix_matches.clear()
            self.suffix_matches.clear()
            self.regex_matches.clear()
            self.all_actions.clear()
            self._seen.clear()
            self.has_sync = False
            self._finalized = False
            logger.info("🧹 注册表已清空并解冻")

    def is_finalized(self) -> bool:
        return self._finalized

    # -- 查询 ---------------------------------------------------------------
    def resolve(self, key: str) -> Optional[ActionMetadata]:
        """返回匹配 key 的 action，未匹配返回 None。

        未 finalize 时抛 RegistryNotInitializedError。
        """
        if not self._finalized:
            raise RegistryNotInitializedError(
                "注册表未初始化，请先调用 init_actions()"
            )

        # 1. 精确匹配：最常见路径，直接命中字典
        metadata = self.exact_matches.get(key)
        if metadata is not None:
            return metadata

        # 2. 前缀匹配：列表已按 (-priority, -len) 排序
        for prefix, meta in self.prefix_matches:
            if key.startswith(prefix):
                return meta

        # 3. 后缀匹配：列表已按 (-priority, -len) 排序
        for suffix, meta in self.suffix_matches:
            if key.endswith(suffix):
                return meta

        # 4. 正则匹配：列表已按 -priority 排序
        for meta in self.regex_matches:
            regex = meta.match_pattern.regex
            if regex is not None and regex.match(key):
                return meta

        return None

    def list_all(self) -> List[ActionMetadata]:
        """按 priority 降序返回全部 action。"""
        return sorted(self.all_actions, key=lambda meta: -meta.priority)


# ============================================================================
# 调试视图
# ============================================================================
@dataclass(frozen=True)
class ActionInfo:
    """list_actions() 的返回值，仅用于展示与调试。"""

    regex: str
    priority: int
    description: str
    sync: bool
    strategy: str
    module: str
    filename: str
    line: int


global_registry = LayeredRegistry()
