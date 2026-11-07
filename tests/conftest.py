import pytest

from dispatcher3 import reset, shutdown_executor


@pytest.fixture(autouse=True)
def clean_state():
    """每个用例前后都清空注册表，保证用例之间完全隔离。"""
    reset()
    yield
    reset()
    shutdown_executor(wait=True)
