import ctypes
import platform
import sys


def main() -> int:
    from mstsc_manager.log import logger, setup_logging

    log_file = setup_logging()

    from PySide6 import __version__ as pyside_ver
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    import paramiko
    from mstsc_manager import APP_NAME, __version__
    from mstsc_manager.i18n import i18n
    from mstsc_manager.storage import config_path
    from mstsc_manager.ui.icons import app_icon
    from mstsc_manager.ui.main_window import MainWindow

    logger.info("=" * 60)
    logger.info(
        "{} v{} starting | python {} | PySide6 {} | paramiko {} | {} | frozen={}",
        APP_NAME, __version__, platform.python_version(), pyside_ver, paramiko.__version__,
        platform.platform(), bool(getattr(sys, "frozen", False)),
    )
    logger.info("log file: {}", log_file)
    logger.debug("argv: {}", sys.argv[1:])

    # Windows: own AppUserModelID so the taskbar shows this app's icon instead of python.exe's
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"ccbs.{APP_NAME}.{__version__}")
        except Exception as e:  # noqa: BLE001
            logger.warning("SetCurrentProcessExplicitAppUserModelID failed: {}", e)

    app = QApplication(sys.argv)
    app.setOrganizationName("ccbs")
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))
    icon = app_icon()
    app.setWindowIcon(icon)

    i18n.load()
    logger.info("config file: {}", config_path())

    win = MainWindow()
    win.setWindowIcon(icon)
    win.show()
    code = app.exec()
    logger.info("exit code={}", code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
