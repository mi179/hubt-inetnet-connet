<div align="center">

# 🦞 cyber-lobster

**校园网自动重连工具 · 赛博龙虾守护者**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)]()

**一键配置 · 多账号切换 · 断网自动重连 · Windows 弹窗通知 · 开机自启**

</div>

---

## 📖 简介

`cyber-lobster` 是一个纯 Python 实现的校园网自动重连工具，专为 ePortal 认证系统设计。它运行在后台 7x24 小时检测外网连通性，一旦发现断网立即自动重新认证，让 NAS、工控机、软路由等设备保持永久在线。

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| 🦞 **炫酷极客主菜单** | 双击即入交互菜单，支持 🎲 随机皮肤（二次元老婆 / HUBT 校名 / 赛博机甲） |
| 🔄 **多账号一键切换** | 保存多个学号，菜单 [2] 切换 / [3] 添加 / [4] 注销 |
| 🔌 **标准注销下线** | 调用 ePortal 标准 logout 接口，干净下线 |
| 📡 **7x24 断网重连** | 10 秒检测一次外网，断开自动 RSA 加密重连，Windows 原生弹窗通知 |
| 🚀 **开机自启** | 一键设置 Windows 开机启动 / Linux crontab + systemd |
| 🪟 **Windows 弹窗** | 原生 `ctypes.MessageBoxW` 通知，无需任何第三方库 |
| 🔒 **隐私安全** | 配置仅存家目录 `~/.cyber_lobster_config.json`，权限 600 |

---

## 🚀 快速开始

### 方式一：Windows EXE（推荐）

从 [Releases](https://github.com/mi179/hubt-inetnet-connet/releases) 下载 `cyber-lobster.exe`，双击运行：

```
         🦞  cyber-lobster  v0.2.0

  📡 网络状态:  ✅ 外网连通
  👤 当前账号:  20240000000 (电信)

     [1]  🚀  一键连网并进入守护挂机模式
     [2]  🔄  切换当前账号
     [3]  ➕  添加新账号
     [4]  🔌  注销下线
     [5]  🎲  切换界面皮肤
     [0]  ❌  退出程序
```

> 💡 **首次运行** → 选 [3] 添加账号，验证成功后自动进入守护模式  
> 💡 **以后双击** → 菜单任你选，监控/切号/注销/换皮肤

### 方式二：从源码运行

```bash
git clone https://github.com/mi179/hubt-inetnet-connet.git
cd cyber-lobster
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cyber-lobster
```

### 方式三：打包成单文件 EXE

```bash
pip install pyinstaller
python build.py
# 输出: dist/cyber-lobster.exe
```

---

## 📋 全部命令

| 命令 | 说明 |
|------|------|
| `cyber-lobster`（无参数） | 进入交互主菜单 |
| `cyber-lobster watch` | 断网自动重连守护模式 |
| `cyber-lobster setup` | 配置向导（添加账号） |
| `cyber-lobster switch` | 切换当前默认账号 |
| `cyber-lobster logout` | 注销下线 |
| `cyber-lobster autostart` | 设置开机自启 |
| `cyber-lobster status` | 系统状态（CPU / 内存） |
| `cyber-lobster ping` | Ping 检测网关 |
| `cyber-lobster --help` | 查看全部帮助 |

---

## 🏗️ 项目结构

```
cyber-lobster/
├── exe_main.py                  # EXE 双击入口（主菜单）
├── build.py                     # PyInstaller 打包脚本
├── pyproject.toml               # 项目元数据
├── src/cyber_lobster/
│   ├── cli.py                   #  CLI 框架（9 个子命令）
│   ├── config.py                #  多账号配置文件管理
│   ├── logger.py                #  时间戳日志 + Windows 弹窗
│   ├── network.py               #  Ping / HTTP 连通性检测
│   ├── network_login.py         #  ePortal 登录 + RSA + 注销
│   └── system.py                #  CPU 温度 / 内存检测
└── tests/
```

---

## 🔄 工作流程

```
┌─────────────┐
│  双击 EXE    │
└──────┬──────┘
       ▼
┌──────────────┐
│  交互主菜单    │ ← 随机皮肤 + 网络状态
│  [1] 监控     │
│  [2] 切换账号  │
│  [3] 添加账号  │
│  [4] 注销下线  │
│  [5] 换皮肤    │
│  [0] 退出     │
└──────┬───────┘
       │ 选 [1]
       ▼
┌──────────────┐      ┌───────────────┐
│  守护监控模式   │────→│  每 10s 检测   │
│  Ctrl+C 返回   │     │  外网连通性    │
└──────────────┘      └───────┬───────┘
                              │ 断连
                              ▼
                       ┌──────────────┐
                       │  自动 RSA 登录 │
                       │  Windows 弹窗  │
                       └───────┬──────┘
                               │ 成功
                               ▼
                       ┌──────────────┐
                       │  继续监控     │
                       └──────────────┘
```

---

## 🪟 Windows 弹窗效果

断网重连成功 / 注销成功时自动弹出：

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

> 密码存明文（登录时自动 RSA 加密），文件权限 600 仅当前用户可读。

---

## 📋 更新日志

### v0.2.0 (2026-05-17)
- 🆕 交互主菜单 — 赛博 Logo + 实时网络状态
- 🆕 3 套随机 ASCII 皮肤 + 菜单 [5] 一键切换
- 🆕 多账号切换 & 注销下线
- 🆕 开机自启设置（Windows / Linux）
- 🆕 EXE 双模式：双击菜单 / 命令行参数
- 🔧 Windows 原生 ctypes 弹窗
- 🔧 配置迁移至家目录，多账号存储

### v0.1.0 (2026-05-16)
- 🆕 ePortal RSA 加密登录
- 🆕 断网自动重连 watch 监控
- 🆕 交互式配置向导 setup
- 🆕 单文件 EXE 打包

---

## 📄 License

[MIT](LICENSE)

---

<div align="center">
  Made with ❤️ · 赛博龙虾守护着你的校园网
</div>
