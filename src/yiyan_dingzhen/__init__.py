"""一言鼎臻核心包。"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yiyan-dingzhen")
except PackageNotFoundError:  # 在源码目录直接运行时
    __version__ = "0.2.0"

__all__ = ["__version__"]
