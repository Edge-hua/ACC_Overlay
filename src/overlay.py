import ctypes
import mmap
import json
import os
import time
import math
import sys
import struct
import threading
from collections import deque

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPolygonF

from accapi.client import AccClient, Event

# ================= 游戏连接配置 (雷达用) =================
ACC_IP = "127.0.0.1"
ACC_PORT = 9000
ACC_PASSWORD = "asd"


# ==================== 共享内存结构体 ====================
class SPageFilePhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', ctypes.c_int),
        ('gas', ctypes.c_float),
        ('brake', ctypes.c_float),
        ('fuel', ctypes.c_float),
        ('gear', ctypes.c_int),
        ('rpms', ctypes.c_int),
        ('steerAngle', ctypes.c_float),
        ('speedKmh', ctypes.c_float),
        ('velocity', ctypes.c_float * 3),
        ('accG', ctypes.c_float * 3),
        ('wheelSlip', ctypes.c_float * 4),
        ('wheelLoad', ctypes.c_float * 4),
        ('wheelsPressure', ctypes.c_float * 4),
        ('wheelAngularSpeed', ctypes.c_float * 4),
        ('tyreWear', ctypes.c_float * 4),
        ('tyreDirtyLevel', ctypes.c_float * 4),
        ('tyreCoreTemperature', ctypes.c_float * 4),
        ('camberRAD', ctypes.c_float * 4),
        ('suspensionTravel', ctypes.c_float * 4),
        ('drs', ctypes.c_float),
        ('tc', ctypes.c_float),
        ('heading', ctypes.c_float),
        ('pitch', ctypes.c_float),
        ('roll', ctypes.c_float),
        ('cgHeight', ctypes.c_float),
        ('carDamage', ctypes.c_float * 5),
        ('numberOfTyresOut', ctypes.c_int),
        ('pitLimiterOn', ctypes.c_int),
        ('abs', ctypes.c_float),
        ('kersCharge', ctypes.c_float),
        ('kersInput', ctypes.c_float),
        ('autoShifterOn', ctypes.c_int),
        ('rideHeight', ctypes.c_float * 2),
        ('turboBoost', ctypes.c_float),
        ('ballast', ctypes.c_float),
        ('airDensity', ctypes.c_float),
        ('airTemp', ctypes.c_float),
        ('roadTemp', ctypes.c_float),
        ('localAngularVel', ctypes.c_float * 3),
        ('finalFF', ctypes.c_float),
        ('performanceMeter', ctypes.c_float),
        ('engineBrake', ctypes.c_int),
        ('ersRecoveryLevel', ctypes.c_int),
        ('ersPowerLevel', ctypes.c_int),
        ('ersHeatCharging', ctypes.c_int),
        ('ersIsCharging', ctypes.c_int),
        ('kersCurrentKJ', ctypes.c_float),
        ('drsAvailable', ctypes.c_int),
        ('drsEnabled', ctypes.c_int),
        ('brakeTemp', ctypes.c_float * 4),
        ('clutch', ctypes.c_float),
        ('tyreTempI', ctypes.c_float * 4),
        ('tyreTempM', ctypes.c_float * 4),
        ('tyreTempO', ctypes.c_float * 4),
        ('isAIControlled', ctypes.c_int),
        ('tyreContactPoint', (ctypes.c_float * 3) * 4),
        ('tyreContactNormal', (ctypes.c_float * 3) * 4),
        ('tyreContactHeading', (ctypes.c_float * 3) * 4),
        ('brakeBias', ctypes.c_float),
        ('localVelocity', ctypes.c_float * 3),
        ('P2PActivations', ctypes.c_int),
        ('P2PStatus', ctypes.c_int),
        ('currentMaxRpm', ctypes.c_float),
        ('mz', ctypes.c_float * 4),
        ('fx', ctypes.c_float * 4),
        ('fy', ctypes.c_float * 4),
        ('slipRatio', ctypes.c_float * 4),
        ('slipAngle', ctypes.c_float * 4),
        ('tcinAction', ctypes.c_int),
        ('absInAction', ctypes.c_int),
        ('suspensionDamage', ctypes.c_float * 4),
        ('tyreTemp', ctypes.c_float * 4),
        ('waterTemp', ctypes.c_float),
        ('brakePressure', ctypes.c_float * 4),
        ('frontBrakeCompound', ctypes.c_int),
        ('rearBrakeCompound', ctypes.c_int),
        ('padLife', ctypes.c_float * 4),
        ('discLife', ctypes.c_float * 4),
        ('ignitionOn', ctypes.c_int),
        ('starterEngineOn', ctypes.c_int),
        ('isEngineRunning', ctypes.c_int),
        ('kerbVibration', ctypes.c_float),
        ('slipVibrations', ctypes.c_float),
        ('gVibrations', ctypes.c_float),
        ('absVibrations', ctypes.c_float)
    ]


class SPageFileGraphics(ctypes.Structure):
    """acpmf_graphics 前缀（至 numberOfLaps）；PenaltyShortCut 用固定偏移从 mmap 原字节读取，避免整页 ctypes 过大导致 mmap 失败。"""
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),
        ("session", ctypes.c_int),
        ("currentTime", ctypes.c_wchar * 15),
        ("lastTime", ctypes.c_wchar * 15),
        ("bestTime", ctypes.c_wchar * 15),
        ("split", ctypes.c_wchar * 15),
        ("completedLaps", ctypes.c_int),
        ("position", ctypes.c_int),
        ("iCurrentTime", ctypes.c_int),
        ("iLastTime", ctypes.c_int),
        ("iBestTime", ctypes.c_int),
        ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float),
        ("isInPit", ctypes.c_int),
        ("currentSectorIndex", ctypes.c_int),
        ("lastSectorTime", ctypes.c_int),
        ("numberOfLaps", ctypes.c_int),
    ]


