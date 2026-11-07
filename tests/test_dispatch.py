"""dispatch 的匹配、返回值、异常语义。"""
import pytest

from dispatcher3 import (
    NoMatchError,
    RegistryNotInitializedError,
    action,
    dispatch,
    init_actions,
    is_initialized,
)


def test_dispatch_before_init_raises():
    @action(r"^a$")
    def handler(event):
        return "a"

    with pytest.raises(RegistryNotInitializedError):
        dispatch("a", None)


def test_exact_match():
    @action(r"^user/123$")
    def handler(event):
        return "exact"

    init_actions()
    assert dispatch("user/123", None) == "exact"


def test_prefix_match():
    @action(r"^api/v1/.*")
    def handler(event):
        return "prefix"

    init_actions()
    assert dispatch("api/v1/users/1", None) == "prefix"


def test_regex_match():
    @action(r"^user/[0-9]+$")
    def handler(event):
        return "regex"

    init_actions()
    assert dispatch("user/42", None) == "regex"


def test_dot_in_regex_is_not_literal():
    """回归：'^user.123$' 必须能匹配 'userX123'。"""
    @action(r"^user.123$")
    def handler(event):
        return "dot"

    init_actions()
    assert dispatch("userX123", None) == "dot"
    assert dispatch("user.123", None) == "dot"
    with pytest.raises(NoMatchError):
        dispatch("userXX123", None)


def test_no_match_raises():
    @action(r"^a$")
    def handler(event):
        return "a"

    init_actions()
    with pytest.raises(NoMatchError):
        dispatch("nope", None)


def test_strategy_tier_order():
    """精确 > 前缀 > 正则。"""
    @action(r"^k/x$", priority=1)
    def exact(event):
        return "exact"

    @action(r"^k/.*", priority=99)
    def prefix(event):
        return "prefix"

    @action(r"^k/.*$", priority=99)
    def regex(event):
        return "regex"

    init_actions()
    assert dispatch("k/x", None) == "exact"
    assert dispatch("k/y", None) == "prefix"


def test_handler_exception_propagates():
    @action(r"^boom$")
    def handler(event):
        raise ValueError("boom")

    init_actions()
    with pytest.raises(ValueError, match="boom"):
        dispatch("boom", None)


def test_event_passed_by_reference():
    seen = {}

    @action(r"^ref$")
    def handler(event):
        seen["obj"] = event
        return event

    payload = {"id": 1}
    init_actions()
    assert dispatch("ref", payload) is payload
    assert seen["obj"] is payload


def test_handler_return_value_is_returned():
    @action(r"^ret$")
    def handler(event):
        return None

    init_actions()
    assert dispatch("ret", None) is None


def test_is_initialized():
    assert not is_initialized()
    init_actions()
    assert is_initialized()


def test_suffix_match():
    @action(r".*\.log$")
    def handler(event):
        return "suffix"

    init_actions()
    assert dispatch("var/app.log", None) == "suffix"
    with pytest.raises(NoMatchError):
        dispatch("var/app.log.bak", None)


def test_suffix_tier_order():
    """精确 > 前缀 > 后缀 > 正则。"""
    @action(r".*\.json$", priority=99)
    def suffix(event):
        return "suffix"

    @action(r"^api/.*", priority=1)
    def prefix(event):
        return "prefix"

    @action(r"^order/[0-9]+/.*", priority=99)
    def regex(event):
        return "regex"

    init_actions()

    # 前缀层命中，后缀层排在它后面
    assert dispatch("api/v1/a.json", None) == "prefix"
    # 没有前缀匹配时才轮到后缀
    assert dispatch("other/a.json", None) == "suffix"
    # 后缀不匹配则落到正则
    assert dispatch("order/42/a.txt", None) == "regex"


def test_suffix_priority_within_tier():
    @action(r".*\.log$", priority=1)
    def generic(event):
        return "generic"

    @action(r".*error\.log$", priority=10)
    def specific(event):
        return "specific"

    init_actions()
    assert dispatch("a/error.log", None) == "specific"
    assert dispatch("a/app.log", None) == "generic"
