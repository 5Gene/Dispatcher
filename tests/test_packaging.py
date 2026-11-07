"""打包与公开 API 的完整性。"""
import importlib

import dispatcher3
from setuptools import find_packages


def test_find_packages_includes_dispatcher3():
    """回归：缺少 __init__.py 时 find_packages() 返回空，wheel 里没有代码。"""
    packages = find_packages()
    assert "dispatcher3" in packages


def test_public_api_is_exported():
    for name in ["action", "dispatch", "dispatch_async", "init_actions",
                 "list_actions", "reset", "is_initialized", "shutdown_executor",
                 "NoMatchError", "RegistryFrozenError", "RegistryNotInitializedError"]:
        assert hasattr(dispatcher3, name), name
        assert name in dispatcher3.__all__


def test_version_present():
    assert dispatcher3.__version__


def test_all_names_resolve():
    for name in dispatcher3.__all__:
        getattr(dispatcher3, name)
