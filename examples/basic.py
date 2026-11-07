"""最小可运行示例：定义 action、初始化、同步分发。

运行::

    python -m examples.basic
"""
from dispatcher3 import action, dispatch, init_actions, list_actions


@action(r"^user/[0-9]+$", description="按 ID 查询用户", priority=10)
def get_user(user_id):
    return {"id": user_id, "name": "user-%s" % user_id}


@action(r"^api/v1/.*", description="v1 接口", priority=5)
def api_v1(path):
    return {"path": path, "version": 1}


@action(r"^critical/.*", description="关键操作，全局排他", priority=100, sync=True)
def critical(event):
    return {"event": event, "exclusive": True}


def main():
    init_actions()

    print("已注册的 action:")
    for info in list_actions():
        print("  %-16s priority=%-3d strategy=%-6s sync=%s"
              % (info.regex, info.priority, info.strategy, info.sync))

    print()
    print(dispatch("user/123", 123))
    print(dispatch("api/v1/users", "api/v1/users"))
    print(dispatch("critical/deploy", "deploy"))


if __name__ == "__main__":
    main()