# ==================== 基础悬浮类 ====================
class OverlayBase(QWidget):
    def __init__(self, module_name, width, height, alpha=0.9):
        super().__init__()
        self.module_name = module_name
        self.config_file = "acc_windows.json"

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(width, height)
        self.setWindowOpacity(alpha)

        self.old_pos = None
        self.load_position()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        self.save_position()

    def load_position(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                if self.module_name in config:
                    p = config[self.module_name]
                    self.move(p['x'], p['y'])
        except:
            pass

    def save_position(self):
        try:
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
            config[self.module_name] = {"x": self.x(), "y": self.y()}
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except:
            pass

    # ================= 绘图辅助函数 =================
    def draw_rounded_rect(self, painter, x1, y1, x2, y2, radius, color):
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(x1, y1, x2 - x1, y2 - y1), radius, radius)

    def draw_rect(self, painter, x1, y1, x2, y2, color):
        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))

    def draw_line(self, painter, x1, y1, x2, y2, color, width=1.0):
        pen = QPen(QColor(color), width)
        painter.setPen(pen)
        painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def draw_text(self, painter, x, y, text, font_family, font_size, color, weight="normal", anchor="center"):
        font = QFont(font_family, font_size, QFont.Weight.Bold if weight == "bold" else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(QColor(color))
        if anchor == "center":
            rect = QRectF(x - 200, y - 50, 400, 100)
            flags = Qt.AlignmentFlag.AlignCenter
        elif anchor == "w":
            rect = QRectF(x, y - 50, 400, 100)
            flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        elif anchor == "e":
            rect = QRectF(x - 400, y - 50, 400, 100)
            flags = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        painter.drawText(rect, flags, text)


# ==========================================================
# 模块 1：圈速计时器 (紫/绿/黄)
# ==========================================================
class ACCTimer(OverlayBase):
    _GRAPHICS_SHM_READ_BYTES = 2048
    _PLAYER_CAR_ID_OFFSET = 1220
    _PENALTY_SHORTCUT_OFFSET = 1232

    def __init__(self):
        super().__init__("timer", 280, 115, 0.9)
        self.refresh_rate = 50

        self.current_session_type = -1 

        self.last_completed_laps = 0
        self.last_sector_index = 0
        self.lap_start_cleared = True
        self.personal_bests = [9999999, 9999999, 9999999]
        self.session_global_bests = [9999999, 9999999, 9999999]
        self._penalty_short_baseline = -1

        self.s1_cum = 0
        self.s2_cum = 0
        self.current_sector_times = [0, 0, 0]
        self.sector_colors = ["#333338", "#333338", "#333338"]

        self.current_lap_ms = 0
        self.lap_finish_timestamp = 0

        self.my_car_index = None
        self.my_position = 0
        self.cars_data = {}
        self._cars_lock = threading.Lock()
        self._pending_car_updates = {}
        self._pending_focused_car = None
        self.client = None

        # 断线重连心跳变量
        self.last_data_time = time.time()
        self.last_reconnect_time = time.time()

        self.connect_client()
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.update_data)
        self.data_timer.start(self.refresh_rate)

    def reset_session_data(self):
        self.last_completed_laps = 0
        self.last_sector_index = 0
        self.lap_start_cleared = True
        self.personal_bests = [9999999, 9999999, 9999999]
        self.session_global_bests = [9999999, 9999999, 9999999]
        self._penalty_short_baseline = -1

        self.s1_cum = 0
        self.s2_cum = 0
        self.current_sector_times = [0, 0, 0]
        self.sector_colors = ["#333338", "#333338", "#333338"]

        self.current_lap_ms = 0
        self.lap_finish_timestamp = 0

        self.my_car_index = None
        self.my_position = 0
        self.cars_data = {}
        with self._cars_lock:
            self._pending_car_updates = {}
            self._pending_focused_car = None

    def connect_client(self):
        if self.client is not None:
            try:
                self.client.stop()
            except:
                pass
        self.client = AccClient()
        self.client.onRealtimeUpdate.subscribe(self.on_global_update)
        self.client.onRealtimeCarUpdate.subscribe(self.on_car_update)
        try:
            self.client.start(ACC_IP, ACC_PORT, ACC_PASSWORD)
        except Exception as e:
            print(f"[Timer UDP 错误] 无法连接到 ACC: {e}")

    def on_global_update(self, event: Event):
        self.last_data_time = time.time()
        try:
            c = event.content
            idx = -1
            for key in ["FocusedCarIndex", "focusedCarIndex", "focused_car_index"]:
                if hasattr(c, key):
                    idx = getattr(c, key)
                    break
            if idx >= 0:
                with self._cars_lock:
                    self._pending_focused_car = idx
        except Exception:
            pass

    def on_car_update(self, event: Event):
        self.last_data_time = time.time()
        try:
            c = event.content
            car_idx = -1
            for key in ["CarIndex", "carIndex", "car_index"]:
                if hasattr(c, key):
                    car_idx = getattr(c, key)
                    break
            if car_idx < 0 and isinstance(c, dict):
                for key in ["CarIndex", "carIndex", "car_index"]:
                    if key in c:
                        car_idx = c[key]
                        break

            if car_idx < 0:
                return
            with self._cars_lock:
                self._pending_car_updates[car_idx] = c
        except Exception:
            pass

    def _flush_pending_car_updates(self):
        with self._cars_lock:
            batch = self._pending_car_updates
            self._pending_car_updates = {}
            focus = self._pending_focused_car
            self._pending_focused_car = None
        if focus is not None:
            self.my_car_index = focus

        for c in batch.values():
            try:
                self._merge_realtime_car(c)
            except Exception as e:
                import traceback
                print(f"[Timer 数据解析报错] 车辆数据出错: {e}")
                traceback.print_exc()

        self._update_global_bests_from_cars()

    def _update_global_bests_from_cars(self):
        for data in self.cars_data.values():
            splits = data.get("splits", [0, 0, 0])
            for i in range(3):
                if 0 < splits[i] < self.session_global_bests[i]:
                    self.session_global_bests[i] = splits[i]

    def _merge_realtime_car(self, c):
        def get_attr(obj, names, default=None):
            if isinstance(obj, dict):
                for n in names:
                    if n in obj and obj[n] is not None:
                        return obj[n]
            else:
                for n in names:
                    try:
                        if hasattr(obj, n):
                            val = getattr(obj, n)
                            if val is not None:
                                return val
                    except:
                        pass
            return default

        def parse_ms(val):
            if val is None: return 0
            try:
                v = int(val)
                if 0 < v < 2147000000: return v
            except:
                pass
            return 0

        def extract_lap(lap_obj):
            if lap_obj is None: return 0, [0, 0, 0]
            if isinstance(lap_obj, (int, float)): return parse_ms(lap_obj), [0, 0, 0]
            if isinstance(lap_obj, str) and lap_obj.isdigit(): return parse_ms(lap_obj), [0, 0, 0]

            ms = parse_ms(get_attr(lap_obj, ["LaptimeMS", "laptimeMS", "LapTimeMS", "lapTimeMs", "laptime_ms"], 0))
            sp_raw = get_attr(lap_obj, ["Splits", "splits", "split"], [])
            
            sp = [0, 0, 0]
            if sp_raw:
                try:
                    sp_list = list(sp_raw)
                    for i in range(min(3, len(sp_list))):
                        sp[i] = parse_ms(sp_list[i])
                except Exception:
                    pass
            
            if ms <= 0 and sum(sp) > 0 and sp[0] > 0 and sp[1] > 0 and sp[2] > 0:
                ms = sum(sp)
            return ms, sp

        car_idx = get_attr(c, ["CarIndex", "carIndex", "car_index"], -1)
        if car_idx < 0: return

        existing = self.cars_data.get(car_idx, {
            "car_index": car_idx,
            "position": 0,
            "cup_position": 0,
            "lap_ms": 0,
            "splits": [0, 0, 0],
            "last_lap_invalid": False
        })

        raw_pos = get_attr(c, ["Position", "position", "position_pos"], 0) or 0
        cup_pos = get_attr(c, ["CupPosition", "cupPosition", "cup_position"], 0) or 0
        if raw_pos > 0: existing["position"] = raw_pos
        if cup_pos > 0: existing["cup_position"] = cup_pos

        best_lap = get_attr(c, ["BestSessionLap", "bestSessionLap", "best_session_lap"])
        last_lap = get_attr(c, ["LastLap", "lastLap", "last_lap"])
        cur_lap = get_attr(c, ["CurrentLap", "currentLap", "current_lap"])

        best_ms, best_sp = extract_lap(best_lap)
        last_ms, last_sp = extract_lap(last_lap)
        cur_ms, cur_sp = extract_lap(cur_lap)

        def lap_invalid(lap_obj):
            if not lap_obj: return False
            return bool(get_attr(lap_obj, ["IsInvalid", "isInvalid", "is_invalid"], False))

        # 圈速更新逻辑
        if last_ms > 0:
            existing["lap_ms"] = last_ms
            existing["last_lap_invalid"] = lap_invalid(last_lap)
        elif best_ms > 0:
            existing["lap_ms"] = best_ms
            existing["last_lap_invalid"] = lap_invalid(best_lap)

        # 分段更新逻辑
        if sum(cur_sp) > 0:
            existing["splits"] = cur_sp
        elif sum(last_sp) > 0:
            existing["splits"] = last_sp
        elif sum(best_sp) > 0:
            existing["splits"] = best_sp
        
        self.cars_data[car_idx] = existing

        if car_idx == self.my_car_index:
            if raw_pos > 0: self.my_position = raw_pos
            elif cup_pos > 0: self.my_position = cup_pos

    def _race_position(self, data):
        pos = data.get("position", 0) or 0
        if pos <= 0:
            pos = data.get("cup_position", 0) or 0
        if self.my_car_index is not None and data.get("car_index") == self.my_car_index and self.my_position > 0:
            return self.my_position
        return pos

    def _is_me(self, data):
        if self.my_car_index is not None:
            return data.get("car_index") == self.my_car_index
        return self.my_position > 0 and self._race_position(data) == self.my_position

    def _sorted_race_cars(self):
        out = [d for d in self.cars_data.values() if self._race_position(d) > 0]
        out.sort(key=self._race_position)
        return out

    def closeEvent(self, event):
        if self.client:
            try:
                self.client.stop()
            except:
                pass
        super().closeEvent(event)

    def format_ms(self, ms):
        if ms is None or ms <= 0 or ms >= 2147000000: return "--:--.---"
        seconds = (ms / 1000) % 60
        minutes = (ms // 60000) % 60
        return f"{int(minutes):02d}:{seconds:06.3f}"

    def format_sector_ms(self, ms):
        if ms is None or ms <= 0 or ms >= 2147000000: return "-.-"
        sec = ms / 1000.0
        if sec < 60:
            return f"{sec:.1f}"
        else:
            return f"{int(sec // 60)}:{sec % 60:04.1f}"

    def update_sector_color(self, sector_idx, s_time, invalid=False):
        if s_time <= 0: return
        if invalid:
            self.sector_colors[sector_idx] = "#c0392b"
            return

        if s_time < self.session_global_bests[sector_idx]:
            self.session_global_bests[sector_idx] = s_time
            self.personal_bests[sector_idx] = s_time
            self.sector_colors[sector_idx] = "#9b59b6"
        elif s_time < self.personal_bests[sector_idx]:
            self.personal_bests[sector_idx] = s_time
            self.sector_colors[sector_idx] = "#2ecc71"
        else:
            self.sector_colors[sector_idx] = "#f1c40f"

    def draw_opponent_row(self, painter, y_pos, fallback_pos, data):
        if data:
            pos_val = self._race_position(data)
            if pos_val <= 0:
                pos_val = fallback_pos
        else:
            pos_val = fallback_pos
        pos_str = f"P{pos_val}" if pos_val > 0 else "P-"
        lap_ms = data.get("lap_ms", 0) if data else 0
        splits = data.get("splits", [0, 0, 0]) if data else [0, 0, 0]

        self.draw_text(painter, 25, y_pos, pos_str, "Arial", 11, "#aaaaaa", "bold")
        lap_inv = data.get("last_lap_invalid", False) if data else False
        lap_color = "#c0392b" if lap_inv and lap_ms > 0 else "#ffffff"
        self.draw_text(painter, 85, y_pos, self.format_ms(lap_ms), "Arial", 11, lap_color, "bold")

        sx = 155
        for i in range(3):
            s_val = splits[i] if i < len(splits) else 0
            val_str = self.format_sector_ms(s_val) if s_val > 0 else "-.-"
            sp_color = "#c0392b" if lap_inv and s_val > 0 else "#888888"
            self.draw_text(painter, sx + i * 42, y_pos, val_str, "Arial", 9, sp_color, "normal")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.draw_rounded_rect(painter, 1, 1, self.width() - 1, self.height() - 1, 12, "#222225")

        car_ahead = None
        car_behind = None

        if self.my_position > 0 and self.cars_data:
            valid_cars = self._sorted_race_cars()
            idx = -1
            
            for i, data in enumerate(valid_cars):
                if self._is_me(data):
                    idx = i
                    break
            
            if idx >= 0:
                car_ahead = valid_cars[idx - 1] if idx > 0 else None
                car_behind = valid_cars[idx + 1] if idx < len(valid_cars) - 1 else None
            else:
                ahead_candidates = [c for c in valid_cars if self._race_position(c) < self.my_position]
                behind_candidates = [c for c in valid_cars if self._race_position(c) > self.my_position]
                car_ahead = ahead_candidates[-1] if ahead_candidates else None
                car_behind = behind_candidates[0] if behind_candidates else None

        self.draw_opponent_row(painter, 21, self.my_position - 1 if self.my_position > 1 else 0, car_ahead)
        self.draw_line(painter, 15, 36, self.width() - 15, 36, "#333338")

        my_pos_str = f"P{self.my_position}" if self.my_position > 0 else "P-"
        self.draw_text(painter, 25, 57, my_pos_str, "Arial", 13, "#32cd32", "bold")
        self.draw_text(painter, 85, 57, self.format_ms(self.current_lap_ms), "Arial", 13, "#ffffff", "bold")

        y1 = 46
        y2 = 50
        sw = 36
        centers = [155, 197, 239]

        for i in range(3):
            cx = centers[i]
            x1 = cx - sw / 2
            self.draw_rect(painter, x1, y1, x1 + sw, y2, self.sector_colors[i])
            s_time_str = self.format_sector_ms(self.current_sector_times[i])
            sc = self.sector_colors[i]
            if sc == "#333338":
                t_color = "#55555d"
            elif sc == "#c0392b":
                t_color = "#ffffff"
            else:
                t_color = sc
            self.draw_text(painter, cx, y2 + 14, s_time_str, "Arial", 10, t_color, "bold")

        self.draw_line(painter, 15, 78, self.width() - 15, 78, "#333338")
        self.draw_opponent_row(painter, 94, self.my_position + 1 if self.my_position > 0 else 0, car_behind)

    def update_data(self):
        # 断线自动重连
        current_time = time.time()
        if current_time - self.last_data_time > 3.0:
            if current_time - self.last_reconnect_time > 5.0:
                print("[Timer] UDP 遥测断开，正在尝试重新连接 ACC...")
                self.connect_client()
                self.last_reconnect_time = current_time
        
        self._flush_pending_car_updates()
        shm_graphics = None
        try:
            read_sz = max(ctypes.sizeof(SPageFileGraphics), self._GRAPHICS_SHM_READ_BYTES)
            try:
                shm_graphics = mmap.mmap(-1, read_sz, "acpmf_graphics", access=mmap.ACCESS_READ)
            except FileNotFoundError:
                shm_graphics = mmap.mmap(-1, read_sz, "Local\\acpmf_graphics", access=mmap.ACCESS_READ)

            shm_graphics.seek(0)
            data = shm_graphics.read(read_sz)
            gsz = ctypes.sizeof(SPageFileGraphics)
            graphics = SPageFileGraphics.from_buffer_copy(data[:gsz])
            off = self._PENALTY_SHORTCUT_OFFSET
            pen_sc = struct.unpack_from("<i", data, off)[0] if len(data) >= off + 4 else 0
            if self.my_car_index is None and len(data) >= self._PLAYER_CAR_ID_OFFSET + 4:
                pid = struct.unpack_from("<i", data, self._PLAYER_CAR_ID_OFFSET)[0]
                if pid >= 0:
                    self.my_car_index = pid

            if graphics.packetId == 0:
                self.reset_session_data()
                self.current_session_type = -1
            else:
                if self.current_session_type != graphics.session:
                    self.reset_session_data()
                    self.current_session_type = graphics.session

                curr_sector = graphics.currentSectorIndex
                curr_laps = graphics.completedLaps

                if self._penalty_short_baseline < 0:
                    self._penalty_short_baseline = pen_sc

                if graphics.position > 0:
                    self.my_position = graphics.position

                if curr_laps < self.last_completed_laps:
                    self.last_completed_laps = curr_laps
                    self.last_sector_index = curr_sector
                    self.sector_colors = ["#333338", "#333338", "#333338"]
                    self.current_sector_times = [0, 0, 0]
                    self.s1_cum = 0
                    self.s2_cum = 0
                    self.lap_start_cleared = True
                    self.lap_finish_timestamp = 0
                    self._penalty_short_baseline = pen_sc

                elif curr_laps > self.last_completed_laps:
                    self.lap_finish_timestamp = time.time()

                    if self.s2_cum > 0 and graphics.iLastTime > 0:
                        s3_time = graphics.iLastTime - self.s2_cum
                        if s3_time > 0:
                            cut = pen_sc > self._penalty_short_baseline
                            self.update_sector_color(2, s3_time, invalid=cut)
                            self.current_sector_times[2] = s3_time
                            self._penalty_short_baseline = pen_sc

                    self.last_completed_laps = curr_laps
                    self.last_sector_index = curr_sector
                    self.lap_start_cleared = False

                elif curr_sector != self.last_sector_index:
                    if self.last_sector_index == 0 and curr_sector == 1:
                        self.s1_cum = graphics.lastSectorTime
                        if self.s1_cum > 0:
                            cut = pen_sc > self._penalty_short_baseline
                            self.update_sector_color(0, self.s1_cum, invalid=cut)
                            self.current_sector_times[0] = self.s1_cum
                            self._penalty_short_baseline = pen_sc
                    elif self.last_sector_index == 1 and curr_sector == 2:
                        self.s2_cum = graphics.lastSectorTime
                        s2_time = self.s2_cum - self.s1_cum if self.s1_cum > 0 else 0
                        if s2_time > 0:
                            cut = pen_sc > self._penalty_short_baseline
                            self.update_sector_color(1, s2_time, invalid=cut)
                            self.current_sector_times[1] = s2_time
                            self._penalty_short_baseline = pen_sc
                    self.last_sector_index = curr_sector

                if curr_sector == 0 and 50 < graphics.distanceTraveled < 200 and not self.lap_start_cleared:
                    self.sector_colors = ["#333338", "#333338", "#333338"]
                    self.current_sector_times = [0, 0, 0]
                    self.s1_cum = 0
                    self.s2_cum = 0
                    self.lap_start_cleared = True
                    self._penalty_short_baseline = pen_sc

                if graphics.distanceTraveled < 10 and self.last_sector_index > 0:
                    self.last_sector_index = 0
                    self.s1_cum = 0
                    self.s2_cum = 0
                    self.sector_colors = ["#333338", "#333338", "#333338"]
                    self.current_sector_times = [0, 0, 0]
                    self._penalty_short_baseline = pen_sc

                if time.time() - self.lap_finish_timestamp < 5.0 and graphics.iLastTime > 0:
                    self.current_lap_ms = graphics.iLastTime
                else:
                    self.current_lap_ms = graphics.iCurrentTime

        except Exception:
            pass
        finally:
            if shm_graphics is not None:
                shm_graphics.close()

        self.update()

# ==========================================================
# 模块 2：轮胎状态面板
# ==========================================================
class ACCTyrePanel(OverlayBase):
    def __init__(self):
        super().__init__("tyres", 220, 235, 0.85)
        self.refresh_rate = 100
        self.is_connected = False

        self.core_temp = [0.0, 0.0, 0.0, 0.0]
        self.pressure = [0.0, 0.0, 0.0, 0.0]
        self.brake_temp = [0.0, 0.0, 0.0, 0.0]
        self.slip_ratios = [0.0, 0.0, 0.0, 0.0]
        self.pad_life = [29.0, 29.0, 29.0, 29.0]

        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.update_data)
        self.data_timer.start(self.refresh_rate)

    def interpolate_color(self, color1, color2, factor):
        r1, g1, b1 = color1
        r2, g2, b2 = color2
        return f"#{int(r1 + (r2 - r1) * factor):02x}{int(g1 + (g2 - g1) * factor):02x}{int(b1 + (b2 - b1) * factor):02x}"

    def get_brake_color(self, temp):
        cyan = (0, 204, 255)
        green = (39, 174, 96)
        orange = (243, 156, 18)
        red = (231, 76, 60)
        if temp <= 100:
            return "#00ccff"
        elif temp < 300:
            return self.interpolate_color(cyan, green, (temp - 100) / 200.0)
        elif temp <= 700:
            return "#27ae60"
        elif temp < 840:
            return self.interpolate_color(green, orange, (temp - 700) / 140.0)
        elif temp < 900:
            return self.interpolate_color(orange, red, (temp - 840) / 60.0)
        else:
            return "#e74c3c"

    def get_dynamic_bg_color(self, temp):
        cyan = (0, 153, 204)
        green = (39, 174, 96)
        yellow = (212, 172, 13)
        red = (192, 57, 43)
        if temp <= 60.0:
            return "#0099cc"
        elif temp < 75.0:
            return self.interpolate_color(cyan, green, (temp - 60.0) / 15.0)
        elif temp <= 90.0:
            return "#27ae60"
        elif temp < 100.0:
            return self.interpolate_color(green, yellow, (temp - 90.0) / 10.0)
        elif temp < 105.0:
            return self.interpolate_color(yellow, red, (temp - 100.0) / 5.0)
        else:
            return "#c0392b"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_panel_color = "#222225"
        self.draw_rounded_rect(painter, 1, 1, self.width() - 1, self.height() - 1, 12, bg_panel_color)
        self.draw_text(painter, self.width() / 2, 16, "TYRE & BRAKE", "Arial", 9, "#aaaaaa", "bold")
        self.draw_line(painter, 15, 28, self.width() - 15, 28, "#44444a")

        if not self.is_connected:
            self.draw_text(painter, self.width() / 2, self.height() / 2, "等待数据...", "Arial", 11, "#ffffff", "bold")
            return

        coords = [(30, 40, 78, 124), (142, 40, 190, 124), (30, 136, 78, 220), (142, 136, 190, 220)]
        front_brake = (self.brake_temp[0] + self.brake_temp[1]) / 2
        rear_brake = (self.brake_temp[2] + self.brake_temp[3]) / 2

        self.draw_text(painter, 110, 68, "FRONT", "Arial", 7, "#55555d", "bold")
        self.draw_text(painter, 110, 84, f"{int(front_brake)}°", "Arial", 10, self.get_brake_color(front_brake), "bold")
        self.draw_text(painter, 110, 164, "REAR", "Arial", 7, "#55555d", "bold")
        self.draw_text(painter, 110, 180, f"{int(rear_brake)}°", "Arial", 10, self.get_brake_color(rear_brake), "bold")

        for i in range(4):
            x1, y1, x2, y2 = coords[i]
            cx = (x1 + x2) / 2
            temp_val = self.core_temp[i]
            bg_color = self.get_dynamic_bg_color(temp_val)
            brake_bg = self.get_brake_color(self.brake_temp[i])

            by1, by2 = y1 + 20, y2 - 20
            current_pad = self.pad_life[i]
            remain_pct = max(0, min(100, (current_pad / 29.0) * 100))

            wear_color = "#e0e0e0"
            if remain_pct < 10:
                wear_color = "#e74c3c"
            elif remain_pct < 30:
                wear_color = "#f1c40f"
            wear_text = f"{int(remain_pct)}%"

            if i % 2 == 0:
                sx1, sy1 = x1 - 17, y1
                sx2, sy2 = x1 - 3, y2
                self.draw_rounded_rect(painter, sx1, sy1, sx1 + 28, sy2, 14, "#333338")

                slip = self.slip_ratios[i]
                if slip > 0.03:
                    cx_s, cy_s = (sx1 + sx2) / 2, (sy1 + sy2) / 2
                    ew = sx2 - sx1 - 4
                    eh = max(4.0, (sy2 - sy1 - 8) * slip)
                    s_color = "#2ecc71" if slip < 0.4 else ("#f1c40f" if slip < 0.75 else "#e74c3c")
                    painter.setBrush(QColor(s_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QRectF(cx_s - ew / 2, cy_s - eh / 2, ew, eh))

                self.draw_rect(painter, sx2, sy1, sx1 + 28, sy2, bg_panel_color)
                self.draw_rounded_rect(painter, x1, y1, x2, y2, 14, bg_color)
                self.draw_rect(painter, x1, y1, x1 + 14, y2, bg_color)

                bx1, bx2 = x2 + 2, x2 + 12
                self.draw_rect(painter, bx1, by1, bx2, by2, brake_bg)
                text_y = by1 - 10 if i < 2 else by2 + 10
                self.draw_text(painter, bx1, text_y, wear_text, "Arial", 9, wear_color, "bold", "w")
            else:
                sx1, sy1 = x2 + 3, y1
                sx2, sy2 = x2 + 17, y2
                self.draw_rounded_rect(painter, sx2 - 28, sy1, sx2, sy2, 14, "#333338")

                slip = self.slip_ratios[i]
                if slip > 0.03:
                    cx_s, cy_s = (sx1 + sx2) / 2, (sy1 + sy2) / 2
                    ew = sx2 - sx1 - 4
                    eh = max(4.0, (sy2 - sy1 - 8) * slip)
                    s_color = "#2ecc71" if slip < 0.4 else ("#f1c40f" if slip < 0.75 else "#e74c3c")
                    painter.setBrush(QColor(s_color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QRectF(cx_s - ew / 2, cy_s - eh / 2, ew, eh))

                self.draw_rect(painter, sx2 - 28, sy1, sx1, sy2, bg_panel_color)
                self.draw_rounded_rect(painter, x1, y1, x2, y2, 14, bg_color)
                self.draw_rect(painter, x2 - 14, y1, x2, y2, bg_color)

                bx1, bx2 = x1 - 12, x1 - 2
                self.draw_rect(painter, bx1, by1, bx2, by2, brake_bg)
                text_y = by1 - 10 if i < 2 else by2 + 10
                self.draw_text(painter, bx2, text_y, wear_text, "Arial", 9, wear_color, "bold", "e")

            self.draw_text(painter, cx, y1 + 25, f"{self.pressure[i]:.1f}", "Arial", 12, "#ffffff", "bold")
            self.draw_text(painter, cx, y1 + 40, "psi", "Arial", 8, "#e0e0e0", "bold")
            self.draw_text(painter, cx, y2 - 28, f"{int(temp_val)}°C", "Arial", 12, "#ffffff", "bold")
            self.draw_text(painter, cx, y2 - 13, "core", "Arial", 8, "#e0e0e0", "bold")

    def update_data(self):
        shm = None
        try:
            try:
                shm = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), "acpmf_physics", access=mmap.ACCESS_READ)
            except FileNotFoundError:
                shm = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), "Local\\acpmf_physics", access=mmap.ACCESS_READ)

            shm.seek(0)
            data = shm.read(ctypes.sizeof(SPageFilePhysics))
            physics = SPageFilePhysics.from_buffer_copy(data)
            
            if physics.packetId == 0:
                self.is_connected = False
            else:
                self.is_connected = True
                
                # 1. 抓取赛车底盘的绝对局部速度 (单位: m/s)
                # v_lat 是横向侧滑速度，v_lon 是纵向推进速度
                v_lat = abs(physics.localVelocity[0])
                v_lon = abs(physics.localVelocity[2])

                # 2. 计算底盘整体的横向滑移强度
                # 正常行驶时 v_lat 几乎为0；当推头或甩尾时，横向速度会显著增加
                car_lateral_slip = 0.0
                if v_lon > 3.0:
                    car_lateral_slip = v_lat / v_lon  # 计算侧滑角的正切值
                
                # 映射横向滑移强度 (GT3赛车侧滑比达到 0.15 左右已经是严重的抓地力流失)
                lat_intensity = min(1.0, car_lateral_slip / 0.15)

                for i in range(4):
                    self.core_temp[i] = physics.tyreCoreTemperature[i]
                    self.pressure[i] = physics.wheelsPressure[i]
                    self.brake_temp[i] = physics.brakeTemp[i]
                    self.pad_life[i] = physics.padLife[i]

                    if v_lon > 3.0:
                        # 3. 计算车轮的纵向滑移 (对比轮胎线速度与底盘纵向速度)
                        omega = abs(physics.wheelAngularSpeed[i])
                        v_wheel = omega * 0.34  # 0.34m 是 GT3 轮胎有效滚动半径的最佳常数
                        
                        lon_diff = abs(v_wheel - v_lon)
                        # 映射纵向滑移强度 (差值 > 3.5m/s 基本视为严重抱死或空转)
                        lon_intensity = min(1.0, lon_diff / 3.5)

                        # 4. 向量合成最终的 UI 显示滑移量 (摩擦力圆原理)
                        # 将纵向抱死/空转 与 横向侧滑 结合
                        combined_slip = math.hypot(lon_intensity, lat_intensity)
                        
                        normalized_slip = min(1.0, combined_slip)
                        
                        # 设置死区：消除正常过弯时的微小物理蠕变，保持 UI 干净
                        if normalized_slip < 0.12:
                            normalized_slip = 0.0
                            
                        self.slip_ratios[i] = normalized_slip
                    else:
                        self.slip_ratios[i] = 0.0
                        
        except Exception:
            self.is_connected = False
        finally:
            if shm is not None:
                shm.close()
                
        self.update()


