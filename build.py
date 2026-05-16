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


def main():
    # 确保在项目根目录
    project_root = Path(__file__).parent.resolve()
    os.chdir(project_root)

    # 检查 pyinstaller
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("❌ 请先安装 PyInstaller:  pip install pyinstaller")
        sys.exit(1)

    # 清理旧构建
    for p in ["build", "dist", "*.spec"]:
        shutil.rmtree(p, ignore_errors=True)
    for spec in project_root.glob("*.spec"):
        spec.unlink()

    # ── PyInstaller 参数 ──
    args = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                    # 单文件 exe
        "--name", "cyber-lobster",      # 输出文件名
        "--console",                    # 需要控制台（输入输出）
        "--clean",                      # 清理缓存
        "--noconfirm",                  # 覆盖不询问
        # 显式添加数据/模块，防止漏捡
        "--hidden-import", "cyber_lobster",
        "--hidden-import", "cyber_lobster.cli",
        "--hidden-import", "cyber_lobster.config",
        "--hidden-import", "cyber_lobster.network",
        "--hidden-import", "cyber_lobster.network_login",
        "--hidden-import", "cyber_lobster.system",
        "--hidden-import", "requests",
        "--hidden-import", "urllib3",
        "--hidden-import", "charset_normalizer",
        "--hidden-import", "certifi",
        "--hidden-import", "idna",
        # 入口
        "exe_main.py",
    ]

    print("🦞  cyber-lobster 打包中...")
    print(f"    PyInstaller: {sys.executable} -m PyInstaller")
    print(f"    入口:        exe_main.py")
    print(f"    输出:        dist/cyber-lobster.exe")
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
