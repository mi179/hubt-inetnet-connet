#!/usr/bin/env python3
"""
cyber-lobster EXE 入口 —— 双击即用的校园网自动重连工具。

无参运行自动流:
  无配置 → setup 交互向导 → 登录验证 → 保存 → watch 监控
  有配置 → 直接进入 watch 监控
"""

import sys
import time
import random
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

    password = getpass.getpass("  密码（输入时不显示，正常敲回车即可）: ")
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


# ── 多套 Logo 皮肤（随机显示） ──

LOGOS = [
    # ── 皮肤1: HUBT专属版 ──
    r""" ██╗  ██╗██╗   ██╗██████╗ ████████╗
 ██║  ██║██║   ██║██╔══██╗╚══██╔══╝
 ███████║██║   ██║██████╔╝   ██║   
 ██╔══██║██║   ██║██╔══██╗   ██║   
 ██║  ██║╚██████╔╝██████╔╝   ██║   
 ╚═╝  ╚═╝ ╚═════╝ ╚═════╝    ╚═╝   
       🦞 Cyber-Lobster v{version} 🦞""",

    # ── 皮肤2: 颜文字老婆版 ──
    r"""   (\_/)
  ( •_•)  < 主人，今天的网络也交给我吧！
  / >🦞""",

    # ── 皮肤3: 赛博机甲龙虾版 ──
    r"""     / \      / \ 
    (   )____(   )
     \  /    \  / 
      \|  🦞  |/  
       |      |   
       \______/   
  [ CYBER LOBSTER SYSTEM ONLINE ]""",
]


def _clear_screen() -> None:
    """清屏（跨平台）。"""
    import os as _os
    _os.system("cls" if sys.platform == "win32" else "clear")


def _check_online_status() -> tuple[bool, str]:
    """检测网络状态，返回 (是否在线, 状态描述)。"""
    try:
        ok = check_connectivity(timeout=2.0)
    except Exception:
        ok = False
    if ok:
        return (True, "✅ 外网连通")
    return (False, "❌ 外网断开")


