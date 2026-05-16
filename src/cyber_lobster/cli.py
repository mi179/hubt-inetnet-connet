"""cyber-lobster CLI 主入口（argparse）。"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import NoReturn

from cyber_lobster import __version__
from cyber_lobster.config import load as load_config
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
    parse_login_response,
    detect_query_string,
    DEFAULT_HOST,
    DEFAULT_SERVICE,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cyber-lobster",
        description="🦞 Homelab 网络与服务器运维工具",
        epilog="更多信息: https://github.com/your-org/cyber-lobster",
    )
    parser.add_argument(
        "--version", action="version", version=f"cyber-lobster {__version__}"
    )
    parser.add_argument(
        "--config",
        help="配置文件路径（默认按优先级查找）",
        default=None,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # status — 系统状态
    p_status = sub.add_parser("status", help="查看本机系统状态（CPU 温度 / 内存）")
    p_status.add_argument(
        "--all-sensors",
        action="store_true",
        help="显示所有 thermal 传感器温度",
    )

    # ping — 网关连通性
    sub.add_parser("ping", help="Ping 检测已配置的网关")

    # check — 全部检查
    sub.add_parser("check", help="系统状态 + 网关连通性一并检查")

    # setup — 交互配置向导
    sub.add_parser("setup", help="交互式配置向导（创建/修改 config.json）")

    # login — 校园网 ePortal 认证
    p_login = sub.add_parser("login", help="校园网 ePortal 自动登录")
    p_login.add_argument("user_id", nargs="?", default="", help="学号 / 账号")
    p_login.add_argument("password", nargs="?", default="", help="加密后的密码 hash")
    p_login.add_argument("--host", default=DEFAULT_HOST, help=f"认证服务器地址（默认 {DEFAULT_HOST}）")
    p_login.add_argument("--service", default=DEFAULT_SERVICE, choices=["DX", "LT", "YD"],
                         help=f"运营商（默认 {DEFAULT_SERVICE}）")
    p_login.add_argument("--query-string", default="",
                         help="原重定向 URL 中的 queryString 参数（URL 编码）")
    p_login.add_argument("--from-config", action="store_true",
                         help="从 config.json 读取登录配置（优先）")

    # watch — 断网自动重连
    p_watch = sub.add_parser("watch", help="持续监控外网连通性，断网自动重连")
    p_watch.add_argument("--interval", type=int, default=10,
                         help="检测间隔秒数（默认 10）")
    p_watch.add_argument("--timeout", type=float, default=3.0,
                         help="单次连通检测超时秒数（默认 3）")
    p_watch.add_argument("--check-url", type=str, default="",
                         help="自定义连通检测 URL（默认自动选）")

    return parser


def cmd_status(args: argparse.Namespace) -> int:
    """子命令: status"""
    print("🦞 cyber-lobster — 系统状态")
    print("=" * 40)

    # CPU 温度
    temp = get_cpu_temp()
    if temp is not None:
        print(f"🌡 CPU 封装温度:  {temp:.1f} °C")
        if temp > 80:
            print("   ⚠ 温度偏高，建议检查散热！")
    else:
        print("🌡 CPU 温度:      无法读取（非 Linux 或缺少传感器）")

    if args.all_sensors:
        sensors = get_all_temp_sensors()
        if sensors:
            print("\n   ── 全部传感器 ──")
            for name, val in sensors.items():
                mark = "  ⚠" if val > 80 else ""
                print(f"     {name:20s}: {val:.1f} °C{mark}")

    # 内存
    mem = get_memory_info()
    if mem:
        print(f"🧠 内存使用:      {format_memory(mem)}")
        swap_total = mem.get("SwapTotal", 0)
        swap_free = mem.get("SwapFree", 0)
        if swap_total:
            swap_used = swap_total - swap_free
            pct = swap_used / swap_total * 100
            print(f"   Swap:          {swap_used // 1024} MiB / {swap_total // 1024} MiB ({pct:.1f}%)")

    print()
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    """子命令: ping"""
    cfg = load_config(args.config)

    if not cfg.gateways:
        print("🦞 未配置待检测的网关，请编辑 config.json。")
        return 1

    print(f"🦞 cyber-lobster — Ping 检测 ({cfg.ping_count} 次)")
    print("=" * 40)

    results = check_gateways(cfg.gateways, count=cfg.ping_count, timeout=cfg.ping_timeout)
    for r in results:
        icon = "✅" if r.alive else "❌"
        extra = ""
        if r.alive and r.avg_rtt is not None:
            extra = f"  ↓ 最小/平均/最大 = {r.min_rtt:.1f}/{r.avg_rtt:.1f}/{r.max_rtt:.1f} ms  丢包 {r.loss_pct:.0f}%"
        elif not r.alive:
            extra = "  无法连通"
        print(f"{icon} {r.target}{extra}")

    print()
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """子命令: check = status + ping"""
    code1 = cmd_status(args)
    code2 = cmd_ping(args)
    return code1 or code2


def cmd_login(args: argparse.Namespace) -> int:
    """子命令: login — ePortal 认证"""
    if args.from_config:
        cfg = load_config(args.config)
        login_cfg = cfg.login or {}

        # ── 配置缺失 → 自动进向导 ──
        if not login_cfg:
            print("⚠ 未找到有效配置。")
            try:
                ans = input("  是否进入配置向导？[Y/n]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "n"
            if ans in ("", "y", "yes"):
                try:
                    login_cfg = setup_config_wizard(args.config)
                except (OSError, KeyboardInterrupt):
                    print("❌ 配置取消。")
                    return 1
            else:
                print("❌ 请先运行 cyber-lobster setup 创建配置。")
                return 1

        creds = PortalCredentials(
            user_id=login_cfg.get("user_id", ""),
            password=login_cfg.get("password", ""),
            service=login_cfg.get("service", DEFAULT_SERVICE),
            query_string=login_cfg.get("query_string", ""),
        )
        host = login_cfg.get("host", DEFAULT_HOST)
    else:
        if not args.user_id or not args.password:
            print("❌ 请提供 user_id 和 password，或使用 --from-config。")
            print("   用法: cyber-lobster login <学号> <密码hash>")
            print("   或:   cyber-lobster login --from-config")
            return 1
        creds = PortalCredentials(
            user_id=args.user_id,
            password=args.password,
            service=args.service,
            query_string=args.query_string,
        )
        host = args.host

    print(f"🦞 cyber-lobster — 校园网 ePortal 登录")
    print(f"   服务器: {host}")
    print(f"   账号:   {creds.user_id}")
    print(f"   运营商: {creds.service}")
    print("=" * 40)

    result = login_with_session_retry(creds, host=host)

    if result.success:
        msg = parse_login_response(result.body)
        print("✅ 登录成功！")
        if msg:
            print("   服务器响应:", json.dumps(msg, ensure_ascii=False, indent=4))
        return 0
    else:
        print(f"❌ 登录失败")
        if result.error:
            print(f"   错误: {result.error}")
        if result.status_code:
            print(f"   HTTP {result.status_code}")
        if result.body:
            msg = parse_login_response(result.body)
            if msg:
                print(f"   响应: {msg}")
            else:
                print(f"   响应: {result.body[:300]}")
        return 1


# ── 挂机监控 ──────────────────────────────────────

def _ts() -> str:
    """当前时间戳字符串，格式 [2026-05-16 23:45:00]"""
    from datetime import datetime
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")


def cmd_watch(args: argparse.Namespace) -> int:
    """子命令: watch — 断网自动重连"""
    from cyber_lobster.config import _find_config as find_config

    interval = args.interval
    timeout = args.timeout

    # 检查配置是否存在
    cfg_path = find_config(args.config)
    if not cfg_path:
        print(f"{_ts()} ⚠ 未找到 config.json。")
        print("   请先运行 cyber-lobster setup 配置账号。")
        return 1

    print(f"🦞 cyber-lobster — 监控模式启动")
    print(f"   检测间隔:  {interval}s")
    print(f"   检测超时:  {timeout}s")
    print(f"   按 Ctrl+C 退出")
    print("=" * 40)

    fail_count = 0

    try:
        while True:
            ts = _ts()

            try:
                online = check_connectivity(timeout=timeout)
            except Exception as exc:
                online = False
                print(f"{ts} ⚠ 检测异常: {exc}")

            if online:
                if fail_count > 0:
                    print(f"{ts} ✅ 网络已恢复（之前断线 {fail_count} 次）")
                    fail_count = 0
                else:
                    print(f"{ts} 网络正常")
            else:
                fail_count += 1
                print(f"{ts} ❌ 掉线 ({fail_count})，正在重连...")

                try:
                    # 重新加载配置（可能被用户中途修改）
                    cfg = load_config(args.config)
                    login_cfg = cfg.login or {}
                    if not login_cfg:
                        print(f"    ⚠ 配置无效，请运行 cyber-lobster setup")
                    else:
                        creds = PortalCredentials(
                            user_id=login_cfg.get("user_id", ""),
                            password=login_cfg.get("password", ""),
                            service=login_cfg.get("service", DEFAULT_SERVICE),
                            query_string=login_cfg.get("query_string", ""),
                        )
                        host = login_cfg.get("host", DEFAULT_HOST)
                        result = login_with_session_retry(creds, host=host,
                                                          max_session_attempts=1,
                                                          request_retries=2)
                        if result.success:
                            resp = parse_login_response(result.body)
                            msg = resp.get("message", "") or resp.get("result", "")
                            print(f"    ✅ 重连成功: {msg}")
                            fail_count = 0
                        else:
                            print(f"    ❌ 重连失败: {result.error or result.body[:80]}")
                except Exception as exc:
                    print(f"    ❌ 重连异常: {type(exc).__name__}: {exc}")

            import time
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n{_ts()} 监控已停止。")
        return 0


# ── 交互配置向导 ──────────────────────────────────

CONFIG_FIELDS = [
    ("user_id",     "学号",           None),
    ("password",    "密码（明文或已加密 hash）", None),
    ("service",     "运营商 [DX 电信 / LT 联通 / YD 移动]", "DX"),
    ("host",        "认证服务器地址",  DEFAULT_HOST),
]

VALID_SERVICES = {"DX", "LT", "YD"}


def _prompt_nonempty(label: str, default: str | None = None) -> str:
    """提示用户输入，不允许留空。"""
    while True:
        hint = f" [{default}]" if default else ""
        val = input(f"  {label}{hint}: ").strip()
        if not val and default:
            return default
        if val:
            return val
        print("  ⚠ 此项不能为空，请重新输入。")


def _prompt_choice(label: str, choices: set[str], default: str) -> str:
    """提示用户从选项中选择一项。"""
    while True:
        val = input(f"  {label} [{default}]: ").strip().upper()
        if not val:
            return default
        if val in choices:
            return val
        print(f"  ⚠ 仅支持 {', '.join(sorted(choices))}，请重新输入。")


def setup_config_wizard(config_path: str | None = None) -> dict:
    """交互式配置向导。

    返回保存的配置 dict，同时将配置写入 config.json。
    """
    print()
    print("🦞   cyber-lobster 配置向导")
    print("═" * 40)
    print("  按提示输入认证信息，完成后自动保存。")
    print()

    # 逐项询问
    user_id = _prompt_nonempty("学号")
    password = _prompt_nonempty("密码（明文或已加密 hash）")
    service = _prompt_choice("运营商 [DX 电信 / LT 联通 / YD 移动]", VALID_SERVICES, "DX")
    host = _prompt_nonempty("认证服务器地址", DEFAULT_HOST)
    # query_string 可选，不强制
    qs_hint = (
        "（可选）queryString，从浏览器重定向地址栏复制;\n"
        "  留空则登录时自动检测"
    )
    query_string = input(f"  queryString {qs_hint}: ").strip()

    # 组装配置
    config = {
        "user_id": user_id,
        "password": password,
        "service": service,
        "host": host,
    }
    if query_string:
        config["query_string"] = query_string

    # 确认摘要
    print()
    print("  ── 确认信息 ──")
    print(f"    学号:          {user_id}")
    pwd_preview = password[:6] + "****" if len(password) > 8 else "****"
    print(f"    密码:          {pwd_preview}")
    svc_name = {"DX": "电信", "LT": "联通", "YD": "移动"}.get(service, service)
    print(f"    运营商:        {svc_name} ({service})")
    print(f"    服务器:        {host}")

    # 保存
    save_path = Path(config_path or "config.json")
    try:
        save_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  ✅ 配置已保存到 {save_path}")
    except OSError as exc:
        print(f"  ❌ 写入失败 ({exc})")
        print("  请检查目录权限后重试。")
        raise

    print("═" * 40)
    print()
    return config


def cmd_setup(args: argparse.Namespace) -> int:
    """子命令: setup — 配置向导"""
    setup_config_wizard(args.config)
    print("🦞 配置已完成。运行以下命令登录：")
    print("   cyber-lobster login --from-config")
    return 0


# ── 命令注册表 ──────────────────────────────────

COMMANDS = {
    "status": cmd_status,
    "ping": cmd_ping,
    "check": cmd_check,
    "setup": cmd_setup,
    "login": cmd_login,
    "watch": cmd_watch,
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
        print("\n[cyber-lobster] 已取消", file=sys.stderr)
        sys.exit(130)
