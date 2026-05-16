"""日志工具模块。

提供统一的时间戳日志输出，以及 Windows 原生弹窗通知。
"""

import sys
from datetime import datetime


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def info(msg: str) -> None:
    print(f"[{_ts()}] [INFO] {msg}")


def warn(msg: str) -> None:
    print(f"[{_ts()}] [WARN] {msg}")


def error(msg: str) -> None:
    print(f"[{_ts()}] [ERROR] {msg}", file=sys.stderr)


def success(msg: str) -> None:
    print(f"[{_ts()}] [OK]   {msg}")


def notify_win32(title: str, message: str) -> None:
    """Windows 系统原生弹窗通知（仅在 Windows 有效）。"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # MB_OK | MB_ICONINFORMATION = 0x40
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
    except Exception:
        pass
