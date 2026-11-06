from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, fields
from typing import Any

# (显示名, 宽, 高)。宽高为 0 表示特殊项。
RESOLUTION_PRESETS: list[tuple[str, int, int]] = [
    ("1280 × 720", 1280, 720),
    ("1366 × 768", 1366, 768),
    ("1600 × 900", 1600, 900),
    ("1920 × 1080", 1920, 1080),
    ("2560 × 1440", 2560, 1440),
    ("3840 × 2160", 3840, 2160),
]
RES_FULLSCREEN = "fullscreen"
RES_CUSTOM = "custom"

SSH_AUTH_PASSWORD = "password"
SSH_AUTH_KEY = "key"

# mstsc 启动方式：命令行参数（无安全确认框）/ .rdp 文件（设置更全，但新版 Windows 每次弹确认）
LAUNCH_CLI = "cli"
LAUNCH_FILE = "file"


def _from_dict(cls, data: dict[str, Any] | None):
    """按 dataclass 字段过滤字典，忽略未知键，缺失键用默认值。"""
    data = data or {}
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in names})


@dataclass
class RdpConfig:
    host: str = ""
    port: int = 3389
    username: str = ""
    domain: str = ""
    # resolution: "WxH" 预设 / "fullscreen" / "custom"
    resolution: str = "1920x1080"
    custom_width: int = 1600
    custom_height: int = 900
    multimon: bool = False
    launch_mode: str = LAUNCH_CLI
    # ---- 以下仅 .rdp 文件方式生效 ----
    redirect_clipboard: bool = True
    redirect_drives: bool = False
    smart_sizing: bool = True
    # 走隧道时证书名和 127.0.0.1 不匹配，0 = 不弹证书警告
    ignore_cert: bool = True

    def resolve_size(self) -> tuple[bool, int, int]:
        """返回 (是否全屏, 宽, 高)。"""
        if self.resolution == RES_FULLSCREEN:
            return True, 0, 0
        if self.resolution == RES_CUSTOM:
            return False, self.custom_width, self.custom_height
        try:
            w, h = self.resolution.lower().split("x")
            return False, int(w), int(h)
        except ValueError:
            return False, 1920, 1080


@dataclass
class SshConfig:
    enabled: bool = False
    host: str = ""
    port: int = 22
    username: str = ""
    auth: str = SSH_AUTH_PASSWORD
    key_path: str = ""
    # 密码 / 私钥口令，DPAPI 加密后的 base64；为空表示未保存
    secret_enc: str = ""
    save_secret: bool = False
    bind_host: str = "127.0.0.1"
    # 0 = 自动分配
    local_port: int = 0
    keepalive: int = 15
    # 连接/认证/通道建立的超时秒数
    connect_timeout: int = 30
    close_with_mstsc: bool = True


@dataclass
class Connection:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "New Connection"
    group: str = ""
    notes: str = ""
    rdp: RdpConfig = field(default_factory=RdpConfig)
    ssh: SshConfig = field(default_factory=SshConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Connection":
        c = _from_dict(cls, {k: v for k, v in data.items() if k not in ("rdp", "ssh")})
        c.rdp = _from_dict(RdpConfig, data.get("rdp"))
        c.ssh = _from_dict(SshConfig, data.get("ssh"))
        return c

    def clone(self) -> "Connection":
        d = self.to_dict()
        d["id"] = uuid.uuid4().hex
        return Connection.from_dict(d)
