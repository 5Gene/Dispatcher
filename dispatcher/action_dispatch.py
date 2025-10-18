"""
Action Dispatch - Python 实现

一个高性能的基于装饰器的 Action 注册与分发系统

特性：
- 声明式注册（@action 装饰器）
- 正则匹配 + 优先级
- 全局同步执行模式
- 分层匹配优化（精确/前缀/正则）
- 读写锁优化并发性能
- 类型安全（类型提示）
"""

import re
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar
from dataclasses import dataclass
from enum import Enum
import time

# ============================================================================
# 类型定义
# ============================================================================

T = TypeVar('T')
ActionFunc = Callable[[Any], None]


class DispatchError(Exception):
    """分发错误基类"""
    pass


class NoMatchError(DispatchError):
    """没有匹配的 action"""
    pass


class LockPoisonedError(DispatchError):
    """锁被污染（某个线程异常）"""
    pass


# ============================================================================
# 读写锁实现（优化并发性能）
# ============================================================================

class RWLock:
    """
    读写锁实现
    
    特性：
    - 多个读锁可以并发
    - 写锁独占，与所有其他锁互斥
    - 写锁优先（避免写饥饿）
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._read_ready = threading.Condition(self._lock)
        self._readers = 0
        self._writers = 0
        self._write_waiters = 0
    
    def acquire_read(self):
        """获取读锁"""
        self._lock.acquire()
        try:
            # 等待写锁释放
            while self._writers > 0 or self._write_waiters > 0:
                self._read_ready.wait()
            self._readers += 1
        finally:
            self._lock.release()
    
    def release_read(self):
        """释放读锁"""
        self._lock.acquire()
        try:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()
        finally:
            self._lock.release()
    
    def acquire_write(self):
        """获取写锁"""
        self._lock.acquire()
        self._write_waiters += 1
        try:
            # 等待所有读锁和写锁释放
            while self._readers > 0 or self._writers > 0:
                self._read_ready.wait()
            self._writers += 1
            self._write_waiters -= 1
        except:
            self._write_waiters -= 1
            raise
        finally:
            self._lock.release()
    
    def release_write(self):
        """释放写锁"""
        self._lock.acquire()
        try:
            self._writers -= 1
            self._read_ready.notify_all()
        finally:
            self._lock.release()


# ============================================================================
# 匹配策略（分层匹配优化）
# ============================================================================

class MatchStrategy(Enum):
    """匹配策略类型"""
    EXACT = "exact"      # 精确匹配 O(1)
    PREFIX = "prefix"    # 前缀匹配 O(m)
    REGEX = "regex"      # 复杂正则 O(k)


@dataclass
class MatchPattern:
    """匹配模式"""
    strategy: MatchStrategy
    pattern: str  # 精确字符串或前缀
    regex: Optional[re.Pattern] = None  # 编译后的正则


def analyze_regex(regex_str: str) -> MatchPattern:
    """
    分析正则表达式，确定最优匹配策略
    
    返回：
    - 精确匹配：^literal$
    - 前缀匹配：^prefix.*
    - 复杂正则：其他
    """
    # 检查精确匹配：^literal$ 且不含特殊字符
    if regex_str.startswith('^') and regex_str.endswith('$'):
        middle = regex_str[1:-1]
        special_chars = r'*+?[](){}|\\'
        if not any(c in middle for c in special_chars):
            return MatchPattern(
                strategy=MatchStrategy.EXACT,
                pattern=middle
            )
    
    # 检查前缀匹配：^prefix.* 或 ^prefix.*$
    if regex_str.startswith('^'):
        if regex_str.endswith('.*') or regex_str.endswith('.*$'):
            prefix_end = -2 if regex_str.endswith('.*') else -3
            prefix = regex_str[1:prefix_end]
            special_chars = r'*+?[](){}|\\'
            if not any(c in prefix for c in special_chars):
                return MatchPattern(
                    strategy=MatchStrategy.PREFIX,
                    pattern=prefix
                )
    
    # 复杂正则
    return MatchPattern(
        strategy=MatchStrategy.REGEX,
        pattern=regex_str,
        regex=re.compile(regex_str)
    )


# ============================================================================
# Action 元数据
# ============================================================================

@dataclass
class ActionMetadata:
    """Action 元数据"""
    func: ActionFunc
    regex_str: str
    priority: int
    description: str
    sync: bool
    match_pattern: MatchPattern


# ============================================================================
# 分层注册表（性能优化）
# ============================================================================

class LayeredRegistry:
    """
    分层注册表
    
    优化策略：
    - 精确匹配：dict O(1)
    - 前缀匹配：list O(m)，按长度降序
    - 复杂正则：list O(k)，按优先级降序
    """
    
    def __init__(self):
        self.exact_matches: Dict[str, ActionMetadata] = {}
        self.prefix_matches: List[Tuple[str, ActionMetadata]] = []
        self.regex_matches: List[ActionMetadata] = []
        self.all_actions: List[ActionMetadata] = []
    
    def register(self, metadata: ActionMetadata):
        """注册 action"""
        self.all_actions.append(metadata)
        
        pattern = metadata.match_pattern
        
        if pattern.strategy == MatchStrategy.EXACT:
            # 精确匹配：只保留优先级最高的
            existing = self.exact_matches.get(pattern.pattern)
            if existing is None or metadata.priority > existing.priority:
                self.exact_matches[pattern.pattern] = metadata
        
        elif pattern.strategy == MatchStrategy.PREFIX:
            # 前缀匹配：按长度降序插入
            self.prefix_matches.append((pattern.pattern, metadata))
            self.prefix_matches.sort(key=lambda x: len(x[0]), reverse=True)
        
        else:  # REGEX
            # 复杂正则：按优先级降序插入
            self.regex_matches.append(metadata)
            self.regex_matches.sort(key=lambda x: x.priority, reverse=True)
    
    def find(self, key: str) -> Optional[ActionMetadata]:
        """
        查找匹配的 action
        
        按照以下顺序：
        1. 精确匹配 O(1)
        2. 前缀匹配 O(m)
        3. 复杂正则 O(k)
        """
        # 1. 精确匹配（最快）
        if key in self.exact_matches:
            return self.exact_matches[key]
        
        # 2. 前缀匹配（较快）
        for prefix, metadata in self.prefix_matches:
            if key.startswith(prefix):
                return metadata
        
        # 3. 复杂正则（较慢）
        for metadata in self.regex_matches:
            if metadata.match_pattern.regex and metadata.match_pattern.regex.match(key):
                return metadata
        
        return None
    
    def list_all(self) -> List[ActionMetadata]:
        """列出所有 action"""
        return sorted(self.all_actions, key=lambda x: x.priority, reverse=True)


# ============================================================================
# 全局状态
# ============================================================================

# 全局注册表
_registry = LayeredRegistry()

# 全局读写锁
_global_lock = RWLock()


# ============================================================================
# 装饰器
# ============================================================================

def action(regex: str, priority: int = 0, description: str = "", sync: bool = False):
    """
    Action 装饰器
    
    参数：
        regex: 匹配 key 的正则表达式
        priority: 优先级，数值越大越高，默认 0
        description: 描述信息，默认空字符串
        sync: 是否启用全局同步模式，默认 False
    
    示例：
        @action(regex=r'^user/\d+/read$', priority=10, sync=False)
        def handle_user_read(event):
            print(f"读取用户: {event.user_id}")
    """
    def decorator(func: ActionFunc) -> ActionFunc:
        # 分析正则表达式
        match_pattern = analyze_regex(regex)
        
        # 创建元数据
        metadata = ActionMetadata(
            func=func,
            regex_str=regex,
            priority=priority,
            description=description,
            sync=sync,
            match_pattern=match_pattern
        )
        
        # 注册到全局表
        _registry.register(metadata)
        
        # 返回原函数（不修改）
        return func
    
    return decorator


# ============================================================================
# 分发函数
# ============================================================================

def dispatch(key: str, event: Any) -> None:
    """
    事件分发函数
    
    执行流程：
    1. 获取读锁进行匹配（允许并发）
    2. 查找匹配的 action（分层匹配优化）
    3. 根据 sync 标志决定执行策略：
       - sync = False: 保持读锁执行（允许并发）
       - sync = True: 升级为写锁执行（全局排他）
    
    参数：
        key: 匹配键
        event: 事件对象（Python 默认引用传递，零拷贝）
    
    异常：
        NoMatchError: 没有匹配的 action
        LockPoisonedError: 锁被污染
    
    示例：
        dispatch("user/123/read", UserEvent(user_id=123))
    """
    try:
        # 1. 获取读锁进行匹配（允许并发）
        _global_lock.acquire_read()
        
        try:
            # 2. 查找匹配的 action（分层匹配，性能优化）
            metadata = _registry.find(key)
            
            if metadata is None:
                raise NoMatchError(f"没有找到匹配 '{key}' 的 action")
            
            # 3. 根据 sync 标志决定执行策略
            if metadata.sync:
                # sync = True: 升级为写锁（全局排他）
                _global_lock.release_read()
                _global_lock.acquire_write()
                
                try:
                    # 在写锁保护下执行（独占）
                    metadata.func(event)
                finally:
                    _global_lock.release_write()
            else:
                # sync = False: 保持读锁执行（允许并发）
                try:
                    # Python 的对象传递就是引用传递，零拷贝
                    metadata.func(event)
                finally:
                    _global_lock.release_read()
        except:
            # 如果还持有读锁，需要释放
            try:
                _global_lock.release_read()
            except:
                pass
            raise
    
    except Exception as e:
        if isinstance(e, (NoMatchError, LockPoisonedError)):
            raise
        # 其他异常也抛出
        raise


# ============================================================================
# 调试工具
# ============================================================================

@dataclass
class ActionInfo:
    """Action 信息（用于调试）"""
    regex: str
    priority: int
    description: str
    sync: bool
    strategy: str


def list_actions() -> List[ActionInfo]:
    """
    列出所有已注册的 action
    
    返回：
        按优先级降序排列的 action 列表
    """
    return [
        ActionInfo(
            regex=meta.regex_str,
            priority=meta.priority,
            description=meta.description,
            sync=meta.sync,
            strategy=meta.match_pattern.strategy.value
        )
        for meta in _registry.list_all()
    ]


# ============================================================================
# 性能统计（可选）
# ============================================================================

@dataclass
class PerformanceStats:
    """性能统计"""
    total_dispatches: int = 0
    exact_matches: int = 0
    prefix_matches: int = 0
    regex_matches: int = 0
    total_time_ns: int = 0
    
    def average_time_us(self) -> float:
        """平均耗时（微秒）"""
        if self.total_dispatches == 0:
            return 0.0
        return (self.total_time_ns / self.total_dispatches) / 1000.0


_stats = PerformanceStats()


def dispatch_with_stats(key: str, event: Any) -> None:
    """带性能统计的 dispatch"""
    start = time.perf_counter_ns()
    
    try:
        dispatch(key, event)
    finally:
        elapsed = time.perf_counter_ns() - start
        _stats.total_dispatches += 1
        _stats.total_time_ns += elapsed


def get_stats() -> PerformanceStats:
    """获取性能统计"""
    return _stats


def reset_stats():
    """重置性能统计"""
    global _stats
    _stats = PerformanceStats()


# ============================================================================
# 示例和测试
# ============================================================================

if __name__ == "__main__":
    # 简单测试
    from dataclasses import dataclass
    
    @dataclass
    class TestEvent:
        id: int
        message: str
    
    @action(regex=r"^test/.*$", priority=1)
    def handle_test(event: TestEvent):
        print(f"[TEST] 收到: id={event.id}, msg={event.message}")
    
    @action(regex=r"^user/\d+$", priority=10, sync=False)
    def handle_user(event: TestEvent):
        print(f"[USER] 处理用户: {event.id}")
    
    @action(regex=r"^critical/.*$", priority=100, sync=True)
    def handle_critical(event: TestEvent):
        print(f"[CRITICAL] 关键操作: {event.id} (全局排他)")
        import time
        time.sleep(0.1)
    
    print("=== Python Action Dispatch 测试 ===\n")
    
    print("已注册的 actions:")
    for info in list_actions():
        print(f"  - regex: {info.regex}, priority: {info.priority}, "
              f"sync: {info.sync}, strategy: {info.strategy}")
    print()
    
    print("测试分发:")
    dispatch("test/something", TestEvent(1, "测试消息"))
    dispatch("user/123", TestEvent(123, "用户操作"))
    dispatch("critical/op", TestEvent(999, "关键操作"))
    
    try:
        dispatch("unknown/key", TestEvent(0, "未知"))
    except NoMatchError as e:
        print(f"预期的错误: {e}")
    
    print("\n=== 测试完成 ===")

