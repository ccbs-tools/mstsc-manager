"""应用图标：优先加载 assets/icon.ico（源码运行取项目根目录，打包后取 _MEIPASS），找不到就现画一个。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def assets_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "assets"
    return Path(__file__).resolve().parents[2] / "assets"


def draw_icon_pixmap(size: int) -> QPixmap:
    """蓝底显示器 + 绿色隧道弧线。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 64.0

    # 背景圆角方块
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#1e6fd9"))
    p.drawRoundedRect(QRectF(4 * s, 4 * s, 56 * s, 56 * s), 12 * s, 12 * s)

    # 显示器
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(14 * s, 16 * s, 36 * s, 24 * s), 3 * s, 3 * s)
    p.setBrush(QColor("#1e6fd9"))
    p.drawRect(QRectF(17 * s, 19 * s, 30 * s, 18 * s))
    p.setBrush(QColor("#ffffff"))
    p.drawRect(QRectF(29 * s, 40 * s, 6 * s, 5 * s))
    p.drawRoundedRect(QRectF(22 * s, 45 * s, 20 * s, 3 * s), 1.5 * s, 1.5 * s)

    # 隧道弧线
    pen = QPen(QColor("#3ddc84"), 4 * s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(20 * s, 22 * s, 24 * s, 24 * s), 20 * 16, 140 * 16)
    p.end()
    return pm


def app_icon() -> QIcon:
    ico = assets_dir() / "icon.ico"
    if ico.exists():
        return QIcon(str(ico))
    icon = QIcon()
    for sz in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(draw_icon_pixmap(sz))
    return icon
