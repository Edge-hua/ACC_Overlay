import sys
import subprocess
import os
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QFrame, QMainWindow)
from PyQt6.QtCore import Qt, QTimer, QSize, QPropertyAnimation, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont


class ToggleSwitch(QWidget):
    clicked = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(55, 28)
        self._state = False
        self._offset = 3
        self.color_off = QColor("#44444a")
        self.color_on = QColor("#32cd32")
        self.color_handle = QColor("#ffffff")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.color_on if self._state else self.color_off)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 14, 14)

        p.setBrush(self.color_handle)
        x_pos = self.width() - 25 if self._state else 3
        p.drawEllipse(x_pos, 3, 22, 22)

    def mousePressEvent(self, event):
        self._state = not self._state
        self.update()
        self.clicked.emit(self._state)

    def set_state(self, state):
        self._state = state
        self.update()


class SelectDot(QWidget):
    """模块选择标记：绿色圆点表示已选中，灰色表示未选中"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(18, 18)
        self._selected = True
        self.color_on = QColor("#32cd32")
        self.color_off = QColor("#44444a")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.color_on if self._selected else self.color_off)
        p.drawEllipse(2, 2, 14, 14)

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
        self.setWindowTitle("ACC 赛车辅助工具箱")
        # 【修改1】增加高度，从 370 增加到 410，以容纳新的模块行
        self.setFixedSize(350, 410)
        self.setStyleSheet("background-color: #222225;")

        # 【修改2】在进程字典中加入 "delta": None
        self.processes = {"radar": None, "overlay": None, "tyres": None, "timer": None, "delta": None}
        self.switches = {}
        self.select_dots = {}
        self.game_running = False

        self.init_ui()

        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_game_status)
        self.check_timer.start(2000)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(40, 20, 40, 10)

        # 标题区
        title = QLabel("仪表盘控制中心")
        title.setStyleSheet("color: white; font-family: 'Microsoft YaHei'; font-size: 20px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("ASSETTO CORSA COMPETIZIONE")
        subtitle.setStyleSheet("color: #55555d; font-family: Arial; font-size: 10px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(15)

        # 【修改3】在模块列表中加入 "实时秒差"
        modules = [
            ("相对雷达", "radar"), 
            ("遥测踏板", "overlay"), 
            ("轮胎面板", "tyres"), 
            ("圈速计时", "timer"),
            ("实时秒差", "delta")  # 新增的模块
        ]

        # 总开关行
        master_row = QFrame()
        master_layout = QHBoxLayout(master_row)
        master_layout.setContentsMargins(0, 5, 0, 5)

        master_lbl = QLabel("一键启动")
        master_lbl.setStyleSheet("color: #ffcc00; font-family: 'Microsoft YaHei'; font-size: 14px; font-weight: bold;")

        self.master_switch = ToggleSwitch()
        self.master_switch.clicked.connect(self.handle_master_toggle)

        master_layout.addWidget(master_lbl)
        master_layout.addStretch()
        master_layout.addWidget(self.master_switch)
        layout.addWidget(master_row)

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #333338;")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        for name, key in modules:
            row = QFrame()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 5, 0, 5)

            dot = SelectDot()
            self.select_dots[key] = dot

            lbl = QLabel(name)
            lbl.setStyleSheet("color: #dcdcdc; font-family: 'Microsoft YaHei'; font-size: 14px;")

            switch = ToggleSwitch()
            switch.clicked.connect(lambda s, k=key, w=switch: self.handle_toggle(s, k, w))
            self.switches[key] = switch

            row_layout.addWidget(lbl)
            row_layout.addStretch()
            row_layout.addWidget(dot)
            row_layout.addSpacing(8)
            row_layout.addWidget(switch)
            layout.addWidget(row)

        # 底部状态栏
        self.status_bar = QLabel("系统就绪")
        self.status_bar.setStyleSheet("color: #666666; font-size: 12px; background-color: #1a1a1d; padding: 5px;")
        self.status_bar.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.statusBar().addPermanentWidget(self.status_bar)
   
    def check_game_status(self):
        try:
            output = subprocess.check_output('tasklist', creationflags=subprocess.CREATE_NO_WINDOW).decode('mbcs',
                                                                                                           'ignore').lower()
            self.game_running = "ac2-win64-shipping.exe" in output or "acc.exe" in output
        except:
            self.game_running = False

        status_text = "游戏运行中" if self.game_running else "游戏未启动"
        color = "#32cd32" if self.game_running else "#aaaaaa"
        self.status_bar.setText(status_text)
        self.status_bar.setStyleSheet(f"color: {color};")

    def handle_toggle(self, is_on, key, switch_widget):
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
        # 判断是否运行在 PyInstaller 打包后的环境中
        if getattr(sys, 'frozen', False):
            # 如果是 exe 环境，直接调用打包后的子程序 exe
            # 假设子程序打包后叫 ACC_Overlay.exe
            cmd = ["ACC_Overlay.exe", key]
        else:
            # 源码环境：使用绝对路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script = os.path.join(script_dir, "overlay.py")
            python_exe = sys.executable
            cmd = [python_exe, script, key]

        try:
            self.processes[key] = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            self.status_bar.setText("启动失败")
            print(f"启动错误: {e}")

    def stop_module(self, key):
        p = self.processes[key]
        if p:
            try:
                # /F 强制终止，/T 杀死进程树（连同被 PyInstaller 引导程序派生出的真实进程一起干掉）
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(p.pid)],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                # 兜底方案，万一 taskkill 失败则调用原生的 terminate
                p.terminate()
            self.processes[key] = None

    def closeEvent(self, event):
        # 主窗口关闭时，也要确保所有的子模块被彻底干净地清理
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