from dispatcher.action_dispatch_v3 import action


@action(r"\d", "匹配数字")
def method1(arg):
    print(f"Method d 1 ==> {arg}")
    # with lock:
    #     time.sleep(10)
    print(f"Method d 2 ==> {arg}")
    return "Method d 2"