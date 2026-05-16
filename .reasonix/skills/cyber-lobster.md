---
name: cyber-lobster
description: 启动 cyber-lobster 校园网断网自动重连 — 安装依赖、配置账号、进入 watch 监控模式
---

## cyber-lobster — Homelab 校园网自动重连工具

项目位于 `cyber-lobster/`，纯 Python + requests，用于 ePortal 校园网认证的断网自动重连。

### 首次使用

```bash
cd cyber-lobster

# 1. 创建虚拟环境并安装
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 2. 运行配置向导（输入学号、密码明文、运营商）
cyber-lobster setup

# 3. 启动监控（每 10 秒检测一次，断网自动重连）
cyber-lobster watch
```

### 常用子命令

| 命令 | 说明 |
|------|------|
| `cyber-lobster status` | 查看 CPU 温度 + 内存 |
| `cyber-lobster ping` | Ping 检测配置的网关 |
| `cyber-lobster check` | status + ping 一键全检 |
| `cyber-lobster setup` | 交互配置向导 |
| `cyber-lobster login --from-config` | 手动执行一次登录 |
| `cyber-lobster watch` | 监控模式（断网自动重连） |

### watch 参数

```bash
cyber-lobster watch --interval 5 --timeout 2
# --interval 检测间隔（秒，默认 10）
# --timeout  HTTP 超时（秒，默认 3）
```

### 注意事项

- 密码支持明文（自动 RSA 加密）或已加密的 256 位 hex hash
- config.json 含密码，已被 .gitignore 排除
- 按 Ctrl+C 干净退出 watch 模式
