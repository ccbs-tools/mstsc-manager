from __future__ import annotations

import json
import platform
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..changelog import REPO_HOME
from ..i18n import LANGUAGES, i18n, tr
from ..log import LOG_DIR, LOG_FILE, logger
from ..models import SSH_AUTH_KEY, SSH_AUTH_PASSWORD, Connection
from ..session import S_CONNECTING, S_IDLE, S_RUNNING, ST_IDLE, STEPS, SessionWorker
from ..storage import app_data_dir, config_path, load_connections, save_connections
from .connection_form import ConnectionForm
from .status_panel import STATUS_COLORS, StatusPanel, dot_pixmap
from .version_dialogs import ChangelogDialog, UpdateCheckDialog

ROLE_ID = Qt.ItemDataRole.UserRole


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1080, 720)

        self._conns: list[Connection] = load_connections()
        self._sessions: dict[str, SessionWorker] = {}
        # 每条连接的面板状态缓存，切换选中项时恢复
        self._status: dict[str, tuple[str, str]] = {}
        self._steps: dict[str, dict[str, tuple[str, str]]] = {}
        self._logs: dict[str, list[str]] = {}

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save)

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_body()
        self._refresh_list()
        if self._list.count():
            self._list.setCurrentRow(0)
        self._update_actions()

        i18n.languageChanged.connect(self.retranslate)
        self.retranslate()

    # ------------------------------------------------------------------ UI
    def _build_actions(self):
        self.act_new = QAction(self, shortcut=QKeySequence.StandardKey.New, triggered=self._new_conn)
        self.act_dup = QAction(self, shortcut="Ctrl+D", triggered=self._dup_conn)
        self.act_del = QAction(self, shortcut=QKeySequence.StandardKey.Delete, triggered=self._del_conn)
        self.act_import = QAction(self, triggered=self._import)
        self.act_export = QAction(self, triggered=self._export)
        self.act_open_dir = QAction(self, triggered=self._open_config_dir)
        self.act_quit = QAction(self, shortcut=QKeySequence.StandardKey.Quit, triggered=self.close)
        self.act_test_port = QAction(self, triggered=self._test_port)
        self.act_test = QAction(self, shortcut="F6", triggered=lambda: self._start(test_only=True))
        self.act_connect = QAction(self, shortcut="F5", triggered=lambda: self._start(test_only=False))
        self.act_disconnect = QAction(self, shortcut="F7", triggered=self._stop)
        self.act_open_log_dir = QAction(self, triggered=self._open_log_dir)
        self.act_repo = QAction(self, triggered=self._open_repo)
        self.act_changelog = QAction(self, triggered=self._show_changelog)
        self.act_check_update = QAction(self, triggered=self._show_update_check)
        self.act_about = QAction(self, triggered=self._about)

        self._lang_group = QActionGroup(self)
        self._lang_group.setExclusive(True)
        self._lang_actions: list[tuple[QAction, str]] = []
        for code, label in LANGUAGES:
            a = QAction(label, self, checkable=True)
            a.setChecked(code == i18n.lang)
            a.triggered.connect(lambda _=False, c=code: i18n.set(c))
            self._lang_group.addAction(a)
            self._lang_actions.append((a, code))

    def _build_menus(self):
        mb = self.menuBar()
        self.menu_file = mb.addMenu("")
        for a in (self.act_new, self.act_dup, self.act_del):
            self.menu_file.addAction(a)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_import)
        self.menu_file.addAction(self.act_export)
        self.menu_file.addAction(self.act_open_dir)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_quit)

        self.menu_lang = mb.addMenu("")
        for a, _ in self._lang_actions:
            self.menu_lang.addAction(a)

        self.menu_help = mb.addMenu("")
        self.menu_help.addAction(self.act_repo)
        self.menu_help.addAction(self.act_open_log_dir)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.act_changelog)
        self.menu_help.addAction(self.act_check_update)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.act_about)

    def _build_toolbar(self):
        tb = QToolBar(self)
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(tb)
        for a in (self.act_new, self.act_dup, self.act_del):
            tb.addAction(a)
        tb.addSeparator()
        for a in (self.act_test_port, self.act_test, self.act_connect, self.act_disconnect):
            tb.addAction(a)

    def _build_body(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # 左侧
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 0, 6)
        self._filter = QLineEdit()
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._refresh_list)
        self._list = QListWidget()
        self._list.setIconSize(QSize(12, 12))
        self._list.currentItemChanged.connect(self._on_select)
        self._list.itemDoubleClicked.connect(lambda _: self._start(test_only=False))
        ll.addWidget(self._filter)
        ll.addWidget(self._list, 1)
        splitter.addWidget(left)

        # 右侧
        right = QSplitter(Qt.Orientation.Vertical)
        self._form = ConnectionForm()
        self._form.changed.connect(self._on_form_changed)
        self._panel = StatusPanel()
        form_wrap = QWidget()
        fl = QVBoxLayout(form_wrap)
        fl.setContentsMargins(6, 6, 6, 0)
        fl.addWidget(self._form)
        panel_wrap = QWidget()
        pl = QVBoxLayout(panel_wrap)
        pl.setContentsMargins(6, 0, 6, 6)
        self._panel_title = QLabel()
        pl.addWidget(self._panel_title)
        pl.addWidget(self._panel)
        right.addWidget(form_wrap)
        right.addWidget(panel_wrap)
        right.setSizes([440, 260])
        splitter.addWidget(right)
        splitter.setSizes([260, 820])
        splitter.setStretchFactor(1, 1)

    # ------------------------------------------------------------------ 多语言
    def retranslate(self, *_):
        self.setWindowTitle(tr("app.title"))
        self.menu_file.setTitle(tr("menu.file"))
        self.menu_lang.setTitle(tr("menu.language"))
        self.menu_help.setTitle(tr("menu.help"))
        self.act_new.setText(tr("menu.new"))
        self.act_dup.setText(tr("menu.dup"))
        self.act_del.setText(tr("menu.del"))
        self.act_import.setText(tr("menu.import"))
        self.act_export.setText(tr("menu.export"))
        self.act_open_dir.setText(tr("menu.open_dir"))
        self.act_quit.setText(tr("menu.quit"))
        self.act_open_log_dir.setText(tr("menu.open_log_dir"))
        self.act_repo.setText(tr("menu.repo"))
        self.act_changelog.setText(tr("menu.changelog"))
        self.act_check_update.setText(tr("menu.check_update"))
        self.act_about.setText(tr("menu.about"))
        # 工具栏按钮用短文案
        self.act_new.setIconText(tr("tb.new"))
        self.act_dup.setIconText(tr("tb.dup"))
        self.act_del.setIconText(tr("tb.del"))
        self.act_test_port.setText(tr("tb.test_port"))
        self.act_test.setText(tr("tb.test"))
        self.act_connect.setText(tr("tb.connect"))
        self.act_disconnect.setText(tr("tb.disconnect"))
        for a, code in self._lang_actions:
            a.setChecked(code == i18n.lang)
        self._filter.setPlaceholderText(tr("list.filter"))
        self._panel_title.setText(tr("panel.title"))
        self.statusBar().showMessage(tr("status.config_file", path=config_path()))
        for i in range(self._list.count()):
            it = self._list.item(i)
            c = self._conn_by_id(it.data(ROLE_ID))
            if c:
                it.setToolTip(self._item_tooltip(c))

    # ------------------------------------------------------------------ 列表
    def _refresh_list(self):
        current_id = self._current_id()
        kw = self._filter.text().strip().lower()
        self._list.blockSignals(True)
        self._list.clear()
        for c in sorted(self._conns, key=lambda c: (c.group, c.name.lower())):
            hay = f"{c.name} {c.group} {c.rdp.host} {c.ssh.host}".lower()
            if kw and kw not in hay:
                continue
            item = QListWidgetItem(self._item_text(c))
            item.setData(ROLE_ID, c.id)
            item.setIcon(self._status_icon(c.id))
            item.setToolTip(self._item_tooltip(c))
            self._list.addItem(item)
            if c.id == current_id:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)
        if self._list.currentItem() is None and self._list.count():
            self._list.setCurrentRow(0)
        elif self._list.currentItem() is None:
            self._on_select(None, None)

    @staticmethod
    def _item_text(c: Connection) -> str:
        return f"[{c.group}] {c.name}" if c.group else c.name

    @staticmethod
    def _item_tooltip(c: Connection) -> str:
        s = f"{c.rdp.host}:{c.rdp.port}"
        if c.ssh.enabled:
            s += "\n" + tr("tooltip.via_ssh", user=c.ssh.username, host=c.ssh.host, port=c.ssh.port)
        if c.notes:
            s += f"\n{c.notes}"
        return s

    def _status_icon(self, conn_id: str) -> QIcon:
        status = self._status.get(conn_id, (S_IDLE, ""))[0]
        return QIcon(dot_pixmap(STATUS_COLORS.get(status, "#9e9e9e")))

    def _find_item(self, conn_id: str) -> QListWidgetItem | None:
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it.data(ROLE_ID) == conn_id:
                return it
        return None

    def _current_id(self) -> str | None:
        it = self._list.currentItem()
        return it.data(ROLE_ID) if it else None

    def _conn_by_id(self, cid: str | None) -> Connection | None:
        return next((c for c in self._conns if c.id == cid), None)

    def _current_conn(self) -> Connection | None:
        return self._conn_by_id(self._current_id())

    def _on_select(self, cur, _prev):
        conn = self._current_conn()
        self._form.load(conn)
        self._restore_panel(conn.id if conn else None)
        self._update_actions()

    def _restore_panel(self, conn_id: str | None):
        self._panel.reset()
        if not conn_id:
            self._panel.set_log_lines([])
            return
        for step, (state, msg) in self._steps.get(conn_id, {}).items():
            self._panel.set_step(step, state, msg)
        st, detail = self._status.get(conn_id, (S_IDLE, ""))
        self._panel.set_status(st, detail)
        self._panel.set_log_lines(self._logs.get(conn_id, []))

    # ------------------------------------------------------------------ 增删改
    def _select_conn(self, cid: str):
        it = self._find_item(cid)
        if it:
            self._list.setCurrentItem(it)

    def _new_conn(self):
        c = Connection(name=tr("conn.new_name"))
        logger.info("connection created id={}", c.id[:8])
        self._conns.append(c)
        self._save()
        self._filter.clear()
        self._refresh_list()
        self._select_conn(c.id)
        self._form.name.setFocus()
        self._form.name.selectAll()

    def _dup_conn(self):
        src = self._current_conn()
        if not src:
            return
        c = src.clone()
        c.name = src.name + tr("conn.copy_suffix")
        logger.info("connection duplicated {} -> {} ({!r})", src.id[:8], c.id[:8], c.name)
        self._conns.append(c)
        self._save()
        self._refresh_list()
        self._select_conn(c.id)

    def _del_conn(self):
        c = self._current_conn()
        if not c:
            return
        if c.id in self._sessions:
            QMessageBox.warning(self, tr("del.blocked_title"), tr("del.blocked_text"))
            return
        if QMessageBox.question(self, tr("del.title"), tr("del.text", name=c.name)) != QMessageBox.StandardButton.Yes:
            return
        logger.info("connection deleted {} ({!r}, {}:{})", c.id[:8], c.name, c.rdp.host, c.rdp.port)
        self._conns.remove(c)
        for d in (self._status, self._steps, self._logs):
            d.pop(c.id, None)
        self._save()
        self._refresh_list()

    def _on_form_changed(self):
        c = self._current_conn()
        if c:
            it = self._find_item(c.id)
            if it:
                it.setText(self._item_text(c))
                it.setToolTip(self._item_tooltip(c))
        self._save_timer.start()
        self._update_actions()

    def _save(self):
        try:
            save_connections(self._conns)
        except OSError as e:
            logger.error("save config failed: {!r}", e)
            self.statusBar().showMessage(tr("save.failed", err=e), 5000)

    # ------------------------------------------------------------------ 文件菜单
    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("import.title"), "", tr("json.filter"))
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            items = data["connections"] if isinstance(data, dict) else data
            incoming = [Connection.from_dict(d) for d in items]
        except (OSError, ValueError, KeyError, TypeError) as e:
            logger.error("import from {} failed: {!r}", path, e)
            QMessageBox.critical(self, tr("import.title"), tr("import.failed", err=e))
            return
        box = QMessageBox(self)
        box.setWindowTitle(tr("import.mode_title"))
        box.setText(tr("import.mode_text"))
        merge_btn = box.addButton(tr("import.merge"), QMessageBox.ButtonRole.AcceptRole)
        replace_btn = box.addButton(tr("import.replace"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is replace_btn:
            if self._sessions:
                QMessageBox.warning(self, tr("del.blocked_title"), tr("del.blocked_text"))
                return
            logger.info("import (replace) {} connection(s) from {}, dropping {} existing",
                        len(incoming), path, len(self._conns))
            self._conns = incoming
        elif clicked is merge_btn:
            by_id = {c.id: c for c in self._conns}
            for c in incoming:
                if c.id in self._sessions:
                    continue
                by_id[c.id] = c
            logger.info("import (merge) {} connection(s) from {}, total now {}", len(incoming), path, len(by_id))
            self._conns = list(by_id.values())
        else:
            logger.debug("import cancelled")
            return
        self._save()
        self._refresh_list()
        self.statusBar().showMessage(tr("import.done", n=len(incoming)), 5000)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("export.title"), "connections.json", tr("json.filter"))
        if not path:
            return
        try:
            payload = {"version": 1, "connections": [c.to_dict() for c in self._conns]}
            Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            logger.error("export to {} failed: {!r}", path, e)
            QMessageBox.critical(self, tr("export.title"), tr("export.failed", err=e))
            return
        logger.info("exported {} connection(s) to {}", len(self._conns), path)
        QMessageBox.information(self, tr("export.title"), tr("export.done", n=len(self._conns), path=path))

    def _open_config_dir(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data_dir())))

    def _open_log_dir(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR)))

    def _open_repo(self):
        ok = QDesktopServices.openUrl(QUrl(REPO_HOME))
        logger.info("open repository homepage {} -> {}", REPO_HOME, "ok" if ok else "failed")

    def _show_changelog(self):
        ChangelogDialog(self).exec()

    def _show_update_check(self):
        UpdateCheckDialog(self).exec()

    def _about(self):
        import paramiko
        from PySide6 import __version__ as qt_ver

        QMessageBox.about(
            self, tr("about.title"),
            tr("about.text", title=tr("app.title"), ver=__version__, config=config_path(), log=LOG_FILE,
               py=platform.python_version(), qt=qt_ver, pm=paramiko.__version__),
        )

    # ------------------------------------------------------------------ 动作
    def _update_actions(self):
        c = self._current_conn()
        running = bool(c and c.id in self._sessions)
        self.act_dup.setEnabled(c is not None)
        self.act_del.setEnabled(c is not None and not running)
        self.act_test_port.setEnabled(c is not None and c.ssh.enabled)
        self.act_test.setEnabled(c is not None and not running)
        self.act_connect.setEnabled(c is not None and not running)
        self.act_disconnect.setEnabled(running)

    def _test_port(self):
        c = self._current_conn()
        if not c:
            return
        self._form._tabs.setCurrentIndex(1)
        self._form.test_local_port()

    def _validate(self, c: Connection) -> str | None:
        if not c.rdp.host:
            return tr("validate.host")
        if c.ssh.enabled:
            if not c.ssh.host:
                return tr("validate.ssh_host")
            if not c.ssh.username:
                return tr("validate.ssh_user")
            if c.ssh.auth == SSH_AUTH_KEY and not c.ssh.key_path:
                return tr("validate.ssh_key")
        return None

    def _start(self, test_only: bool):
        c = self._current_conn()
        if not c or c.id in self._sessions:
            return
        err = self._validate(c)
        if err:
            logger.warning("start refused for {}: validation failed ({})", c.id[:8], err)
            QMessageBox.warning(self, tr("validate.title"), err)
            return

        secret = ""
        if c.ssh.enabled:
            secret = self._form.current_secret()
            if c.ssh.auth == SSH_AUTH_PASSWORD and not secret:
                secret, ok = QInputDialog.getText(
                    self, tr("ssh_pwd.title"), tr("ssh_pwd.text", user=c.ssh.username, host=c.ssh.host),
                    QLineEdit.EchoMode.Password,
                )
                if not ok:
                    logger.info("start cancelled at password prompt for {}", c.id[:8])
                    return
        logger.info("user action: {} {} ({!r})", "test" if test_only else "connect", c.id[:8], c.name)

        self._save_timer.stop()
        self._save()

        self._logs[c.id] = []
        self._steps[c.id] = {k: (ST_IDLE, "") for k in STEPS}
        self._status[c.id] = (S_CONNECTING, "")
        self._restore_panel(c.id)

        worker = SessionWorker(c, secret, test_only=test_only, parent=self)
        cid = c.id
        worker.step_changed.connect(lambda s, st, m, cid=cid: self._on_step(cid, s, st, m))
        worker.log.connect(lambda line, cid=cid: self._on_log(cid, line))
        worker.status_changed.connect(lambda st, d, cid=cid: self._on_status(cid, st, d))
        worker.finished_session.connect(lambda cid=cid: self._on_finished(cid))
        self._sessions[cid] = worker
        worker.start()
        self._update_actions()

    def _stop(self):
        c = self._current_conn()
        if not c:
            return
        w = self._sessions.get(c.id)
        if w:
            logger.info("user action: disconnect {} ({!r})", c.id[:8], c.name)
            self._on_log(c.id, tr("s.disconnecting"))
            w.request_stop()

    # ------------------------------------------------------------------ worker 回调
    def _on_step(self, cid: str, step: str, state: str, msg: str):
        self._steps.setdefault(cid, {})[step] = (state, msg)
        if cid == self._current_id():
            self._panel.set_step(step, state, msg)

    def _on_log(self, cid: str, line: str):
        buf = self._logs.setdefault(cid, [])
        buf.append(line)
        if len(buf) > 2000:
            del buf[: len(buf) - 2000]
        if cid == self._current_id():
            self._panel.append_log(line)

    def _on_status(self, cid: str, status: str, detail: str):
        self._status[cid] = (status, detail)
        it = self._find_item(cid)
        if it:
            it.setIcon(self._status_icon(cid))
        if cid == self._current_id():
            self._panel.set_status(status, detail)
        if status == S_RUNNING:
            self.statusBar().showMessage(f"{self._name_of(cid)}: {detail}", 5000)

    def _on_finished(self, cid: str):
        w = self._sessions.pop(cid, None)
        if w:
            w.wait(2000)
            w.deleteLater()
        st, _ = self._status.get(cid, (S_IDLE, ""))
        if st in (S_CONNECTING, S_RUNNING):
            self._on_status(cid, S_IDLE, tr("s.disconnected"))
        else:
            it = self._find_item(cid)
            if it:
                it.setIcon(self._status_icon(cid))
        self._update_actions()

    def _name_of(self, cid: str) -> str:
        c = self._conn_by_id(cid)
        return c.name if c else cid

    # ------------------------------------------------------------------ 关闭
    def closeEvent(self, event: QCloseEvent):
        if self._sessions:
            r = QMessageBox.question(self, tr("quit.title"), tr("quit.text", n=len(self._sessions)))
            if r != QMessageBox.StandardButton.Yes:
                logger.info("quit cancelled by user ({} session(s) running)", len(self._sessions))
                event.ignore()
                return
        logger.info("main window closing, {} session(s) to stop", len(self._sessions))
        self._save_timer.stop()
        self._save()
        for w in list(self._sessions.values()):
            w.request_stop()
        for w in list(self._sessions.values()):
            if not w.wait(3000):
                logger.warning("session thread did not finish within 3s")
        event.accept()
