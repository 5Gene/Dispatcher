"""扫描包下所有模块并自动注册其中的 @action。

运行::

    python -m examples.auto_import
"""
from dispatcher3 import auto_import_package_modules, dispatch, init_actions, list_actions, enable_logging


def main():
    imported = auto_import_package_modules(["examples.actions"])
    print("已导入模块:", imported)

    # 扫描与冻结是两步：导入只负责触发注册，init_actions() 才构建索引
    init_actions()

    print()
    print("已注册的 action:")
    for info in list_actions():
        print("  %-24s priority=%-3d strategy=%-6s sync=%s"
              % (info.regex, info.priority, info.strategy, info.sync))

    print()
    print(dispatch("user/7", 7))
    print(dispatch("user/7/update", 7))
    print(dispatch("order/refund", "refund"))


if __name__ == "__main__":
    enable_logging()
    main()
