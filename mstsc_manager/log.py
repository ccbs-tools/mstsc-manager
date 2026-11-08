"""Logging (loguru).

File: %APPDATA%\\ccbs\\mstsc-manager\\logs\\app.log, rotated at 10 MB, 3 files kept (including current).
APP_DATA_DIR (%APPDATA%\\ccbs\\mstsc-manager) is also the home of connections.json / known_hosts (see storage.py).
Usage:
    from .log import logger
    logger.info("...")

Log messages are written in English regardless of the UI language.
Never log passwords, passphrases or decrypted secrets.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from loguru import logger

from . import APP_NAME

APP_DATA_DIR = Path(os.environ.get("APPDATA") or Path.home()) / "ccbs" / APP_NAME
LOG_DIR = APP_DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
ROTATION = "10 MB"
RETENTION = 3

_FILE_FMT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | "
    "{name}:{function}:{line} | {message}"
)
_CONSOLE_FMT = (
    "<green>{time:HH:mm:ss.SSS}</green> | <level>{level:<7}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>"
)

_configured = False


def setup_logging(console_level: str = "INFO") -> Path:
    """Initialise logging; repeated calls are no-ops. Returns the log file path."""
    global _configured
    if _configured:
        return LOG_FILE
    _configured = True

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.remove()
    # Under PyInstaller --windowed stderr is None: no console sink in that case
    if sys.stderr is not None:
        logger.add(sys.stderr, level=console_level, format=_CONSOLE_FMT, colorize=True)
    logger.add(
        LOG_FILE,
        level="DEBUG",
        format=_FILE_FMT,
        rotation=ROTATION,
        retention=RETENTION,
        encoding="utf-8",
        enqueue=True,       # safe from worker threads (SSH tunnel / session)
        backtrace=False,
        diagnose=False,     # never dump local variables (could contain secrets)
    )

    sys.excepthook = _excepthook
    _install_stdlib_bridge()
    _install_qt_handler()
    return LOG_FILE


def _excepthook(exc_type, exc, tb) -> None:
    logger.opt(exception=(exc_type, exc, tb)).critical("Unhandled exception")


class _InterceptHandler(logging.Handler):
    """Forward stdlib `logging` records (paramiko etc.) into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, "[{}] {}", record.name, record.getMessage())


def _install_stdlib_bridge() -> None:
    logging.basicConfig(handlers=[_InterceptHandler()], level=logging.INFO, force=True)
    # paramiko is chatty at DEBUG (every packet); INFO gives connect/auth/channel events
    logging.getLogger("paramiko").setLevel(logging.INFO)


def _install_qt_handler() -> None:
    """Route Qt's own qWarning / qCritical into the log."""
    try:
        from PySide6 import QtCore
    except Exception:  # noqa: BLE001
        return

    level_map = {
        QtCore.QtMsgType.QtDebugMsg: "DEBUG",
        QtCore.QtMsgType.QtInfoMsg: "INFO",
        QtCore.QtMsgType.QtWarningMsg: "WARNING",
        QtCore.QtMsgType.QtCriticalMsg: "ERROR",
        QtCore.QtMsgType.QtFatalMsg: "CRITICAL",
    }

    def handler(msg_type, _ctx, message) -> None:
        logger.log(level_map.get(msg_type, "INFO"), "[Qt] {}", message)

    QtCore.qInstallMessageHandler(handler)


__all__ = ["logger", "setup_logging", "APP_DATA_DIR", "LOG_DIR", "LOG_FILE"]
