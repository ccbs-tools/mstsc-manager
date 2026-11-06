from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import i18n, tr
from ..session import (
    S_CONNECTING,
    S_ERROR,
    S_IDLE,
    S_RUNNING,
    ST_FAIL,
    ST_IDLE,
    ST_OK,
    ST_RUNNING,
    ST_SKIP,
    STEPS,
)

STEP_COLORS = {
    ST_IDLE: "#b0b0b0",
    ST_RUNNING: "#f0a500",
    ST_OK: "#2eb85c",
    ST_FAIL: "#e04545",
    ST_SKIP: "#d0d0d0",
}
STATUS_COLORS = {
    S_IDLE: "#9e9e9e",
    S_CONNECTING: "#f0a500",
    S_RUNNING: "#2eb85c",
    S_ERROR: "#e04545",
}


def dot_pixmap(color: str, size: int = 12) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, size - 2, size - 2)
    p.end()
    return pm


class StatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cur_status = S_IDLE
        self._cur_steps: dict[str, str] = {k: ST_IDLE for k in STEPS}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # 总状态行
        top = QHBoxLayout()
        self._status_dot = QLabel()
        self._status_text = QLabel()
        f = self._status_text.font()
        f.setBold(True)
        self._status_text.setFont(f)
        self._status_detail = QLabel("")
        self._status_detail.setStyleSheet("color:#666;")
        top.addWidget(self._status_dot)
        top.addWidget(self._status_text)
        top.addSpacing(8)
        top.addWidget(self._status_detail, 1)
        self._clear_btn = QPushButton()
        self._clear_btn.setFlat(True)
        top.addWidget(self._clear_btn)
        root.addLayout(top)

        # 步骤表
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(box)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        self._rows: dict[str, tuple[QLabel, QLabel, QLabel, QLabel]] = {}
        for i, key in enumerate(STEPS):
            dot = QLabel()
            name = QLabel()
            name.setMinimumWidth(150)
            state = QLabel()
            state.setMinimumWidth(64)
            msg = QLabel()
            msg.setStyleSheet("color:#555;")
            msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(dot, i, 0)
            grid.addWidget(name, i, 1)
            grid.addWidget(state, i, 2)
            grid.addWidget(msg, i, 3)
            self._rows[key] = (dot, name, state, msg)
        grid.setColumnStretch(3, 1)
        root.addWidget(box)

        # 日志
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        self._log.setStyleSheet("font-family: Consolas, 'Microsoft YaHei UI'; font-size: 9pt;")
        root.addWidget(self._log, 1)

        self._clear_btn.clicked.connect(self._log.clear)
        i18n.languageChanged.connect(self.retranslate)
        self.reset()
        self.retranslate()

    def retranslate(self, *_):
        self._clear_btn.setText(tr("panel.clear_log"))
        for i, key in enumerate(STEPS):
            _, name, state, _ = self._rows[key]
            name.setText(f"{i + 1}. {tr('step.' + key)}")
            state.setText(tr("st." + self._cur_steps[key]))
        self._status_text.setText(tr("status." + self._cur_status))

    def reset(self) -> None:
        for key in STEPS:
            self.set_step(key, ST_IDLE, "")
        self.set_status(S_IDLE, "")

    def set_step(self, step: str, state: str, msg: str) -> None:
        if step not in self._rows:
            return
        self._cur_steps[step] = state
        dot, _, st, m = self._rows[step]
        dot.setPixmap(dot_pixmap(STEP_COLORS.get(state, "#b0b0b0")))
        st.setText(tr("st." + state))
        st.setStyleSheet(f"color:{STEP_COLORS.get(state, '#888')};")
        if msg or state in (ST_IDLE, ST_SKIP):
            m.setText(msg)

    def set_status(self, status: str, detail: str) -> None:
        self._cur_status = status
        self._status_dot.setPixmap(dot_pixmap(STATUS_COLORS.get(status, "#9e9e9e"), 14))
        self._status_text.setText(tr("status." + status))
        self._status_detail.setText(detail)

    def append_log(self, line: str) -> None:
        self._log.appendPlainText(line)

    def set_log_lines(self, lines: list[str]) -> None:
        self._log.setPlainText("\n".join(lines))
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())
