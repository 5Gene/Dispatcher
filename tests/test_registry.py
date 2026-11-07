"""注册表：注册、冻结、重置、重复检测、层内优先级。"""
import pytest

from dispatcher3 import (
    MatchStrategy,
    RegistryFrozenError,
    action,
    init_actions,
    list_actions,
    reset,
)
from dispatcher3.dto import ActionMetadata, MatchPattern, global_registry


def make_metadata(regex, priority=0, name="f", sync=False, module="m"):
    def func(event):
        return name

    func.__name__ = name
    func.__qualname__ = name
    func.__module__ = module
    return ActionMetadata(
        func=func,
        regex_str=regex,
        priority=priority,
        description="",
        sync=sync,
        match_pattern=__import__("dispatcher3").analyze_regex(regex),
        module=module,
        line=1,
        qualname=name,
    )


def test_register_after_finalize_raises():
    @action(r"^a$")
    def handler(event):
        return "a"

    init_actions()
    with pytest.raises(RegistryFrozenError):
        global_registry.register(make_metadata(r"^b$", name="late"))


def test_reset_allows_reregistration():
    @action(r"^a$")
    def handler(event):
        return "a"

    init_actions()
    assert global_registry.is_finalized()

    reset()
    assert not global_registry.is_finalized()
    assert global_registry.all_actions == []

    @action(r"^a$")
    def handler2(event):
        return "a2"

    init_actions()
    assert global_registry.is_finalized()


def test_duplicate_registration_detected_by_module_and_qualname():
    def same(event):
        return 1

    same.__module__ = "pkg.mod_a"
    same.__qualname__ = "same"

    def same_other(event):
        return 2

    same_other.__module__ = "pkg.mod_b"
    same_other.__qualname__ = "same"

    # 不同模块的同名函数不是重复
    global_registry.register(make_metadata(r"^a$", name="same", module="pkg.mod_a"))
    global_registry.register(make_metadata(r"^b$", name="same", module="pkg.mod_b"))

    # 同模块同名才是重复
    with pytest.raises(RegistryFrozenError, match="重复注册"):
        global_registry.register(make_metadata(r"^c$", name="same", module="pkg.mod_a"))


def test_metadata_records_real_module_and_line():
    @action(r"^a$")
    def handler(event):
        return "a"

    meta = global_registry.all_actions[0]
    assert meta.module == __name__
    assert meta.line > 0
    assert meta.qualname.endswith("handler")


def test_exact_same_pattern_higher_priority_wins():
    global_registry.register(make_metadata(r"^k$", priority=1, name="low", module="m1"))
    global_registry.register(make_metadata(r"^k$", priority=9, name="high", module="m2"))
    init_actions()
    assert global_registry.resolve("k").func(None) == "high"


def test_exact_same_priority_keeps_first():
    global_registry.register(make_metadata(r"^k$", priority=5, name="first", module="m1"))
    global_registry.register(make_metadata(r"^k$", priority=5, name="second", module="m2"))
    init_actions()
    assert global_registry.resolve("k").func(None) == "first"


def test_prefix_priority_beats_longer_prefix():
    """回归：旧版本按前缀长度排序，priority 被忽略。"""
    global_registry.register(make_metadata(r"^api/.*", priority=100, name="generic", module="m1"))
    global_registry.register(make_metadata(r"^api/v1/.*", priority=1, name="specific", module="m2"))
    init_actions()
    assert global_registry.resolve("api/v1/users").func(None) == "generic"


def test_prefix_same_priority_longer_wins():
    global_registry.register(make_metadata(r"^api/.*", priority=5, name="short", module="m1"))
    global_registry.register(make_metadata(r"^api/v1/.*", priority=5, name="long", module="m2"))
    init_actions()
    assert global_registry.resolve("api/v1/users").func(None) == "long"


def test_regex_priority_order():
    global_registry.register(make_metadata(r"^user/[0-9]+$", priority=1, name="low", module="m1"))
    global_registry.register(make_metadata(r"^user/.*", priority=9, name="high", module="m2"))
    init_actions()
    assert global_registry.resolve("user/1").func(None) == "high"


def test_list_actions_sorted_by_priority_desc():
    global_registry.register(make_metadata(r"^a$", priority=1, name="a", module="m1"))
    global_registry.register(make_metadata(r"^b$", priority=7, name="b", module="m2"))
    init_actions()
    assert [info.regex for info in list_actions()] == [r"^b$", r"^a$"]
    assert list_actions()[0].strategy == MatchStrategy.EXACT.name.lower()


def test_finalize_is_idempotent():
    @action(r"^a$")
    def handler(event):
        return "a"

    init_actions()
    init_actions()
    assert len(global_registry.all_actions) == 1


def test_suffix_priority_beats_longer_suffix():
    global_registry.register(make_metadata(r".*\.log$", priority=100,
                                           name="generic", module="m1"))
    global_registry.register(make_metadata(r".*error\.log$", priority=1,
                                           name="specific", module="m2"))
    init_actions()
    assert global_registry.resolve("a/error.log").func(None) == "generic"


def test_suffix_same_priority_longer_wins():
    global_registry.register(make_metadata(r".*\.log$", priority=5,
                                           name="short", module="m1"))
    global_registry.register(make_metadata(r".*error\.log$", priority=5,
                                           name="long", module="m2"))
    init_actions()
    assert global_registry.resolve("a/error.log").func(None) == "long"


def test_suffix_strategy_recorded():
    global_registry.register(make_metadata(r".*\.log$", name="s", module="m1"))
    init_actions()
    assert global_registry.suffix_matches[0][0] == ".log"
    assert global_registry.resolve("a.log") is not None
