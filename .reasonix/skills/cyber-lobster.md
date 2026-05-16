---
name: cyber-lobster
description: 🦞 校园网断网自动重连工具 — 安装/配置/打包/发布全流程
---

## cyber-lobster

校园网 ePortal 自动重连工具。纯 Python + requests，v0.7.0。

### 项目位置

```
/home/miao/cyber-lobster/
```

### 项目结构

```
cyber-lobster/
├── exe_main.py                     # EXE 入口（主菜单 + 5 款皮肤 + 监控模式）
├── build.py                        # PyInstaller 打包脚本
├── .github/workflows/release.yml   # GitHub Actions 云端自动打包
├── .reasonix/skills/               # 技能文件
│   ├── cyber-lobster.md            # 本文件
│   ├── doc-guard.md                # 文档卫士
│   └── release.md                  # 自动化发布
├── pyproject.toml                  # 项目元数据
├── src/cyber_lobster/
│   ├── cli.py                      # CLI 框架（9 个子命令）
│   ├── config.py                   # 多账号 + 皮肤 + 开机自启配置
│   ├── logger.py                   # 时间戳日志 + Windows 弹窗
│   ├── network.py                  # HTTP 连通性检测 + Ping
│   ├── network_login.py            # ePortal 登录 + RSA + 注销
│   └── system.py                   # CPU 温度 / 内存
└── tests/
```

### 功能特性

| 特性 | 说明 |
|------|------|
| 🦞 主菜单 | 双击即入，7 项功能 + 实时网络状态 |
| 🎨 5 款皮肤 | HUBT/颜文字/机甲/初音/黑客 + 自定义导入 |
| 🔄 多账号 | 切换/添加/注销，下线旧号 再上线新号 |
| 📡 守护监控 | 实时状态栏 + B 返回菜单 + Q 退出 |
| ⚙️ 开机自启 | 自动认证开关/开机自启开关/选择启动账号 |
| 🪟 Windows 弹窗 | 重连/切换/注销时原生通知 |

### 源码运行

```bash
cd /home/miao/cyber-lobster
source .venv/bin/activate
python exe_main.py
```

### EXE 打包（Windows PowerShell）

```powershell
cd \\wsl.localhost\Ubuntu\home\miao\cyber-lobster
py -3.12 build.py
# 输出: dist\cyber-lobster.exe
```

建议同时打包 ZIP：
```powershell
Compress-Archive -Path dist\cyber-lobster.exe -DestinationPath dist\cyber-lobster.zip
```

### 发布新版

```bash
# 1. 更新版本号 + 更新日志
# 2. 提交 + tag
git tag vX.X.X
git push origin main --tags
# 3. 网页创建 Release + 上传 EXE + ZIP
```

### 配置文件

路径: `~/.cyber_lobster_config.json`

包含：多账号、custom_skins、current_skin、auto_auth、auto_start、auto_start_id
