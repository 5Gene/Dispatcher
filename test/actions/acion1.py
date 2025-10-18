from dispatcher.action_dispatch_v3 import action


@action(r"\w", "匹配字母", 10)
def method2(arg):
    print(f"Method w 2 ==> {arg}")
    return "Method w 2 ==> " + arg