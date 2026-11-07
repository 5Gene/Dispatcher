"""dispatcher3 —— 基于装饰器的 action 注册与分发。

Quick start::

    from dispatcher3 import action, dispatch, init_actions

    @action(r"^user/[0-9]+$", priority=10)
    def handle_user(event):
        return event

    init_actions()
    print(dispatch("user/123", {"id": 123}))
"""
from dispatcher3.dto import (
    ActionInfo,
    DispatchError,
    MatchStrategy,
    NoMatchError,
    RegistryFrozenError,
    RegistryNotInitializedError,
    global_registry,
)
from dispatcher3.dispatcher import (
    action,
    analyze_regex,
    auto_import_package_modules,
    dispatch,
    dispatch_async,
    init_actions,
    is_initialized,
    list_actions,
    reset,
    shutdown_executor,
)
from dispatcher3.log import disable_logging, enable_logging

__version__ = "0.2.0"

__all__ = [
    "ActionInfo",
    "DispatchError",
    "MatchStrategy",
    "NoMatchError",
    "RegistryFrozenError",
    "RegistryNotInitializedError",
    "action",
    "analyze_regex",
    "auto_import_package_modules",
    "disable_logging",
    "dispatch",
    "dispatch_async",
    "enable_logging",
    "global_registry",
    "init_actions",
    "is_initialized",
    "list_actions",
    "reset",
    "shutdown_executor",
    "__version__",
]
