import sys
import subprocess
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QFrame, QMainWindow)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPixmap, QPolygonF, QPainterPath
from PyQt6.QtCore import QPointF
import math


PURPLE = "#8b5cf6"
GREEN_ON = "#22c55e"
STAR_YELLOW = "#eab308"
STAR_GRAY = "#2e2e32"
BG_DARK = "#0c0c0e"
BG_CARD = "#141417"
BG_HOVER = "#1a1a1e"
TEXT_PRIMARY = "#e4e4e7"
TEXT_SECONDARY = "#71717a"
TEXT_DIM = "#52525b"
BORDER = "#222226"


class ToggleSwitch(QWidget):
    clicked = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 22)
        self._state = False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(GREEN_ON) if self._state else QColor("#2e2e32"))
        p.drawRoundedRect(0, 0, self.width(), self.height(), 11, 11)
        p.setBrush(QColor("#ffffff"))
        x = self.width() - 19 if self._state else 2
        p.drawEllipse(x, 2, 18, 18)

    def mousePressEvent(self, event):
        self._state = not self._state
        self.update()
        self.clicked.emit(self._state)

    def set_state(self, state):
        self._state = state
        self.update()


class StarDot(QWidget):
    """五角星收藏标记：选中时金黄色，未选中时深灰"""

    _STAR_POINTS = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._selected = True

    def _star_polygon(self, cx, cy, outer_r, inner_r):
        """生成五角星多边形顶点，10个点交替外径/内径，从上方开始"""
        pts = []
        # 十个顶点，从正上方(-90°)顺时针
        for i in range(10):
            r = outer_r if i % 2 == 0 else inner_r
            angle = math.radians(-90 + i * 36)
            pts.append(QPointF(cx + r * math.cos(angle), cy + r * math.sin(angle)))
        return QPolygonF(pts)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        color = QColor(STAR_YELLOW) if self._selected else QColor(STAR_GRAY)
        p.setBrush(color)
        poly = self._star_polygon(8, 8, 7.5, 3.5)
        path = QPainterPath()
        path.addPolygon(poly)
        p.drawPath(path)

    def mousePressEvent(self, event):
        self._selected = not self._selected
        self.update()

    def is_selected(self):
        return self._selected

    def set_selected(self, val):
        self._selected = val
        self.update()


class ACCControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("X-SPEED Racing · ACC 控制中心")
        self.setFixedSize(320, 440)
        self.setStyleSheet(f"background-color: {BG_DARK};")

        self.processes = {
            "radar": None, "overlay": None, "tyres": None,
            "timer": None, "delta": None
        }
        self.switches = {}
        self.select_dots = {}
        self.game_running = False

        self.init_ui()
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_game_status)
        self.check_timer.start(2000)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- header ----
        header = QFrame()
        header.setFixedHeight(90)
        header.setStyleSheet(f"background-color: {BG_DARK};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 14, 18, 14)

        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "config", "logo.jpg")
        logo_lbl = QLabel()
        if os.path.exists(logo_path):
            logo_lbl.setPixmap(QPixmap(logo_path).scaled(
                56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        logo_lbl.setFixedSize(56, 56)
        logo_lbl.setStyleSheet("border-radius: 28px;")
        hl.addWidget(logo_lbl)
        hl.addSpacing(12)

        brand_block = QVBoxLayout()
        brand_block.setSpacing(0)

        brand = QLabel("X-SPEED")
        brand.setStyleSheet(
            f"color: {PURPLE}; font-family: 'Arial Black'; font-size: 20px; "
            "font-weight: 900; letter-spacing: 2px;"
        )
        brand_block.addWidget(brand)

        sub = QLabel("RACING")
        sub.setStyleSheet(
            "color: #ffffff; font-family: 'Arial Black'; font-size: 11px; "
            "font-weight: 900; letter-spacing: 8px; padding-left: 1px;"
        )
        brand_block.addWidget(sub)

        acc = QLabel("ACC 控制中心")
        acc.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-family: 'Microsoft YaHei'; font-size: 10px; padding-left: 1px;"
        )
        brand_block.addWidget(acc)

        hl.addLayout(brand_block)
        hl.addStretch()
        layout.addWidget(header)

        # ---- divider ----
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {BORDER};")
        layout.addWidget(div)

        # ---- body ----
        body = QFrame()
        body.setStyleSheet(f"background-color: {BG_DARK};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(14, 14, 14, 8)
        bl.setSpacing(6)

        # master row
        master = QFrame()
        master.setStyleSheet(f"""
            QFrame {{
                background-color: {BG_CARD};
                border-radius: 6px;
                border: 1px solid {BORDER};
            }}
        """)
        master.setFixedHeight(38)
        ml = QHBoxLayout(master)
        ml.setContentsMargins(12, 0, 10, 0)

        master_lbl = QLabel("一键启动")
        master_lbl.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-family: 'Microsoft YaHei'; font-size: 13px;"
        )
        ml.addWidget(master_lbl)
        ml.addStretch()

        self.master_switch = ToggleSwitch()
        self.master_switch.clicked.connect(self.handle_master_toggle)
        ml.addWidget(self.master_switch)
        bl.addWidget(master)

        # section label
        bl.addSpacing(6)
        sec = QLabel("模块")
        sec.setStyleSheet(
            f"color: {TEXT_DIM}; font-family: 'Microsoft YaHei'; font-size: 10px; "
            "font-weight: bold; letter-spacing: 2px; padding-left: 2px;"
        )
        bl.addWidget(sec)

        modules = [
            ("相对雷达",     "radar"),
            ("遥测踏板",     "overlay"),
            ("轮胎面板",     "tyres"),
            ("圈速计时",     "timer"),
            ("实时秒差",     "delta"),
        ]

        for name, key in modules:
            card = QFrame()
            card.setFixedHeight(36)
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {BG_CARD};
                    border-radius: 5px;
                    border: 1px solid transparent;
                }}
                QFrame:hover {{
                    background-color: {BG_HOVER};
                    border: 1px solid #2a2a2f;
                }}
            """)
            rl = QHBoxLayout(card)
            rl.setContentsMargins(12, 0, 8, 0)

            lbl = QLabel(name)
            lbl.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-family: 'Microsoft YaHei'; font-size: 13px;"
            )
            rl.addWidget(lbl)
            rl.addStretch()

            dot = StarDot()
            self.select_dots[key] = dot

            switch = ToggleSwitch()
            switch.clicked.connect(lambda s, k=key: self.handle_toggle(s, k))
            self.switches[key] = switch

            rl.addWidget(dot)
            rl.addSpacing(8)
            rl.addWidget(switch)
            bl.addWidget(card)

        bl.addStretch()

        # status
        status = QFrame()
        status.setFixedHeight(28)
        sl = QHBoxLayout(status)
        sl.setContentsMargins(16, 0, 16, 0)

        self.status_dot = QLabel()
        self.status_dot.setFixedSize(6, 6)
        self.status_dot.setStyleSheet("background-color: #52525b; border-radius: 3px;")
        sl.addWidget(self.status_dot)
        sl.addSpacing(6)

        self.status_bar = QLabel("游戏未启动")
        self.status_bar.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-family: 'Microsoft YaHei'; font-size: 10px;"
        )
        sl.addWidget(self.status_bar)
        sl.addStretch()

        bl.addWidget(status)
        layout.addWidget(body)

    # ---- logic ----

    def check_game_status(self):
        try:
            output = subprocess.check_output(
                'tasklist', creationflags=subprocess.CREATE_NO_WINDOW
            ).decode('mbcs', 'ignore').lower()
            running = "ac2-win64-shipping.exe" in output or "acc.exe" in output
        except Exception:
            running = False

        if running != self.game_running:
            self.game_running = running
            if running:
                self.status_bar.setText("游戏运行中")
                self.status_bar.setStyleSheet(
                    "color: #4ade80; font-family: 'Microsoft YaHei'; font-size: 10px; font-weight: bold;"
                )
                self.status_dot.setStyleSheet("background-color: #4ade80; border-radius: 3px;")
            else:
                self.status_bar.setText("游戏未启动")
                self.status_bar.setStyleSheet(
                    f"color: {TEXT_SECONDARY}; font-family: 'Microsoft YaHei'; font-size: 10px;"
                )
                self.status_dot.setStyleSheet("background-color: #52525b; border-radius: 3px;")

    def handle_toggle(self, is_on, key):
        if is_on:
            self.start_module(key)
        else:
            self.stop_module(key)

    def handle_master_toggle(self, is_on):
        if is_on:
            for key, dot in self.select_dots.items():
                if dot.is_selected() and self.processes[key] is None:
                    self.start_module(key)
                    self.switches[key].set_state(True)
        else:
            for key in self.processes:
                if self.processes[key] is not None:
                    self.stop_module(key)
                    self.switches[key].set_state(False)

    def start_module(self, key):
        if getattr(sys, 'frozen', False):
            cmd = ["ACC_Overlay.exe", key]
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script = os.path.join(script_dir, "overlay.py")
            cmd = [sys.executable, script, key]
        try:
            self.processes[key] = subprocess.Popen(
                cmd, creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            print(f"启动错误: {e}")

    def stop_module(self, key):
        p = self.processes[key]
        if p:
            try:
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(p.pid)],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                p.terminate()
            self.processes[key] = None

    def closeEvent(self, event):
        for p in self.processes.values():
            if p:
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(p.pid)],
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except Exception:
                    p.terminate()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ACCControlPanel()
    window.show()
    sys.exit(app.exec())
