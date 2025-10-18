"""
Action Dispatch - Python 实现 v2（改进版）

解决静态注册问题：
1. 显式初始化机制
2. 注册检查和验证
3. 冻结机制防止运行时修改
"""

import re
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Set
from dataclasses import dataclass
from enum import Enum
import time
import inspect
import sys

T = TypeVar('T')
ActionFunc = Callable[[Any], None]


class DispatchError(Exception):
    """分发错误基类"""
    pass


class NoMatchError(DispatchError):
    """没有匹配的 action"""
    pass


class RegistryNotInitializedError(DispatchError):
    """注册表未初始化"""
    pass


class RegistryFrozenError(DispatchError):
    """注册表已冻结，不允许修改"""
    pass


# ============================================================================
# 读写锁实现
# ============================================================================

class RWLock:
    """读写锁"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._read_ready = threading.Condition(self._lock)
        self._readers = 0
        self._writers = 0
        self._write_waiters = 0
    
    def acquire_read(self):
        self._lock.acquire()
        try:
            while self._writers > 0 or self._write_waiters > 0:
                self._read_ready.wait()
            self._readers += 1
        finally:
            self._lock.release()
    
    def release_read(self):
        self._lock.acquire()
        try:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()
        finally:
            self._lock.release()
    
    def acquire_write(self):
        self._lock.acquire()
        self._write_waiters += 1
        try:
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
        self._lock.acquire()
        try:
            self._writers -= 1
            self._read_ready.notify_all()
        finally:
            self._lock.release()


# ============================================================================
# 匹配策略
# ============================================================================

class MatchStrategy(Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    REGEX = "regex"


@dataclass
class MatchPattern:
    strategy: MatchStrategy
    pattern: str
    regex: Optional[re.Pattern] = None


def analyze_regex(regex_str: str) -> MatchPattern:
    """分析正则表达式"""
    if regex_str.startswith('^') and regex_str.endswith('$'):
        middle = regex_str[1:-1]
        special_chars = r'*+?[](){}|\\'
        if not any(c in middle for c in special_chars):
            return MatchPattern(strategy=MatchStrategy.EXACT, pattern=middle)
    
    if regex_str.startswith('^'):
        if regex_str.endswith('.*') or regex_str.endswith('.*$'):
            prefix_end = -2 if regex_str.endswith('.*') else -3
            prefix = regex_str[1:prefix_end]
            special_chars = r'*+?[](){}|\\'
            if not any(c in prefix for c in special_chars):
                return MatchPattern(strategy=MatchStrategy.PREFIX, pattern=prefix)
    
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
    func: ActionFunc
    regex_str: str
    priority: int
    description: str
    sync: bool
    match_pattern: MatchPattern
    # 新增：记录注册位置（用于调试）
    module: str
    line: int


# ============================================================================
# 改进的注册表
# ============================================================================

class LayeredRegistry:
    """
    改进的分层注册表
    
    新增功能：
    1. 冻结机制：初始化后不允许修改
    2. 显式初始化：必须调用 finalize() 才能使用
    3. 注册验证：检测重复注册
    """
    
    def __init__(self):
        self.exact_matches: Dict[str, ActionMetadata] = {}
        self.prefix_matches: List[Tuple[str, ActionMetadata]] = []
        self.regex_matches: List[ActionMetadata] = []
        self.all_actions: List[ActionMetadata] = []
        
        # 新增状态管理
        self._finalized = False
        self._registered_funcs: Set[str] = set()  # 跟踪已注册的函数
    
    def register(self, metadata: ActionMetadata):
        """注册 action（只在初始化阶段允许）"""
        if self._finalized:
            raise RegistryFrozenError(
                f"注册表已冻结，不允许运行时注册 action: {metadata.func.__name__} "
                f"(定义于 {metadata.module}:{metadata.line})"
            )
        
        # 检测重复注册
        func_id = f"{metadata.module}:{metadata.func.__name__}"
        if func_id in self._registered_funcs:
            print(f"⚠️  警告：重复注册 {func_id}")
        self._registered_funcs.add(func_id)
        
        self.all_actions.append(metadata)
    
    def finalize(self):
        """
        完成注册，构建索引结构并冻结
        
        调用此函数后：
        1. 构建分层索引（精确/前缀/正则）
        2. 冻结注册表，不再允许新注册
        3. dispatch() 才能正常工作
        """
        if self._finalized:
            return  # 已经初始化过了
        
        print(f"🔧 正在初始化 action 注册表...")
        print(f"   发现 {len(self.all_actions)} 个 action")
        
        # 构建分层索引
        for metadata in self.all_actions:
            pattern = metadata.match_pattern
            
            if pattern.strategy == MatchStrategy.EXACT:
                existing = self.exact_matches.get(pattern.pattern)
                if existing is None or metadata.priority > existing.priority:
                    self.exact_matches[pattern.pattern] = metadata
            
            elif pattern.strategy == MatchStrategy.PREFIX:
                self.prefix_matches.append((pattern.pattern, metadata))
            
            else:
                self.regex_matches.append(metadata)
        
        # 排序
        self.prefix_matches.sort(key=lambda x: len(x[0]), reverse=True)
        self.regex_matches.sort(key=lambda x: x.priority, reverse=True)
        
        # 冻结
        self._finalized = True
        
        # 统计
        print(f"   精确匹配: {len(self.exact_matches)} 个")
        print(f"   前缀匹配: {len(self.prefix_matches)} 个")
        print(f"   正则匹配: {len(self.regex_matches)} 个")
        print(f"✅ 注册表初始化完成并已冻结\n")
    
    def find(self, key: str) -> Optional[ActionMetadata]:
        """查找匹配的 action"""
        if not self._finalized:
            raise RegistryNotInitializedError(
                "注册表未初始化！请先调用 finalize_registry() 或 init_actions()"
            )
        
        # 1. 精确匹配
        if key in self.exact_matches:
            return self.exact_matches[key]
        
        # 2. 前缀匹配
        for prefix, metadata in self.prefix_matches:
            if key.startswith(prefix):
                return metadata
        
        # 3. 复杂正则
        for metadata in self.regex_matches:
            if metadata.match_pattern.regex and metadata.match_pattern.regex.match(key):
                return metadata
        
        return None
    
    def is_finalized(self) -> bool:
        """检查是否已初始化"""
        return self._finalized
    
    def list_all(self) -> List[ActionMetadata]:
        """列出所有 action"""
        return sorted(self.all_actions, key=lambda x: x.priority, reverse=True)


# ============================================================================
# 全局状态（单例模式，确保真正全局唯一）
# ============================================================================

class _GlobalState:
    """
    全局状态单例
    
    问题：直接使用模块级变量在多次导入时会创建多个实例
    解决：使用类变量确保全局唯一
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.registry = LayeredRegistry()
                    cls._instance.global_lock = RWLock()
        return cls._instance


