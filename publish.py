import os
import shutil
import subprocess


def run_cmd(command):
    subprocess.run(command, check=True)


if __name__ == '__main__':
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")
    run_cmd("python.exe -m pip install --upgrade pip")
    run_cmd("python -m pip install --upgrade twine")
    run_cmd("pip install wheel setuptools")
    run_cmd("pip install packaging")
    run_cmd("python setup.py sdist bdist_wheel")


# tNDAxZi05MWZlLTI3NzZkZTE5MGI1MAACFFsxLFsibG9ndHJhbnNsYXRlIl1dAAIsWzIsWyJlMzExZmU4MC0wNjdhLTQ3YjAtYTYyNS0wNTU5ODAzODZhMmIiXV0AAAYgmsU-X81dIECmBzOwxMjBP0hgFSLIO2Fc6Ra4tR91tfg
# python.exe -m pip install --upgrade pip
# python -m pip install --upgrade twine
# pip install wheel setuptools
# pip install packaging
# python setup.py sdist bdist_wheel

# 发布到测试地址
# twine upload --repository testpypi dist/*
# twine upload dist/*

# [pypi]
#   username = __token__
#   password = pypi-AgEIcHlwaS5vcmcCJDM1MzcxMjcyLTRlM

# https://github.com/5hmlA/PyTools/tags
# https://pypi.org/project/LogTranslate/

# todo
# 1 按行读取文件
# 2 所有translate 都新增一个大tag，每行字符串先判断是否包含所有translate的tag之后在执行解析