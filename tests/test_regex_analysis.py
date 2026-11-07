"""analyze_regex 的策略判定必须与正则语义严格等价。"""
import pytest

from dispatcher3 import MatchStrategy, analyze_regex


@pytest.mark.parametrize("regex, expected_literal", [
    (r"^user/123$", "user/123"),
    (r"^abc$", "abc"),
    (r"^$", ""),
    (r"^a b$", "a b"),
    (r"^api_v1$", "api_v1"),
    (r"^a-b$", "a-b"),
])
def test_exact(regex, expected_literal):
    pattern = analyze_regex(regex)
    assert pattern.strategy is MatchStrategy.EXACT
    assert pattern.pattern == expected_literal


@pytest.mark.parametrize("regex, expected_prefix", [
    (r"^api/v1/.*", "api/v1/"),
    (r"^api/v1/.*$", "api/v1/"),
    (r"^test/.*", "test/"),
    (r"^.*$", ""),
])
def test_prefix(regex, expected_prefix):
    pattern = analyze_regex(regex)
    assert pattern.strategy is MatchStrategy.PREFIX
    assert pattern.pattern == expected_prefix


@pytest.mark.parametrize("regex", [
    r"^user/\d+$",      # 字符类
    r"^user.123$",       # 未转义的点 —— 旧版本会误判为 EXACT
    r"^v1.0$",           # 同上
    r"^a|b$",            # 分支
    r"^x[abc]$",         # 字符集
    r"^a+b$",            # 量词
    r"^a{2}$",           # 计数
    r"^(a)$",            # 分组
    r"^a\d$",           # 语义转义 \d，不是字面量
    r"^a\w+$",          # 语义转义 \w
    r"^\$",             # 锚点吃掉后只剩一个孤立反斜杠
    r"user",             # 无锚点
    r".*abc",            # 没有 $，是"包含"而不是后缀
])
def test_regex_fallback(regex):
    assert analyze_regex(regex).strategy is MatchStrategy.REGEX


def test_regex_is_compiled():
    pattern = analyze_regex(r"^user/\d+$")
    assert pattern.regex is not None
    assert pattern.regex.match("user/123")


def test_invalid_regex_raises_value_error():
    with pytest.raises(ValueError, match="非法正则"):
        analyze_regex(r"^[unclosed$")


def test_prefix_with_dot_is_not_downgraded():
    """'^api.v1/.*' 中的点不能当作字面量。"""
    pattern = analyze_regex(r"^api.v1/.*")
    assert pattern.strategy is MatchStrategy.REGEX
    assert pattern.regex.match("apiXv1/users")


# ---------------------------------------------------------------------------
# 后缀
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("regex, expected_suffix", [
    (r".*\.log$", ".log"),
    (r"^.*\.json$", ".json"),
    (r".*/health$", "/health"),
    (r".*_test$", "_test"),
])
def test_suffix(regex, expected_suffix):
    pattern = analyze_regex(regex)
    assert pattern.strategy is MatchStrategy.SUFFIX
    assert pattern.pattern == expected_suffix


def test_suffix_requires_dollar_anchor():
    """' .*abc' 没有 $，语义是"包含"，不能降级成后缀。"""
    assert analyze_regex(r".*abc").strategy is MatchStrategy.REGEX


def test_suffix_does_not_swallow_everything():
    """' .*$' 是通配，应由前缀层（空前缀）接管，而不是后缀层。"""
    assert analyze_regex(r".*$").strategy is MatchStrategy.REGEX
    assert analyze_regex(r"^.*$").strategy is MatchStrategy.PREFIX


# ---------------------------------------------------------------------------
# 转义元字符
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("regex, expected_literal", [
    (r"^a\.b$", "a.b"),
    (r"^v1\.0$", "v1.0"),
    (r"^a\*b$", "a*b"),
    (r"^a\\b$", "a\\b"),
])
def test_escaped_metacharacter_is_literal(regex, expected_literal):
    """\\。这类转义元字符等价于字面量，可以安全降级。"""
    pattern = analyze_regex(regex)
    assert pattern.strategy is MatchStrategy.EXACT
    assert pattern.pattern == expected_literal


def test_semantic_escape_is_not_downgraded():
    """\\d / \\w / \\s 是语义转义，必须留在正则层。"""
    for regex in (r"^\d+$", r"^\w+$", r"^\s$", r"^\bfoo$"):
        assert analyze_regex(regex).strategy is MatchStrategy.REGEX, regex