# 获取全局单例
_state = _GlobalState()
_registry = _state.registry
_global_lock = _state.global_lock


# ============================================================================
# 改进的装饰器
# ============================================================================

def action(regex: str, priority: int = 0, description: str = "", sync: bool = False):
    """
    Action 装饰器
    
    ⚠️ 重要：
    1. 只能在模块顶层使用（不要在函数内或条件语句中使用）
    2. 必须在程序启动时调用 init_actions() 完成初始化
    3. 初始化后不允许动态注册新的 action
    
    正确用法：
        @action(regex=r'^user/.*$', priority=10)
        def handle_user(event):
            pass
        
        if __name__ == '__main__':
            init_actions()  # 显式初始化
            dispatch("user/123", event)
    
    错误用法：
        def create_handler():
            @action(regex=r'^dynamic/.*$')  # ❌ 运行时注册
            def handler(event):
                pass
    """
    def decorator(func: ActionFunc) -> ActionFunc:
        # 获取调用位置（用于调试）
        frame = inspect.currentframe()
        if frame and frame.f_back:
            module = frame.f_back.f_globals.get('__name__', '<unknown>')
            line = frame.f_back.f_lineno
        else:
            module = '<unknown>'
            line = 0
        
        # 分析正则表达式
        match_pattern = analyze_regex(regex)
        
        # 创建元数据
        metadata = ActionMetadata(
            func=func,
            regex_str=regex,
            priority=priority,
            description=description,
            sync=sync,
            match_pattern=match_pattern,
            module=module,
            line=line
        )
        
        # 注册到全局表（如果已冻结会抛出异常）
        try:
            _registry.register(metadata)
        except RegistryFrozenError as e:
            print(f"\n❌ 错误：{e}")
            print(f"💡 提示：不要在运行时动态注册 action")
            print(f"   应该在模块顶层定义所有 action，然后调用 init_actions()")
            raise
        
        return func
    
    return decorator


