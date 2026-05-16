"""system 模块基础测试（非 Linux 跳过传感器相关测试）。"""

import os
from unittest import TestCase, skipIf
from cyber_lobster.system import get_cpu_temp, get_memory_info, format_memory


class TestCpuTemp(TestCase):
    @skipIf(os.name != "posix", "仅 Linux")
    def test_get_cpu_temp_returns_float_or_none(self):
        """不应抛异常，返回 float 或 None"""
        result = get_cpu_temp()
        self.assertTrue(result is None or isinstance(result, float))


class TestMemory(TestCase):
    def test_get_memory_info_has_keys(self):
        info = get_memory_info()
        if info:
            self.assertIn("MemTotal", info)
            self.assertIn("MemAvailable", info)

    def test_format_memory_returns_str(self):
        fake = {"MemTotal": 8388608, "MemAvailable": 4194304}
        formatted = format_memory(fake)
        self.assertIsInstance(formatted, str)
        self.assertIn("GiB", formatted)
