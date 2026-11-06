"""启动 mstsc：默认走命令行参数；可选生成 .rdp 文件。"""

from __future__ import annotations

import subprocess
import winreg
from pathlib import Path

from .log import logger
from .models import LAUNCH_FILE, Connection
from .storage import sessions_dir

_TSC_SERVERS_KEY = r"Software\Microsoft\Terminal Server Client\Servers"


def _full_username(conn: Connection) -> str:
    r = conn.rdp
    if r.domain and r.username:
        return f"{r.domain}\\{r.username}"
    return r.username


# ---------------------------------------------------------------- 命令行方式
def build_mstsc_args(conn: Connection, address: str, port: int) -> list[str]:
    r = conn.rdp
    fullscreen, w, h = r.resolve_size()
    args = ["mstsc.exe", f"/v:{address}:{port}"]
    if fullscreen:
        args.append("/f")
        if r.multimon:
            args.append("/multimon")
    else:
        args += [f"/w:{w}", f"/h:{h}"]
    return args


def set_username_hint(address: str, username: str) -> None:
    """写入 mstsc 自己用来记住"上次用户名"的注册表项，让登录框预填用户名。"""
    if not username:
        return
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{_TSC_SERVERS_KEY}\\{address}") as k:
            winreg.SetValueEx(k, "UsernameHint", 0, winreg.REG_SZ, username)
        logger.debug("mstsc: UsernameHint for {} set to {!r}", address, username)
    except OSError as e:
        logger.warning("mstsc: failed to set UsernameHint for {}: {!r}", address, e)


# ---------------------------------------------------------------- .rdp 文件方式
def build_rdp_text(conn: Connection, address: str, port: int) -> str:
    r = conn.rdp
    fullscreen, w, h = r.resolve_size()
    username = _full_username(conn)

    lines = [
        f"full address:s:{address}:{port}",
        f"screen mode id:i:{2 if fullscreen else 1}",
        f"use multimon:i:{1 if r.multimon else 0}",
        "session bpp:i:32",
        f"smart sizing:i:{1 if r.smart_sizing else 0}",
        f"redirectclipboard:i:{1 if r.redirect_clipboard else 0}",
        f"redirectdrives:i:{1 if r.redirect_drives else 0}",
        "redirectprinters:i:0",
        "autoreconnection enabled:i:1",
        "prompt for credentials:i:1",
        f"authentication level:i:{0 if r.ignore_cert else 2}",
        "promptcredentialonce:i:1",
    ]
    if not fullscreen:
        lines += [f"desktopwidth:i:{w}", f"desktopheight:i:{h}", "winposstr:s:0,1,0,0,%d,%d" % (w + 16, h + 60)]
    if username:
        lines.append(f"username:s:{username}")
    return "\r\n".join(lines) + "\r\n"


def write_rdp_file(conn: Connection, address: str, port: int) -> Path:
    path = sessions_dir() / f"{conn.id}.rdp"
    # newline="" 防止 \r\n 被再次翻译成 \r\r\n；UTF-16 带 BOM 是 mstsc 自己的保存格式
    path.write_text(build_rdp_text(conn, address, port), encoding="utf-16", newline="")
    return path


# ---------------------------------------------------------------- 统一入口
def launch_mstsc(conn: Connection, address: str, port: int) -> tuple[subprocess.Popen, str]:
    """返回 (进程, 启动方式描述)。"""
    if conn.rdp.launch_mode == LAUNCH_FILE:
        rdp_file = write_rdp_file(conn, address, port)
        logger.info("mstsc: launching with .rdp file {}", rdp_file)
        proc = subprocess.Popen(["mstsc.exe", str(rdp_file)])
        logger.info("mstsc: started pid={}", proc.pid)
        return proc, f".rdp {rdp_file.name}"
    set_username_hint(address, _full_username(conn))
    args = build_mstsc_args(conn, address, port)
    logger.info("mstsc: launching {}", " ".join(args))
    proc = subprocess.Popen(args)
    logger.info("mstsc: started pid={}", proc.pid)
    return proc, " ".join(args[1:])
