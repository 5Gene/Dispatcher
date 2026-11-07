"""匹配策略与优先级规则 —— 覆盖三种匹配层和所有优先级场景。

运行::

    python -m examples.matching
"""
from dispatcher3 import action, analyze_regex, dispatch, init_actions, reset


def show_analysis():
    print("=" * 72)
    print("一、正则会被降级成哪种策略")
    print("=" * 72)
    cases = [
        (r"^user/123$", "无元字符 -> 精确"),
        (r"^$", "空串也是精确"),
        (r"^api/v1/.*", "前缀 + 通配"),
        (r"^api/v1/.*$", "前缀 + 通配 + 锚点"),
        (r".*\.log$", "后缀 + 通配"),
        (r"^.*\.json$", "后缀 + 通配 + 锚点"),
        (r"^a\.b$", "转义的点 -> 精确 'a.b'"),
        (r"^user/[0-9]+$", "字符类 -> 完整正则"),
        (r"^user.123$", "未转义的点 -> 完整正则（旧版会误判为精确）"),
        (r"^a|b$", "分支 -> 完整正则"),
        (r"^x[abc]$", "字符集 -> 完整正则"),
        (r".*abc", "没有 $ -> 包含语义，不能降级"),
    ]
    for regex, note in cases:
        pattern = analyze_regex(regex)
        print("  %-18r %-8s %-12r  %s"
              % (regex, pattern.strategy.name, pattern.pattern, note))
    print()


def show_suffix():
    print("=" * 72)
    print("二、后缀匹配")
    print("=" * 72)

    @action(r".*\.log$", description="任意日志", priority=10)
    def any_log(event):
        return "任意 .log"

    @action(r".*error\.log$", description="错误日志", priority=20)
    def error_log(event):
        return "error.log"

    @action(r".*\.json$", description="JSON", priority=10)
    def json_file(event):
        return ".json"

    init_actions()
    for key in ("var/app.log", "var/error.log", "data/a.json"):
        print("  dispatch(%-16r) -> %s" % (key, dispatch(key, None)))
    print("  说明：同层内 priority 高者胜（error.log 赢过 .log），")
    print("        同 priority 时更长后缀胜。")
    print()


def show_three_tiers():
    print("=" * 72)
    print("三、四种匹配层各自命中")
    print("=" * 72)

    @action(r"^exact/key$", description="精确")
    def on_exact(event):
        return "精确命中"

    @action(r"^prefix/.*", description="前缀")
    def on_prefix(event):
        return "前缀命中"

    @action(r"^regex/[0-9]+$", description="正则")
    def on_regex(event):
        return "正则命中"

    @action(r".*\.md$", description="后缀")
    def on_suffix(event):
        return "后缀命中"

    init_actions()
    for key in ("exact/key", "prefix/anything", "regex/42", "doc/readme.md"):
        print("  dispatch(%-16r) -> %s" % (key, dispatch(key, None)))
    print()


def show_priority_same_tier():
    print("=" * 72)
    print("四、同层内 priority 高者胜")
    print("=" * 72)
    reset()

    @action(r"^api/.*", priority=100)
    def generic(event):
        return "generic(priority=100)"

    @action(r"^api/v1/.*", priority=1)
    def specific(event):
        return "specific(priority=1)"

    init_actions()
    print("  前缀层两条都匹配 'api/v1/users'：")
    print("    ->", dispatch("api/v1/users", None))
    print("  说明：priority 优先，不会因为 v1 前缀更长就赢")
    print()


def show_longest_prefix_tiebreak():
    print("=" * 72)
    print("五、同层同 priority 时，更长前缀优先")
    print("=" * 72)
    reset()

    @action(r"^api/.*", priority=5)
    def short(event):
        return "api/(priority=5)"

    @action(r"^api/v1/.*", priority=5)
    def long(event):
        return "api/v1/(priority=5)"

    init_actions()
    print("  ->", dispatch("api/v1/users", None))
    print("  ->", dispatch("api/other", None))
    print()


def show_tier_short_circuit():
    print("=" * 72)
    print("六、层间短路：精确层命中就不再往下看")
    print("=" * 72)
    reset()

    @action(r"^k/x$", priority=1)
    def exact(event):
        return "精确(priority=1)"

    @action(r"^k/.*", priority=999)
    def prefix(event):
        return "前缀(priority=999)"

    init_actions()
    print("  dispatch('k/x')  ->", dispatch("k/x", None))
    print("  dispatch('k/y')  ->", dispatch("k/y", None))
    print("  说明：层间不比较 priority。精确层是 O(1) 字典命中，")
    print("        为了比 priority 去扫前缀层就把这个优势丢了。")
    print()


def main():
    reset()
    show_analysis()
    reset()
    show_suffix()
    reset()
    show_three_tiers()
    show_priority_same_tier()
    show_longest_prefix_tiebreak()
    show_tier_short_circuit()


if __name__ == "__main__":
    main()
