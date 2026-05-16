---
name: cyber-lobster
description: 🦞 校园网断网自动重连工具 — 安装/配置/打包/发布全流程
---

## cyber-lobster

校园网 ePortal 自动重连工具。纯 Python + requests，支持多账号 / 切换 / 注销 / 开机自启 / Windows 弹窗。

### 项目位置

```
/home/miao/cyber-lobster/
```

### 源码运行

```bash
cd /home/miao/cyber-lobster
source .venv/bin/activate
python exe_main.py        # 双击自动流（菜单 / 向导 / 监控）
# 或
cyber-lobster watch       # CLI 子命令
```

### 常用子命令

| 命令 | 说明 |
|------|------|
| `cyber-lobster setup` | 配置向导 |
| `cyber-lobster switch` | 切换账号 |
| `cyber-lobster logout` | 注销下线 |
| `cyber-lobster watch` | 断网监控 |
| `cyber-lobster autostart` | 开机自启 |

### EXE 打包

```bash
cd /home/miao/cyber-lobster
source .venv/bin/activate
pip install pyinstaller
python build.py
# 输出: dist/cyber-lobster (Linux) 或在 Windows 下为 dist/cyber-lobster.exe
```

Windows 打包需在 Windows PowerShell 中：
```powershell
cd \\wsl.localhost\Ubuntu\home\miao\cyber-lobster
py -3.12 -m pip install -e .
py -3.12 build.py
```

### GitHub 发布

```bash
git tag v0.1.0
git push origin v0.1.0
# 然后用 GitHub API 或网页创建 Release 并上传 EXE
```

### 配置文件

路径: `~/.cyber_lobster_config.json`
