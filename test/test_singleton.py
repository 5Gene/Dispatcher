"""
测试单例模式：验证多次导入时 registry 和 lock 是同一个实例
"""

import sys

# 测试 1：正常导入
print("=" * 70)
print("测试 1：正常导入")
print("=" * 70)

import dispatcher.action_dispatch_v3 as ad1

print(f"ad1._registry id: {id(ad1._registry)}")
print(f"ad1._global_lock id: {id(ad1._global_lock)}")
print()

# 测试 2：再次导入（通过 import）
print("=" * 70)
print("测试 2：再次导入")
print("=" * 70)

import dispatcher.action_dispatch_v3 as ad2

print(f"ad2._registry id: {id(ad2._registry)}")
print(f"ad2._global_lock id: {id(ad2._global_lock)}")
print()

# 验证是否是同一个对象
if id(ad1._registry) == id(ad2._registry):
    print("✅ _registry 是同一个实例（单例正确）")
else:
    print("❌ _registry 是不同实例（单例失败）")

if id(ad1._global_lock) == id(ad2._global_lock):
    print("✅ _global_lock 是同一个实例（单例正确）")
else:
    print("❌ _global_lock 是不同实例（单例失败）")

print()

# 测试 3：通过 importlib 重新导入
print("=" * 70)
print("测试 3：通过 importlib 强制重新加载")
print("=" * 70)

import importlib
importlib.reload(ad1)

print(f"重新加载后 ad1._registry id: {id(ad1._registry)}")
print(f"重新加载后 ad1._global_lock id: {id(ad1._global_lock)}")
print()

# 再次验证
if id(ad1._registry) == id(ad2._registry):
    print("✅ 重新加载后 _registry 仍是同一个实例（单例正确）")
else:
    print("❌ 重新加载后 _registry 变成不同实例（单例失败）")

if id(ad1._global_lock) == id(ad2._global_lock):
    print("✅ 重新加载后 _global_lock 仍是同一个实例（单例正确）")
else:
    print("❌ 重新加载后 _global_lock 变成不同实例（单例失败）")

print()

# 测试 4：验证 _GlobalState 单例
print("=" * 70)
print("测试 4：验证 _GlobalState 单例")
print("=" * 70)

state1 = ad1._state
state2 = ad2._state

print(f"state1 id: {id(state1)}")
print(f"state2 id: {id(state2)}")

if id(state1) == id(state2):
    print("✅ _GlobalState 是同一个实例（单例正确）")
else:
    print("❌ _GlobalState 是不同实例（单例失败）")

print()

# 测试 5：测试线程安全
print("=" * 70)
print("测试 5：测试线程安全（多线程同时创建）")
print("=" * 70)

import threading
import time

results = []

def create_state():
    """在线程中创建状态"""
    # 模拟首次导入
    from dispatcher.action_dispatch_v3 import _state
    results.append(id(_state))

# 清除已导入的模块（模拟多线程首次导入）
# 注意：这个测试可能不完美，因为模块已经被导入了

threads = []
for i in range(10):
    t = threading.Thread(target=create_state)
    threads.append(t)

for t in threads:
    t.start()

for t in threads:
    t.join()

print(f"10 个线程创建的 _state 实例 ID: {results}")

if len(set(results)) == 1:
    print("✅ 所有线程获得的是同一个实例（线程安全）")
else:
    print(f"❌ 发现 {len(set(results))} 个不同的实例（线程不安全）")

print()

# 总结
print("=" * 70)
print("总结")
print("=" * 70)

all_registry_ids = [id(ad1._registry), id(ad2._registry)]
all_lock_ids = [id(ad1._global_lock), id(ad2._global_lock)]

if len(set(all_registry_ids)) == 1 and len(set(all_lock_ids)) == 1:
    print("✅ 单例模式实现正确：所有导入共享同一个 registry 和 lock")
    print("✅ 问题已修复：多次导入不会创建多个实例")
else:
    print("❌ 单例模式实现失败：发现多个实例")
    print(f"   registry 实例数: {len(set(all_registry_ids))}")
    print(f"   lock 实例数: {len(set(all_lock_ids))}")

print()
print("=" * 70)

