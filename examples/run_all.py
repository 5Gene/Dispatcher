"""依次运行全部示例。

每个示例跑在独立子进程里，避免注册表状态互相干扰。

运行::

    python -m examples.run_all
"""
import subprocess
import sys

EXAMPLES = [
    "examples.basic",
    "examples.matching",
    "examples.concurrency",
    "examples.errors",
    "examples.async_dispatch",
    "examples.auto_import",
    "examples.introspection",
    "examples.logging_demo",
]


def main():
    failed = []
    for name in EXAMPLES:
        print("\n" + "#" * 72)
        print("# " + name)
        print("#" * 72)
        result = subprocess.run([sys.executable, "-m", name])
        if result.returncode != 0:
            failed.append(name)

    print("\n" + "=" * 72)
    if failed:
        print("❌ 失败:", failed)
        return 1
    print("✅ 全部 %d 个示例运行通过" % len(EXAMPLES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
