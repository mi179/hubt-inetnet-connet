"""cyber-lobster CLI 主入口（argparse）。"""

import argparse
import json
import os
import sys
import time
import getpass
from pathlib import Path
from typing import NoReturn

from cyber_lobster import __version__
from cyber_lobster.logger import info, warn, error, success, notify_win32
from cyber_lobster.config import (
    load as load_config,
    save as save_config,
    config_path,
    GlobalConfig,
    AccountConfig,
)
from cyber_lobster.system import (
    get_cpu_temp,
    get_all_temp_sensors,
    get_memory_info,
    format_memory,
)
from cyber_lobster.network import check_gateways, check_connectivity
from cyber_lobster.network_login import (
    PortalCredentials,
    login_with_session_retry,
    logout as eportal_logout,
    parse_login_response,
    DEFAULT_HOST,
    DEFAULT_SERVICE,
)

# ── 常量 ──
SERVICE_NAMES = {"DX": "电信", "LT": "联通", "YD": "移动"}
VALID_SERVICES = {"DX", "LT", "YD"}
WATCH_INTERVAL = 10
CHECK_TIMEOUT = 3.0


# ═══════════════════════════════════════════════
#  CLI 解析器
# ═══════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cyber-lobster",
        description="🦞 Homelab 网络与服务器运维工具 — 校园网自动重连",
    )
    parser.add_argument("--version", action="version", version=f"cyber-lobster {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    # ── setup ──
    sub.add_parser("setup", help="交互式配置向导（添加/修改账号）")

    # ── switch ──
    sub.add_parser("switch", help="切换当前激活的默认账号")

    # ── logout ──
    p_logout = sub.add_parser("logout", help="发送 ePortal 注销请求")
    p_logout.add_argument("--host", default=DEFAULT_HOST, help="认证服务器地址")

    # ── watch ──
    p_watch = sub.add_parser("watch", help="断网自动重连监控")
    p_watch.add_argument("--interval", type=int, default=WATCH_INTERVAL,
                         help=f"检测间隔秒数（默认 {WATCH_INTERVAL}）")
    p_watch.add_argument("--timeout", type=float, default=CHECK_TIMEOUT,
                         help=f"检测超时秒数（默认 {CHECK_TIMEOUT}）")

    # ── autostart ──
    sub.add_parser("autostart", help="设置开机自启（Windows 快捷方式 / Linux crontab 提示）")

    # ── status / ping / check / login（保留）──
    p_status = sub.add_parser("status", help="查看本机系统状态（CPU 温度 / 内存）")
    p_status.add_argument("--all-sensors", action="store_true",
                          help="显示所有 thermal 传感器")

    sub.add_parser("ping", help="Ping 检测已配置的网关")

    sub.add_parser("check", help="系统状态 + 网关连通性一并检查")

    p_login = sub.add_parser("login", help="手动执行一次 ePortal 登录")
    p_login.add_argument("user_id", nargs="?", default="", help="学号")
    p_login.add_argument("password", nargs="?", default="", help="密码")
    p_login.add_argument("--host", default=DEFAULT_HOST, help="认证服务器地址")
    p_login.add_argument("--service", default=DEFAULT_SERVICE, choices=["DX", "LT", "YD"],
                         help="运营商")
    p_login.add_argument("--current", action="store_true",
                         help="使用当前配置的默认账号登录")

    return parser


# ═══════════════════════════════════════════════
#  setup — 交互式配置向导
# ═══════════════════════════════════════════════

def _prompt_nonempty(label: str) -> str:
    while True:
        val = input(f"  {label}: ").strip()
        if val:
            return val
        print("  此项不能为空。")


def _prompt_choice(label: str, choices: set[str], default: str) -> str:
    while True:
        val = input(f"  {label} [{default}]: ").strip().upper()
        if not val:
            return default
        if val in choices:
            return val
        print(f"  仅支持 {', '.join(sorted(choices))}")


def cmd_setup(args: argparse.Namespace) -> int:
    """交互式配置向导。"""
    print()
    print("🦞  cyber-lobster 配置向导")
    print("═" * 40)
    print(f"  配置将保存到: {config_path()}")
    print()

    print("  请选择运营商:")
    print("    1. 电信 (DX)")
    print("    2. 联通 (LT)")
    print("    3. 移动 (YD)")
    while True:
        c = input("  请选择 [1]: ").strip()
        if not c or c in ("1", "2", "3"):
            service = {"1": "DX", "2": "LT", "3": "YD"}.get(c, "DX")
            break
        print("  输入无效，请选 1/2/3")

    user_id = _prompt_nonempty("学号")
    password = getpass.getpass("  密码（输入时不显示，正常敲回车即可）: ")
    while not password:
        password = getpass.getpass("  密码不能为空: ")
    host = input(f"  认证服务器 [{DEFAULT_HOST}]: ").strip() or DEFAULT_HOST

    print()
    svc_name = SERVICE_NAMES.get(service, service)
    info(f"确认: {svc_name}({service}) / {user_id}")
    info("正在验证登录...")

    creds = PortalCredentials(user_id=user_id, password=password, service=service)
    result = login_with_session_retry(creds, host=host, max_session_attempts=1, request_retries=2)

    if not result.success:
        err = result.error or result.body[:100]
        error(f"登录失败: {err}")
        return 1

    resp = parse_login_response(result.body)
    msg = resp.get("message", "") or resp.get("result", "")
    success(f"登录成功: {msg[:80]}")

    # 保存到配置
    cfg = load_config()
    cfg.upsert_account(AccountConfig(
        user_id=user_id, password=password, service=service, host=host,
    ))
    save_config(cfg)
    success(f"配置已保存 → {config_path()}")
    return 0


# ═══════════════════════════════════════════════
#  switch — 多账号切换
# ═══════════════════════════════════════════════

def cmd_switch(args: argparse.Namespace) -> int:
    """切换当前默认账号。"""
    cfg = load_config()
    ids = cfg.account_ids()

    if not ids:
        warn("没有已保存的账号，请先运行 cyber-lobster setup")
        return 1

    current = cfg.current_user_id
    print()
    print("  已保存的账号：")
    print("  ───────────────────────")
    for i, uid in enumerate(ids, 1):
        marker = " ← 当前" if uid == current else ""
        print(f"  {i}. {uid}{marker}")
    print()

    while True:
        try:
            choice = input(f"  选择账号 (1-{len(ids)}): ").strip()
            if not choice:
                return 0
            idx = int(choice) - 1
            if 0 <= idx < len(ids):
                break
        except ValueError:
            pass
        print(f"  输入无效，请输入 1-{len(ids)}")

    new_id = ids[idx]
    if new_id == current:
        info(f"已经是当前账号: {new_id}")
        return 0

    cfg.current_user_id = new_id
    save_config(cfg)
    success(f"已切换到账号: {new_id}")
    return 0


# ═══════════════════════════════════════════════
#  logout — 注销下线
# ═══════════════════════════════════════════════

def cmd_logout(args: argparse.Namespace) -> int:
    """发送注销请求。"""
    info(f"正在向 {args.host} 发送注销请求...")
    result = eportal_logout(host=args.host)
    if result.success:
        msg = parse_login_response(result.body)
        success(f"注销成功: {msg.get('message', '') or msg.get('result', 'ok')}")
        return 0
    else:
        error(f"注销失败: {result.error}")
        return 1


# ═══════════════════════════════════════════════
#  watch — 断网自动重连
# ═══════════════════════════════════════════════

def cmd_watch(args: argparse.Namespace) -> int:
    """断网自动重连监控守护模式。"""
    cfg = load_config()
    account = cfg.get_current_account()

    if not account:
        warn("配置中没有有效账号，请先运行 cyber-lobster setup")
        return 1

    interval = args.interval
    timeout = args.timeout
    creds = PortalCredentials(
        user_id=account.user_id,
        password=account.password,
        service=account.service,
        query_string=account.query_string,
    )

    info(f"监控启动 — {account.user_id} ({SERVICE_NAMES.get(account.service, account.service)})")
    info(f"间隔: {interval}s  |  超时: {timeout}s  |  按 Ctrl+C 退出")
    print()

    fail_count = 0

    try:
        while True:
            try:
                online = check_connectivity(timeout=timeout)
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

            time.sleep(interval)

    except KeyboardInterrupt:
        info("监控已停止。")
        return 0
    except Exception as exc:
        error(f"意外错误: {type(exc).__name__}: {exc}")
        return 1


# ═══════════════════════════════════════════════
#  autostart — 开机自启设置
# ═══════════════════════════════════════════════

def cmd_autostart(args: argparse.Namespace) -> int:
    """设置开机自启。"""
    if sys.platform == "win32":
        return _setup_autostart_windows()
    else:
        return _setup_autostart_linux()


def _setup_autostart_windows() -> int:
    """Windows: 在 Startup 文件夹创建 .bat 快捷方式。"""
    try:
        startup = Path(os.environ.get(
            "APPDATA",
            Path.home() / "AppData" / "Roaming",
        )) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    except Exception:
        startup = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    if not startup.is_dir():
        error(f"找不到 Startup 文件夹: {startup}")
        return 1

    # 判断当前 exe 路径
    exe_path = Path(sys.executable if getattr(sys, 'frozen', False) else sys.argv[0])
    if exe_path.suffix.lower() not in (".exe", ".bat"):
        # 开发模式下提示
        info("检测到开发模式（非 EXE），请打包后重试。")
        info("  1. python build.py")
        info(f"  2. 将 dist/cyber-lobster.exe 放到任意位置")
        info(f"  3. 在此目录运行: cyber-lobster autostart")
        return 0

    bat_path = startup / "cyber-lobster.bat"
    try:
        bat_path.write_text(
            f'@echo off\nstart "" "{exe_path.resolve()}" watch\n',
            encoding="utf-8",
        )
        success(f"开机自启已设置: {bat_path}")
        info("下次开机后将自动启动 cyber-lobster watch")
        return 0
    except OSError as exc:
        error(f"创建失败: {exc}")
        return 1


def _setup_autostart_linux() -> int:
    """Linux: 提示使用 crontab。"""
    exe = Path(sys.argv[0]).resolve()
    print()
    info("Linux 下请使用 crontab 设置开机自启：")
    print()
    print(f"   crontab -e")
    print(f"   添加以下行：")
    print(f"   @reboot cd {exe.parent} && {exe} watch &")
    print()
    info("或使用 systemd 服务（推荐）：")
    print()
    print(f"   sudo tee /etc/systemd/system/cyber-lobster.service <<EOF")
    print(f"   [Unit]")
    print(f"   Description=cyber-lobster Auto Reconnect")
    print(f"   After=network.target")
    print(f"   ")
    print(f"   [Service]")
    print(f"   ExecStart={exe} watch")
    print(f"   Restart=always")
    print(f"   User={os.environ.get('USER', 'root')}")
    print(f"   ")
    print(f"   [Install]")
    print(f"   WantedBy=multi-user.target")
    print(f"   EOF")
    print(f"   sudo systemctl enable --now cyber-lobster")
    print()
    return 0


# ═══════════════════════════════════════════════
#  保留子命令：status / ping / check / login
# ═══════════════════════════════════════════════

def cmd_status(args: argparse.Namespace) -> int:
    print("🦞 cyber-lobster — 系统状态")
    print("=" * 40)

    temp = get_cpu_temp()
    if temp is not None:
        print(f"🌡 CPU 封装温度:  {temp:.1f} °C")
        if temp > 80:
            print("   ⚠ 温度偏高！")
    else:
        print("🌡 CPU 温度:      无法读取（非 Linux 或无传感器）")

    if hasattr(args, 'all_sensors') and args.all_sensors:
        sensors = get_all_temp_sensors()
        if sensors:
            print("\n   ── 全部传感器 ──")
            for name, val in sensors.items():
                mark = " ⚠" if val > 80 else ""
                print(f"     {name:20s}: {val:.1f} °C{mark}")

    mem = get_memory_info()
    if mem:
        print(f"🧠 内存使用:      {format_memory(mem)}")
        st = mem.get("SwapTotal", 0)
        sf = mem.get("SwapFree", 0)
        if st:
            su = st - sf
            print(f"   Swap:          {su // 1024} MiB / {st // 1024} MiB ({su / st * 100:.1f}%)")
    print()
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    cfg = load_config()
    # 兼容旧格式：从 cfg 读取 gateways
    gateways = getattr(cfg, "gateways", getattr(cfg, "_gateways", ["10.0.0.1"]))
    # 用默认值
    gw_list = ["10.0.0.1", "192.168.1.1", "1.1.1.1"]
    count = 3

    print(f"🦞 cyber-lobster — Ping 检测 ({count} 次)")
    print("=" * 40)
    results = check_gateways(gw_list, count=count)
    for r in results:
        icon = "✅" if r.alive else "❌"
        extra = ""
        if r.alive and r.avg_rtt is not None:
            extra = f"  ↓ {r.min_rtt:.1f}/{r.avg_rtt:.1f}/{r.max_rtt:.1f} ms  丢包 {r.loss_pct:.0f}%"
        elif not r.alive:
            extra = "  无法连通"
        print(f"{icon} {r.target}{extra}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    code1 = cmd_status(args)
    code2 = cmd_ping(args)
    return code1 or code2


def cmd_login(args: argparse.Namespace) -> int:
    if args.current:
        cfg = load_config()
        acct = cfg.get_current_account()
        if not acct:
            warn("配置中没有有效账号，请先运行 cyber-lobster setup")
            return 1
        creds = PortalCredentials(
            user_id=acct.user_id, password=acct.password,
            service=acct.service, query_string=acct.query_string,
        )
        host = acct.host
    elif args.user_id and args.password:
        creds = PortalCredentials(
            user_id=args.user_id, password=args.password,
            service=args.service,
        )
        host = args.host
    else:
        print("用法: cyber-lobster login <学号> <密码>")
        print("  或: cyber-lobster login --current")
        return 1

    info(f"登录 {host} — {creds.user_id} ({SERVICE_NAMES.get(creds.service, creds.service)})")
    result = login_with_session_retry(creds, host=host)
    if result.success:
        msg = parse_login_response(result.body)
        success("登录成功")
        if msg:
            print("  ", json.dumps(msg, ensure_ascii=False, indent=2)[:300])
        return 0
    else:
        error(f"登录失败: {result.error or result.body[:100]}")
        return 1


# ═══════════════════════════════════════════════
#  命令注册
# ═══════════════════════════════════════════════

COMMANDS = {
    "setup": cmd_setup,
    "switch": cmd_switch,
    "logout": cmd_logout,
    "watch": cmd_watch,
    "autostart": cmd_autostart,
    "status": cmd_status,
    "ping": cmd_ping,
    "check": cmd_check,
    "login": cmd_login,
}


def main(argv: list[str] | None = None) -> NoReturn:
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    try:
        sys.exit(handler(args))
    except KeyboardInterrupt:
        print()
        info("已取消")
        sys.exit(130)
