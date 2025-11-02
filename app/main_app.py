# gui_pyside6_final.py
"""
GeoAttendance — Smart Student Attendance UI (improved visuals + fixed stylesheet warnings)

Changes & fixes:
- Removed unsupported CSS "transform" property (fixes the repeated "Unknown property transform" warnings).
- Reworked GlowButton: hover/press lift is animated via a QGraphicsDropShadowEffect (no stylesheet transform).
- Overhauled CameraView's detection ring: multi-layered shimmer, bloom (additive glow), dynamic pulses and richer sparkle.
- Minor UI polish and safer icon loading.
- Backend usage unchanged (keeps imports for app.auth/app.attendance/app.database).

"""
import sys
import os
import time
import traceback
import random
import math
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer, Property
from PySide6.QtGui import (
    QImage, QPixmap, QFont, QColor, QPainter, QPalette, QPen, QBrush,
    QConicalGradient, QRadialGradient, QPainterPath
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QFormLayout, QFrame, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QGraphicsDropShadowEffect,
    QStackedWidget
)

import cv2
from PIL import Image

# Import your backend (keep project structure)
try:
    from app.auth import AuthManager
    from app.attendance import AttendanceManager
    from app.database import init_db, get_attendance_history
except Exception as e:
    print("Error importing backend modules (app.auth / app.attendance / app.database).")
    print("Make sure you run this script from your project root and app package exists.")
    raise

# ---------------- Utilities ----------------

def set_drop_shadow(widget, blur=18, x_offset=0, y_offset=8, color=QColor(0,0,0,160)):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(x_offset, y_offset)
    eff.setColor(color)
    widget.setGraphicsEffect(eff)

class Toast(QWidget):
    """Small transient message with improved styling and placement."""
    def __init__(self, parent, text, duration=2500):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.duration = duration

        self.bg = QFrame(self)
        # softer cyan gradient with glass blur look
        self.bg.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(10,200,255,0.95), stop:1 rgba(80,140,255,0.92));
                border-radius: 12px;
            }
        """)
        set_drop_shadow(self.bg, blur=22, y_offset=8, color=QColor(6,120,160,140))
        self.label = QLabel(text, self.bg)
        self.label.setStyleSheet("color: #041017; padding: 12px 16px;")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout = QVBoxLayout(self.bg)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.label)
        self.bg.adjustSize()
        self.resize(self.bg.size())

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)
        self.timer.start(self.duration)

        self.anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        self.anim.setDuration(420)
        self.anim.finished.connect(self.close)
        self.setWindowOpacity(0.0)

        # entrance animation (fade in)
        in_anim = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        in_anim.setDuration(260)
        in_anim.setStartValue(0.0)
        in_anim.setEndValue(1.0)
        in_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def show_at(self, global_point):
        self.move(global_point)
        self.show()

    def fade_out(self):
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()

# ---------------- Background widget (paints animated starfield) ----------------

class BackgroundWidget(QWidget):
    """Widget that paints an animated starfield and hosts child layouts on top."""
    def __init__(self, parent=None, star_count=120):
        super().__init__(parent)
        self.stars = []
        self.star_count = star_count
        self._init_stars()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(36)  # ~28 FPS for smoother motion

    def _init_stars(self):
        w = max(900, self.width() or 900)
        h = max(650, self.height() or 650)
        self.stars = []
        for _ in range(self.star_count):
            x = random.uniform(0, w)
            y = random.uniform(0, h)
            size = random.uniform(0.5, 3.8)
            speed = (size / 3.8) * 1.6 + 0.25
            color = QColor(200 + int((size/3.8)*55), 220, 255, 180)
            self.stars.append([x, y, size, speed, color])

    def resizeEvent(self, event):
        self._init_stars()
        super().resizeEvent(event)

    def _tick(self):
        h = self.height() or 650
        for s in self.stars:
            s[1] += s[3]
            if s[1] > h + 12:
                s[1] = -12
                s[0] = random.uniform(0, self.width() or 900)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # radial gradient background — deeper, subtle vignette
        grad = QtGui.QRadialGradient(self.width()*0.25, self.height()*0.18, max(self.width(), self.height())*1.5)
        grad.setColorAt(0.0, QColor(12,18,34,235))
        grad.setColorAt(0.6, QColor(8,12,24,235))
        grad.setColorAt(1.0, QColor(3,6,12,255))
        painter.fillRect(self.rect(), grad)
        # soft nebula overlay
        painter.setOpacity(0.08)
        brush = QtGui.QBrush(QColor(20, 40, 70, 180))
        painter.fillRect(self.rect(), brush)
        painter.setOpacity(1.0)
        # stars
        for x, y, size, _, color in self.stars:
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QtCore.QPointF(x, y), size, size)

# ---------------- Worker threads ----------------

class CameraWorker(QThread):
    frame_ready = Signal(QImage)
    fps_signal = Signal(float)
    error = Signal(str)

    def __init__(self, attendance_manager, parent=None):
        super().__init__(parent)
        self.attendance_manager = attendance_manager
        self.running = False

    def run(self):
        self.running = True
        last_time = time.time()
        frames = 0
        try:
            while self.running:
                cap = getattr(self.attendance_manager, "cap", None)
                if cap is None or not cap.isOpened():
                    self.msleep(120)
                    continue
                ret, frame = cap.read()
                if not ret:
                    self.msleep(30)
                    continue
                frames += 1
                now = time.time()
                if (now - last_time) >= 1.0:
                    fps = frames / (now - last_time)
                    self.fps_signal.emit(fps)
                    last_time = now
                    frames = 0
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                # scale to a reasonable size to save CPUs; keep decent square for the circular crop
                scaled = qimg.scaled(900, 900, Qt.KeepAspectRatio)
                self.frame_ready.emit(scaled)
                self.msleep(22)
        except Exception as e:
            self.error.emit(str(e))
            traceback.print_exc()

    def stop(self):
        self.running = False
        self.wait(600)

class AttendanceWorker(QThread):
    finished = Signal(bool, str)
    def __init__(self, attendance_manager, student_id, name, photo_path=None, parent=None):
        super().__init__(parent)
        self.attendance_manager = attendance_manager
        self.student_id = student_id
        self.name = name
        self.photo_path = photo_path

    def run(self):
        try:
            def cb(success, message):
                self.finished.emit(bool(success), str(message))
            # call backend; expects a callback signature
            self.attendance_manager.detect_and_mark(self.student_id, self.name, self.photo_path, cb)
        except Exception as e:
            self.finished.emit(False, f"Error: {e}")
            traceback.print_exc()

# ---------------- UI components ----------------

class GlassFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # updated frosted glass effect with subtle border + inner glow
        self.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(255,255,255,0.03), stop:1 rgba(255,255,255,0.02));
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.06);
            }
        """)
        set_drop_shadow(self, blur=20, y_offset=10, color=QColor(2,8,14,140))

