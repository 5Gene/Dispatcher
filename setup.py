from setuptools import setup, find_packages

# PyCharm 自动生成 requirements.txt
# 使用Python打开自己的工程，然后点击Tools，最后点击Sync Python Requirements

readme_path = 'README.md'

setup(
    name='dispatcher3',
    version='0.1',
    author='5hmlA',
    author_email='gene.jzy@gmail.com',
    # 指定运行时需要的Python版本
    python_requires='>=3.6',
    # 找到当前目录下有哪些包 当前(setup.py)目录下的文件夹 当前目录的py不包含 打包的是把所有代码放一个文件夹下文件名为库名字
    packages=find_packages(),
    # 要打包的代码所在目录和库名字不一样，需要手动指定
    # packages=['dispatcher3'],
    # 配置readme
    long_description=open(readme_path, encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    license="MIT Licence",
    # 手动指定
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
    ],
    install_requires=[
        # 只包含包名。 这种形式只检查包的存在性，不检查版本。 方便，但不利于控制风险。
        # 'setuptools==38.2.4'，指定版本。 这种形式把风险降到了最低，确保了开发、测试与部署的版本一致，不会出现意外。 缺点是不利于更新，每次更新都需要改动代码
    ],
    keywords='action, dispatcher3',
    url='https://github.com/5hmlA/PyTools',
    description='python library for dispatch action'
)


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
#   password = pypi-AgEIcHlwaS5vcmcCJDM1MzcxMjcyLTRlMjY

