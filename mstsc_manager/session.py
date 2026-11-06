"""连接流程编排：端口检查 -> SSH 隧道 -> 目标探测 -> 启动 mstsc -> 运行中 -> 清理。"""

from __future__ import annotations

import subprocess
import threading
import time

import paramiko
from PySide6.QtCore import QThread, Signal

from .i18n import tr
from .log import logger
from .models import LAUNCH_FILE, Connection
from .netutil import check_local_port, find_free_port, tcp_probe
from .rdp import launch_mstsc
from .tunnel import SshTunnel

# 步骤 key（显示名通过 tr("step.<key>") 获取）
STEP_PORT = "port"
STEP_SSH = "ssh"
STEP_PROBE = "probe"
STEP_MSTSC = "mstsc"
STEPS: list[str] = [STEP_PORT, STEP_SSH, STEP_PROBE, STEP_MSTSC]

# 步骤状态
ST_IDLE = "idle"
ST_RUNNING = "running"
ST_OK = "ok"
ST_FAIL = "fail"
ST_SKIP = "skip"

# 会话整体状态
S_IDLE = "idle"
S_CONNECTING = "connecting"
S_RUNNING = "running"
S_ERROR = "error"


class SessionWorker(QThread):
    step_changed = Signal(str, str, str)   # step, state, message
    log = Signal(str)
    status_changed = Signal(str, str)      # status, summary
    finished_session = Signal()

    def __init__(self, conn: Connection, secret: str, test_only: bool = False, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.secret = secret
        self.test_only = test_only
        self._tunnel: SshTunnel | None = None
        self._proc: subprocess.Popen | None = None
        self._stop_evt = threading.Event()
        self._current_step = STEP_PORT
        self.status = S_IDLE

    # ---- 对外 ----
    def request_stop(self) -> None:
        logger.info("[{}] stop requested (status={})", self._tag, self.status)
        self._stop_evt.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                logger.info("[{}] mstsc pid={} terminated", self._tag, self._proc.pid)
            except OSError as e:
                logger.warning("[{}] terminate mstsc pid={} failed: {!r}", self._tag, self._proc.pid, e)
        if self._tunnel:
            self._tunnel.close()

    # ---- 内部工具 ----
    @property
    def _tag(self) -> str:
        return f"{self.conn.name}/{self.conn.id[:8]}"

    def _emit_log(self, msg: str) -> None:
        self.log.emit(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def _set_status(self, status: str, summary: str = "") -> None:
        if status != self.status:
            logger.info("[{}] status {} -> {}", self._tag, self.status, status)
        self.status = status
        self.status_changed.emit(status, summary)

    def _step(self, step: str, state: str, msg: str = "") -> None:
        if state == ST_RUNNING:
            self._current_step = step
            self._step_t0 = time.perf_counter()
        elif state in (ST_OK, ST_FAIL) and step == self._current_step:
            logger.info("[{}] step {} {} in {:.0f} ms", self._tag, step, state,
                        (time.perf_counter() - self._step_t0) * 1000)
        self.step_changed.emit(step, state, msg)
        if msg:
            self._emit_log(msg)

    # ---- 主流程 ----
    def run(self) -> None:
        conn = self.conn
        ssh = conn.ssh
        rdp = conn.rdp
        self._step_t0 = time.perf_counter()
        t_start = time.perf_counter()
        logger.info("[{}] session start | mode={} | target {}:{} | ssh={} | resolution={} | launch={}",
                    self._tag, "test" if self.test_only else "connect", rdp.host, rdp.port,
                    f"{ssh.username}@{ssh.host}:{ssh.port} ({ssh.auth})" if ssh.enabled else "off",
                    rdp.resolution, rdp.launch_mode)
        for key in STEPS:
            self.step_changed.emit(key, ST_IDLE, "")
        self._set_status(S_CONNECTING, tr("s.testing") if self.test_only else tr("s.connecting"))

        try:
            address, port = rdp.host, rdp.port

            if ssh.enabled:
                # 1. 本地端口
                self._step(STEP_PORT, ST_RUNNING)
                local_port = ssh.local_port
                if local_port <= 0:
                    local_port = find_free_port(ssh.bind_host)
                    self._step(STEP_PORT, ST_OK, tr("s.auto_port", host=ssh.bind_host, port=local_port))
                else:
                    ok, msg = check_local_port(ssh.bind_host, local_port)
                    if not ok:
                        raise RuntimeError(msg)
                    self._step(STEP_PORT, ST_OK, msg)

                # 2. SSH
                self._step(STEP_SSH, ST_RUNNING,
                           tr("s.ssh_connecting", user=ssh.username, host=ssh.host, port=ssh.port))
                self._tunnel = SshTunnel(ssh, rdp.host, rdp.port, self.secret, self._emit_log)
                self._tunnel.connect()
                if self._stop_evt.is_set():
                    raise RuntimeError(tr("s.cancelled"))
                self._tunnel.start_forward(local_port)
                self._step(STEP_SSH, ST_OK, tr("s.tunnel_ready", host=ssh.bind_host, port=self._tunnel.local_port))
                # mstsc 解析 localhost 优先走 ::1，而隧道只监听 IPv4，这里固定成 127.0.0.1
                address = "127.0.0.1" if ssh.bind_host.lower() == "localhost" else ssh.bind_host
                port = self._tunnel.local_port

                # 3. 通过隧道探测
                self._step(STEP_PROBE, ST_RUNNING, tr("s.probe_via", host=rdp.host, port=rdp.port))
                ms = self._tunnel.probe_target()
                self._step(STEP_PROBE, ST_OK, tr("s.reachable", host=rdp.host, port=rdp.port, ms=f"{ms:.0f}"))
            else:
                self._step(STEP_PORT, ST_SKIP, "")
                self._step(STEP_SSH, ST_SKIP, "")
                self._step(STEP_PROBE, ST_RUNNING, tr("s.probe_direct", host=rdp.host, port=rdp.port))
                ms = tcp_probe(rdp.host, rdp.port, timeout=10.0)
                logger.info("probe: {}:{} reachable directly in {:.0f} ms", rdp.host, rdp.port, ms)
                self._step(STEP_PROBE, ST_OK, tr("s.reachable", host=rdp.host, port=rdp.port, ms=f"{ms:.0f}"))

            if self.test_only:
                self._step(STEP_MSTSC, ST_SKIP, "")
                self._set_status(S_IDLE, tr("s.test_passed"))
                self._emit_log(tr("s.test_done"))
                return

            # 4. mstsc
            self._step(STEP_MSTSC, ST_RUNNING)
            self._proc, how = launch_mstsc(conn, address, port)
            fullscreen, w, h = rdp.resolve_size()
            size = tr("s.fullscreen") if fullscreen else f"{w}×{h}"
            self._step(STEP_MSTSC, ST_OK,
                       tr("s.mstsc_started", pid=self._proc.pid, addr=address, port=port, size=size))
            self._emit_log(tr("s.launch_args", args=how))
            if rdp.launch_mode == LAUNCH_FILE:
                self._emit_log(tr("s.file_mode_hint"))
            self._set_status(S_RUNNING, tr("s.running", addr=address, port=port))

            # 运行中：等待 mstsc 退出 / 隧道断开 / 用户停止
            t_run = time.perf_counter()
            while not self._stop_evt.is_set():
                if self._proc.poll() is not None:
                    logger.info("[{}] mstsc pid={} exited code={} after {:.0f}s", self._tag, self._proc.pid,
                                self._proc.returncode, time.perf_counter() - t_run)
                    self._emit_log(tr("s.mstsc_exited", code=self._proc.returncode))
                    break
                if self._tunnel and not self._tunnel.is_active():
                    logger.warning("[{}] ssh transport dropped after {:.0f}s", self._tag, time.perf_counter() - t_run)
                    self._emit_log(tr("s.ssh_dropped"))
                    self._set_status(S_ERROR, tr("s.ssh_dropped"))
                    break
                time.sleep(0.5)

            if self._tunnel and not ssh.close_with_mstsc and not self._stop_evt.is_set() and self._tunnel.is_active():
                logger.info("[{}] keeping tunnel open after mstsc exit (close_with_mstsc=False)", self._tag)
                self._emit_log(tr("s.keep_tunnel"))
                while not self._stop_evt.is_set() and self._tunnel.is_active():
                    time.sleep(0.5)

            if self.status != S_ERROR:
                self._set_status(S_IDLE, tr("s.disconnected"))

        except Exception as e:  # noqa: BLE001
            step = self._current_step
            msg = self._friendly_error(step, e)
            # 预期内的错误（网络/认证/端口占用/取消）只记一行；其它类型带完整堆栈
            expected = isinstance(e, (OSError, RuntimeError, paramiko.SSHException))
            logger.opt(exception=not expected).error("[{}] step {} failed: {!r}", self._tag, step, e)
            self._step(step, ST_FAIL, tr("s.failed", msg=msg))
            self._set_status(S_ERROR, msg)
        finally:
            if self._tunnel:
                self._tunnel.close()
                self._tunnel = None
                self._emit_log(tr("s.tunnel_closed"))
            logger.info("[{}] session end | status={} | total {:.1f}s", self._tag, self.status,
                        time.perf_counter() - t_start)
            self.finished_session.emit()

    @staticmethod
    def _friendly_error(step: str, e: Exception) -> str:
        text = str(e)
        if step == STEP_SSH:
            if isinstance(e, paramiko.PasswordRequiredException):
                return tr("e.key_passphrase")
            if isinstance(e, paramiko.AuthenticationException):
                return tr("e.auth")
            if isinstance(e, paramiko.BadHostKeyException):
                return tr("e.hostkey")
            if isinstance(e, TimeoutError) or "timed out" in text.lower():
                return tr("e.ssh_timeout")
            if isinstance(e, OSError) and not isinstance(e, paramiko.SSHException):
                return tr("e.ssh_connect", err=e.strerror or e)
        if step == STEP_PROBE:
            if isinstance(e, paramiko.ChannelException):
                return tr("e.probe_channel")
            if isinstance(e, TimeoutError) or "timed out" in text.lower():
                return tr("e.probe_timeout")
            if isinstance(e, OSError):
                return tr("e.probe_unreachable", err=e.strerror or e)
        return text or type(e).__name__