class GlowButton(QPushButton):
    """
    Button with a polished gradient and an animated shadow-based 'lift' on hover/press.
    This avoids using unsupported stylesheet properties like 'transform' and uses a real
    QGraphicsDropShadowEffect animated through Qt properties.
    """
    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, parent)
        self.setMinimumHeight(42)
        self.setCursor(QtGui.QCursor(Qt.PointingHandCursor))
        # subtle icon support
        if icon:
            self.setIcon(icon)
            self.setIconSize(QtCore.QSize(18,18))

        # polished style: gradient, hover lift, focus ring
        self.setStyleSheet("""
            QPushButton {
                color: #e8fbff;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                           stop:0 rgba(0,200,255,0.12), stop:1 rgba(18,22,44,0.92));
                border-radius: 11px;
                padding: 8px 14px;
                font-weight: 700;
                border: 1px solid rgba(255,255,255,0.04);
            }
            QPushButton:hover {
                /* visual change (no transform) */
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                           stop:0 rgba(0,230,255,0.16), stop:1 rgba(28,32,56,0.98));
            }
            QPushButton:pressed {
                background: rgba(0,180,220,0.12);
            }
            QPushButton:focus {
                border: 1px solid rgba(100,220,255,0.9);
            }
        """)

        # animated shadow effect
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(14.0)
        self._shadow.setOffset(0.0, 6.0)
        self._shadow.setColor(QColor(6, 170, 210, 135))
        self.setGraphicsEffect(self._shadow)

        # animations
        self._lift_group = QtCore.QParallelAnimationGroup(self)
        self._anim_blur = QtCore.QPropertyAnimation(self, b"shadowBlur", self)
        self._anim_blur.setDuration(260)
        self._anim_blur.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._anim_offset = QtCore.QPropertyAnimation(self, b"shadowOffsetY", self)
        self._anim_offset.setDuration(260)
        self._anim_offset.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._lift_group.addAnimation(self._anim_blur)
        self._lift_group.addAnimation(self._anim_offset)

        # pressed animation (quick)
        self._press_group = QtCore.QParallelAnimationGroup(self)
        self._anim_press_blur = QtCore.QPropertyAnimation(self, b"shadowBlur", self)
        self._anim_press_blur.setDuration(110)
        self._anim_press_blur.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._anim_press_offset = QtCore.QPropertyAnimation(self, b"shadowOffsetY", self)
        self._anim_press_offset.setDuration(110)
        self._anim_press_offset.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._press_group.addAnimation(self._anim_press_blur)
        self._press_group.addAnimation(self._anim_press_offset)

        # hook press/release
        self.pressed.connect(self._on_pressed)
        self.released.connect(self._on_released)

    # Qt property wrappers so QPropertyAnimation can animate them
    def getShadowBlur(self):
        return float(self._shadow.blurRadius())

    def setShadowBlur(self, v):
        self._shadow.setBlurRadius(float(v))

    def getShadowOffsetY(self):
        return float(self._shadow.offset().y())

    def setShadowOffsetY(self, v):
        off = self._shadow.offset()
        self._shadow.setOffset(off.x(), float(v))

    shadowBlur = Property(float, getShadowBlur, setShadowBlur)
    shadowOffsetY = Property(float, getShadowOffsetY, setShadowOffsetY)

    def enterEvent(self, ev):
        # animate to lifted state
        self._anim_blur.stop()
        self._anim_offset.stop()
        self._anim_blur.setStartValue(self.getShadowBlur())
        self._anim_blur.setEndValue(26.0)
        self._anim_offset.setStartValue(self.getShadowOffsetY())
        self._anim_offset.setEndValue(2.0)
        self._lift_group.start()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        # return to normal state
        self._anim_blur.stop()
        self._anim_offset.stop()
        self._anim_blur.setStartValue(self.getShadowBlur())
        self._anim_blur.setEndValue(14.0)
        self._anim_offset.setStartValue(self.getShadowOffsetY())
        self._anim_offset.setEndValue(6.0)
        self._lift_group.start()
        super().leaveEvent(ev)

    def _on_pressed(self):
        # quick pressed effect (slightly reduce blur and increase offset to look pressed)
        self._anim_press_blur.stop()
        self._anim_press_offset.stop()
        self._anim_press_blur.setStartValue(self.getShadowBlur())
        self._anim_press_blur.setEndValue(max(8.0, self.getShadowBlur() * 0.6))
        self._anim_press_offset.setStartValue(self.getShadowOffsetY())
        self._anim_press_offset.setEndValue(self.getShadowOffsetY() + 6.0)
        self._press_group.start()

    def _on_released(self):
        # restore to hover/normal state quickly
        self._anim_press_blur.stop()
        self._anim_press_offset.stop()
        # animate back to typical hover blur/offset (if mouse still over, keep "hovered" target)
        target_blur = 26.0 if self.underMouse() else 14.0
        target_offset = 2.0 if self.underMouse() else 6.0
        self._anim_press_blur.setStartValue(self.getShadowBlur())
        self._anim_press_blur.setEndValue(target_blur)
        self._anim_press_offset.setStartValue(self.getShadowOffsetY())
        self._anim_press_offset.setEndValue(target_offset)
        self._press_group.start()

