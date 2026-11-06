"""基于 paramiko 的 SSH 本地端口转发（等价于 ssh -N -L bind:port:target:3389 user@jump）。"""

from __future__ import annotations

import select
import socketserver
import threading
import time
from typing import Callable

import paramiko

from .i18n import tr
from .log import logger
from .models import SSH_AUTH_KEY, SshConfig
from .storage import known_hosts_path

LogFn = Callable[[str], None]


class _ForwardHandler(socketserver.BaseRequestHandler):
    server: "_ForwardServer"

    def handle(self) -> None:
        srv = self.server
        peer = self.request.getpeername()
        logger.debug("forward: accepted {} -> {}:{}", peer, srv.target_host, srv.target_port)
        try:
            chan = srv.transport.open_channel(
                "direct-tcpip", (srv.target_host, srv.target_port), peer, timeout=srv.timeout,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("forward: open_channel to {}:{} failed: {!r}", srv.target_host, srv.target_port, e)
            srv.log(tr("t.channel_failed", err=e))
            return
        if chan is None:
            logger.warning("forward: open_channel to {}:{} rejected by server", srv.target_host, srv.target_port)
            srv.log(tr("t.rejected"))
            return
        sent = recv = 0
        t0 = time.perf_counter()
        try:
            while True:
                r, _, _ = select.select([self.request, chan], [], [], 1.0)
                if self.request in r:
                    data = self.request.recv(32768)
                    if not data:
                        break
                    chan.sendall(data)
                    sent += len(data)
                if chan in r:
                    data = chan.recv(32768)
                    if not data:
                        break
                    self.request.sendall(data)
                    recv += len(data)
        except Exception as e:  # noqa: BLE001
            logger.debug("forward: relay ended with {!r}", e)
        finally:
            try:
                chan.close()
            finally:
                self.request.close()
            logger.debug("forward: closed {} after {:.1f}s, sent {} B, received {} B",
                         peer, time.perf_counter() - t0, sent, recv)


class _ForwardServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, addr, transport: paramiko.Transport, target_host: str, target_port: int,
                 timeout: float, log: LogFn):
        self.transport = transport
        self.target_host = target_host
        self.target_port = target_port
        self.timeout = timeout
        self.log = log
        super().__init__(addr, _ForwardHandler)


class SshTunnel:
    def __init__(self, cfg: SshConfig, target_host: str, target_port: int, secret: str, log: LogFn):
        self.cfg = cfg
        self.target_host = target_host
        self.target_port = target_port
        self.secret = secret
        self.log = log
        self._client: paramiko.SSHClient | None = None
        self._server: _ForwardServer | None = None
        self._thread: threading.Thread | None = None
        self.local_port: int = 0
        self.timeout: float = max(5, cfg.connect_timeout)

    # ---- 连接跳板机 ----
    def connect(self) -> None:
        client = paramiko.SSHClient()
        kh = known_hosts_path()
        client.load_host_keys(str(kh))
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        to = self.timeout
        kwargs: dict = dict(
            hostname=self.cfg.host,
            port=self.cfg.port,
            username=self.cfg.username,
            timeout=to,
            banner_timeout=to,
            auth_timeout=to,
            allow_agent=False,
            look_for_keys=False,
        )
        if self.cfg.auth == SSH_AUTH_KEY:
            kwargs["key_filename"] = self.cfg.key_path
            kwargs["passphrase"] = self.secret or None
        else:
            kwargs["password"] = self.secret

        logger.info("ssh: connecting {}@{}:{} auth={} key={!r} timeout={}s keepalive={}s",
                    self.cfg.username, self.cfg.host, self.cfg.port, self.cfg.auth,
                    self.cfg.key_path if self.cfg.auth == SSH_AUTH_KEY else None, to, self.cfg.keepalive)
        t0 = time.perf_counter()
        try:
            client.connect(**kwargs)
        except Exception as e:
            logger.error("ssh: connect to {}:{} failed after {:.0f} ms: {!r}",
                         self.cfg.host, self.cfg.port, (time.perf_counter() - t0) * 1000, e)
            raise
        client.save_host_keys(str(kh))
        transport = client.get_transport()
        if transport is None:
            raise RuntimeError("SSH transport not established")
        if self.cfg.keepalive > 0:
            transport.set_keepalive(self.cfg.keepalive)
        self._client = client
        ms = (time.perf_counter() - t0) * 1000
        logger.info("ssh: connected to {}:{} in {:.0f} ms, server version {!r}, hostkey {} {}",
                    self.cfg.host, self.cfg.port, ms, transport.remote_version,
                    transport.get_remote_server_key().get_name(), transport.get_remote_server_key().fingerprint)
        self.log(tr("t.logged_in", user=self.cfg.username, host=self.cfg.host, port=self.cfg.port, ms=f"{ms:.0f}"))

    # ---- 本地监听 ----
    def start_forward(self, local_port: int) -> int:
        if not self._client:
            raise RuntimeError("SSH not connected")
        transport = self._client.get_transport()
        try:
            self._server = _ForwardServer(
                (self.cfg.bind_host, local_port), transport, self.target_host, self.target_port,
                self.timeout, self.log,
            )
        except OSError as e:
            logger.error("forward: cannot bind {}:{}: {!r}", self.cfg.bind_host, local_port, e)
            raise
        self.local_port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, name="ssh-forward", daemon=True)
        self._thread.start()
        logger.info("forward: listening {}:{} -> {}:{}", self.cfg.bind_host, self.local_port,
                    self.target_host, self.target_port)
        self.log(tr("t.established", bind=self.cfg.bind_host, lport=self.local_port,
                    host=self.target_host, port=self.target_port))
        return self.local_port

    # ---- 通过隧道探测目标端口 ----
    def probe_target(self) -> float:
        if not self._client:
            raise RuntimeError("SSH not connected")
        transport = self._client.get_transport()
        t0 = time.perf_counter()
        try:
            chan = transport.open_channel(
                "direct-tcpip", (self.target_host, self.target_port), ("127.0.0.1", 0), timeout=self.timeout
            )
        except Exception as e:
            logger.error("probe: {}:{} via jump host failed after {:.0f} ms: {!r}",
                         self.target_host, self.target_port, (time.perf_counter() - t0) * 1000, e)
            raise
        if chan is None:
            raise RuntimeError("jump host could not open a channel to the target")
        chan.close()
        ms = (time.perf_counter() - t0) * 1000
        logger.info("probe: {}:{} reachable via jump host in {:.0f} ms", self.target_host, self.target_port, ms)
        return ms

    def is_active(self) -> bool:
        if not self._client:
            return False
        t = self._client.get_transport()
        return bool(t and t.is_active())

    def close(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception as e:  # noqa: BLE001
                logger.debug("forward: shutdown error {!r}", e)
            self._server = None
            logger.info("forward: listener {}:{} closed", self.cfg.bind_host, self.local_port)
        if self._client:
            try:
                self._client.close()
            except Exception as e:  # noqa: BLE001
                logger.debug("ssh: close error {!r}", e)
            self._client = None
            logger.info("ssh: disconnected from {}:{}", self.cfg.host, self.cfg.port)