def show_menu(cfg: GlobalConfig) -> int:
    """交互式主菜单（无论有没有配置都显示）。"""
    current = cfg.get_current_account()
    current_logo = random.choice(LOGOS)

    while True:
        _clear_screen()

        # ── Logo（随机皮肤）──
        print(current_logo.format(version=__version__))
        print()

        # ── 状态栏 ──
        online, status_text = _check_online_status()
        if current:
            svc = SERVICE_NAMES.get(current.service, current.service)
            print(f"  📡 网络状态:  {status_text}")
            print(f"  👤 当前账号:  {current.user_id} ({svc})")
        else:
            print(f"  📡 网络状态:  {status_text}")
            print(f"  👤 当前账号:  （无 — 请先添加账号）")
        print(f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()

        # ── 菜单选项 ──
        print(f"     [1]  🚀  一键连网并进入守护挂机模式")
        print(f"     [2]  🔄  切换当前账号")
        print(f"     [3]  ➕  添加新账号")
        print(f"     [4]  🔌  注销下线")
        print(f"     [5]  🎲  切换界面皮肤")
        print(f"     [6]  ⚙️  开机自启设置")
        print(f"     [0]  ❌  退出程序")
        print()
        print(f"  ───────────────────────────────────")
        print()

        choice = input(f"  请输入选项 [1]: ").strip()

        # ── 1. 一键连网 + 守护挂机 ──
        if not choice or choice == "1":
            if not current:
                warn("没有可用账号，请先 [3] 添加新账号")
                input("  按 Enter 返回菜单...")
                continue

            # 若已离线，根据 auto_auth 决定是否自动认证
            if not online:
                if cfg.auto_auth:
                    info("检测到断网，正在尝试登录...")
                    creds = PortalCredentials(
                        user_id=current.user_id,
                        password=current.password,
                        service=current.service,
                    )
                    result = login_with_session_retry(
                        creds, host=current.host,
                        max_session_attempts=1, request_retries=2,
                    )
                    if result.success:
                        success("登录成功！进入守护模式")
                        notify_win32("🦞 赛博龙虾守护者", "校园网已连通！")
                    else:
                        err = (result.error or result.body[:60]).replace("\n", " ")
                        warn(f"登录失败: {err}")
                        input("  按 Enter 返回菜单...")
                        continue
                else:
                    warn("自动认证已关闭，跳过登录，直接进入守护模式（断网时将无法自动重连）")
            else:
                info("网络已连通，直接进入守护模式")

            return run_watch_loop(cfg)

        # ── 2. 切换账号（先下线旧号 → 切换配置 → 上线新号）──
        elif choice == "2":
            ids = cfg.account_ids()
            if not ids:
                warn("没有已保存的账号，请先 [3] 添加")
                input("  按 Enter 返回菜单...")
                continue

            print()
            print("  ── 已保存的账号 ──")
            for i, uid in enumerate(ids, 1):
                mark = " ← 当前" if uid == cfg.current_user_id else ""
                print(f"    {i}. {uid}{mark}")
            print("    0. 返回")
            print()
            try:
                c = input(f"  选择账号 (1-{len(ids)}): ").strip()
                if c == "0" or not c:
                    continue
                idx = int(c) - 1
                if 0 <= idx < len(ids):
                    new_id = ids[idx]

                    # 如果新账号和当前账号不同，先下线旧号
                    if new_id != cfg.current_user_id and current:
                        from cyber_lobster.network_login import logout as eportal_logout
                        info(f"正在注销旧账号: {current.user_id}...")
                        r = eportal_logout(host=current.host)
                        if r.success:
                            success("旧账号已下线")
                        else:
                            warn(f"注销旧账号失败（继续切换）: {r.error}")

                    # 切换配置
                    cfg.current_user_id = new_id
                    save_config(cfg)
                    success(f"已切换到: {new_id}")

                    # 询问是否立即上线
                    do_login = input("  立即登录新账号？[Y/n]: ").strip().lower()
                    if do_login in ("", "y", "yes"):
                        new_account = cfg.get_current_account()
                        if new_account:
                            creds = PortalCredentials(
                                user_id=new_account.user_id,
                                password=new_account.password,
                                service=new_account.service,
                            )
                            info(f"正在登录新账号: {new_account.user_id}...")
                            result = login_with_session_retry(
                                creds, host=new_account.host,
                                max_session_attempts=1, request_retries=2,
                            )
                            if result.success:
                                success(f"新账号 {new_account.user_id} 上线成功 ✅")
                                notify_win32("🦞 赛博龙虾守护者", f"已切换账号: {new_account.user_id}")
                            else:
                                err = (result.error or result.body[:60]).replace("\n", " ")
                                warn(f"新账号上线失败: {err}")
                else:
                    warn("序号无效")
            except (ValueError, IndexError):
                warn("输入无效")
            input("  按 Enter 返回菜单...")
            continue

        # ── 3. 添加新账号 ──
        elif choice == "3":
            account = run_setup_wizard()
            if account:
                cfg.upsert_account(account)
                save_config(cfg)
                success(f"账号已保存 → {config_path()}")
                # 自动刷新当前用户
                current = cfg.get_current_account()
            input("  按 Enter 返回菜单...")
            continue

        # ── 4. 注销下线 ──
        elif choice == "4":
            if not current:
                warn("没有账号可注销")
                input("  按 Enter 返回菜单...")
                continue

            from cyber_lobster.network_login import logout as eportal_logout
            info(f"正在向 {current.host} 发送注销...")
            r = eportal_logout(host=current.host)
            if r.success:
                success("已注销下线 ✅")
                notify_win32("🦞 赛博龙虾守护者", "已成功注销下线")
            else:
                warn(f"注销失败: {r.error}")
            input("  按 Enter 返回菜单...")
            continue

        # ── 5. 切换界面皮肤 ──
        elif choice == "5":
            current_logo = random.choice(LOGOS)
            continue

        # ── 6. 开机自启设置 ──
        elif choice == "6":
            print()
            print("  ── 开机自启设置 ──")
            print()
            print(f"    当前状态: {'🟢 已开启' if cfg.auto_auth else '🔴 已关闭'} 自动认证")
            toggle = input(f"    切换自动认证？[Y/n]: ").strip().lower()
            if toggle in ("", "y", "yes"):
                cfg.auto_auth = not cfg.auto_auth
                save_config(cfg)
                success(f"自动认证已{'开启' if cfg.auto_auth else '关闭'}")
            print()
            print("  ── Windows 开机自启 ──")
            if sys.platform == "win32":
                do_autostart = input("  设置 cyber-lobster 开机自启？[Y/n]: ").strip().lower()
                if do_autostart in ("", "y", "yes"):
                    from cyber_lobster.cli import _setup_autostart_windows
                    _setup_autostart_windows()
            else:
                from cyber_lobster.cli import _setup_autostart_linux
                _setup_autostart_linux()
            input("  按 Enter 返回菜单...")
            continue

        # ── 0. 退出 ──
        elif choice == "0":
            _clear_screen()
            print()
            print(f"  🦞  cyber-lobster v{__version__}")
            print(f"  再见 👋  校园网一路畅通！")
            print()
            return 0

        else:
            print("  输入无效，请选择 0-6")
            input("  按 Enter 返回菜单...")
            continue


def main() -> int:
    cfg = load_config()
    return show_menu(cfg)


def entry_point() -> int:
    """统一入口：有参数走 CLI，无参数走自动流。"""
    if len(sys.argv) > 1:
        # 有命令行参数 → 交给 cli.py 处理
        from cyber_lobster.cli import main as cli_main
        return cli_main()
    # 无参数 → 双击自动流
    return main()


if __name__ == "__main__":
    sys.exit(entry_point())
