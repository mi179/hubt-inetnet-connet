#!/usr/bin/env python3
"""
cyber-lobster EXE 入口 —— 双击即用的校园网自动重连工具。

无参运行自动流:
  无配置 → setup 交互向导 → 登录验证 → 保存 → watch 监控
  有配置 → 直接进入 watch 监控
"""

import sys
import time
import getpass
from pathlib import Path

from cyber_lobster import __version__
from cyber_lobster.logger import info, warn, error, success, notify_win32
from cyber_lobster.config import (
    load as load_config,
    save as save_config,
    config_path,
    GlobalConfig,
    AccountConfig,
)
from cyber_lobster.network_login import (
    PortalCredentials,
    login_with_session_retry,
    parse_login_response,
    DEFAULT_HOST,
)
from cyber_lobster.network import check_connectivity

# ── 常量 ──
WATCH_INTERVAL = 10
CHECK_TIMEOUT = 3.0

SERVICE_MENU = {"1": "DX", "2": "LT", "3": "YD"}
SERVICE_NAMES = {"DX": "电信", "LT": "联通", "YD": "移动"}


def run_setup_wizard() -> AccountConfig | None:
    """交互式配置向导，登录验证成功后返回 AccountConfig。"""
    print()
    print("  ── 首次使用，请配置认证信息 ──")
    print()

    # 运营商
    print("  请选择运营商:")
    print("    1. 电信 (DX)")
    print("    2. 联通 (LT)")
    print("    3. 移动 (YD)")
    while True:
        choice = input("  请选择 [1]: ").strip()
        if not choice or choice in SERVICE_MENU:
            service = SERVICE_MENU.get(choice, "DX")
            break
        print("  输入无效，请选 1/2/3")

    user_id = input("  学号: ").strip()
    while not user_id:
        user_id = input("  学号不能为空: ").strip()

    password = getpass.getpass("  密码: ")
    while not password:
        password = getpass.getpass("  密码不能为空: ")

    host_input = input(f"  认证服务器地址 [{DEFAULT_HOST}]: ").strip()
    host = host_input or DEFAULT_HOST

    svc_name = SERVICE_NAMES.get(service, service)
    print()
    info(f"确认: {svc_name}({service}) / {user_id}")
    info("正在验证登录...")

    # 验证
    creds = PortalCredentials(
        user_id=user_id, password=password, service=service,
    )
    result = login_with_session_retry(creds, host=host, max_session_attempts=1, request_retries=2)

    if not result.success:
        err = result.error or result.body[:100]
        error(f"登录失败: {err}")
        print("  请重新运行本程序重试。")
        return None

    resp = parse_login_response(result.body)
    msg = resp.get("message", "") or resp.get("result", "")
    success(f"登录成功: {msg[:80]}")

    return AccountConfig(
        user_id=user_id,
        password=password,
        service=service,
        host=host,
    )


def run_watch_loop(cfg: GlobalConfig) -> int:
    """断网自动重连监控循环。"""
    account = cfg.get_current_account()
    if not account:
        error("配置中没有有效账号，请运行 cyber-lobster setup")
        return 1

    info(f"进入监控模式 — {account.user_id} ({SERVICE_NAMES.get(account.service, account.service)})")
    info(f"检测间隔: {WATCH_INTERVAL}s  |  按 Ctrl+C 退出")
    print()

    fail_count = 0
    creds = PortalCredentials(
        user_id=account.user_id,
        password=account.password,
        service=account.service,
        query_string=account.query_string,
    )

    try:
        while True:
            try:
                online = check_connectivity(timeout=CHECK_TIMEOUT)
            except Exception:
                online = False

            if online:
                if fail_count > 0:
                    success(f"网络已恢复（之前断连 {fail_count} 次）")
                    notify_win32("🦞 赛博龙虾守护者", "校园网已自动重新连通！")
                    fail_count = 0
                else:
                    info("网络正常")
            else:
                fail_count += 1
                warn(f"断连 ({fail_count})，正在重连...")

                try:
                    result = login_with_session_retry(
                        creds, host=account.host,
                        max_session_attempts=1, request_retries=2,
                    )
                    if result.success:
                        success("重连成功")
                        notify_win32("🦞 赛博龙虾守护者", "校园网已自动重新连通！")
                        fail_count = 0
                    else:
                        err = (result.error or result.body[:60]).replace("\n", " ")
                        warn(f"重连失败: {err}")
                except Exception as exc:
                    warn(f"重连异常: {type(exc).__name__}: {exc}")

            time.sleep(WATCH_INTERVAL)

    except KeyboardInterrupt:
        info("监控已停止。再见 👋")
        return 0
    except Exception as exc:
        error(f"意外错误: {type(exc).__name__}: {exc}")
        return 1


def main() -> int:
    print(f"  🦞  cyber-lobster v{__version__}  —  校园网自动重连")
    print(f"  ═══════════════════════════════════════════")
    print(f"  配置: {config_path()}")

    cfg = load_config()

    if not cfg.has_accounts():
        info("没有找到已保存的配置")

        account = run_setup_wizard()
        if account is None:
            return 1

        # 保存并进入监控
        cfg.upsert_account(account)
        save_config(cfg)
        success(f"配置已保存 → {config_path()}")
        return run_watch_loop(cfg)

    # 已有配置 → 直接进入监控
    current = cfg.get_current_account()
    if current:
        info(f"已加载配置: {current.user_id}")
    return run_watch_loop(cfg)


if __name__ == "__main__":
    sys.exit(main())
