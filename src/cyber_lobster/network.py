"""网络连通性检测（基于 ping）。"""

import subprocess
import re
import statistics
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PingResult:
    target: str
    alive: bool
    sent: int = 0
    received: int = 0
    loss_pct: float = 100.0
    rtt_ms: list[float] = field(default_factory=list)

    @property
    def avg_rtt(self) -> Optional[float]:
        return statistics.mean(self.rtt_ms) if self.rtt_ms else None

    @property
    def max_rtt(self) -> Optional[float]:
        return max(self.rtt_ms) if self.rtt_ms else None

    @property
    def min_rtt(self) -> Optional[float]:
        return min(self.rtt_ms) if self.rtt_ms else None


# Linux ping output: 64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=1.23 ms
RE_PING = re.compile(r"time=(\d+\.?\d*)\s*ms")
RE_SUMMARY = re.compile(
    r"(\d+)\s+packets transmitted, (\d+)\s+(?:received|packets received)"
)


def ping_host(host: str, count: int = 3, timeout: int = 5) -> PingResult:
    """对单个 host 执行 ping，返回 PingResult。"""
    cmd = ["ping", "-c", str(count), "-W", str(timeout), host]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=count * (timeout + 1) + 2,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return PingResult(target=host, alive=False)

    stdout = proc.stdout
    rtts = [float(m) for m in RE_PING.findall(stdout)]

    transmitted = count
    received = 0
    for m in RE_SUMMARY.finditer(stdout):
        transmitted = int(m.group(1))
        received = int(m.group(2))

    loss_pct = ((transmitted - received) / transmitted * 100) if transmitted else 100

    return PingResult(
        target=host,
        alive=received > 0,
        sent=transmitted,
        received=received,
        loss_pct=loss_pct,
        rtt_ms=rtts,
    )


def check_gateways(
    gateways: list[str], count: int = 3, timeout: int = 5
) -> list[PingResult]:
    """依次检测多个网关。"""
    results: list[PingResult] = []
    for gw in gateways:
        results.append(ping_host(gw, count=count, timeout=timeout))
    return results
