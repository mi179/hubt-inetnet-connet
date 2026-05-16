<div align="center">

# 🦞 cyber-lobster

**校园网自动重连工具 · 赛博龙虾守护者**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)]()

ePortal 校园网认证 · 断网自动重连 · 多账号管理 · 开机自启 · 单文件 EXE

</div>

---

## 📖 简介

`cyber-lobster` 是一个纯 Python 实现的校园网自动重连工具，专为 ePortal 认证系统设计。它运行在后台，每隔 10 秒检测一次外网连通性，一旦发现断网立即自动重新认证，让 NAS、工控机、软路由等设备保持永久在线。

### ✨ 特性

- ✅ **交互主菜单** — 双击即见随机赛博 Logo + 实时网络状态 + 6 项功能菜单
- ✅ **多套皮肤随机** — HUBT 专属版 / 颜文字老婆版 / 赛博机甲龙虾版，[5] 一键切换
- ✅ **自动重连** — 检测到断网后自动 RSA 加密登录，无需人工干预
- ✅ **多账号管理** — 保存多个学号，菜单 [2] 一键切换 + [4] 注销下线
- ✅ **Windows 原生弹窗** — 重连成功 / 注销成功桌面通知
- ✅ **开机自启** — 菜单一键设置（Windows Startup / Linux crontab + systemd）
- ✅ **单文件 EXE** — 基于 PyInstaller 打包，无需 Python 环境
- ✅ **隐私安全** — 配置仅存家目录 `~/.cyber_lobster_config.json`，权限 600

---

## 🚀 快速开始

### 方式一：Windows 用户（推荐）

