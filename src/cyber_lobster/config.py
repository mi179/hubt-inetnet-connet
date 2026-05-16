"""配置文件加载管理。

配置统一存储在系统家目录： ~/.cyber_lobster_config.json
支持多账号，结构如下:

{
  "current_user_id": "20240000000",
  "accounts": {
    "20240000000": {
      "password": "ExamplePass123",
      "service": "DX",
      "host": "172.16.54.18",
      "query_string": ""
    }
  }
}
"""

import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ── 路径常量（固定在家目录，Windows / Linux 通用）──
CONFIG_FILENAME = ".cyber_lobster_config.json"
CONFIG_PATH = Path.home() / CONFIG_FILENAME


@dataclass
class AccountConfig:
    """单个账号的认证配置。"""
    user_id: str = ""
    password: str = ""           # 明文密码（登录时自动 RSA 加密）
    service: str = "DX"          # 运营商: DX / LT / YD
    host: str = "172.16.54.18"   # 认证服务器
    query_string: str = ""       # 重定向 queryString（可选）


@dataclass
class GlobalConfig:
    """全局配置（对应 JSON 文件）。"""
    current_user_id: str = ""
    accounts: dict[str, dict] = field(default_factory=dict)
    auto_auth: bool = True       # 开机/启动时是否自动认证
    auto_start: bool = False     # 是否 Windows 开机自启
    auto_start_id: str = ""      # 开机自启时自动使用的账号（空=不自动进入watch）
    current_skin: str = "random"            # 当前皮肤: "random" 或皮肤名
    custom_skins: dict[str, str] = field(default_factory=dict)  # 用户自定义皮肤 {"名字": "ASCII"}

    # ── 便捷方法 ──

    def get_current_account(self) -> Optional[AccountConfig]:
        """获取当前激活的账号配置，无则返回 None。"""
        raw = self.accounts.get(self.current_user_id)
        if not raw:
            return None
        return AccountConfig(
            user_id=raw.get("user_id", self.current_user_id),
            password=raw.get("password", ""),
            service=raw.get("service", "DX"),
            host=raw.get("host", "172.16.54.18"),
            query_string=raw.get("query_string", ""),
        )

    def upsert_account(self, account: AccountConfig) -> None:
        """添加或更新一个账号，并设为当前账号。"""
        self.accounts[account.user_id] = {
            "password": account.password,
            "service": account.service,
            "host": account.host,
            "query_string": account.query_string,
        }
        self.current_user_id = account.user_id

    def has_accounts(self) -> bool:
        return len(self.accounts) > 0

    def account_ids(self) -> list[str]:
        return list(self.accounts.keys())

    def remove_account(self, user_id: str) -> bool:
        if user_id in self.accounts:
            del self.accounts[user_id]
            if self.current_user_id == user_id:
                self.current_user_id = next(iter(self.accounts)) if self.accounts else ""
            return True
        return False


# ═══════════════════════════════════════════════
#  读写接口
# ═══════════════════════════════════════════════


def load() -> GlobalConfig:
    """从家目录加载配置，文件不存在时返回全默认值。"""
    if not CONFIG_PATH.is_file():
        return GlobalConfig()

    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print(f"[config] ⚠ 配置文件损坏 ({CONFIG_PATH})，使用默认值", file=sys.stderr)
        return GlobalConfig()

    return GlobalConfig(
        current_user_id=raw.get("current_user_id", ""),
        accounts=raw.get("accounts", {}),
        auto_auth=raw.get("auto_auth", True),
        auto_start=raw.get("auto_start", False),
        auto_start_id=raw.get("auto_start_id", ""),
        current_skin=raw.get("current_skin", "random"),
        custom_skins=raw.get("custom_skins", {}),
    )


def save(cfg: GlobalConfig) -> bool:
    """保存配置到家目录，设置 600 权限。"""
    try:
        CONFIG_PATH.write_text(
            json.dumps({
                "current_user_id": cfg.current_user_id,
                "accounts": cfg.accounts,
                "auto_auth": cfg.auto_auth,
                "auto_start": cfg.auto_start,
                "auto_start_id": cfg.auto_start_id,
                "current_skin": cfg.current_skin,
                "custom_skins": cfg.custom_skins,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Unix 权限：仅 owner 可读写
        try:
            CONFIG_PATH.chmod(0o600)
        except OSError:
            pass
        return True
    except OSError as exc:
        print(f"[config] ❌ 保存失败: {exc}", file=sys.stderr)
        return False


def config_path() -> str:
    return str(CONFIG_PATH)