# ==========================================================
# 模块 3：遥测曲线踏板
# ==========================================================
class ACCOverlay(OverlayBase):
    def __init__(self):
        super().__init__("overlay", 470, 85, 0.85)
        self.refresh_rate = 30
        self.history_length = 110

        self.gas_history = deque([0.0] * self.history_length, maxlen=self.history_length)
        self.brake_history = deque([0.0] * self.history_length, maxlen=self.history_length)
        self.abs_history = deque([False] * self.history_length, maxlen=self.history_length)
        self.tc_history = deque([False] * self.history_length, maxlen=self.history_length)
        self._abs_hold = 0
        self._tc_hold = 0

        self.current_speed = 0
        self.current_gear_str = "-"
        self.current_gas = 0.0
        self.current_brake = 0.0

        self.is_connected = False
        self.top_speed = 0
        self.min_speed = 0
        self.temp_max = 0
        self.temp_min = 999
        self.was_braking = False
        self._blip_start_speed = None
        self.abs_active = False
        self.tc_active = False

        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.update_data)
        self.data_timer.start(self.refresh_rate)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color_bg = "#222225"
        color_slot = "#333338"
        color_grid = "#44444a"
        color_gas = "#32cd32"
        color_brake = "#ff2400"
        color_gear = "#ffcc00"
        color_top_speed = "#ff8800"

        self.draw_rounded_rect(painter, 1, 1, self.width() - 1, self.height() - 1, 15, color_bg)

        gx = 5;
        gy = 8;
        gw = 275;
        gh = 70
        self.draw_rect(painter, gx, gy, gx + gw, gy + gh, color_slot)

        for i in range(1, 4):
            self.draw_line(painter, gx, gy + gh * (i / 4), gx + gw, gy + gh * (i / 4), color_grid)
        for i in range(1, 5):
            self.draw_line(painter, gx + gw * (i / 5), gy, gx + gw * (i / 5), gy + gh, color_grid)

        dx = gw / max(1, self.history_length - 1)
        brake_pts = [QPointF(gx + i * dx, gy + gh - (self.brake_history[i] * gh)) for i in range(self.history_length)]
        gas_pts = [QPointF(gx + i * dx, gy + gh - (self.gas_history[i] * gh)) for i in range(self.history_length)]

        if len(self.gas_history) >= 4:
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for i in range(self.history_length - 1):
                c = "#f1c40f" if self.abs_history[i] else color_brake
                painter.setPen(QPen(QColor(c), 2.5))
                painter.drawLine(brake_pts[i], brake_pts[i + 1])

            for i in range(self.history_length - 1):
                c = "#f1c40f" if self.tc_history[i] else color_gas
                painter.setPen(QPen(QColor(c), 2.5))
                painter.drawLine(gas_pts[i], gas_pts[i + 1])

        bx = 290;
        by = 8;
        bw = 20;
        bh = 70;
        gap = 8
        x_g = bx + bw + gap

        self.draw_rect(painter, bx, by, bx + bw, by + bh, color_slot)
        self.draw_rect(painter, x_g, by, x_g + bw, by + bh, color_slot)

        brake_fill = "#f1c40f" if self.abs_active else color_brake
        gas_fill = "#f1c40f" if self.tc_active else color_gas

        if self.current_brake > 0:
            self.draw_rect(painter, bx, by + bh - (self.current_brake * bh), bx + bw, by + bh, brake_fill)
        if self.current_gas > 0:
            self.draw_rect(painter, x_g, by + bh - (self.current_gas * bh), x_g + bw, by + bh, gas_fill)

        y_gap = 3
        b_top_color = brake_fill if self.current_brake >= 0.99 else color_grid
        b_bot_color = brake_fill if self.current_brake <= 0.01 else color_grid
        self.draw_line(painter, bx + 2, by - y_gap, bx + bw - 2, by - y_gap, b_top_color, 2)
        self.draw_line(painter, bx + 2, by + bh + y_gap, bx + bw - 2, by + bh + y_gap, b_bot_color, 2)

        g_top_color = gas_fill if self.current_gas >= 0.99 else color_grid
        g_bot_color = gas_fill if self.current_gas <= 0.01 else color_grid
        self.draw_line(painter, x_g + 2, by - y_gap, x_g + bw - 2, by - y_gap, g_top_color, 2)
        self.draw_line(painter, x_g + 2, by + bh + y_gap, x_g + bw - 2, by + bh + y_gap, g_bot_color, 2)

        gear_x1 = 345;
        gear_x2 = 400;
        panel_y1 = 5;
        panel_y2 = 75
        self.draw_rounded_rect(painter, gear_x1, panel_y1, gear_x2, panel_y2, 8, color_slot)
        gear_text = self.current_gear_str if self.is_connected else "-"
        self.draw_text(painter, (gear_x1 + gear_x2) / 2, 40, gear_text, "Arial", 46, color_gear, "bold")

        speed_x1 = 405;
        speed_x2 = 465
        self.draw_rounded_rect(painter, speed_x1, panel_y1, speed_x2, panel_y2, 8, color_slot)
        speed_center_x = (speed_x1 + speed_x2) / 2

        if self.is_connected:
            self.draw_text(painter, speed_center_x, 18, str(int(self.top_speed)), "Arial", 14, color_top_speed, "bold")
            self.draw_text(painter, speed_center_x, 42, str(int(self.current_speed)), "Arial", 26, "#ffffff", "bold")
            self.draw_text(painter, speed_center_x, 66, str(int(self.min_speed)), "Arial", 14, color_gas, "bold")
        else:
            self.draw_text(painter, speed_center_x, 40, "---", "Arial", 20, "#888888", "bold")
            self.draw_text(painter, self.width() / 2, self.height() / 2, "等待游戏数据...", "Arial", 16, "#ffffff",
                           "bold")

    def update_data(self):
        shm = None
        try:
            try:
                shm = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), "acpmf_physics", access=mmap.ACCESS_READ)
            except FileNotFoundError:
                shm = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), "Local\\acpmf_physics", access=mmap.ACCESS_READ)

            shm.seek(0)
            data = shm.read(ctypes.sizeof(SPageFilePhysics))
            physics = SPageFilePhysics.from_buffer_copy(data)

            if physics.packetId == 0:
                self.is_connected = False
            else:
                self.is_connected = True
                self.current_speed = physics.speedKmh
                raw_gear = physics.gear
                self.current_gear_str = "R" if raw_gear == 0 else "N" if raw_gear == 1 else str(raw_gear - 1)

                self.current_gas = physics.gas
                self.current_brake = physics.brake
                self.gas_history.append(self.current_gas)
                self.brake_history.append(self.current_brake)
                self.abs_active = physics.abs > 0.01
                self.tc_active = physics.tc > 0.01

                if self.abs_active:
                    self._abs_hold = 8
                else:
                    self._abs_hold = max(0, self._abs_hold - 1)
                if self.tc_active:
                    self._tc_hold = 8
                else:
                    self._tc_hold = max(0, self._tc_hold - 1)
                self.abs_history.append(self._abs_hold > 0)
                self.tc_history.append(self._tc_hold > 0)

                # 最低弯速：油门松开时记录最低速，重新踩下油门时锁存
                # 速度趋势过滤：降档自动补油时速度仍在下降，不触发锁存
                if physics.gas > 0.05:
                    if not self.was_braking:
                        if self._blip_start_speed is None:
                            self._blip_start_speed = physics.speedKmh
                        if physics.speedKmh > self._blip_start_speed:
                            self.min_speed = self.temp_min
                            self.temp_max = physics.speedKmh
                            self.was_braking = True
                            self._blip_start_speed = None
                    if self.was_braking and physics.speedKmh > self.temp_max:
                        self.temp_max = physics.speedKmh
                else:
                    if self.was_braking:
                        self.top_speed = self.temp_max
                        self.temp_min = physics.speedKmh
                        self.was_braking = False
                    self._blip_start_speed = None
                    if physics.speedKmh < self.temp_min:
                        self.temp_min = physics.speedKmh
        except Exception:
            self.is_connected = False
        finally:
            if shm is not None:
                shm.close()

        self.update()


