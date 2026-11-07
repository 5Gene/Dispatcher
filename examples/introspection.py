"""内省 —— 看看注册表里到底有什么。

运行::

    python -m examples.introspection
"""
from dispatcher3 import (
    action,
    analyze_regex,
    dispatch,
    global_registry,
    init_actions,
    list_actions,
    reset,
)
from dispatcher3.lock import global_lock


def main():
    reset()

    @action(r"^user/[0-9]+$", description="按 ID 查用户", priority=10)
    def get_user(event):
        return event

    @action(r"^user/[0-9]+/update$", description="更新用户", priority=20, sync=True)
    def update_user(event):
        return event

    @action(r"^api/v1/.*", description="v1 接口", priority=5)
    def api_v1(event):
        return event

    @action(r"^health$", description="健康检查", priority=100)
    def health(event):
        return event

    init_actions()

    print("=" * 72)
    print("一、list_actions() —— 按 priority 降序")
    print("=" * 72)
    print("  %-22s %-6s %-8s %-6s %-20s %s"
          % ("regex", "prio", "strategy", "sync", "位置", "description"))
    for info in list_actions():
        print("  %-22s %-6d %-8s %-6s %-20s %s"
              % (info.regex, info.priority, info.strategy, info.sync,
                 "%s:%d" % (info.filename, info.line), info.description))
    print()

    print("=" * 72)
    print("二、注册表分层视图")
    print("=" * 72)
    print("  精确层 (dict, O(1)):")
    for literal, meta in global_registry.exact_matches.items():
        print("    %-16r -> %s" % (literal, meta.qualname))
    print("  前缀层 (按 priority, 长度降序):")
    for prefix, meta in global_registry.prefix_matches:
        print("    %-16r -> %s (priority=%d)" % (prefix, meta.qualname, meta.priority))
    print("  正则层 (按 priority 降序):")
    for meta in global_registry.regex_matches:
        print("    %-16r -> %s (priority=%d)"
              % (meta.regex_str, meta.qualname, meta.priority))
    print()

    print("=" * 72)
    print("三、单个正则的分析结果")
    print("=" * 72)
    for regex in (r"^health$", r"^api/v1/.*", r"^user/[0-9]+$"):
        pattern = analyze_regex(regex)
        print("  %-18r -> %-7s %r" % (regex, pattern.strategy.name, pattern.pattern))
    print()

    print("=" * 72)
    print("四、锁状态")
    print("=" * 72)
    print("  has_sync =", global_registry.has_sync)
    print("  (readers, writer, waiters) =", global_lock.snapshot())
    dispatch("health", None)
    print("  dispatch 之后 =", global_lock.snapshot())
    print()


if __name__ == "__main__":
    main()