# ============================================================================
# 显式初始化函数
# ============================================================================

def init_actions():
    """
    初始化 action 注册表
    
    ⚠️ 必须在任何 dispatch() 调用之前调用此函数！
    
    建议在程序入口处调用：
        if __name__ == '__main__':
            init_actions()  # 初始化
            main()          # 开始业务逻辑
    
    或者使用自动初始化：
        init_actions_auto()  # 自动导入所有模块并初始化
    """
    _registry.finalize()


def init_actions_auto(module_names: Optional[List[str]] = None):
    """
    自动初始化：导入指定模块然后初始化
    
    参数：
        module_names: 要导入的模块列表，如 ['handlers', 'api.handlers']
                     如果为 None，只初始化已导入的 action
    
    示例：
        # 自动导入并初始化
        init_actions_auto(['myapp.handlers', 'myapp.api'])
        
        # 或者只初始化已导入的
        import myapp.handlers  # 导入包含 @action 的模块
        init_actions_auto()    # 初始化
    """
    if module_names:
        print(f"📦 正在导入模块...")
        for module_name in module_names:
            try:
                __import__(module_name)
                print(f"   ✓ {module_name}")
            except ImportError as e:
                print(f"   ✗ {module_name}: {e}")
        print()
    
    _registry.finalize()


def is_initialized() -> bool:
    """检查注册表是否已初始化"""
    return _registry.is_finalized()


# ============================================================================
# 分发函数
# ============================================================================

def dispatch(key: str, event: Any) -> None:
    """事件分发函数"""
    try:
        _global_lock.acquire_read()
        
        try:
            metadata = _registry.find(key)
            
            if metadata is None:
                raise NoMatchError(f"没有找到匹配 '{key}' 的 action")
            
            if metadata.sync:
                _global_lock.release_read()
                _global_lock.acquire_write()
                
                try:
                    metadata.func(event)
                finally:
                    _global_lock.release_write()
            else:
                try:
                    metadata.func(event)
                finally:
                    _global_lock.release_read()
        except:
            try:
                _global_lock.release_read()
            except:
                pass
            raise
    
    except Exception as e:
        if isinstance(e, (NoMatchError, RegistryNotInitializedError)):
            raise
        raise


# ============================================================================
# 调试工具
# ============================================================================

@dataclass
class ActionInfo:
    regex: str
    priority: int
    description: str
    sync: bool
    strategy: str
    module: str
    line: int


def list_actions() -> List[ActionInfo]:
    """列出所有已注册的 action"""
    return [
        ActionInfo(
            regex=meta.regex_str,
            priority=meta.priority,
            description=meta.description,
            sync=meta.sync,
            strategy=meta.match_pattern.strategy.value,
            module=meta.module,
            line=meta.line
        )
        for meta in _registry.list_all()
    ]


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    from dataclasses import dataclass
    
    @dataclass
    class TestEvent:
        id: int
        message: str
    
    # ✅ 正确：模块顶层定义
    @action(regex=r"^test/.*$", priority=1)
    def handle_test(event: TestEvent):
        print(f"[TEST] 收到: id={event.id}")
    
    @action(regex=r"^user/\d+$", priority=10)
    def handle_user(event: TestEvent):
        print(f"[USER] 处理用户: {event.id}")
    
    @action(regex=r"^critical/.*$", priority=100, sync=True)
    def handle_critical(event: TestEvent):
        print(f"[CRITICAL] 关键操作: {event.id}")
    
    print("=" * 60)
    print("Action Dispatch v2 - 改进版测试")
    print("=" * 60)
    print()
    
    # ⚠️ 必须显式初始化
    init_actions()
    
    print("已注册的 actions:")
    for info in list_actions():
        print(f"  {info.regex} (优先级: {info.priority}, sync: {info.sync})")
        print(f"    定义于: {info.module}:{info.line}")
    print()
    
    print("测试分发:")
    dispatch("test/something", TestEvent(1, "测试"))
    dispatch("user/123", TestEvent(123, "用户"))
    dispatch("critical/op", TestEvent(999, "关键"))
    
    print()
    
    # ❌ 演示错误用法
    print("演示运行时注册错误:")
    try:
        @action(regex=r"^runtime/.*$")
        def runtime_handler(event):
            pass
    except RegistryFrozenError as e:
        print(f"✓ 正确地阻止了运行时注册：{e}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

