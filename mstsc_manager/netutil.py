from __future__ import annotations

import errno
import socket
import time

from .i18n import tr


def check_local_port(host: str, port: int) -> tuple[bool, str]:
    """尝试在 host:port 上监听，返回 (是否空闲, 说明)。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 不设 SO_REUSEADDR，确保被占用时能真实报错
        s.bind((host, port))
        s.listen(1)
        return True, tr("port.free", host=host, port=port)
    except OSError as e:
        if e.errno in (errno.EADDRINUSE, 10048):
            return False, tr("port.busy", host=host, port=port)
        if e.errno in (errno.EACCES, 10013):
            return False, tr("port.denied", host=host, port=port)
        return False, tr("port.error", host=host, port=port, err=e.strerror or e)
    finally:
        s.close()


def find_free_port(host: str, start: int = 13389, end: int = 13489) -> int:
    for p in range(start, end):
        ok, _ = check_local_port(host, p)
        if ok:
            return p
    # 兜底：让系统分配
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, 0))
        return s.getsockname()[1]
    finally:
        s.close()


def tcp_probe(host: str, port: int, timeout: float = 5.0) -> float:
    """直接 TCP 握手，返回耗时(ms)，失败抛 OSError。"""
    t0 = time.perf_counter()
    with socket.create_connection((host, port), timeout=timeout):
        pass
    return (time.perf_counter() - t0) * 1000
