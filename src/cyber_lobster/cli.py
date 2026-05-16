"""cyber-lobster CLI 主入口（argparse）。"""

import argparse
import json
import sys
from typing import NoReturn

from cyber_lobster import __version__
from cyber_lobster.config import load as load_config
from cyber_lobster.system import (
    get_cpu_temp,
    get_all_temp_sensors,
    get_memory_info,
    format_memory,
)
from cyber_lobster.network import check_gateways
from cyber_lobster.network_login import (
    PortalCredentials,
    login_with_session_retry,
    parse_login_response,
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

    # login — 校园网 ePortal 认证
    p_login = sub.add_parser("login", help="校园网 ePortal 自动登录")
    p_login.add_argument("user_id", help="学号 / 账号")
    p_login.add_argument("password", help="加密后的密码 hash")
    p_login.add_argument("--host", default=DEFAULT_HOST, help=f"认证服务器地址（默认 {DEFAULT_HOST}）")
    p_login.add_argument("--service", default=DEFAULT_SERVICE, choices=["DX", "LT", "YD"],
                         help=f"运营商（默认 {DEFAULT_SERVICE}）")
    p_login.add_argument("--query-string", default="",
                         help="原重定向 URL 中的 queryString 参数（URL 编码）")
    p_login.add_argument("--from-config", action="store_true",
                         help="从 config.json 读取登录配置（字段见示例文件）")

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
        if not login_cfg:
            print("❌ config.json 中缺少登录凭据。")
            print("   请包含以下字段（扁平即可）：")
            print('    "user_id": "20251022129",')
            print('    "password": "<hash>",')
            print('    "service": "DX"')
            return 1
        creds = PortalCredentials(
            user_id=login_cfg.get("user_id", ""),
            password=login_cfg.get("password", ""),
            service=login_cfg.get("service", DEFAULT_SERVICE),
            query_string=login_cfg.get("query_string", ""),
        )
        host = login_cfg.get("host", DEFAULT_HOST)
    else:
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
            print(f"   响应: {result.body[:300]}")
        return 1


COMMANDS = {
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
        print("\n[cyber-lobster] 已取消", file=sys.stderr)
        sys.exit(130)
