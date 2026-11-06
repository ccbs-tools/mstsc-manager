"""版本历史。

发新版本时在 RELEASES 最前面加一条，同时改 pyproject.toml / __init__.py 的版本号（见 dev.md）。
GitHub Actions 发布 Release 时会从这里生成说明文字，中英文 notes 都要写。
"""

from __future__ import annotations

from . import __version__ as APP_VERSION

REPO_HOME = "https://github.com/ccbs-tools/mstsc-manager"

RELEASES: tuple[dict, ...] = (
    {
        "version": "0.1.0",
        "date": "2026-11-06",
        "notes": {
            "zh": [
                "初始版本。",
                "管理远程桌面(mstsc)连接：分辨率档位、全屏/多显示器、命令行或 .rdp 文件两种启动方式。",
                "每条连接可配置 SSH 跳板机本地端口转发（密码/私钥），连接前检查本地端口、探测目标 RDP 端口并分步显示状态。",
                "菜单栏：文件（导入/导出配置）、语言（中/英切换）、帮助；日志写入 %APPDATA%\\mstsc-manager\\logs。",
                "GitHub Actions 自动打包（PyInstaller 文件夹模式）并发布 Release。",
            ],
            "en": [
                "Initial release.",
                "Manage Remote Desktop (mstsc) connections: resolution presets, full screen / multi-monitor, "
                "launch via command line or .rdp file.",
                "Per-connection SSH jump-host local port forwarding (password / key); checks the local port, "
                "probes the target RDP port and shows step-by-step status before launching.",
                "Menu bar: File (import/export), Language (EN/ZH), Help; logs under %APPDATA%\\mstsc-manager\\logs.",
                "GitHub Actions packaging (PyInstaller one-folder) and Release publishing.",
            ],
        },
    },
)


def release_notes(entry: dict, lang: str) -> list[str]:
    notes = entry.get("notes") or {}
    return list(notes.get(lang) or notes.get("en") or [])


__all__ = ["APP_VERSION", "REPO_HOME", "RELEASES", "release_notes"]
