#!/usr/bin/env python3
"""
cyber-lobster EXE 入口 —— 双击即用的校园网自动重连工具。

行为:
  1. 检查 ~/.cyber_lobster.json 是否有已保存的配置
  2.   → 有: 直接进入 watch 监控模式
  3.   → 无: 交互式向导 (选择运营商/输入学号密码)
  4.        → 尝试登录验证
  5.        → 成功: 保存配置到 ~/.cyber_lobster.json，进入监控
  6.        → 失败: 提示重新输入

配置仅保存在用户家目录，绝不污染程序所在目录。
"""

import json
import sys
import time
import getpass
from datetime import datetime
from pathlib import Path

# ── 显式导入，确保 PyInstaller 打包不丢依赖 ──
from cyber_lobster import __version__
from cyber_lobster.network_login import (
    PortalCredentials,
    login_with_session_retry,
    parse_login_response,
    DEFAULT_HOST,
)
from cyber_lobster.network import check_connectivity


# ── 配置路径（固定在家目录） ──
CONFIG_PATH = Path.home() / ".cyber_lobster.json"

SERVICE_MENU = {"1": "DX", "2": "LT", "3": "YD"}
SERVICE_NAMES = {"DX": "电信", "LT": "联通", "YD": "移动"}

WATCH_INTERVAL = 10   # 检测间隔（秒）
CHECK_TIMEOUT = 3.0   # 连通性检测超时（秒）


# ═══════════════════════════════════════
#  配置读写
# ═══════════════════════════════════════

def load_config() -> dict | None:
    """从家目录加载已保存的配置。"""
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if raw.get("user_id") and raw.get("password"):
            return raw
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return None


def save_config(config: dict) -> None:
    """保存配置到家目录（仅登录成功后才调用）。"""
    CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    # 类 Unix 系统设置仅 owner 可读写
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass


# ═══════════════════════════════════════
#  交互式向导
# ═══════════════════════════════════════

def _ts() -> str:
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")


def _print_banner():
    print()
    print("  ╔══════════════════════════════╗")
    print("  ║   🦞  cyber-lobster          ║")
    print("  ║   校园网自动重连工具         ║")
    print(f"  ║   版本 {__version__:<20s}║")
    print("  ╚══════════════════════════════╝")
    print()


def run_wizard() -> tuple[PortalCredentials, str]:
    """交互式配置向导，返回 (creds, host)。"""
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

    # 学号
    user_id = input("  学号: ").strip()
    while not user_id:
        user_id = input("  学号不能为空: ").strip()

    # 密码
    password = getpass.getpass("  密码: ")
    while not password:
        password = getpass.getpass("  密码不能为空: ")

    # host（可选，默认）
    host_input = input(f"  认证服务器地址 [{DEFAULT_HOST}]: ").strip()
    host = host_input or DEFAULT_HOST

    print()
    svc_name = SERVICE_NAMES.get(service, service)
    print(f"  📋 确认: {svc_name}({service}) / {user_id}")

    return PortalCredentials(
        user_id=user_id,
        password=password,
        service=service,
    ), host


# ═══════════════════════════════════════
#  监控循环
# ═══════════════════════════════════════

def run_watch(creds: PortalCredentials, host: str = DEFAULT_HOST) -> int:
    """进入断网自动重连监控模式。"""
    print()
    print(f"  ✅ 登录验证通过，进入监控模式")
    print(f"    运营商: {SERVICE_NAMES.get(creds.service, creds.service)}")
    print(f"    学号:   {creds.user_id}")
    print(f"    间隔:   {WATCH_INTERVAL}s 检测一次")
    print(f"    按 Ctrl+C 退出")
    print(f"  ═══════════════════════════════")
    print()

    fail_count = 0

    try:
        while True:
            ts = _ts()

            try:
                online = check_connectivity(timeout=CHECK_TIMEOUT)
            except Exception:
                online = False

            if online:
                if fail_count > 0:
                    print(f"  {ts} ✅ 网络已恢复（之前断连 {fail_count} 次）")
                    fail_count = 0
                else:
                    print(f"  {ts} 网络正常")
            else:
                fail_count += 1
                print(f"  {ts} ❌ 断连 ({fail_count})，正在重连...", end="")

                try:
                    result = login_with_session_retry(
                        creds, host=host,
                        max_session_attempts=1,
                        request_retries=2,
                    )
                    if result.success:
                        print(f"\r  {ts} ✅ 重连成功                                ")
                        fail_count = 0
                    else:
                        err = (result.error or result.body[:60]).replace("\n", " ")
                        print(f"\r  {ts} ❌ 重连失败: {err}")
                except Exception as exc:
                    print(f"\r  {ts} ❌ 异常: {type(exc).__name__}")

            time.sleep(WATCH_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n  {_ts()} 监控已停止。再见 👋")
        return 0
    except Exception as exc:
        print(f"\n  💥 意外错误: {type(exc).__name__}: {exc}")
        print("  程序将退出。")
        return 1


# ═══════════════════════════════════════
#  入口
# ═══════════════════════════════════════

def main() -> int:
    _print_banner()

    # ── 尝试加载已有配置 ──
    saved = load_config()
    if saved:
        print(f"  📂 找到已保存的配置: {saved['user_id']}")
        creds = PortalCredentials(
            user_id=saved["user_id"],
            password=saved["password"],
            service=saved.get("service", "DX"),
            query_string=saved.get("query_string", ""),
        )
        host = saved.get("host", DEFAULT_HOST)
        return run_watch(creds, host)

    # ── 无配置 → 交互向导 → 登录验证 → 保存 → 监控 ──
    creds, host = run_wizard()

    # 先验证登录
    print(f"  🔐 正在验证登录...")
    result = login_with_session_retry(
        creds, host=host,
        max_session_attempts=1,
        request_retries=2,
    )

    if result.success:
        # 登录成功 → 保存配置（密码存明文，下次启动重新 RSA 加密）
        save_config({
            "user_id": creds.user_id,
            "password": creds.password,       # 明文，登录时自动 RSA
            "service": creds.service,
            "host": host,
            "query_string": creds.query_string,
        })
        resp = parse_login_response(result.body)
        msg = resp.get("message", "") or resp.get("result", "")
        print(f"  ✅ 登录成功: {msg[:80]}")
        return run_watch(creds, host)
    else:
        # 登录失败
        err = result.error or result.body[:100]
        print(f"  ❌ 登录失败: {err}")
        print()
        print("  可能原因:")
        print("    - 账号或密码错误")
        print("    - 运营商选错")
        print("    - 校园网认证服务器不可达")
        print()
        print("  请重新运行本程序重试。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
