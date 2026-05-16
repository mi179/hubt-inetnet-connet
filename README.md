# 🦞 cyber-lobster

> Homelab 网络与服务器运维 CLI 工具

`cyber-lobster` 是一个纯标准库实现的 Python CLI 工具，专为个人 Homelab 环境设计，用于快速检查 Linux 系统的运行状态及网络连通性。

---

## 快速开始

```bash
# 1. 安装（开发模式）
pip install -e .

# 2. 配置网关地址（可选，默认三个示例地址）
cp config.json.example config.json
# 编辑 config.json，填入你家网关/旁路由的 IP

# 3. 运行
cyber-lobster check
```

---

## 使用方法

### 查看系统状态

```bash
cyber-lobster status
```

输出 CPU 封装温度、内存使用量。加 `--all-sensors` 可查看所有 thermal 传感器。

### Ping 检测网关

```bash
cyber-lobster ping
```

对 `config.json` 中配置的网关逐一发 Ping 包，显示通断、延迟和丢包率。  
也可直接测试不在配置文件里的目标：

```bash
cyber-lobster ping --help   # 目前只检测已配网关，后期会支持 --host 参数
```

### 一键全检

```bash
cyber-lobster check
```

等价于 `status` + `ping` 一起跑，适合日常巡检。

---

## 配置文件

查找优先级（先到先用）：

1. 命令行 `--config /path/to/config.json`
2. 当前目录 `./config.json`
3. `~/.config/cyber-lobster/config.json`

参考 `config.json.example`：

```json
{
  "gateways": ["192.168.1.1", "10.0.0.1", "1.1.1.1"],
  "ping_count": 3,
  "ping_timeout": 5
}
```

---

## 目录结构

```
cyber-lobster/
├── README.md                   ← 本文件
├── pyproject.toml              ← 项目元数据
├── config.json.example         ← 网关配置示例
├── src/
│   └── cyber_lobster/
│       ├── __init__.py         ← 包版本信息
│       ├── __main__.py         ← python -m 入口
│       ├── cli.py              ← argparse 命令行框架
│       ├── config.py           ← 配置文件加载
│       ├── system.py           ← CPU 温度 / 内存检测
│       └── network.py          ← Ping 连通性检测
└── tests/
    ├── __init__.py
    └── test_system.py          ← 基础单元测试
```

---

## 设计原则

- **标准库为主** — 零外部依赖，`pip install` 即用
- **仅限 Linux** — 通过 `/sys/class/thermal` 和 `/proc/meminfo` 读取数据
- **CLI 优先** — 纯命令行交互，适合 SSH 连入 NAS / 工控机 / 软路由后一键巡检
- **简单可靠** — 每个文件职责清晰，方便按需魔改

---

## 路线图（初步想法）

- [ ] 支持 `--host` 参数临时指定 Ping 目标
- [ ] 持续运行模式（`watch`），每隔 N 秒刷新
- [ ] 磁盘使用 / 进程统计 / 系统负载
- [ ] 通知推送（如检测到离线发 Telegram / Discord 消息）
- [ ] Docker 容器状态检测
- [ ] 彩色输出（ANSI escape codes）

---

## License

MIT
