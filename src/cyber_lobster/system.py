"""Linux 系统状态检测（标准库，仅限 Linux）。"""

import os
import re
from pathlib import Path

# ---- CPU 温度 ----

THERMAL_BASE = Path("/sys/class/thermal")


def get_cpu_temp() -> float | None:
    """读取 CPU 封装温度（摄氏度），失败返回 None。

    遍历 thermal_zone*，取 type == "x86_pkg_temp" 或 "cpu-thermal"
    的温度，单位是毫摄氏度。
    """
    if not THERMAL_BASE.is_dir():
        return None

    for zone in sorted(THERMAL_BASE.iterdir()):
        if not zone.name.startswith("thermal_zone"):
            continue
        type_path = zone / "type"
        temp_path = zone / "temp"
        if not (type_path.is_file() and temp_path.is_file()):
            continue
        try:
            zone_type = type_path.read_text().strip()
            if zone_type in ("x86_pkg_temp", "cpu-thermal"):
                raw = int(temp_path.read_text().strip())
                return raw / 1000.0
        except (ValueError, OSError):
            continue
    return None


def get_all_temp_sensors() -> dict[str, float]:
    """返回所有 thermal_zone 的温度（摄氏度）。"""
    result: dict[str, float] = {}
    if not THERMAL_BASE.is_dir():
        return result

    for zone in sorted(THERMAL_BASE.iterdir()):
        if not zone.name.startswith("thermal_zone"):
            continue
        try:
            zone_type = (zone / "type").read_text().strip()
            raw = int((zone / "temp").read_text().strip())
            result[zone_type] = raw / 1000.0
        except (ValueError, OSError):
            continue
    return result


# ---- 内存 ----

RE_MEMLINE = re.compile(r"^(\w+):\s+(\d+)\s+kB$")


def get_memory_info() -> dict[str, int]:
    """从 /proc/meminfo 读取关键内存指标（KB）。"""
    info: dict[str, int] = {}
    try:
        text = Path("/proc/meminfo").read_text()
    except OSError:
        return info

    for line in text.splitlines():
        m = RE_MEMLINE.match(line)
        if m:
            info[m.group(1)] = int(m.group(2))
    return info


def format_memory(info: dict[str, int]) -> str:
    """将 MemTotal / MemAvailable 格式化为人类可读形式。"""
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    used = total - avail
    pct = (used / total * 100) if total else 0
    return f"{_human_kb(used)} / {_human_kb(total)} ({pct:.1f}%)"


def _human_kb(kb: int) -> str:
    """KB → GiB 友好显示。"""
    gib = kb / (1024 * 1024)
    if gib >= 1:
        return f"{gib:.2f} GiB"
    mib = kb / 1024
    return f"{mib:.0f} MiB"


def diagnose_platform():
    """跨平台检查：非 Linux 打印友好提示。"""
    if os.name != "posix":
        print("⚠ 本工具目前仅支持 Linux。")
