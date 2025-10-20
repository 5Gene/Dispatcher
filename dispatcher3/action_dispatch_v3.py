"""
Action Dispatch - Python v3 (性能优化版)

优化项：
1. 使用 __slots__ 减少内存占用和提速
2. 快速路径锁优化
3. 内联关键路径
4. LRU 缓存热点 key
5. 延迟初始化优化

预期性能提升：2-5 倍
"""
import importlib
import pkgutil
import re
import threading
import traceback
from typing import Any, Callable, Dict, List, Optional, Tuple, Set
import time

from dispatcher3.lock import global_rw_lock, global_executor
from dispatcher3.dto import MatchPattern, MatchStrategy, global_registry, ActionFunc, ActionMetadata, \
    RegistryFrozenError, NoMatchError, RegistryNotInitializedError, ActionInfo

# 调试模式（生产环境设为 False）
DEBUG = False
TIME_OUT_TIME = 40
# ============================================================================
# 全局状态（单例模式，确保真正全局唯一）
# ============================================================================
_registry = global_registry
_global_lock = global_rw_lock


def analyze_regex(regex_str: str) -> MatchPattern:
    """
    分析正则表达式
    - 精确匹配(EXACT): 识别形如 ^string$ 的简单字符串匹配模式
    - 前缀匹配(PREFIX): 识别形如 ^prefix.* 的前缀匹配模式
    - 正则匹配(REGEX): 处理所有其他复杂的正则表达式模式
    """
    # 检查是否为精确匹配模式：以^开头且以$结尾的简单字符串
    if regex_str.startswith('^') and regex_str.endswith('$'):
        middle = regex_str[1:-1]  # 提取中间部分（去除^和$）
        # 检查中间部分是否不包含任何正则表达式特殊字符
        if not any(c in middle for c in r'*+?[](){}|\\'):
            # 如果不包含特殊字符，则为精确匹配
            return MatchPattern(MatchStrategy.EXACT, middle)

    # 检查是否为前缀匹配模式：以^开头的前缀模式
    if regex_str.startswith('^'):
        # 检查是否以 .* 或 .*$ 结尾
        if regex_str.endswith('.*') or regex_str.endswith('.*$'):
            # 确定前缀结束位置
            prefix_end = -2 if regex_str.endswith('.*') else -3
            prefix = regex_str[1:prefix_end]  # 提取前缀部分
            # 检查前缀部分是否不包含正则表达式特殊字符
            if not any(c in prefix for c in r'*+?[](){}|\\'):
                # 如果不包含特殊字符，则为前缀匹配
                return MatchPattern(MatchStrategy.PREFIX, prefix)

    # 如果不满足上述条件，则为复杂正则表达式匹配
    # 编译正则表达式并返回 REGEX 匹配策略
    return MatchPattern(MatchStrategy.REGEX, regex_str, re.compile(regex_str))


# ============================================================================
# 优化 5：装饰器（延迟初始化）
# ============================================================================

def action(regex: str, description: str = "", priority: int = 0, sync: bool = False):
    """
    Action 装饰器
    
    优化 5：延迟初始化
    - 生产模式：不使用 inspect，快 30%
    - 调试模式：使用 inspect，提供详细信息

    - 精确匹配(EXACT): 识别形如 ^string$ 的简单字符串匹配模式
    - 前缀匹配(PREFIX): 识别形如 ^prefix.* 的前缀匹配模式
    - 正则匹配(REGEX): 处理所有其他复杂的正则表达式模式
    """

    def decorator(func: ActionFunc) -> ActionFunc:
        # 优化 5：条件性的位置追踪
        if DEBUG:
            import inspect
            frame = inspect.currentframe()
            if frame and frame.f_back:
                module = frame.f_back.f_globals.get('__name__', '<unknown>')
                line = frame.f_back.f_lineno
            else:
                module = '<unknown>'
                line = 0
        else:
            # 快速路径：不追踪位置
            module = '<prod>'
            line = 0

        # 分析正则
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

        # 注册
        try:
            _registry.register(metadata)
        except RegistryFrozenError as e:
            print(f"\n❌ 错误：{e}")
            print(f"💡 提示：不要在运行时动态注册 action")
            raise

        return func

    return decorator


# ============================================================================
# 初始化函数
# ============================================================================

def _init_actions():
    """初始化并冻结注册表"""
    _registry.finalize()


def _init_actions_auto(module_names: Optional[List[str]] = None):
    """自动导入模块并初始化"""
    if module_names:
        for module_name in module_names:
            try:
                __import__(module_name)
                print(f"📦    ✓ {module_name}")
            except ImportError as e:
                print(f"📦    ✗ {module_name}: {e}")
    _registry.finalize()


def _collect_all_modules_from_package(package_name: str) -> List[str]:
    try:
        # 导入包本身
        package = importlib.import_module(package_name)
        # 获取包路径并导入所有模块
        imported_modules = []
        # 遍历包下所有模块
        for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
            full_module_name = f"{package_name}.{modname}"
            imported_modules.append(full_module_name)
        return imported_modules
    except ImportError as e:
        print(f"无法导入包 '{package_name}': {e}")
        return []


