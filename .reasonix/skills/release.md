---
name: release
description: 自动化版本发布 — 分析差异/更新 README/提升版本/git tag 推送/打印 Release Note
---

## release — 自动化版本发布工作流

当用户说「执行 release」或「帮我发个新版」时，严格按照以下步骤执行：

### 步骤 1：分析差异

```bash
# 查看上一次 tag 以来的所有提交
git log $(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)..HEAD --oneline --no-decorate

# 如果没 tag，从第一个 commit 开始统计
```

从 git log 中提取关键功能点，分类整理为：
- 🆕 **新增功能** (feat:)
- 🐞 **Bug 修复** (fix:)
- 🔧 **优化重构** (refactor:)
- 📝 **文档更新** (docs:)

### 步骤 2：自动更新 README.md

**如果 README.md 不存在** → 调用 `write_file` 创建标准模板（包含简介、特性、用法、目录结构、更新日志）。

**如果已存在** → 更新以下三个区域：

**① 功能特性 (Features)** — 扫描 `src/` 目录下的关键模块，确保 README.md 的 ✨ 特性列表覆盖所有当前功能：
- 交互主菜单（多皮肤随机显示）
- 断网自动重连（RSA 加密）
- 多账号管理（切换/添加/注销）
- Windows 原生弹窗通知
- 开机自启
- 单文件 EXE

**② 使用说明 (Usage)** — 确保命令参考与 `cli.py` 中的子命令完全一致（对比 `build_parser()` 中的 subparsers）。

**③ 更新日志 (Changelog)** — 在 README 末尾追加新的版本条目，格式：
```markdown
## 📋 更新日志

### vX.X.X (YYYY-MM-DD)
- 🆕 新增功能1
- 🆕 新增功能2
- 🔧 优化功能3
```

### 步骤 3：提升版本号

读取 `src/cyber_lobster/__init__.py` 中的 `__version__`，执行小版本递增（v0.1.0 → v0.2.0）。

用 `edit_file` 修改：
- `src/cyber_lobster/__init__.py` 中的 `__version__`
- `pyproject.toml` 中的 `version`

### 步骤 4：Git 提交 + Tag + 推送

```bash
git -C $(pwd) add -A
git -C $(pwd) commit -m "chore: release vX.X.X"
git -C $(pwd) tag vX.X.X
git -C $(pwd) push origin main --tags
```

> 如果推送需要认证，remote 已内置 token，无需额外操作。

### 步骤 5：打印 Release Note

在终端输出以下格式的 Markdown，用户可直接复制粘贴到 GitHub Release 页面：

```markdown
## 🦞 cyber-lobster vX.X.X

### ✨ 新增功能
- ...

### 🔧 优化改进
- ...

### 🐞 修复
- ...

### 📦 下载
cyber-lobster.exe — 见 GitHub Releases 页面
```