# ==================== 赛道圈速 & 维修区数据（雷达用） ====================
DEFAULT_LAP_TIMES = {
    "Misano World Circuit": "1:34.35", "Silverstone Circuit": "1:59.85",
    "Circuit Paul Ricard": "1:54.75", "Circuit de Barcelona-Catalunya": "1:46.59",
    "Brands Hatch": "1:26.70", "Hungaroring": "1:46.08",
    "Autodromo Nazionale Monza": "1:48.63", "Nürburgring Grand Prix Circuit": "1:55.77",
    "Circuit de Spa-Francorchamps": "2:18.72", "Circuit Zandvoort": "1:37.41",
    "Circuit Zolder": "1:29.76", "Kyalami Grand Prix Circuit": "1:42.00",
    "Suzuka Circuit": "2:01.38", "WeatherTech Raceway Laguna Seca": "1:23.13",
    "Mount Panorama Circuit, Bathurst": "2:02.40",
    "Autodromo Enzo e Dino Ferrari (Imola)": "1:41.49",
    "Donington Park": "1:28.74", "Oulton Park": "1:29.25",
    "Snetterton Circuit": "1:48.12", "Watkins Glen International": "1:45.06",
    "Circuit of the Americas (COTA)": "2:09.54", "Indianapolis Motor Speedway": "1:36.90",
    "Circuit Ricardo Tormo (Valencia)": "1:32.31", "Red Bull Ring": "1:29.25",
    "Nürburgring 24h Circuit": "8:14.70",
}
PIT_LANE_TIMES = {
    "Circuit de Spa-Francorchamps": 71.6, "Silverstone Circuit": 69.8,
    "Circuit Zandvoort": 52.6, "Circuit Ricardo Tormo (Valencia)": 47.3,
    "Circuit de Barcelona-Catalunya": 39.5, "Autodromo Enzo e Dino Ferrari (Imola)": 39.5,
    "Misano World Circuit": 30.0, "Circuit Zolder": 29.0,
    "Suzuka Circuit": 28.4, "Kyalami Grand Prix Circuit": 27.2,
    "Circuit Paul Ricard": 27.0, "Circuit of the Americas (COTA)": 25.0,
    "Donington Park": 25.0, "Brands Hatch Circuit": 25.0,
    "Autodromo Nazionale Monza": 24.3, "Nürburgring Grand Prix Circuit": 22.5,
    "Nürburgring 24h Circuit": 22.5, "Hungaroring": 21.9,
    "Red Bull Ring": 20.3, "WeatherTech Raceway Laguna Seca": 20.0,
    "Mount Panorama Circuit, Bathurst": 20.0, "Watkins Glen International": 20.0,
    "Indianapolis Motor Speedway": 20.0, "Snetterton Circuit": 19.0,
    "Oulton Park": 13.0,
}
_GENERIC_WORDS = {
    "circuit", "circuito", "autodromo", "nazionale", "track", "raceway",
    "grand", "prix", "international", "world", "park", "de", "del", "di",
    "of", "the", "mount", "panorama", "weathertech", "cota",
    "enzo", "e", "dino", "speedway", "centre", "center",
    "ricardo", "tormo", "ferrari",
}


