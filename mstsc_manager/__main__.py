"""入口：python -m mstsc_manager

顺序固定：先初始化日志，再 import Qt 与业务模块，最后建 QApplication 和主窗口。
"""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    import platform

    from .log import logger, setup_logging

    log_file = setup_logging()

    import paramiko
    from PySide6 import __version__ as pyside_ver
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from . import APP_NAME, ORG, __version__
    from .i18n import i18n
    from .storage import config_path
    from .ui.icons import app_icon
    from .ui.main_window import MainWindow

    args = sys.argv[1:] if argv is None else argv
    logger.info("=" * 60)
    logger.info(
        "{} v{} starting | python {} | PySide6 {} | paramiko {} | {} | frozen={}",
        APP_NAME, __version__, platform.python_version(), pyside_ver, paramiko.__version__,
        platform.platform(), bool(getattr(sys, "frozen", False)),
    )
    logger.info("log file: {}", log_file)
    logger.debug("argv: {}", args)

    # Windows：不用 Python 默认 AppID，任务栏才会显示本程序图标而不是 python.exe
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{ORG}.{APP_NAME}")
        except Exception as e:  # noqa: BLE001
            logger.warning("SetCurrentProcessExplicitAppUserModelID failed: {}", e)

    app = QApplication(sys.argv)
    app.setOrganizationName(ORG)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    icon = app_icon()
    app.setWindowIcon(icon)

    i18n.load()                      # 读取上次选的语言（首次跟随系统），需在 QApplication 之后
    logger.info("config file: {}", config_path())

    win = MainWindow()
    win.setWindowIcon(icon)
    win.show()
    code = app.exec()
    logger.info("exit code={}", code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
