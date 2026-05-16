#!/usr/bin/env python3
"""
cyber-lobster 打包脚本 —— 将 EXE 入口编译为单文件 exe。

用法:
    pip install pyinstaller
    python build.py

输出在 dist/cyber-lobster.exe（Windows）或 dist/cyber-lobster（Linux）。
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def find_pyinstaller() -> list[str]:
    """查找可用的 PyInstaller 命令。

    优先使用当前 Python 的 -m PyInstaller，
    若失败则依次尝试 pyinstaller / pyinstaller3.12 等命令。
    返回 argv 列表。
    """
    # 先用 sys.executable 跑 -m PyInstaller --version 验证
    try:
        r = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return [sys.executable, "-m", "PyInstaller"]
    except (OSError, subprocess.TimeoutExpired):
        pass

    # 回退：直接找 pyinstaller 命令
    candidates = ["pyinstaller", "pyinstaller3.12", "pyinstaller3.11", "pyi-makespec"]
    for cmd in candidates:
        try:
            r = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                return [cmd]
        except (OSError, subprocess.TimeoutExpired):
            continue

    return []


def main():
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)

    # ── 找 PyInstaller ──
    pyi_cmd = find_pyinstaller()
    if not pyi_cmd:
        print("❌ 找不到 PyInstaller。请安装:  pip install pyinstaller")
        print()
        print("   如果已安装但仍找不到，尝试:  python -m pip install pyinstaller")
        sys.exit(1)

    # ── 清理旧构建 ──
    for p in ["build", "dist"]:
        shutil.rmtree(p, ignore_errors=True)
    for spec in project_root.glob("*.spec"):
        spec.unlink(missing_ok=True)

    # ── PyInstaller 参数 ──
    args = pyi_cmd + [
        "--onefile",                    # 单文件 exe
        "--name", "cyber-lobster",      # 输出文件名
        "--console",                    # 需要控制台（输入输出）
        "--clean",                      # 清理缓存
        "--noconfirm",                  # 覆盖不询问
        "--hidden-import", "cyber_lobster",
        "--hidden-import", "cyber_lobster.cli",
        "--hidden-import", "cyber_lobster.config",
        "--hidden-import", "cyber_lobster.logger",
        "--hidden-import", "cyber_lobster.network",
        "--hidden-import", "cyber_lobster.network_login",
        "--hidden-import", "cyber_lobster.system",
        "--hidden-import", "requests",
        "--hidden-import", "urllib3",
        "--hidden-import", "charset_normalizer",
        "--hidden-import", "certifi",
        "--hidden-import", "idna",
        "--hidden-import", "msvcrt",
        "exe_main.py",
    ]

    print("🦞  cyber-lobster 打包中...")
    print(f"    命令: {' '.join(args)}")
    print()

    result = subprocess.run(args, cwd=project_root)

    if result.returncode != 0:
        print(f"\n❌ 打包失败 (exit {result.returncode})")
        sys.exit(1)

    # 验证输出
    if sys.platform == "win32":
        exe_path = project_root / "dist" / "cyber-lobster.exe"
    else:
        exe_path = project_root / "dist" / "cyber-lobster"

    if exe_path.is_file():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n✅ 打包成功！")
        print(f"   路径: {exe_path}")
        print(f"   大小: {size_mb:.1f} MB")
        print()
        print("   直接双击运行，或:")
        print(f"   {exe_path}")
    else:
        print(f"\n❌ 未找到输出文件: {exe_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