def _normalize_track(name):
    s = name.lower()
    for ch in "-_'.,:;!?()[]":
        s = s.replace(ch, " ")
    words = s.split()
    return frozenset(w for w in words if w not in _GENERIC_WORDS and len(w) > 1)


_NORM_IDX_LAP = {_normalize_track(k): k for k in DEFAULT_LAP_TIMES}
_NORM_IDX_PIT = {_normalize_track(k): k for k in PIT_LANE_TIMES}


def _resolve_key(idx, raw):
    sig = _normalize_track(raw)
    return idx.get(sig)


def _shorten_name(raw):
    """从 ACC 赛道名提取简短名称"""
    s = raw.strip()
    prefixes = [
        "Circuit de ", "Circuito de ", "Autodromo Nazionale ",
        "Autodromo Enzo e Dino Ferrari (", "Autodromo ",
        "WeatherTech Raceway ", "Mount Panorama Circuit, ",
        "Circuit of the Americas (", "Circuit Ricardo Tormo (",
    ]
    for p in prefixes:
        if s.startswith(p):
            s = s[len(p):]
            s = s.rstrip(")")
            break
    suffixes = [
        " Grand Prix Circuit", " World Circuit", " Circuit",
        " Motor Speedway", " International", " Park",
    ]
    for suf in suffixes:
        if s.endswith(suf):
            s = s[:-len(suf)]
            break
    return s


