"""订单相关 action。"""
import time

from dispatcher3 import action


@action(r"^order/.*", description="订单前缀路由", priority=5)
def any_order(event):
    time.sleep(0.1)
    return {"order": event, "kind": "generic"}


@action(r"^order/refund$", description="退款", priority=50, sync=True)
def refund_order(event):
    time.sleep(0.1)
    return {"order": event, "kind": "refund"}
