"""用户相关 action。"""
import time

from dispatcher3 import action


@action(r"^user/[0-9]+$", description="按 ID 查询用户", priority=10)
def get_user(event):
    time.sleep(0.1)
    return {"id": event, "name": "user-%s" % event}


@action(r"^user/[0-9]+/update$", description="更新用户", priority=20, sync=True)
def update_user(event):
    time.sleep(0.1)
    return {"id": event, "updated": True}
