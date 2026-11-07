"""构建分发包的辅助脚本。凭证请通过环境变量传入，不要写进仓库。

用法::

    python publish.py                      # 仅构建
    TWINE_USERNAME=__token__ \
    TWINE_PASSWORD=$PYPI_TOKEN \
    python publish.py --upload             # 构建并上传
"""
import argparse
import os
import shutil
import subprocess
import sys


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true", help="构建后上传到 PyPI")
    parser.add_argument("--repository", default="pypi", help="twine repository 名称")
    args = parser.parse_args()

    for path in ("dist", "build"):
        if os.path.exists(path):
            shutil.rmtree(path)

    run([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "build", "twine"])
    run([sys.executable, "-m", "build"])

    if args.upload:
        if not os.environ.get("TWINE_PASSWORD"):
            raise SystemExit("请先设置 TWINE_PASSWORD 环境变量")
        run([sys.executable, "-m", "twine", "upload", "--repository",
             args.repository, *[os.path.join("dist", f) for f in os.listdir("dist")]])


if __name__ == "__main__":
    main()
