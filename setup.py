from setuptools import find_packages, setup

readme_path = "README.md"

setup(
    name="dispatcher3",
    version="0.2.0",
    author="5hmlA",
    author_email="gene.jzy@gmail.com",
    # 代码里用到了 f-string 之外没有 3.7+ 特性，但官方只在 3.8+ 上验证
    python_requires=">=3.8",
    # 显式限定，避免把 tests/examples 打进 wheel
    packages=find_packages(include=["dispatcher3", "dispatcher3.*"]),
    long_description=open(readme_path, encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    # 运行时零依赖，只用标准库
    install_requires=[],
    extras_require={"dev": ["pytest>=7"]},
    keywords="action, dispatcher, router, decorator, dispatch",
    url="https://github.com/5hmlA/PyTools",
    description="Declarative action registration and dispatch for Python",
)
