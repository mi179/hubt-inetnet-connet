#!/usr/bin/env python3
"""
cyber-lobster EXE 入口 —— 交互式校园网自动重连工具。

双击或命令行运行，依次选择运营商、输入账号密码，即可进入监控模式。
所有配置仅存内存，不写配置文件。
"""

import sys
import time
import getpass
from datetime import datetime

# ── 这些显式导入确保 PyInstaller 能收集全依赖 ──
from cyber_lobster import __version__
from cyber_lobster.network_login import (
    PortalCredentials,
    login_with_session_retry,
    ensure_encrypted_password,
    parse_login_response,
    DEFAULT_HOST,
)
from cyber_lobster.network import check_connectivity


SERVICE_MENU = {
    "1": "DX",
    "2": "LT",
    "3": "YD",
}

SERVICE_NAMES = {
    "DX": "电信",
    "LT": "联通",
    "YD": "移动",
}


def _ts() -> str:
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")


def select_operator() -> str:
    """交互选择运营商。"""
    print()
    print("  ╔══════════════════════════╗")
    print("  ║  请选择运营商            ║")
    print("  ╠══════════════════════════╣")
    print("  ║  1. 电信 (DX)            ║")
    print("  ║  2. 联通 (LT)            ║")
    print("  ║  3. 移动 (YD)            ║")
    print("  ╚══════════════════════════╝")
    while True:
        choice = input("  请选择 [1]: ").strip()
        if not choice or choice in SERVICE_MENU:
            return SERVICE_MENU.get(choice, "DX")
        print("  输入无效，请输入 1、2 或 3。")


def main():
    print()
    print("  🦞  cyber-lobster  v" + __version__)
    print("  ═══════════════════════════")
    print("  校园网自动重连工具")
    print("  （配置仅存内存，不写文件）")
    print()

    # ── 交互输入 ──
    service = select_operator()
    service_name = SERVICE_NAMES.get(service, service)

    user_id = input(f"  学号: ").strip()
    while not user_id:
        user_id = input("  学号不能为空: ").strip()

    password = getpass.getpass("  密码: ")
    while not password:
        password = getpass.getpass("  密码不能为空: ")

    # ── 确认 ──
    print()
    print(f"  ✅ 配置完成")
    print(f"     运营商: {service_name} ({service})")
    print(f"     学号:   {user_id}")
    print()
    print(f"  开始监控，按 Ctrl+C 退出")
    print(f"  ═══════════════════════════")
    print()

    # ── 构造凭据（全部在内存） ──
    creds = PortalCredentials(
        user_id=user_id,
        password=password,
        service=service,
    )

    fail_count = 0
    interval = 10  # 检测间隔秒数
    timeout = 3.0  # 连通性检测超时

    # ── 主循环 ──
    try:
        while True:
            ts = _ts()

            try:
                online = check_connectivity(timeout=timeout)
            except Exception as exc:
                online = False

            if online:
                if fail_count > 0:
                    print(f"  {ts} ✅ 网络已恢复（之前断连 {fail_count} 次）")
                    fail_count = 0
                else:
                    print(f"  {ts} 网络正常")
            else:
                fail_count += 1
                print(f"  {ts} ❌ 断连 ({fail_count})，正在重连...")

                try:
                    result = login_with_session_retry(
                        creds, host=DEFAULT_HOST,
                        max_session_attempts=1,
                        request_retries=2,
                    )
                    if result.success:
                        resp = parse_login_response(result.body)
                        msg = resp.get("message", "") or resp.get("result", "")
                        print(f"         ✅ 重连成功: {msg[:60]}")
                        fail_count = 0
                    else:
                        err = result.error or result.body[:60]
                        print(f"         ❌ 重连失败: {err}")
                except Exception as exc:
                    print(f"         ❌ 重连异常: {type(exc).__name__}: {exc}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n  {_ts()} 监控已停止。")
        return 0
    except Exception as exc:
        print(f"\n  {_ts()} 💥 意外错误: {type(exc).__name__}: {exc}")
        print("  程序将退出。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