def parse_laptime(t):
    parts = t.replace(",", ".").split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(parts[0])


# ==========================================================
# 模块 4：相对雷达 (含赛车车损换算)
# ==========================================================
class ACCRadarOverlay(OverlayBase):
    def __init__(self):
        super().__init__("radar", 250, 250, 0.85)
        self.pit_coeff = 0.0
        self.pit_total_sec = 0.0
        self._lap_sec = 0.0
        self._pit_lane_sec = None
        self._track_display = ""
        self._tire_change = True
        self.center_x = self.width() / 2
        self.center_y = self.height() / 2
        self.radius = 90

        self.track_data = {}
        self.my_car_index = None
        self.current_session_type = -1

        # 车损数据 [Front, Rear, Left, Right, Center]
        self.car_damage = [0.0, 0.0, 0.0, 0.0, 0.0]

        self.last_data_time = time.time()
        self.last_reconnect_time = time.time()
        self.client = None

        self.connect_client()
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.update_radar_state)
        self.data_timer.start(30)
        self.damage_scale = 7.08

    def wheelEvent(self, event):
        pass

    def mouseReleaseEvent(self, event):
        dx = event.position().x() - self.center_x
        dy = event.position().y() - self.center_y
        if dx * dx + dy * dy <= self.radius * self.radius:
            self._tire_change = not self._tire_change
            self.update()

    def connect_client(self):
        if self.client is not None:
            try:
                self.client.stop()
            except:
                pass
        self.client = AccClient()
        self.client.onRealtimeUpdate.subscribe(self.on_global_update)
        self.client.onRealtimeCarUpdate.subscribe(self.on_car_update)
        self.client.onTrackDataUpdate.subscribe(self.on_track_data)
        try:
            self.client.start(ACC_IP, ACC_PORT, ACC_PASSWORD)
        except Exception:
            pass

    def on_track_data(self, event):
        raw_name = event.content.trackName
        if not raw_name:
            return
        self._track_display = _shorten_name(raw_name)
        lap_key = _resolve_key(_NORM_IDX_LAP, raw_name)
        pit_key = _resolve_key(_NORM_IDX_PIT, raw_name)
        if lap_key and pit_key:
            self._lap_sec = parse_laptime(DEFAULT_LAP_TIMES[lap_key])
            self._pit_lane_sec = PIT_LANE_TIMES[pit_key]
        self.update()

    def _update_pit_total(self):
        if self._lap_sec and self._pit_lane_sec is not None:
            dmg_sec = sum(self.car_damage) / self.damage_scale
            stop_sec = 30.0 if self._tire_change else 15.0
            self.pit_total_sec = self._pit_lane_sec + stop_sec + dmg_sec
            self.pit_coeff = self.pit_total_sec / self._lap_sec

    def on_global_update(self, event: Event):
        self.last_data_time = time.time()
        new_index = event.content.focusedCarIndex
        if new_index != self.my_car_index: self.my_car_index = new_index

    def on_car_update(self, event: Event):
        self.last_data_time = time.time()
        self.track_data[event.content.carIndex] = event.content.splinePosition

    def update_radar_state(self):
        shm_physics = None
        try:
            try:
                shm_physics = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), "acpmf_physics", access=mmap.ACCESS_READ)
            except FileNotFoundError:
                shm_physics = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), "Local\\acpmf_physics", access=mmap.ACCESS_READ)

            shm_physics.seek(0)
            data = shm_physics.read(ctypes.sizeof(SPageFilePhysics))
            physics = SPageFilePhysics.from_buffer_copy(data)

            if physics.packetId > 0:
                for i in range(5):
                    self.car_damage[i] = physics.carDamage[i]
                self._update_pit_total()
            else:
                for i in range(5):
                    self.car_damage[i] = 0.0
        except Exception:
            for i in range(5):
                self.car_damage[i] = 0.0
        finally:
            if shm_physics is not None:
                shm_physics.close()

        # 检测 session 变更，清空上局残留的车辆数据
        shm_graphics = None
        try:
            read_sz = ctypes.sizeof(SPageFileGraphics)
            try:
                shm_graphics = mmap.mmap(-1, read_sz, "acpmf_graphics", access=mmap.ACCESS_READ)
            except FileNotFoundError:
                shm_graphics = mmap.mmap(-1, read_sz, "Local\\acpmf_graphics", access=mmap.ACCESS_READ)
            shm_graphics.seek(0)
            raw = shm_graphics.read(read_sz)
            gs = SPageFileGraphics.from_buffer_copy(raw)
            if gs.packetId > 0:
                if gs.session != self.current_session_type:
                    self.current_session_type = gs.session
                    self.track_data.clear()
                    self.my_car_index = None
            else:
                self.track_data.clear()
                self.my_car_index = None
        except Exception:
            pass
        finally:
            if shm_graphics is not None:
                shm_graphics.close()

        self.update()
    
    def get_damage_color(self, raw_val):
        sec = raw_val / self.damage_scale
        if sec <= 0.5:
            return "#3a3a40"  # 小于0.5秒的微小形变视为无受损 (暗色)
        elif sec < 5.0:
            return "#f1c40f"  # 轻度受损 (黄)
        elif sec < 15.0:
            return "#e67e22"  # 中度受损 (橙)
        else:
            return "#e74c3c"  # 严重受损 (红)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_r = self.radius + 20
        painter.setBrush(QColor("#222225"))
        painter.setPen(QPen(QColor("#3a3a40"), 1.5))
        painter.drawEllipse(QPointF(self.center_x, self.center_y), bg_r, bg_r)

        pen = QPen(QColor("#55555d"), 1.5, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 4])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(self.center_x, self.center_y), self.radius, self.radius)

        current_time = time.time()

        if current_time - self.last_data_time > 3.0:
            self.draw_text(painter, self.center_x, self.center_y, "连接断开...", "Microsoft YaHei", 11, "#ffaa00",
                           "bold")
            if current_time - self.last_reconnect_time > 5.0:
                self.connect_client()
                self.last_reconnect_time = current_time
        elif self.my_car_index is None or self.my_car_index not in self.track_data:
            self.draw_text(painter, self.center_x, self.center_y, "等待同步...", "Microsoft YaHei", 11, "#888888",
                           "bold")
        else:
            my_spline = self.track_data[self.my_car_index]

            if self.pit_coeff > 0:
                arc_pen = QPen(QColor("#6a3812"), 14)
                painter.setPen(arc_pen)
                painter.drawArc(
                    QRectF(self.center_x - self.radius, self.center_y - self.radius, self.radius * 2, self.radius * 2),
                    90 * 16, int(360 * self.pit_coeff * 16))

            # --- 赛道名 ---
            if self._track_display:
                self.draw_text(painter, self.center_x, self.center_y - 50, self._track_display, "Microsoft YaHei", 10,
                               "#aaaaaa", "bold")

            # --- 换胎开关（车损左侧） ---
            # 竖向换胎开关（圆环与车损之间）
            tx = self.center_x - 52
            ty0 = self.center_y - 22
            ty1 = self.center_y - 8
            if self._tire_change:
                self.draw_text(painter, tx, ty0, "▎换胎", "Microsoft YaHei", 10, "#33cc33", "bold")
                self.draw_text(painter, tx, ty1, "  不换", "Microsoft YaHei", 9, "#555555")
            else:
                self.draw_text(painter, tx, ty0, "  换胎", "Microsoft YaHei", 9, "#555555")
                self.draw_text(painter, tx, ty1, "▎不换", "Microsoft YaHei", 10, "#888888", "bold")

            # --- 车损 UI (放大并居中偏上) ---
            cx = self.center_x
            cy = self.center_y - 12

            def draw_dmg_rect(val, rx, ry, rw, rh):
                painter.setBrush(QColor(self.get_damage_color(val)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(QRectF(rx, ry, rw, rh))

            draw_dmg_rect(self.car_damage[4], cx - 12, cy - 18, 24, 36)  # Center
            draw_dmg_rect(self.car_damage[0], cx - 12, cy - 26, 24, 6)  # Front
            draw_dmg_rect(self.car_damage[1], cx - 12, cy + 20, 24, 6)  # Rear
            draw_dmg_rect(self.car_damage[2], cx - 20, cy - 18, 6, 36)  # Left
            draw_dmg_rect(self.car_damage[3], cx + 14, cy - 18, 6, 36)  # Right

            # --- 文本信息显示 ---
            total_raw_dmg = sum(self.car_damage)
            repair_seconds = total_raw_dmg / self.damage_scale

            if repair_seconds > 0.5:  # 大于0.5秒才显示，过滤掉轻微掉漆或极其微小的碰撞
                # 颜色逻辑与下方同步
                dmg_color = "#e74c3c" if repair_seconds > 15 else ("#e67e22" if repair_seconds > 5 else "#f1c40f")
                # 使用 :.1f 保留一位小数，例如 11.0 秒
                self.draw_text(painter, cx, cy + 40, f"车损：{repair_seconds:.1f} 秒", "Microsoft YaHei", 10, dmg_color,
                               "bold")

            # --- 辅助数据整体下移 ---
            self.draw_text(painter, self.center_x, self.center_y + 55, f"Cars: {len(self.track_data)}", "Arial", 9,
                           "#666666")
            if self.pit_coeff > 0:
                self.draw_text(painter, self.center_x, self.center_y + 73, f"进站耗时:{self.pit_total_sec:.0f}秒", "Microsoft YaHei", 10,
                               "#ff8833", "bold")

            # --- 绘制周围车辆 ---
            for car_idx, spline_pos in self.track_data.items():
                if spline_pos is None: continue
                delta_spline = spline_pos - my_spline
                angle = delta_spline * 2 * math.pi
                x = self.center_x + self.radius * math.sin(angle)
                y = self.center_y - self.radius * math.cos(angle)

                if car_idx == self.my_car_index:
                    painter.setBrush(QColor("#ffcc00"))
                    painter.setPen(QPen(QColor("#ffffff"), 2))
                    painter.drawEllipse(QPointF(x, y), 7, 7)
                else:
                    if delta_spline > 0.5:
                        delta_spline -= 1.0
                    elif delta_spline < -0.5:
                        delta_spline += 1.0
                    color = "#ff4444" if delta_spline > 0 else "#00ffff"
                    painter.setBrush(QColor(color))
                    painter.setPen(QPen(QColor("#ffffff"), 1.5))
                    painter.drawEllipse(QPointF(x, y), 5, 5)

    def closeEvent(self, event):
        if self.client:
            try:
                self.client.stop()
            except:
                pass
        super().closeEvent(event)

# ==========================================================
# 模块 5：实时圈速秒差条带 (Delta)
# ==========================================================
class SPageFileGraphicsDelta(ctypes.Structure):
    """
    专用的局部 ctypes 结构体，精准映射 acpmf_graphics 内存
    直到获取到 iDeltaLapTime (实时秒差) 为止，避免全局污染
    """
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),
        ("session", ctypes.c_int),
        ("currentTime", ctypes.c_wchar * 15),
        ("lastTime", ctypes.c_wchar * 15),
        ("bestTime", ctypes.c_wchar * 15),
        ("split", ctypes.c_wchar * 15),
        ("completedLaps", ctypes.c_int),
        ("position", ctypes.c_int),
        ("iCurrentTime", ctypes.c_int),
        ("iLastTime", ctypes.c_int),
        ("iBestTime", ctypes.c_int),
        ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float),
        ("isInPit", ctypes.c_int),
        ("currentSectorIndex", ctypes.c_int),
        ("lastSectorTime", ctypes.c_int),
        ("numberOfLaps", ctypes.c_int),
        ("tyreCompound", ctypes.c_wchar * 33),
        ("replayTimeMultiplier", ctypes.c_float),
        ("normalizedCarPosition", ctypes.c_float),
        ("activeCars", ctypes.c_int),
        ("carCoordinates", (ctypes.c_float * 3) * 60),
        ("carID", ctypes.c_int * 60),
        ("playerCarID", ctypes.c_int),
        ("penaltyTime", ctypes.c_float),
        ("flag", ctypes.c_int),
        ("penalty", ctypes.c_int),
        ("idealLineOn", ctypes.c_int),
        ("isInPitLane", ctypes.c_int),
        ("surfaceGrip", ctypes.c_float),
        ("mandatoryPitDone", ctypes.c_int),
        ("windSpeed", ctypes.c_float),
        ("windDirection", ctypes.c_float),
        ("isSetupMenuVisible", ctypes.c_int),
        ("mainDisplayIndex", ctypes.c_int),
        ("secondaryDisplayIndex", ctypes.c_int),
        ("TC", ctypes.c_int),
        ("TCCut", ctypes.c_int),
        ("EngineMap", ctypes.c_int),
        ("ABS", ctypes.c_int),
        ("fuelXLap", ctypes.c_int),
        ("isRainLightsOn", ctypes.c_int),
        ("isFlashingLightsOn", ctypes.c_int),
        ("lightStage", ctypes.c_int),
        ("exhaustTemperature", ctypes.c_float),
        ("wiperLV", ctypes.c_int),
        ("DriverStintTotalTimeLeft", ctypes.c_int),
        ("DriverStintTimeLeft", ctypes.c_int),
        ("rainTyres", ctypes.c_int),
        ("sessionIndex", ctypes.c_int),
        ("usedFuel", ctypes.c_float),
        ("deltaLapTime", ctypes.c_wchar * 15),
        ("iDeltaLapTime", ctypes.c_int) # 这里就是实时的毫秒级 Delta
    ]

