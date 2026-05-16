"""配置文件加载管理。

查找顺序（先到先用）：
  1. 命令行 --config 指定路径
  2. ./config.json
  3. ~/.config/cyber-lobster/config.json
  4. ~/.cyber_lobster.json（EXE 交互入口的默认路径）
"""

import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

CONFIG_DIRNAME = "cyber-lobster"
CONFIG_FILENAME = "config.json"
HOME_CONFIG = ".cyber_lobster.json"


@dataclass
class Config:
    """运行时配置"""

    gateways: list[str] = field(default_factory=lambda: ["10.0.0.1"])  # 待检测的网关 IP
    ping_count: int = 3  # 每次 ping 发包数
    ping_timeout: int = 5  # 单次 ping 超时（秒）
    login: dict = field(default_factory=dict)  # ePortal 登录凭据（可选）


def _find_config(custom_path: Optional[str] = None) -> Optional[Path]:
    """按优先级查找配置文件。"""
    candidates: list[Path] = []

    if custom_path:
        candidates.append(Path(custom_path))

    candidates += [
        Path.cwd() / CONFIG_FILENAME,
        Path.home() / ".config" / CONFIG_DIRNAME / CONFIG_FILENAME,
        Path.home() / HOME_CONFIG,
    ]

    for path in candidates:
        if path.is_file():
            return path
    return None


def load(custom_path: Optional[str] = None) -> Config:
    """加载配置，找不到则返回全默认值。"""
    path = _find_config(custom_path)
    if path is None:
        return Config()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[cyber-lobster] ⚠ 配置解析失败 ({path}): {exc}", file=sys.stderr)
        return Config()

    # 支持扁平格式：若没有 login 字段，把 user_id/password 等归入 login
    known_top_keys = {"gateways", "ping_count", "ping_timeout"}
    login_raw = raw.get("login")
    if login_raw is None:
        login_raw = {k: v for k, v in raw.items() if k not in known_top_keys}

    return Config(
        gateways=raw.get("gateways", Config().gateways),
        ping_count=raw.get("ping_count", Config().ping_count),
        ping_timeout=raw.get("ping_timeout", Config().ping_timeout),
        login=login_raw,
    )
