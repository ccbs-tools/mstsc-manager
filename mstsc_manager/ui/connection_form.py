from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import dpapi
from ..i18n import i18n, tr
from ..models import (
    LAUNCH_CLI,
    LAUNCH_FILE,
    RES_CUSTOM,
    RES_FULLSCREEN,
    RESOLUTION_PRESETS,
    SSH_AUTH_KEY,
    SSH_AUTH_PASSWORD,
    Connection,
)
from ..netutil import check_local_port, find_free_port


class ConnectionForm(QWidget):
    """连接配置表单。所有修改直接写回当前 Connection 对象并发出 changed 信号。"""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._conn: Connection | None = None
        self._loading = False
        # (QLabel, i18n key) —— 表单左侧标签，切换语言时统一刷新
        self._labels: list[tuple[QLabel, str]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)
        self._tabs.addTab(self._build_rdp_tab(), "")
        self._tabs.addTab(self._build_ssh_tab(), "")
        self.setEnabled(False)
        i18n.languageChanged.connect(self.retranslate)
        self.retranslate()

    # ------------------------------------------------------------------ 工具
    def _row(self, form: QFormLayout, key: str, field) -> QLabel:
        label = QLabel()
        self._labels.append((label, key))
        form.addRow(label, field)
        return label

    # ------------------------------------------------------------------ 构建
    def _build_rdp_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.name = QLineEdit()
        self.group = QLineEdit()
        self.notes = QLineEdit()
        self._row(form, "f.name", self.name)
        self._row(form, "f.group", self.group)
        self._row(form, "f.notes", self.notes)

        host_row = QHBoxLayout()
        self.rdp_host = QLineEdit()
        self.rdp_port = QSpinBox()
        self.rdp_port.setRange(1, 65535)
        self.rdp_port.setValue(3389)
        self.rdp_port_label = QLabel()
        host_row.addWidget(self.rdp_host, 1)
        host_row.addWidget(self.rdp_port_label)
        host_row.addWidget(self.rdp_port)
        self._row(form, "f.target", host_row)

        cred_row = QHBoxLayout()
        self.rdp_user = QLineEdit()
        self.rdp_domain = QLineEdit()
        self.rdp_domain.setMaximumWidth(140)
        self.rdp_domain_label = QLabel()
        cred_row.addWidget(self.rdp_user, 1)
        cred_row.addWidget(self.rdp_domain_label)
        cred_row.addWidget(self.rdp_domain)
        self._row(form, "f.user", cred_row)

        res_row = QHBoxLayout()
        self.resolution = QComboBox()
        for label, w_, h_ in RESOLUTION_PRESETS:
            self.resolution.addItem(label, f"{w_}x{h_}")
        self.resolution.addItem("", RES_FULLSCREEN)
        self.resolution.addItem("", RES_CUSTOM)
        self.custom_w = QSpinBox()
        self.custom_w.setRange(640, 7680)
        self.custom_h = QSpinBox()
        self.custom_h.setRange(480, 4320)
        self.custom_x = QLabel("×")
        res_row.addWidget(self.resolution, 1)
        res_row.addWidget(self.custom_w)
        res_row.addWidget(self.custom_x)
        res_row.addWidget(self.custom_h)
        self._row(form, "f.resolution", res_row)

        self.multimon = QCheckBox()
        form.addRow("", self.multimon)

        self.launch_mode = QComboBox()
        self.launch_mode.addItem("", LAUNCH_CLI)
        self.launch_mode.addItem("", LAUNCH_FILE)
        # 条目文字在 retranslate() 里才填入，默认 sizeHint 会按空文本计算而被截断；
        # 表单只拉伸 Expanding 字段，所以这里显式占满整行并按内容调整宽度
        self.launch_mode.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.launch_mode.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._row(form, "f.launch_mode", self.launch_mode)

        self.file_only_hint = QLabel()
        self.file_only_hint.setStyleSheet("color:#888;")
        self.file_only_hint.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form.addRow("", self.file_only_hint)
        self.redirect_clipboard = QCheckBox()
        self.redirect_drives = QCheckBox()
        self.smart_sizing = QCheckBox()
        self.ignore_cert = QCheckBox()
        self._file_only = (self.redirect_clipboard, self.redirect_drives, self.smart_sizing, self.ignore_cert)
        for cb in self._file_only:
            form.addRow("", cb)

        # 信号
        for le in (self.name, self.group, self.notes, self.rdp_host, self.rdp_user, self.rdp_domain):
            le.textChanged.connect(self._on_change)
        for sb in (self.rdp_port, self.custom_w, self.custom_h):
            sb.valueChanged.connect(self._on_change)
        self.resolution.currentIndexChanged.connect(self._on_resolution_changed)
        self.launch_mode.currentIndexChanged.connect(self._on_launch_mode_changed)
        for cb in (self.multimon, *self._file_only):
            cb.toggled.connect(self._on_change)
        self._update_resolution_widgets()
        self._update_launch_widgets()
        return w

    def _build_ssh_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        self.ssh_enabled = QGroupBox()
        self.ssh_enabled.setCheckable(True)
        self.ssh_enabled.setChecked(False)
        outer.addWidget(self.ssh_enabled)
        outer.addStretch(1)
        form = QFormLayout(self.ssh_enabled)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        host_row = QHBoxLayout()
        self.ssh_host = QLineEdit()
        self.ssh_port = QSpinBox()
        self.ssh_port.setRange(1, 65535)
        self.ssh_port.setValue(22)
        self.ssh_port_label = QLabel()
        host_row.addWidget(self.ssh_host, 1)
        host_row.addWidget(self.ssh_port_label)
        host_row.addWidget(self.ssh_port)
        self._row(form, "f.jump", host_row)

        self.ssh_user = QLineEdit()
        self._row(form, "f.user", self.ssh_user)

        self.ssh_auth = QComboBox()
        self.ssh_auth.addItem("", SSH_AUTH_PASSWORD)
        self.ssh_auth.addItem("", SSH_AUTH_KEY)
        self._row(form, "f.auth", self.ssh_auth)

        key_row = QHBoxLayout()
        self.ssh_key = QLineEdit()
        self.ssh_key_browse = QPushButton()
        key_row.addWidget(self.ssh_key, 1)
        key_row.addWidget(self.ssh_key_browse)
        self.ssh_key_label = self._row(form, "f.key_label", key_row)

        sec_row = QHBoxLayout()
        self.ssh_secret = QLineEdit()
        self.ssh_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.ssh_save_secret = QCheckBox()
        sec_row.addWidget(self.ssh_secret, 1)
        sec_row.addWidget(self.ssh_save_secret)
        self.ssh_secret_label = QLabel()
        form.addRow(self.ssh_secret_label, sec_row)

        port_row = QHBoxLayout()
        self.ssh_bind = QLineEdit()
        self.ssh_bind.setMaximumWidth(110)
        self.ssh_local_port = QSpinBox()
        self.ssh_local_port.setRange(0, 65535)
        self.ssh_port_test = QPushButton()
        self.ssh_port_pick = QPushButton()
        self.ssh_port_result = QLabel("")
        port_row.addWidget(self.ssh_bind)
        port_row.addWidget(QLabel(":"))
        port_row.addWidget(self.ssh_local_port)
        port_row.addWidget(self.ssh_port_test)
        port_row.addWidget(self.ssh_port_pick)
        port_row.addWidget(self.ssh_port_result, 1)
        self._row(form, "f.local_listen", port_row)

        self.ssh_timeout = QSpinBox()
        self.ssh_timeout.setRange(5, 300)
        self._row(form, "f.timeout", self.ssh_timeout)

        self.ssh_keepalive = QSpinBox()
        self.ssh_keepalive.setRange(0, 600)
        self._row(form, "f.keepalive", self.ssh_keepalive)

        self.ssh_close_with_mstsc = QCheckBox()
        form.addRow("", self.ssh_close_with_mstsc)

        # 信号
        self.ssh_enabled.toggled.connect(self._on_change)
        for le in (self.ssh_host, self.ssh_user, self.ssh_key, self.ssh_secret, self.ssh_bind):
            le.textChanged.connect(self._on_change)
        for sb in (self.ssh_port, self.ssh_local_port, self.ssh_keepalive, self.ssh_timeout):
            sb.valueChanged.connect(self._on_change)
        self.ssh_auth.currentIndexChanged.connect(self._on_auth_changed)
        self.ssh_save_secret.toggled.connect(self._on_change)
        self.ssh_close_with_mstsc.toggled.connect(self._on_change)
        self.ssh_key_browse.clicked.connect(self._browse_key)
        self.ssh_port_test.clicked.connect(self.test_local_port)
        self.ssh_port_pick.clicked.connect(self._pick_free_port)
        self.ssh_local_port.valueChanged.connect(lambda _: self.ssh_port_result.setText(""))
        self._update_auth_widgets()
        return w

    # ------------------------------------------------------------------ 多语言
    def retranslate(self, *_):
        self._tabs.setTabText(0, tr("tab.rdp"))
        self._tabs.setTabText(1, tr("tab.ssh"))
        for label, key in self._labels:
            label.setText(tr(key))
        # 远程桌面
        self.group.setPlaceholderText(tr("f.group_ph"))
        self.rdp_host.setPlaceholderText(tr("f.target_ph"))
        self.rdp_port_label.setText(tr("f.port"))
        self.rdp_domain_label.setText(tr("f.domain"))
        self.rdp_domain.setPlaceholderText(tr("f.optional"))
        self.resolution.setItemText(self.resolution.findData(RES_FULLSCREEN), tr("f.res_fullscreen"))
        self.resolution.setItemText(self.resolution.findData(RES_CUSTOM), tr("f.res_custom"))
        self.multimon.setText(tr("f.multimon"))
        self.launch_mode.setItemText(0, tr("f.launch_cli"))
        self.launch_mode.setItemText(1, tr("f.launch_file"))
        self.file_only_hint.setText(tr("f.file_only_hint"))
        self.file_only_hint.setToolTip(tr("f.file_only_tip"))
        self.redirect_clipboard.setText(tr("f.clipboard"))
        self.redirect_drives.setText(tr("f.drives"))
        self.smart_sizing.setText(tr("f.smart_sizing"))
        self.ignore_cert.setText(tr("f.ignore_cert"))
        # SSH
        self.ssh_enabled.setTitle(tr("f.ssh_group"))
        self.ssh_host.setPlaceholderText(tr("f.jump_ph"))
        self.ssh_port_label.setText(tr("f.port"))
        self.ssh_auth.setItemText(0, tr("f.auth_password"))
        self.ssh_auth.setItemText(1, tr("f.auth_key"))
        self.ssh_key.setPlaceholderText(tr("f.key_ph"))
        self.ssh_key_browse.setText(tr("f.browse"))
        self.ssh_save_secret.setText(tr("f.save_secret"))
        self.ssh_local_port.setSpecialValueText(tr("f.auto"))
        self.ssh_port_test.setText(tr("f.test_port"))
        self.ssh_port_pick.setText(tr("f.pick_port"))
        self.ssh_timeout.setSuffix(tr("f.seconds"))
        self.ssh_timeout.setToolTip(tr("f.timeout_tip"))
        self.ssh_keepalive.setSuffix(tr("f.keepalive_suffix"))
        self.ssh_close_with_mstsc.setText(tr("f.close_with_mstsc"))
        self.ssh_port_result.setText("")
        self._update_auth_widgets()

    # ------------------------------------------------------------------ 加载 / 写回
    def load(self, conn: Connection | None) -> None:
        self._conn = conn
        self.setEnabled(conn is not None)
        if conn is None:
            return
        self._loading = True
        try:
            r, s = conn.rdp, conn.ssh
            self.name.setText(conn.name)
            self.group.setText(conn.group)
            self.notes.setText(conn.notes)
            self.rdp_host.setText(r.host)
            self.rdp_port.setValue(r.port)
            self.rdp_user.setText(r.username)
            self.rdp_domain.setText(r.domain)
            idx = self.resolution.findData(r.resolution)
            self.resolution.setCurrentIndex(idx if idx >= 0 else 3)
            self.custom_w.setValue(r.custom_width)
            self.custom_h.setValue(r.custom_height)
            self.multimon.setChecked(r.multimon)
            idx = self.launch_mode.findData(r.launch_mode)
            self.launch_mode.setCurrentIndex(max(idx, 0))
            self.redirect_clipboard.setChecked(r.redirect_clipboard)
            self.redirect_drives.setChecked(r.redirect_drives)
            self.smart_sizing.setChecked(r.smart_sizing)
            self.ignore_cert.setChecked(r.ignore_cert)

            self.ssh_enabled.setChecked(s.enabled)
            self.ssh_host.setText(s.host)
            self.ssh_port.setValue(s.port)
            self.ssh_user.setText(s.username)
            idx = self.ssh_auth.findData(s.auth)
            self.ssh_auth.setCurrentIndex(max(idx, 0))
            self.ssh_key.setText(s.key_path)
            self.ssh_save_secret.setChecked(s.save_secret)
            secret = ""
            if s.secret_enc:
                try:
                    secret = dpapi.unprotect(s.secret_enc)
                except OSError:
                    secret = ""
            self.ssh_secret.setText(secret)
            self.ssh_bind.setText(s.bind_host or "127.0.0.1")
            self.ssh_local_port.setValue(s.local_port)
            self.ssh_keepalive.setValue(s.keepalive)
            self.ssh_timeout.setValue(s.connect_timeout)
            self.ssh_close_with_mstsc.setChecked(s.close_with_mstsc)
            self.ssh_port_result.setText("")
            self._update_resolution_widgets()
            self._update_launch_widgets()
            self._update_auth_widgets()
        finally:
            self._loading = False

    def _write_back(self) -> None:
        c = self._conn
        if c is None:
            return
        r, s = c.rdp, c.ssh
        c.name = self.name.text().strip() or tr("conn.unnamed")
        c.group = self.group.text().strip()
        c.notes = self.notes.text()
        r.host = self.rdp_host.text().strip()
        r.port = self.rdp_port.value()
        r.username = self.rdp_user.text().strip()
        r.domain = self.rdp_domain.text().strip()
        r.resolution = self.resolution.currentData()
        r.custom_width = self.custom_w.value()
        r.custom_height = self.custom_h.value()
        r.multimon = self.multimon.isChecked()
        r.launch_mode = self.launch_mode.currentData()
        r.redirect_clipboard = self.redirect_clipboard.isChecked()
        r.redirect_drives = self.redirect_drives.isChecked()
        r.smart_sizing = self.smart_sizing.isChecked()
        r.ignore_cert = self.ignore_cert.isChecked()

        s.enabled = self.ssh_enabled.isChecked()
        s.host = self.ssh_host.text().strip()
        s.port = self.ssh_port.value()
        s.username = self.ssh_user.text().strip()
        s.auth = self.ssh_auth.currentData()
        s.key_path = self.ssh_key.text().strip()
        s.save_secret = self.ssh_save_secret.isChecked()
        s.secret_enc = dpapi.protect(self.ssh_secret.text()) if s.save_secret else ""
        s.bind_host = self.ssh_bind.text().strip() or "127.0.0.1"
        s.local_port = self.ssh_local_port.value()
        s.keepalive = self.ssh_keepalive.value()
        s.connect_timeout = self.ssh_timeout.value()
        s.close_with_mstsc = self.ssh_close_with_mstsc.isChecked()

    def current_secret(self) -> str:
        """当前输入框里的密码/口令（无论是否勾选保存）。"""
        return self.ssh_secret.text()

    # ------------------------------------------------------------------ 槽
    def _on_change(self, *_):
        if self._loading or self._conn is None:
            return
        self._write_back()
        self.changed.emit()

    def _on_resolution_changed(self, *_):
        self._update_resolution_widgets()
        self._on_change()

    def _on_auth_changed(self, *_):
        self._update_auth_widgets()
        self._on_change()

    def _on_launch_mode_changed(self, *_):
        self._update_launch_widgets()
        self._on_change()

    def _update_launch_widgets(self):
        file_mode = self.launch_mode.currentData() == LAUNCH_FILE
        for cb in self._file_only:
            cb.setEnabled(file_mode)
        self.file_only_hint.setVisible(not file_mode)

    def _update_resolution_widgets(self):
        custom = self.resolution.currentData() == RES_CUSTOM
        for w in (self.custom_w, self.custom_h, self.custom_x):
            w.setVisible(custom)
        self.multimon.setEnabled(self.resolution.currentData() == RES_FULLSCREEN)

    def _update_auth_widgets(self):
        is_key = self.ssh_auth.currentData() == SSH_AUTH_KEY
        self.ssh_key.setVisible(is_key)
        self.ssh_key_browse.setVisible(is_key)
        self.ssh_key_label.setVisible(is_key)
        self.ssh_secret_label.setText(tr("f.secret_passphrase") if is_key else tr("f.secret_password"))
        self.ssh_secret.setPlaceholderText(tr("f.secret_ph_key") if is_key else tr("f.secret_ph_password"))

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("f.key_dialog"), "", tr("f.all_files"))
        if path:
            self.ssh_key.setText(path)

    def test_local_port(self):
        host = self.ssh_bind.text().strip() or "127.0.0.1"
        port = self.ssh_local_port.value()
        if port == 0:
            p = find_free_port(host)
            self.ssh_port_result.setText(tr("f.port_auto_result", host=host, port=p))
            self.ssh_port_result.setStyleSheet("color:#2eb85c;")
            return
        ok, msg = check_local_port(host, port)
        self.ssh_port_result.setText(msg)
        self.ssh_port_result.setStyleSheet("color:#2eb85c;" if ok else "color:#e04545;")

    def _pick_free_port(self):
        host = self.ssh_bind.text().strip() or "127.0.0.1"
        p = find_free_port(host)
        self.ssh_local_port.setValue(p)
        self.ssh_port_result.setText(tr("port.free", host=host, port=p))
        self.ssh_port_result.setStyleSheet("color:#2eb85c;")