class CameraView(QWidget):
    """Circular camera view with a richer animated detection ring (shimmer + bloom).
    API:
      set_image(QImage)
      start_pulse(duration_ms=1800)
      set_result(success: bool|None, hold_ms=900)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._qimage = None
        self._cached_circle_pixmap = None
        self._cached_diameter = 0
        self._angle = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)  # ~33 FPS animation
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(260, 260)
        # pulse / animation controls
        self._pulse_active = False
        self._pulse_start = 0.0
        self._pulse_duration = 0.0
        # colors: current and target (we'll lerp toward target for smooth transition)
        self._col_yellow = QColor(255, 220, 30)   # electric yellow default
        self._col_green = QColor(80, 220, 110)    # success
        self._col_red = QColor(255, 80, 80)       # failure
        # current color starts as yellow
        self._current_color = QColor(self._col_yellow)
        self._target_color = QColor(self._col_yellow)
        # after showing success/fail, return to default after a timeout (ms)
        self._return_timer = QTimer(self)
        self._return_timer.setSingleShot(True)
        self._return_timer.timeout.connect(self._return_to_yellow)
        # shimmer speed multiplier
        self._shimmer_speed = 1.0
        # aesthetic parameters
        self._bloom_strength = 1.0

    def sizeHint(self):
        return QtCore.QSize(520, 520)

    @Slot(QImage)
    def set_image(self, qimg):
        # store image and invalidate cached circular pixmap if size changed
        if qimg is None:
            self._qimage = None
            self._cached_circle_pixmap = None
            self._cached_diameter = 0
        else:
            self._qimage = qimg.copy()
            self._cached_circle_pixmap = None
            self._cached_diameter = 0
        self.update()

    def clear(self):
        self._qimage = None
        self._cached_circle_pixmap = None
        self._cached_diameter = 0
        self.update()

    def start_pulse(self, duration_ms=1800):
        self._pulse_active = True
        self._pulse_start = time.time()
        self._pulse_duration = duration_ms / 1000.0

    def set_result(self, success: bool | None, hold_ms: int = 900):
        """
        success = True  -> animate ring to green
        success = False -> animate ring to red
        success = None  -> back to yellow immediately
        hold_ms = how long to keep success/fail color before returning to yellow
        """
        if success is True:
            self._target_color = QColor(self._col_green)
            self._shimmer_speed = 1.8
            self._bloom_strength = 1.6
        elif success is False:
            self._target_color = QColor(self._col_red)
            self._shimmer_speed = 1.2
            self._bloom_strength = 1.4
        else:
            self._target_color = QColor(self._col_yellow)
            self._shimmer_speed = 1.0
            self._bloom_strength = 1.0

        # emphasis pulse
        try:
            self.start_pulse(max(500, hold_ms))
        except Exception:
            pass
        if success is not None:
            self._return_timer.start(hold_ms)

    def _return_to_yellow(self):
        self._target_color = QColor(self._col_yellow)
        self._shimmer_speed = 1.0
        self._bloom_strength = 1.0

    def _tick(self):
        # rotate shimmer
        self._angle = (self._angle + 4.6 * self._shimmer_speed) % 360.0
        # manage pulse lifetime
        if self._pulse_active:
            elapsed = time.time() - self._pulse_start
            if elapsed > self._pulse_duration:
                self._pulse_active = False
        # smooth color interpolation toward target (lerp each channel)
        lerp_factor = 0.16  # slightly faster color change
        r = int(self._current_color.red()   + (self._target_color.red()   - self._current_color.red())   * lerp_factor)
        g = int(self._current_color.green() + (self._target_color.green() - self._current_color.green()) * lerp_factor)
        b = int(self._current_color.blue()  + (self._target_color.blue()  - self._current_color.blue())  * lerp_factor)
        a = int(self._current_color.alpha() + (self._target_color.alpha() - self._current_color.alpha()) * lerp_factor)
        self._current_color = QColor(r, g, b, a)
        self.update()

    def _make_circular_pixmap(self, diameter):
        """Create and cache a circular-cropped pixmap sized to diameter."""
        if not self._qimage:
            return None
        if self._cached_circle_pixmap is not None and self._cached_diameter == diameter:
            return self._cached_circle_pixmap
        # create pixmap sized to diameter
        D = max(2, int(math.ceil(diameter)))
        circle_pm = QPixmap(D, D)
        circle_pm.fill(Qt.transparent)
        p = QPainter(circle_pm)
        p.setRenderHint(QPainter.Antialiasing)
        # draw circular clip path
        path = QPainterPath()
        path.addEllipse(0, 0, D, D)
        p.setClipPath(path)
        # scale source image to fill circle (aspect-ratio by expanding)
        src_pix = QPixmap.fromImage(self._qimage)
        # ensure we scale to cover the circle (KeepAspectRatioByExpanding)
        src_scaled = src_pix.scaled(D, D, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        sx = (src_scaled.width() - D) // 2
        sy = (src_scaled.height() - D) // 2
        p.drawPixmap(-sx, -sy, src_scaled)
        p.end()
        self._cached_circle_pixmap = circle_pm
        self._cached_diameter = diameter
        return circle_pm

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        # compute central circle rect
        diameter = max(60, min(w, h) - 36)
        cx = w / 2
        cy = h / 2
        circle_rect = QtCore.QRectF(cx - diameter/2, cy - diameter/2, diameter, diameter)

        # draw subtle background disk (soft multi-stop radial gradient)
        bg_grad = QRadialGradient(circle_rect.center(), diameter * 0.6)
        bg_grad.setColorAt(0.0, QColor(18, 22, 32, 230))
        bg_grad.setColorAt(0.6, QColor(8, 10, 18, 220))
        bg_grad.setColorAt(1.0, QColor(6, 8, 14, 240))
        painter.setBrush(QBrush(bg_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(circle_rect)

        # prepare and draw circular-cropped pixmap
        pm = self._make_circular_pixmap(diameter)
        if pm:
            painter.drawPixmap(circle_rect.x(), circle_rect.y(), pm)
        else:
            # placeholder
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(26,34,46,160))
            painter.drawEllipse(circle_rect)

        # inner vignette for depth (soft)
        vign = QRadialGradient(circle_rect.center(), diameter/2)
        vign.setColorAt(0.0, QColor(0,0,0,0))
        vign.setColorAt(0.7, QColor(0,0,0,36))
        vign.setColorAt(1.0, QColor(0,0,0,120))
        painter.setBrush(QBrush(vign))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(circle_rect)

        # Outer detection ring parameters
        ring_width_base = max(6, diameter * 0.04)
        pulse_factor = 0.0
        if self._pulse_active and self._pulse_duration > 0:
            elapsed = time.time() - self._pulse_start
            t = max(0.0, min(1.0, elapsed / self._pulse_duration))
            # smoother pulse curve
            pulse_factor = math.sin(math.pi * (0.5 - 0.5 * math.cos(math.pi * t)))
        ring_width = ring_width_base + pulse_factor * (ring_width_base * 3.2)
        ring_rect = circle_rect.adjusted(-ring_width*2.6, -ring_width*2.6, ring_width*2.6, ring_width*2.6)

        col = self._current_color
        cyanish = QColor(130, 235, 240)

        # helper mix function
        def mix(c1, c2, t):
            return QColor(
                int(c1.red() * (1 - t) + c2.red() * t),
                int(c1.green() * (1 - t) + c2.green() * t),
                int(c1.blue() * (1 - t) + c2.blue() * t),
                220
            )

        # MAIN RING (rich conical gradient)
        base_grad = QConicalGradient(ring_rect.center(), -self._angle * 0.7)
        base_grad.setColorAt(0.00, mix(col, cyanish, 0.12))
        base_grad.setColorAt(0.10, mix(col, QColor(255,255,255), 0.28))
        base_grad.setColorAt(0.28, mix(col, cyanish, 0.06))
        base_grad.setColorAt(0.48, QColor(0,0,0,0))
        base_grad.setColorAt(1.00, mix(col, cyanish, 0.12))
        pen_main = QPen(QBrush(base_grad), ring_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen_main)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(ring_rect)

        # SECONDARY thin bright band (fast moving narrow highlight)
        shimmer_angle = -self._angle * 1.9
        shimmer_grad = QConicalGradient(ring_rect.center(), shimmer_angle)
        # tight bright band
        shimmer_grad.setColorAt(0.0, QColor(0,0,0,0))
        shimmer_grad.setColorAt(0.02, QColor(255,255,255,int(220 * (0.6 + 0.4*pulse_factor))))
        shimmer_grad.setColorAt(0.05, QColor(255,255,255,int(100 * (1.0 + 0.6*pulse_factor))))
        shimmer_grad.setColorAt(0.12, QColor(0,0,0,0))
        shimmer_pen = QPen(QBrush(shimmer_grad), max(2, int(ring_width * 0.48)), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(shimmer_pen)
        painter.drawEllipse(ring_rect)

        # ADDITIVE BLOOM (composited glow)
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        glow_radius = ring_rect.width() * (0.52 + 0.18 * (pulse_factor))
        glow_rad = QRadialGradient(ring_rect.center(), glow_radius * (1.1 + 0.12 * pulse_factor))
        # stronger core glow
        core_alpha = int(48 * self._bloom_strength * (0.9 + 0.5 * pulse_factor))
        mid_alpha = int(24 * self._bloom_strength * (0.9 + 0.4 * pulse_factor))
        glow_rad.setColorAt(0.0, QColor(col.red(), col.green(), col.blue(), core_alpha))
        glow_rad.setColorAt(0.25, QColor(col.red(), col.green(), col.blue(), mid_alpha))
        glow_rad.setColorAt(1.0, QColor(0,0,0,0))
        painter.setBrush(QBrush(glow_rad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(ring_rect.adjusted(-12, -12, 12, 12))
        # larger fainter halo
        halo_rad = QRadialGradient(ring_rect.center(), ring_rect.width() * 0.9)
        halo_rad.setColorAt(0.0, QColor(col.red(), col.green(), col.blue(), int(18 * self._bloom_strength)))
        halo_rad.setColorAt(0.5, QColor(col.red(), col.green(), col.blue(), int(8 * self._bloom_strength)))
        halo_rad.setColorAt(1.0, QColor(0,0,0,0))
        painter.setBrush(QBrush(halo_rad))
        painter.drawEllipse(ring_rect.adjusted(-40, -40, 40, 40))
        painter.restore()

        # SPARKLE DOT (brighter orb that orbits with angle)
        sparkle_radius = max(3, ring_width * 0.9 + pulse_factor * 4.0)
        angle_rad = math.radians(self._angle * 1.7)
        orbit_r = (ring_rect.width()/2.0) * (0.94 - 0.06 * pulse_factor)
        sx = ring_rect.center().x() + math.cos(angle_rad) * orbit_r
        sy = ring_rect.center().y() + math.sin(angle_rad) * orbit_r
        rg = QRadialGradient(QtCore.QPointF(sx, sy), sparkle_radius * 2.4)
        core_color = QColor(
            min(255, col.red() + 110),
            min(255, col.green() + 110),
            min(255, col.blue() + 110),
            int(255 * (0.92 + 0.08 * pulse_factor))
        )
        rg.setColorAt(0.0, core_color)
        rg.setColorAt(0.45, QColor(core_color.red(), core_color.green(), core_color.blue(), int(170)))
        rg.setColorAt(1.0, QColor(core_color.red(), core_color.green(), core_color.blue(), 0))
        painter.setBrush(QBrush(rg))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QtCore.QRectF(sx - sparkle_radius, sy - sparkle_radius, sparkle_radius*2, sparkle_radius*2))

        # thin outer glow ring
        glow_pen = QPen(QColor(col.red(), col.green(), col.blue(), int(36 + 86 * pulse_factor)), max(2, int(ring_width * 0.34)))
        glow_pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(glow_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(ring_rect.adjusted(-6, -6, 6, 6))

# ---------------- Main Window ----------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 👇 Change app title to "GeoAttendance"
        self.setWindowTitle("GeoAttendance — Smart Attendance System")
        self.resize(1200, 820)
        self.setMinimumSize(920, 680)
        # safe icon loading
        if Path("logo.png").exists():
            self.setWindowIcon(QtGui.QIcon("logo.png"))

        # backend
        self.auth = AuthManager()
        self.attendance_manager = AttendanceManager()

        try:
            init_db()
        except Exception:
            pass

        # Central background widget (paints stars) and layout
        self.bg = BackgroundWidget(self)
        self.setCentralWidget(self.bg)
        main_layout = QVBoxLayout(self.bg)
        main_layout.setContentsMargins(18,18,18,18)

        # header bar (logo + app title)
        header = QWidget(self.bg)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(6,6,6,6)

        # Add logo image
        logo_label = QLabel()
        if Path("logo.png").exists():
            pixmap = QtGui.QPixmap("logo.png")
            pixmap = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        h_layout.addWidget(logo_label)

        # Add app title
        app_label = QLabel("  ⭑  GeoAttendance")
        app_label.setFont(QFont("Segoe UI", 14, QFont.DemiBold))
        app_label.setStyleSheet("color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #a6f3ff, stop:1 #b69cff);")
        h_layout.addWidget(app_label)
        h_layout.addStretch(1)

        info_lbl = QLabel("Lightweight • Secure • Fast")
        info_lbl.setStyleSheet("color:#bfeeff;")
        h_layout.addWidget(info_lbl)
        main_layout.addWidget(header)

        # stacked pages on top of painted background
        self.stack = QStackedWidget(self.bg)
        main_layout.addWidget(self.stack)

        # pages
        self.page_login = self._build_login_page()
        self.page_register = self._build_register_page()
        self.page_main = self._build_main_page()

        self.stack.addWidget(self.page_login)
        self.stack.addWidget(self.page_register)
        self.stack.addWidget(self.page_main)

        self.stack.setCurrentWidget(self.page_login)

        # thread placeholders
        self.camera_worker = None
        self.att_worker = None

    # --- Pages -------------------------------------------------

    def _build_login_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(20)
        layout.setContentsMargins(8,8,8,8)

        # left brand
        left = GlassFrame()
        left.setMinimumWidth(520)
        l_layout = QVBoxLayout(left)
        l_layout.setContentsMargins(32,32,32,32)

        lbl_title = QLabel("SMART\nATTENDANCE")
        lbl_title.setFont(QFont("Segoe UI", 34, QFont.Bold))
        lbl_title.setStyleSheet("color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #a6f3ff, stop:1 #d7b0ff);")
        l_layout.addWidget(lbl_title)
        l_layout.addSpacing(8)
        lbl_sub = QLabel("Next-gen attendance monitoring\nfor modern classrooms")
        lbl_sub.setStyleSheet("color:#cfefff;")
        lbl_sub.setFont(QFont("Segoe UI", 11))
        l_layout.addWidget(lbl_sub)
        l_layout.addSpacing(12)

        # features badges
        feat_row = QHBoxLayout()
        for txt in ("Face Recognition", "Fast", "Secure"):
            b = QLabel(txt)
            b.setStyleSheet("""
                QLabel {
                    padding:6px 10px;
                    border-radius: 10px;
                    background: rgba(255,255,255,0.03);
                    color: #dffcff;
                    font-weight: 600;
                }
            """)
            feat_row.addWidget(b)
        feat_row.addStretch(1)
        l_layout.addLayout(feat_row)
        l_layout.addStretch(1)

        # right form
        right = GlassFrame()
        right.setMinimumWidth(420)
        r_layout = QVBoxLayout(right)
        r_layout.setContentsMargins(24,22,24,22)

        lbl = QLabel("Sign in")
        lbl.setFont(QFont("Segoe UI", 18, QFont.DemiBold))
        lbl.setStyleSheet("color:#e8f7ff;")
        r_layout.addWidget(lbl)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.login_student_id = QLineEdit()
        self.login_student_id.setPlaceholderText("e.g. S2023001")
        self.login_student_id.setFixedHeight(40)
        self.login_student_id.setStyleSheet("padding-left:8px;")
        form.addRow("Student ID:", self.login_student_id)

        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Your password")
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.setFixedHeight(40)
        self.login_password.setStyleSheet("padding-left:8px;")
        form.addRow("Password:", self.login_password)

        r_layout.addLayout(form)
        r_layout.addSpacing(10)

        btn_row = QHBoxLayout()
        self.btn_login = GlowButton("Login")
        self.btn_login.clicked.connect(self.handle_login)
        self.btn_register_nav = GlowButton("Register")
        self.btn_register_nav.clicked.connect(lambda: self.stack.setCurrentWidget(self.page_register))
        btn_row.addWidget(self.btn_login)
        btn_row.addWidget(self.btn_register_nav)
        r_layout.addLayout(btn_row)

        self.login_status = QLabel("")
        self.login_status.setStyleSheet("color:#ff9b9b;")
        r_layout.addWidget(self.login_status)
        r_layout.addStretch(1)

        layout.addWidget(left, 2)
        layout.addWidget(right, 1)
        return page

    def _build_register_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10,10,10,10)

        card = GlassFrame()
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(20,20,20,20)

        title = QLabel("Create a new account")
        title.setFont(QFont("Segoe UI", 16, QFont.DemiBold))
        title.setStyleSheet("color:#e8f7ff;")
        c_layout.addWidget(title)

        form = QFormLayout()
        self.reg_student_id = QLineEdit()
        self.reg_password = QLineEdit()
        self.reg_password.setEchoMode(QLineEdit.Password)
        self.reg_name = QLineEdit()
        self.reg_class = QLineEdit()
        for w in (self.reg_student_id, self.reg_password, self.reg_name, self.reg_class):
            w.setFixedHeight(36)
            w.setStyleSheet("padding-left:8px;")

        form.addRow("Student ID:", self.reg_student_id)
        form.addRow("Password:", self.reg_password)
        form.addRow("Name:", self.reg_name)
        form.addRow("Class:", self.reg_class)

        c_layout.addLayout(form)
        c_layout.addSpacing(14)

        btns = QHBoxLayout()
        create_btn = GlowButton("Register")
        create_btn.clicked.connect(self.handle_register)
        back_btn = GlowButton("Back to Login")
        back_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.page_login))
        btns.addWidget(create_btn)
        btns.addWidget(back_btn)
        c_layout.addLayout(btns)

        layout.addWidget(card, alignment=Qt.AlignCenter)
        return page

    def _build_main_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(8,8,8,8)
        layout.setSpacing(12)

        left_card = GlassFrame()
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(12,12,12,12)

        # top bar
        top_bar = QHBoxLayout()
        self.label_user = QLabel("Welcome, —")
        self.label_user.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        self.label_user.setStyleSheet("color:#dffcff;")
        top_bar.addWidget(self.label_user)
        top_bar.addStretch(1)
        self.btn_logout = GlowButton("Logout")
        self.btn_logout.setMaximumWidth(140)
        self.btn_logout.clicked.connect(self.handle_logout)
        top_bar.addWidget(self.btn_logout)
        left_layout.addLayout(top_bar)

        # camera preview (CameraView circular)
        self.camera_view = CameraView()
        # keep previous nominal area roughly same; CameraView center circle will adapt
        self.camera_view.setFixedSize(760, 500)
        self.camera_view.setStyleSheet("background: transparent;")
        left_layout.addWidget(self.camera_view, alignment=Qt.AlignCenter)

        # controls row
        ctrl_row = QHBoxLayout()
        self.btn_camera = GlowButton("Start Camera")
        self.btn_camera.clicked.connect(self.toggle_camera)
        ctrl_row.addWidget(self.btn_camera)
        self.btn_mark = GlowButton("Mark Attendance")
        self.btn_mark.clicked.connect(self.handle_mark_attendance)
        self.btn_mark.setEnabled(False)
        ctrl_row.addWidget(self.btn_mark)
        ctrl_row.addStretch(1)
        self.fps_label = QLabel("")
        self.fps_label.setStyleSheet("color:#9ef8ff;")
        ctrl_row.addWidget(self.fps_label)
        left_layout.addLayout(ctrl_row)

        right_card = GlassFrame()
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(12,12,12,12)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color:#9ef8ff; font-weight:600;")
        right_layout.addWidget(self.status_label)

        self.info_label = QLabel("Class: —\nStudent ID: —")
        self.info_label.setStyleSheet("color:#cfefff;")
        right_layout.addWidget(self.info_label)
        right_layout.addSpacing(8)

        hist_label = QLabel("Attendance History")
        hist_label.setStyleSheet("color:#e8f7ff; font-weight:700;")
        right_layout.addWidget(hist_label)

        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(["Time", "Name", "Photo", "Confidence", "Late"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.history_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.history_table.setShowGrid(False)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background: transparent;
                color: #e8fbff;
                alternate-background-color: rgba(255,255,255,0.02);
            }
            QHeaderView::section {
                background: rgba(255,255,255,0.02);
                color: #cfefff;
                padding:6px;
                border: none;
            }
        """)
        self.history_table.cellDoubleClicked.connect(self._preview_history_photo)
        self.history_table.setIconSize(QtCore.QSize(92, 60))
        self.history_table.setMinimumHeight(320)
        right_layout.addWidget(self.history_table)

        self.btn_refresh = GlowButton("Refresh History")
        self.btn_refresh.clicked.connect(self.load_history)
        right_layout.addWidget(self.btn_refresh)

        layout.addWidget(left_card, 3)
        layout.addWidget(right_card, 1)
        return page

    # ---------------- Actions ----------------

    def keyPressEvent(self, ev):
        # Enter/Return: if on login page attempt login
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.stack.currentWidget() is self.page_login:
                self.handle_login()
        # Escape: logout if on main page
        if ev.key() == Qt.Key_Escape:
            if self.stack.currentWidget() is self.page_main:
                self.handle_logout()
        super().keyPressEvent(ev)

    def show_toast(self, text, duration=2200):
        t = Toast(self, text, duration)
        # position bottom-right inside main window (map to global)
        gw = self.geometry()
        # map top-left of window to global to guarantee correct placement when window moves
        top_left = self.mapToGlobal(QtCore.QPoint(0, 0))
        x = top_left.x() + gw.width() - t.width() - 28
        y = top_left.y() + gw.height() - t.height() - 36
        t.show_at(QtCore.QPoint(int(x), int(y)))

    def handle_login(self):
        sid = self.login_student_id.text().strip()
        pwd = self.login_password.text().strip()
        if not sid or not pwd:
            self.login_status.setText("Please enter Student ID and Password.")
            return
        ok = self.auth.login(sid, pwd)
        if ok:
            user = self.auth.get_current_user()
            self.label_user.setText(f"Welcome, {user.get('name','—')}  |  Class: {user.get('class_name','—')}")
            self.info_label.setText(f"Class: {user.get('class_name','—')}\nStudent ID: {user.get('student_id','—')}")
            self.stack.setCurrentWidget(self.page_main)
            self.login_status.setText("")
            self.btn_mark.setEnabled(True)
            self.show_toast("Login successful", 1500)
            self.load_history()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid Student ID or Password.")
            self.login_status.setText("Invalid credentials.")

    def handle_register(self):
        sid = self.reg_student_id.text().strip()
        pwd = self.reg_password.text().strip()
        name = self.reg_name.text().strip()
        class_name = self.reg_class.text().strip()
        if not sid or not pwd or not name:
            QMessageBox.warning(self, "Missing Fields", "Student ID, Password, and Name are required.")
            return
        from app.database import add_student
        ok = add_student(sid, pwd, name, class_name)
        if ok:
            self.show_toast("Registered — please login", 1800)
            self.login_student_id.setText(sid)
            self.stack.setCurrentWidget(self.page_login)
        else:
            QMessageBox.warning(self, "Registration Failed", "Student ID already exists.")

    def toggle_camera(self):
        # toggle camera running state
        if self.camera_worker and self.camera_worker.isRunning():
            # stop
            self.camera_worker.stop()
            self.camera_worker = None
            try:
                self.attendance_manager.stop_camera()
            except Exception:
                pass
            self.camera_view.clear()
            self.btn_camera.setText("Start Camera")
            self.show_toast("Camera stopped", 1000)
            self.fps_label.setText("")
        else:
            try:
                self.attendance_manager.start_camera()
            except Exception as e:
                QMessageBox.critical(self, "Camera Error", f"Failed to open camera: {e}")
                return
            self.camera_worker = CameraWorker(self.attendance_manager)
            # connect frames to CameraView
            self.camera_worker.frame_ready.connect(self._update_camera_frame)
            self.camera_worker.error.connect(lambda e: self.show_toast(f"Camera error: {e}", 3200))
            self.camera_worker.fps_signal.connect(lambda f: self.fps_label.setText(f"FPS: {int(f)}"))
            self.camera_worker.start()
            self.btn_camera.setText("Stop Camera")
            self.show_toast("Camera started", 1000)

    @Slot(QImage)
    def _update_camera_frame(self, qimg):
        # forward to CameraView
        try:
            self.camera_view.set_image(qimg)
        except Exception:
            # fallback: set pixmap on a label if something unexpected occurs
            pix = QPixmap.fromImage(qimg)
            self.camera_view.clear()
            # draw as pixmap widget fallback (unlikely)
            lbl = QLabel(self.camera_view)
            lbl.setPixmap(pix.scaled(self.camera_view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            lbl.setGeometry(0,0,self.camera_view.width(), self.camera_view.height())
            lbl.show()

    def handle_mark_attendance(self):
        if not self.auth.is_logged_in():
            QMessageBox.warning(self, "Not logged in", "Please login first.")
            return
        user = self.auth.get_current_user()
        student_id = user.get("student_id")
        name = user.get("name")
        if student_id is None:
            QMessageBox.warning(self, "User error", "Unable to determine current user.")
            return
        self.status_label.setText("Marking attendance...")
        self.btn_mark.setEnabled(False)
        # pulse the ring to indicate active detection
        try:
            self.camera_view.start_pulse(2200)
        except Exception:
            pass
        self.att_worker = AttendanceWorker(self.attendance_manager, student_id, name, None)
        self.att_worker.finished.connect(self._on_attendance_finished)
        self.att_worker.start()
        self.show_toast("Recognizing face...", 2000)

    @Slot(bool, str)
    def _on_attendance_finished(self, success, message):
        self.btn_mark.setEnabled(True)
        # inform CameraView so it transitions the ring color
        try:
            self.camera_view.set_result(success)
        except Exception:
            pass
        # small extra pulse for emphasis
        try:
            self.camera_view.start_pulse(700)
        except Exception:
            pass

        if success:
            self.status_label.setText(message or "Attendance marked")
            self.show_toast(message or "Marked", 1600)
        else:
            self.status_label.setText(message or "Failed")
            self.show_toast(message or "Failed to mark", 2200)
        self.load_history()

    def load_history(self):
        if not self.auth.is_logged_in():
            return
        user = self.auth.get_current_user()
        sid = user.get("student_id")
        try:
            history = get_attendance_history(sid)
        except Exception as e:
            history = []
            print("Error loading history:", e)
        self.history_table.setRowCount(0)
        if not history:
            return
        for rec in history:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            time_str = rec[0] if len(rec) > 0 else ""
            name = rec[1] if len(rec) > 1 else ""
            photo_path = rec[2] if len(rec) > 2 else ""
            confidence = f"{rec[3]}%" if len(rec) > 3 and rec[3] is not None else "N/A"
            is_late = "Yes" if (rec[4] if len(rec) > 4 else 0) else "No"
            self.history_table.setItem(row, 0, QTableWidgetItem(str(time_str)))
            self.history_table.setItem(row, 1, QTableWidgetItem(str(name)))
            if photo_path and os.path.exists(photo_path):
                try:
                    pm = QPixmap(photo_path).scaled(96, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    thumb = QLabel()
                    thumb.setPixmap(pm)
                    thumb.setAlignment(Qt.AlignCenter)
                    thumb.setContentsMargins(2,2,2,2)
                    self.history_table.setCellWidget(row, 2, thumb)
                    # keep original path in item's text (hidden)
                    item = QTableWidgetItem(photo_path)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setForeground(QColor(0,0,0,0))
                    self.history_table.setItem(row, 2, item)
                except Exception:
                    self.history_table.setItem(row, 2, QTableWidgetItem(str(photo_path)))
            else:
                self.history_table.setItem(row, 2, QTableWidgetItem(""))
            self.history_table.setItem(row, 3, QTableWidgetItem(str(confidence)))
            self.history_table.setItem(row, 4, QTableWidgetItem(str(is_late)))
            self.history_table.setRowHeight(row, 72)

    def _preview_history_photo(self, row, column):
        # try to get original path from item text (column 2)
        item = self.history_table.item(row, 2)
        if item:
            path = item.text()
            if path and os.path.exists(path):
                dlg = QDialog(self)
                dlg.setWindowTitle("Attendance Photo")
                dlg.resize(720, 720)
                v = QVBoxLayout(dlg)
                lbl = QLabel()
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setPixmap(QPixmap(path).scaled(680, 680, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                v.addWidget(lbl)
                dlg.exec()
                return
        # fallback: see if there's a widget thumbnail
        w = self.history_table.cellWidget(row, 2)
        if w and isinstance(w, QLabel) and w.pixmap():
            dlg = QDialog(self)
            dlg.setWindowTitle("Attendance Photo")
            dlg.resize(650, 650)
            v = QVBoxLayout(dlg)
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setPixmap(w.pixmap().scaled(620, 620, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            v.addWidget(lbl)
            dlg.exec()
            return
        QMessageBox.information(self, "No photo", "No photo available for this entry.")

    def handle_logout(self):
        # stop camera and threads
        if self.camera_worker and self.camera_worker.isRunning():
            self.camera_worker.stop()
            self.camera_worker = None
            try:
                self.attendance_manager.stop_camera()
            except Exception:
                pass
        self.auth.logout()
        self.stack.setCurrentWidget(self.page_login)
        self.login_password.clear()
        self.login_status.setText("")
        self.camera_view.clear()
        self.status_label.setText("Logged out")
        self.show_toast("Logged out", 1200)

    def closeEvent(self, ev):
        # clean up camera and threads
        try:
            if self.camera_worker and self.camera_worker.isRunning():
                self.camera_worker.stop()
            self.attendance_manager.stop_camera()
        except Exception:
            pass
        super().closeEvent(ev)

# ----------------- Entry point -----------------

def main():
    app = QApplication(sys.argv)
    # improved palette + font smoothing
    pal = QPalette()
    pal.setColor(QPalette.WindowText, QColor("#dffcff"))
    app.setPalette(pal)
    QApplication.setStyle("Fusion")

    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()