从 [Releases](https://github.com/mi179/hubt-inetnet-connet/releases) 下载 `cyber-lobster.exe`，双击运行。

```
        🦞  cyber-lobster  v0.1.0  —  赛博龙虾守护者

  📡 网络状态:  ✅ 外网连通
  👤 当前账号:  （无 — 请先添加账号）

     [1]  🚀  一键连网并进入守护挂机模式
     [2]  🔄  切换当前账号
     [3]  ➕  添加新账号
     [4]  🔌  注销下线
     [5]  🎲  切换界面皮肤
     [0]  ❌  退出程序
```

EXE 也支持命令行参数（在终端/cmd 中运行）：

```cmd
cyber-lobster.exe watch          # 启动监控
cyber-lobster.exe setup          # 配置向导
cyber-lobster.exe switch         # 切换账号
cyber-lobster.exe logout         # 注销下线
cyber-lobster.exe autostart      # 设置开机自启
cyber-lobster.exe --help         # 查看全部命令
```

### 方式二：从源码运行

```bash
# 1. 克隆
git clone https://github.com/mi179/hubt-inetnet-connet.git
cd cyber-lobster

# 2. 安装
python3 -m venv .venv
source .venv/bin/activate   # Linux
# 或 .venv\Scripts\activate  # Windows
pip install -e .

# 3. 运行
cyber-lobster setup          # 首次配置
cyber-lobster watch          # 启动监控
```

### 方式三：打包成 EXE

```bash
pip install pyinstaller
python build.py
# 输出: dist/cyber-lobster.exe
```

---

## 📋 命令参考

| 命令 | 说明 |
|------|------|
| `cyber-lobster setup` | 交互式配置向导（添加/修改账号） |
| `cyber-lobster switch` | 切换当前默认账号 |
| `cyber-lobster watch` | 断网自动重连监控守护模式 |
| `cyber-lobster login --current` | 手动执行一次登录 |
| `cyber-lobster logout` | 发送 ePortal 注销请求 |
| `cyber-lobster autostart` | 设置开机自启 |
| `cyber-lobster status` | 查看系统状态（CPU / 内存） |
| `cyber-lobster ping` | Ping 检测网关 |
| `cyber-lobster check` | 一键全检（status + ping） |

### watch 参数

```bash
cyber-lobster watch --interval 5 --timeout 2
# --interval  检测间隔秒数（默认 10）
# --timeout   检测超时秒数（默认 3）
```

---

## 🏗️ 项目结构

```
cyber-lobster/
├── exe_main.py                 # EXE 双击入口（无脑自动流）
├── build.py                    # PyInstaller 打包脚本
├── pyproject.toml              # 项目元数据
├── src/cyber_lobster/
│   ├── cli.py                  #  CLI 框架（9 个子命令）
│   ├── config.py               #  多账号配置文件管理
│   ├── logger.py               #  时间戳日志 + Windows 弹窗
│   ├── network.py              #  Ping / HTTP 连通性检测
│   ├── network_login.py        #  ePortal 登录 + RSA 加密 + 注销
│   └── system.py               #  CPU 温度 / 内存检测
└── tests/                      #  单元测试
```

---

## 🔧 技术栈

| 模块 | 用途 |
|------|------|
| `argparse` | CLI 命令行框架 |
| `requests` | HTTP 请求 + Session 管理 |
| `RSA-1024` | 客户端密码加密（反转 → 模幂） |
| `ctypes` | Windows 原生弹窗通知 |
| `pathlib` | 跨平台路径处理 |

**核心依赖：仅 `requests` 🎉**

---

## 🪟 Windows 弹窗效果

断网重连成功时自动弹出：

```
┌──────────────────────────────────┐
│  🦞 赛博龙虾守护者               │
│                                  │
│  校园网已自动重新连通！           │
│                                  │
│            [确定]                 │
└──────────────────────────────────┘
```

---

## 🏠 配置文件

路径：`~/.cyber_lobster_config.json`

```json
{
  "current_user_id": "20240000000",
  "accounts": {
    "20240000000": {
      "password": "...",
      "service": "DX",
      "host": "172.16.54.18",
      "query_string": ""
    }
  }
}
```

> `password` 存明文（登录时自动 RSA 加密），文件权限 600 仅当前用户可读。

---

## 🔄 工作流程

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  双击 EXE    │────→│  有配置文件?   │────→│  watch 监控模式 │
└─────────────┘     └──────┬───────┘     └───────┬───────┘
                           │ 无                   │ 每 10s 检测
                           ▼                      ▼
                    ┌──────────────┐     ┌───────────────┐
                    │  setup 向导   │     │  连通性检测     │
                    │  选运营商     │     │  HTTP GET      │
                    │  输学号密码   │     │  223.5.5.5     │
                    │  验证登录     │     └───────┬───────┘
                    │  保存配置     │            │ 断连
                    └──────┬───────┘     ┌───────▼───────┐
                           │             │  自动 RSA 登录  │
                           ▼             │  Windows 弹窗   │
                    ┌──────────────┐     └───────┬───────┘
                    │  watch 监控   │◄────────────┘
                    └──────────────┘     成功 → 继续监控
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📋 更新日志

### v0.2.0 (2026-05-17)
- 🆕 交互主菜单 — 赛博 Logo + 实时网络状态
- 🆕 3 套随机 ASCII 皮肤 + 菜单 [5] 一键切换
- 🆕 release 自动化发布工作流
- 🆕 多账号切换 / 注销下线功能
- 🆕 开机自启设置（Windows / Linux）
- 🔧 Windows 原生 ctypes 弹窗通知
- 🔧 配置迁移至家目录 `~/.cyber_lobster_config.json`
- 🔧 EXE 同时支持双击菜单 / 命令行参数

### v0.1.0 (2026-05-16)
- 🆕 首个稳定版本
- 🆕 ePortal RSA 加密登录
- 🆕 断网自动重连 watch 监控
- 🆕 交互式配置向导 setup
- 🆕 单文件 EXE 打包

---

## 📄 License

[MIT](LICENSE)

---

<div align="center">
  Built with ❤️ for homelab enthusiasts
</div>