class ACCDeltaBar(OverlayBase):
    def __init__(self):
        super().__init__("delta", 360, 50, 0.85)
        self.refresh_rate = 30
        self.is_connected = False
        self.delta_time = 0.0
        
        # 条带的视觉上限，1.5表示正负1.5秒时条带拉满
        self.max_delta_display = 1.5

        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.update_data)
        self.data_timer.start(self.refresh_rate)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.draw_rounded_rect(painter, 1, 1, self.width() - 1, self.height() - 1, 10, "#222225")

        cx = self.width() / 2
        cy = self.height() / 2

        if not self.is_connected:
            self.draw_text(painter, cx, cy, "等待数据...", "Arial", 11, "#888888", "bold")
            return

        bar_max_width = (self.width() - 30) / 2
        bar_height = 18
        bar_y = cy - bar_height / 2

        self.draw_rounded_rect(painter, cx - bar_max_width, bar_y, cx + bar_max_width, bar_y + bar_height, 4, "#333338")

        clamped_delta = max(-self.max_delta_display, min(self.max_delta_display, self.delta_time))
        current_bar_width = (abs(clamped_delta) / self.max_delta_display) * bar_max_width

        # 快了（负数），向右绘制绿条
        if self.delta_time < -0.01:
            self.draw_rounded_rect(painter, cx, bar_y, cx + current_bar_width, bar_y + bar_height, 4, "#2ecc71")
        # 慢了（正数），向左绘制红条
        elif self.delta_time > 0.01:
            self.draw_rounded_rect(painter, cx - current_bar_width, bar_y, cx, bar_y + bar_height, 4, "#e74c3c")

        # 绘制中心基准线
        self.draw_line(painter, cx, bar_y - 4, cx, bar_y + bar_height + 4, "#ffffff", 2.0)

        # UI 显示修正：如果没开始计时，显示横线
        if self.delta_time == 0.0 and current_bar_width == 0:
            text_str = "--.--"
        else:
            text_str = f"{self.delta_time:+.2f}"
        
        self.draw_text(painter, cx + 1, cy + 1, text_str, "Arial", 14, "#000000", "bold")
        self.draw_text(painter, cx, cy, text_str, "Arial", 14, "#ffffff", "bold")

    def update_data(self):
        shm_graphics = None
        try:
            read_sz = ctypes.sizeof(SPageFileGraphicsDelta)
            try:
                shm_graphics = mmap.mmap(-1, read_sz, "acpmf_graphics", access=mmap.ACCESS_READ)
            except FileNotFoundError:
                shm_graphics = mmap.mmap(-1, read_sz, "Local\\acpmf_graphics", access=mmap.ACCESS_READ)

            shm_graphics.seek(0)
            data = shm_graphics.read(read_sz)
            graphics = SPageFileGraphicsDelta.from_buffer_copy(data)

            if graphics.packetId == 0:
                self.is_connected = False
            else:
                self.is_connected = True
                raw_delta = graphics.iDeltaLapTime
                
                # 在 ACC 中，没有参考圈或出场圈时，iDeltaLapTime 会返回极值 2147483647
                if raw_delta == 2147483647:
                    self.delta_time = 0.0
                else:
                    self.delta_time = raw_delta / 1000.0

                # 超过 ±20 秒后不再继续累加显示（比赛结束/飞行圈收工后）
                self.delta_time = max(-20.0, min(20.0, self.delta_time))
        except Exception:
            self.is_connected = False
        finally:
            if shm_graphics is not None:
                shm_graphics.close()

        self.update()

# ==========================================================
# 启动路由
# ==========================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    if len(sys.argv) < 2:
        print("请提供启动模块: radar, overlay, tyres, timer, delta")
        sys.exit(1)

    module_to_run = sys.argv[1]

    if module_to_run == "radar":
        window = ACCRadarOverlay()
    elif module_to_run == "overlay":
        window = ACCOverlay()
    elif module_to_run == "tyres":
        window = ACCTyrePanel()
    elif module_to_run == "timer":
        window = ACCTimer()
    elif module_to_run == "delta":
        window = ACCDeltaBar()
    else:
        print(f"未知模块: {module_to_run}")
        sys.exit(1)

    window.show()
    sys.exit(app.exec())