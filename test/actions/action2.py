import random
import time

from dispatcher3.action_dispatch_v3 import action


@action(r"\d", "匹配数字", priority=20, sync=True)
def method1(arg):
    print(f"Method d 数字🔢 ==> {arg}")
    # with lock:
    time.sleep(random.uniform(1, 5)+4)
    print(f"Method d 耗时结束 ==> {arg}")
    return f"返回值：Method d {arg}"