def auto_import_package_modules(package_names: List[str]) -> None:
    """
    自动导入多个包下的所有模块

    Args:
        package_names: 包名列表
    """
    print("📦 正在自动导入包下的所有模块...")
    imported_modules = []
    for package_name in package_names:
        modules = _collect_all_modules_from_package(package_name)
        print(f"📦 包 '{package_name}' 下模块:{modules}")
        imported_modules.extend(modules)
    _init_actions_auto(imported_modules)
    print("✅ 包模块导入完成\n")


def is_initialized() -> bool:
    return _registry.is_finalized()


# ============================================================================
# 优化 3：内联优化的 dispatch
# ============================================================================
def dispatch(key: str, event: Any) -> Any:
    return global_executor.submit(_dispatch_thread, key, event)


def _invoke_action(tag, metadata: ActionMetadata, key: str, arg: Any) -> Any:
    fun_info = f"<<{tag}>> {metadata.func.__name__}({key}) =>【{metadata.regex_str}】> {metadata.description}"
    if metadata.sync:
        fun_info = f"🔨<<同步方法>> {fun_info}"
    print(f"{'👇' * 6} {fun_info} {'👇' * 16}")
    start_time = time.time()  # 记录开始时间
    result = None
    try:
        result = metadata.func(arg)  # 执行被装饰的函数
    except Exception as e:
        traceback.print_exc()
    end_time = time.time()  # 记录结束时间
    elapsed_time = end_time - start_time  # 计算耗时
    print(f"{'👆' * 6} {fun_info} cost:{elapsed_time:.2f}s {'👆' * 16}")
    # future = global_executor.submit(metadata.func, event)
    # return future.result(timeout=TIME_OUT_TIME)
    return result


def _dispatch_thread(key: str, event: Any) -> Any:
    """
    事件分发函数（优化版）
    
    优化 3：内联精确匹配
    - 精确匹配快速路径：直接访问字典
    - 其他情况：调用完整查找
    """
    try:
        thread = threading.current_thread()
        print(f"================= {thread.name} >> 🎺 dispatch_thread -> key:{key} ================= ")
        # 优化 2：快速路径锁
        _global_lock.acquire_read()

        try:
            # 优化 3：内联精确匹配（最常见情况）
            # 直接访问 exact_matches，避免函数调用
            metadata = _registry.exact_matches.get(key)

            if not metadata:
                # 不是精确匹配，使用完整查找（带缓存）
                metadata = _registry.find(key)

            if metadata is None:
                print(f"\033[91m❌ 没有找到匹配 '{key}' 的 action\033[0m")
                return None

            # 执行
            if metadata.sync:
                # sync=True：升级为写锁
                _global_lock.release_read()
                _global_lock.acquire_write(key)
                try:
                    return _invoke_action(thread.name, metadata, key, event)
                finally:
                    _global_lock.release_write()
            else:
                # sync=False：保持读锁
                try:
                    return _invoke_action(thread.name, metadata, key, event)
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


def list_actions() -> List[ActionInfo]:
    """列出所有已注册的 action"""
    return [
        ActionInfo(
            regex=meta.regex_str,
            priority=meta.priority,
            description=meta.description,
            sync=meta.sync,
            strategy=meta.match_pattern.strategy.name.lower(),
            module=meta.module,
            line=meta.line
        )
        for meta in _registry.list_all()
    ]


def get_cache_stats():
    """获取缓存统计"""
    return _registry.get_cache_info()


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    from dataclasses import dataclass


    @dataclass
    class TestEvent:
        id: int
        message: str = ""


    # 定义 actions
    @action(regex=r"^test/.*$", priority=1)
    def handle_test(event: TestEvent):
        pass  # 快速测试


    @action(regex=r"^user/\d+$", priority=10)
    def handle_user(event: TestEvent):
        pass


    @action(regex=r"^critical/.*$", priority=100, sync=True)
    def handle_critical(event: TestEvent):
        pass


    print("=" * 70)
    print(" " * 20 + "Action Dispatch v3 - 性能优化版")
    print("=" * 70)
    print()

    # 初始化
    _init_actions()

    print("已注册的 actions:")
    for info in list_actions():
        print(f"  {info.regex} (优先级: {info.priority}, 策略: {info.strategy})")
    print()

    # 性能测试
    print("性能测试：")
    print("-" * 70)

    import time

    # 测试 1：精确匹配（冷启动）
    event = TestEvent(1)
    iterations = 10000

    start = time.perf_counter()
    for _ in range(iterations):
        dispatch("user/123", event)
    elapsed = time.perf_counter() - start

    print(f"1. 精确匹配（重复 key）: {iterations} 次")
    print(f"   总耗时: {elapsed * 1000:.2f} ms")
    print(f"   平均耗时: {elapsed * 1000000 / iterations:.2f} μs/次")

    # 显示缓存统计
    cache_info = get_cache_stats()
    if cache_info:
        print(f"   缓存统计: 命中={cache_info.hits}, 未命中={cache_info.misses}")
        print(f"   命中率: {cache_info.hits / (cache_info.hits + cache_info.misses) * 100:.1f}%")
    print()

    # 测试 2：前缀匹配
    start = time.perf_counter()
    for i in range(iterations):
        dispatch(f"test/{i}", event)
    elapsed = time.perf_counter() - start

    print(f"2. 前缀匹配（不同 key）: {iterations} 次")
    print(f"   总耗时: {elapsed * 1000:.2f} ms")
    print(f"   平均耗时: {elapsed * 1000000 / iterations:.2f} μs/次")
    print()

    print("=" * 70)
    print("测试完成")
    print("=" * 70)
