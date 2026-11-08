# 开发

## 环境

本项目用 [uv](https://docs.astral.sh/uv/) 管理 Python 与依赖，不需要单独安装 Python。

```powershell
uv sync --group dev      # 安装运行依赖 + pyinstaller
uv run python main.py    # 源码运行
build.cmd                # 本地打包 → dist\mstsc-manager\mstsc-manager.exe，并压缩成 zip
```

运行时文件：

| 内容 | 位置 |
| --- | --- |
| 连接配置 | `%APPDATA%\ccbs\mstsc-manager\connections.json`（上一版自动备份为 `.bak`） |
| SSH 主机密钥 | `%APPDATA%\ccbs\mstsc-manager\known_hosts` |
| 日志 | `%APPDATA%\ccbs\mstsc-manager\logs\app.log`（10 MB 轮转，保留 3 个） |
| 语言设置 | QSettings（注册表 `HKCU\Software\ccbs\mstsc-manager`） |
| .rdp 临时文件 | `%LOCALAPPDATA%\ccbs\mstsc-manager\sessions\` |

## 目录

```
main.py                      入口：日志初始化、QApplication、主窗口
main.spec                    PyInstaller 文件夹打包配置（裁掉未用的 Qt 模块）
mstsc_manager/
  models.py                  Connection / RdpConfig / SshConfig 数据模型
  storage.py                 配置 JSON 读写与备份
  i18n.py                    中英文文案表，tr() / i18n.languageChanged
  log.py                     loguru 日志；接管未捕获异常、Qt 消息、stdlib logging（paramiko）
  changelog.py               版本历史（Release 说明从这里生成）+ GitHub Releases 检查更新
  netutil.py                 本地端口检查、TCP 探测
  tunnel.py                  paramiko 本地端口转发（ssh -L）
  rdp.py                     生成 mstsc 命令行 / .rdp 文件并启动
  session.py                 连接流程编排（QThread），分步状态与日志
  ui/main_window.py          主窗口、菜单、工具栏、会话管理
  ui/connection_form.py      连接配置表单
  ui/status_panel.py         步骤状态 + 日志面板
  ui/version_dialogs.py      版本介绍 / 检查更新对话框
  ui/icons.py                应用图标
assets/                      图标与 README 截图（rdp.png、ssh-tunnel.png）
README.md / README_zh.md     面向用户的说明（英文为主 / 中文）
```

## 文案

所有界面文字集中在 `mstsc_manager/i18n.py` 的 `_STRINGS`，中英两张表的键必须一致。新增文案时：

1. 两张表各加一条，键名用 `模块.含义` 形式（如 `f.timeout`、`s.tunnel_ready`）。
2. 代码里用 `tr("key", **kwargs)` 取文案；动态刷新的控件在所属类的 `retranslate()` 里更新。

日志（`logger.*`）统一英文，不走 i18n，且不得记录密码/口令。

## 发版

版本号有三处，发版时一起改、保持一致：

1. `mstsc_manager/__init__.py` 的 `__version__`：程序内显示（关于对话框、日志开头）。
2. `pyproject.toml` 的 `version`：GitHub Actions 打包 zip 名用这个，例如 `mstsc-manager-v0.1.1-windows-x64.zip`。
3. `mstsc_manager/changelog.py` 的 `RELEASES`：在最前面加一条版本说明，Actions 发布 Release 时用它生成说明文字。中英文 `notes` 都要写。

改完后提交，再推送同名 tag，例如：

```powershell
git tag v0.1.1
git push origin v0.1.1
```

`.github/workflows/build.yml` 在 `v*` tag 上会打包并把 zip + `SHA256SUMS.txt` 发布到**本仓库**的 Releases；在 Actions 页面手动 "Run workflow" 则只打包，产物在 Artifacts 里保留 7 天。
