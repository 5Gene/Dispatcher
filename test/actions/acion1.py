import random
import time

from dispatcher3.action_dispatch_v3 import action

@action(r"\w", "匹配字母", 10)
def method2(arg):
    print(f"Method w 单词字母 ==> {arg}")
    time.sleep(random.uniform(1, 5)+4)
    print(f"Method w 单词字母 结束结束 ==> {arg}")
    return "返回值：Method w 2 ==> " + arg