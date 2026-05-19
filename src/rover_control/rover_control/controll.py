#!/usr/bin/env python3
"""
Not used in this project, but kept for reference

rover_control/control_gui.py
────────────────────────────────────────────────────────────────────────────
PyQt6 robot control GUI for ROS2 Jazzy + Gazebo Harmonic.

Run:
    ros2 run rover_control control_gui

Controls:
    Mouse  — click and hold directional buttons
    W / ↑  — forward        S / ↓  — backward
    A / ←  — turn left      D / →  — turn right
    Space  — emergency stop
"""

import sys
import threading

import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QSlider, QLabel, QGroupBox,
    QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt6.QtGui import QFont, QKeyEvent


# ─────────────────────────────────────────────────────────────────────────────
#  ROS2 worker  (lives in a background thread, communicates via Qt signals)
# ─────────────────────────────────────────────────────────────────────────────

class RosNode(QObject):
    """
    Wraps a rclpy Node and spins it on a dedicated thread.
    Emits Qt signals so the GUI thread can update widgets safely.
    """

    odom_received = pyqtSignal(float, float, float, float)
    # args: pos_x, pos_y, linear_vel, angular_vel

    def __init__(self) -> None:
        super().__init__()
        self._node = Node('rover_control_gui')
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        self._pub = self._node.create_publisher(Twist, '/cmd_vel', 10)
        self._node.create_subscription(
            Odometry, '/odom', self._odom_cb, 10
        )

        self._thread = threading.Thread(
            target=self._executor.spin, daemon=True
        )
        self._thread.start()

    # ── callbacks ─────────────────────────────────────────────────────────

    def _odom_cb(self, msg: Odometry) -> None:
        self.odom_received.emit(
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
            msg.twist.twist.linear.x,
            msg.twist.twist.angular.z,
        )

    # ── public API ────────────────────────────────────────────────────────

    def publish_vel(self, linear: float, angular: float) -> None:
        msg = Twist()
        msg.linear.x = float(linear)
        msg.angular.z = float(angular)
        self._pub.publish(msg)

    def shutdown(self) -> None:
        self.publish_vel(0.0, 0.0)
        self._executor.shutdown(wait=False)
        self._node.destroy_node()
        rclpy.try_shutdown()


# ─────────────────────────────────────────────────────────────────────────────
#  Directional button — stores the unit direction it represents
# ─────────────────────────────────────────────────────────────────────────────

class DirButton(QPushButton):
    def __init__(
        self,
        label: str,
        linear_sign: float,   # +1 forward, -1 backward, 0 neutral
        angular_sign: float,  # +1 left,    -1 right,    0 neutral
        parent=None,
    ) -> None:
        super().__init__(label, parent)
        self.linear_sign  = linear_sign
        self.angular_sign = angular_sign
        self.setMinimumSize(QSize(72, 72))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # Never steal keyboard focus from the main window
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)


# ─────────────────────────────────────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────────────────────────────────────

class ControlWindow(QMainWindow):

    # Maps Qt.Key → (linear_sign, angular_sign)
    KEY_MAP: dict[Qt.Key, tuple[float, float]] = {
        Qt.Key.Key_W:     ( 1.0,  0.0),
        Qt.Key.Key_S:     (-1.0,  0.0),
        Qt.Key.Key_A:     ( 0.0,  1.0),
        Qt.Key.Key_D:     ( 0.0, -1.0),
        Qt.Key.Key_Up:    ( 1.0,  0.0),
        Qt.Key.Key_Down:  (-1.0,  0.0),
        Qt.Key.Key_Left:  ( 0.0,  1.0),
        Qt.Key.Key_Right: ( 0.0, -1.0),
    }

    def __init__(self, ros: RosNode) -> None:
        super().__init__()
        self._ros = ros
        self._ros.odom_received.connect(self._on_odom)

        self._held_buttons: set[DirButton] = set()
        self._held_keys:    set[Qt.Key]    = set()

        self._linear_max  = 0.5   # m/s   (controlled by slider)
        self._angular_max = 1.0   # rad/s (controlled by slider)

        # Publish at 10 Hz — keeps sending while keys/buttons are held,
        # and sends zeros the moment they are released.
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._publish_loop)
        self._timer.start()

        self._build_ui()
        self._apply_stylesheet()

        self.setWindowTitle('Rover Control')
        self.setMinimumSize(700, 460)
        # Main window must keep focus so key events are delivered here
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root_widget = QWidget()
        self.setCentralWidget(root_widget)
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        root.addWidget(self._make_header())

        mid = QHBoxLayout()
        mid.setSpacing(12)
        mid.addWidget(self._make_dpad(),         stretch=1)
        mid.addWidget(self._make_speed_panel(),  stretch=1)
        root.addLayout(mid)

        root.addWidget(self._make_status_panel())

    # ── header ────────────────────────────────────────────────────────────

    def _make_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName('headerFrame')
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 8)

        title = QLabel('🤖  ROVER CONTROL')
        title.setObjectName('titleLabel')
        title.setFont(QFont('Ubuntu', 16, QFont.Weight.Bold))

        self._status_dot = QLabel('● CONNECTED')
        self._status_dot.setObjectName('connLabel')
        self._status_dot.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(self._status_dot)
        return frame

    # ── d-pad ─────────────────────────────────────────────────────────────

    def _make_dpad(self) -> QGroupBox:
        box = QGroupBox('Drive')
        outer = QVBoxLayout(box)
        outer.setSpacing(8)

        # Button grid
        grid = QGridLayout()
        grid.setSpacing(6)

        self._btn_fwd   = DirButton('▲',  1.0,  0.0)
        self._btn_back  = DirButton('▼', -1.0,  0.0)
        self._btn_left  = DirButton('◀',  0.0,  1.0)
        self._btn_right = DirButton('▶',  0.0, -1.0)

        self._btn_stop = QPushButton('■\nSTOP')
        self._btn_stop.setObjectName('stopBtn')
        self._btn_stop.setMinimumSize(QSize(72, 72))
        self._btn_stop.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Wire direction buttons: track held state
        for btn in (self._btn_fwd, self._btn_back,
                    self._btn_left, self._btn_right):
            btn.pressed.connect(lambda b=btn:  self._held_buttons.add(b))
            btn.released.connect(lambda b=btn: self._held_buttons.discard(b))

        self._btn_stop.clicked.connect(self._emergency_stop)

        grid.addWidget(self._btn_fwd,   0, 1)
        grid.addWidget(self._btn_left,  1, 0)
        grid.addWidget(self._btn_stop,  1, 1)
        grid.addWidget(self._btn_right, 1, 2)
        grid.addWidget(self._btn_back,  2, 1)

        outer.addLayout(grid)

        hint = QLabel(
            'Keyboard:  W A S D  or  ↑ ← ↓ →\n'
            'Space → Emergency Stop'
        )
        hint.setObjectName('hintLabel')
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(hint)

        return box

    # ── speed sliders ─────────────────────────────────────────────────────

    def _make_speed_panel(self) -> QGroupBox:
        box = QGroupBox('Speed Limits')
        lay = QVBoxLayout(box)
        lay.setSpacing(20)

        lay.addWidget(self._make_slider_row(
            label        = 'Linear max',
            unit         = 'm/s',
            min_val      = 5,     # ÷100 → 0.05 m/s
            max_val      = 200,   # ÷100 → 2.00 m/s
            initial      = 50,    # ÷100 → 0.50 m/s
            val_label_fn = lambda v: f'{v/100:.2f}',
            changed_fn   = self._on_linear_changed,
            val_attr     = '_lin_val_label',
            slider_attr  = '_lin_slider',
        ))

        lay.addWidget(self._make_slider_row(
            label        = 'Angular max',
            unit         = 'rad/s',
            min_val      = 5,     # ÷100 → 0.05 rad/s
            max_val      = 300,   # ÷100 → 3.00 rad/s
            initial      = 100,   # ÷100 → 1.00 rad/s
            val_label_fn = lambda v: f'{v/100:.2f}',
            changed_fn   = self._on_angular_changed,
            val_attr     = '_ang_val_label',
            slider_attr  = '_ang_slider',
        ))

        lay.addStretch()
        return box

    def _make_slider_row(
        self, label, unit, min_val, max_val, initial,
        val_label_fn, changed_fn, val_attr, slider_attr,
    ) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # Top row: name on left, current value on right
        top = QHBoxLayout()
        name_lbl = QLabel(f'{label}  <span style="color:#666">{unit}</span>')
        name_lbl.setTextFormat(Qt.TextFormat.RichText)

        val_lbl = QLabel(val_label_fn(initial))
        val_lbl.setObjectName('valLabel')
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        setattr(self, val_attr, val_lbl)

        top.addWidget(name_lbl)
        top.addStretch()
        top.addWidget(val_lbl)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(initial)
        slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        slider.valueChanged.connect(
            lambda v, fn=val_label_fn, l=val_lbl, cb=changed_fn: (
                l.setText(fn(v)), cb(v)
            )
        )
        setattr(self, slider_attr, slider)

        lay.addLayout(top)
        lay.addWidget(slider)
        return w

    # ── status ────────────────────────────────────────────────────────────

    def _make_status_panel(self) -> QGroupBox:
        box = QGroupBox('Telemetry')
        grid = QGridLayout(box)
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)

        # Row 0: commanded velocity
        grid.addWidget(QLabel('Commanded'), 0, 0)
        self._lbl_cmd_lin = QLabel('Lin   0.000 m/s')
        self._lbl_cmd_ang = QLabel('Ang   0.000 rad/s')
        self._lbl_cmd_lin.setObjectName('telLabel')
        self._lbl_cmd_ang.setObjectName('telLabel')
        grid.addWidget(self._lbl_cmd_lin, 0, 1)
        grid.addWidget(self._lbl_cmd_ang, 0, 2)

        # Row 1: odometry
        grid.addWidget(QLabel('Odometry'), 1, 0)
        self._lbl_odom_x  = QLabel('X   0.000 m')
        self._lbl_odom_y  = QLabel('Y   0.000 m')
        self._lbl_odom_vx = QLabel('Vx  0.000 m/s')
        self._lbl_odom_x.setObjectName('telLabel')
        self._lbl_odom_y.setObjectName('telLabel')
        self._lbl_odom_vx.setObjectName('telLabel')
        grid.addWidget(self._lbl_odom_x,  1, 1)
        grid.addWidget(self._lbl_odom_y,  1, 2)
        grid.addWidget(self._lbl_odom_vx, 1, 3)

        return box

    # ── core publish loop ─────────────────────────────────────────────────

    def _publish_loop(self) -> None:
        """Runs at 10 Hz. Computes velocity from active inputs and publishes."""
        lin_sign = 0.0
        ang_sign = 0.0

        # Accumulate from held mouse buttons
        for btn in self._held_buttons:
            lin_sign += btn.linear_sign
            ang_sign += btn.angular_sign

        # Accumulate from held keyboard keys
        for key in self._held_keys:
            dl, da = self.KEY_MAP.get(key, (0.0, 0.0))
            lin_sign += dl
            ang_sign += da

        # Clamp to [-1, 1] so simultaneous opposites cancel cleanly
        lin_sign = max(-1.0, min(1.0, lin_sign))
        ang_sign = max(-1.0, min(1.0, ang_sign))

        linear  = lin_sign * self._linear_max
        angular = ang_sign * self._angular_max

        self._ros.publish_vel(linear, angular)

        # Mirror active key state onto button visuals (setDown = pressed look)
        key_lin = sum(self.KEY_MAP.get(k, (0, 0))[0] for k in self._held_keys)
        key_ang = sum(self.KEY_MAP.get(k, (0, 0))[1] for k in self._held_keys)
        self._btn_fwd.setDown(   key_lin > 0 or self._btn_fwd   in self._held_buttons)
        self._btn_back.setDown(  key_lin < 0 or self._btn_back  in self._held_buttons)
        self._btn_left.setDown(  key_ang > 0 or self._btn_left  in self._held_buttons)
        self._btn_right.setDown( key_ang < 0 or self._btn_right in self._held_buttons)

        # Update commanded-velocity labels
        self._lbl_cmd_lin.setText(f'Lin  {linear:+.3f} m/s')
        self._lbl_cmd_ang.setText(f'Ang  {angular:+.3f} rad/s')

    # ── slots ─────────────────────────────────────────────────────────────

    def _emergency_stop(self) -> None:
        self._held_buttons.clear()
        self._held_keys.clear()
        self._ros.publish_vel(0.0, 0.0)

    def _on_linear_changed(self, val: int) -> None:
        self._linear_max = val / 100.0

    def _on_angular_changed(self, val: int) -> None:
        self._angular_max = val / 100.0

    def _on_odom(self, x: float, y: float, vx: float, vz: float) -> None:
        self._lbl_odom_x.setText( f'X   {x:+.3f} m')
        self._lbl_odom_y.setText( f'Y   {y:+.3f} m')
        self._lbl_odom_vx.setText(f'Vx  {vx:+.3f} m/s')

    # ── keyboard events ───────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        try:
            key = Qt.Key(event.key())
        except ValueError:
            return

        if key == Qt.Key.Key_Space:
            self._emergency_stop()
            return

        if key in self.KEY_MAP:
            self._held_keys.add(key)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.isAutoRepeat():
            return
        try:
            key = Qt.Key(event.key())
        except ValueError:
            return
        self._held_keys.discard(key)

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self._ros.shutdown()
        event.accept()

    # ── stylesheet ────────────────────────────────────────────────────────

    def _apply_stylesheet(self) -> None:
        self.setStyleSheet("""
            /* ── Base ── */
            QMainWindow, QWidget {
                background-color: #12131f;
                color: #dde1f0;
                font-family: 'Ubuntu', 'DejaVu Sans', sans-serif;
                font-size: 13px;
            }

            /* ── Group boxes ── */
            QGroupBox {
                border: 1px solid #2e3058;
                border-radius: 10px;
                margin-top: 14px;
                padding: 10px 8px 8px 8px;
                font-weight: bold;
                color: #8a93d4;
                font-size: 12px;
                letter-spacing: 1px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 4px;
                background-color: #12131f;
            }

            /* ── Direction buttons ── */
            QPushButton {
                background-color: #1e2038;
                color: #c5cae9;
                border: 1px solid #373a6a;
                border-radius: 10px;
                font-size: 22px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2a2d50;
                border-color: #5c6bc0;
                color: #e8eaf6;
            }
            QPushButton:pressed, QPushButton:down {
                background-color: #3949ab;
                border-color: #9fa8da;
                color: #ffffff;
            }

            /* ── Emergency stop ── */
            QPushButton#stopBtn {
                background-color: #3b0f0f;
                color: #ff8a80;
                border: 1px solid #c62828;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton#stopBtn:hover {
                background-color: #6d1515;
                border-color: #ef5350;
                color: #ffcdd2;
            }
            QPushButton#stopBtn:pressed {
                background-color: #c62828;
                color: #ffffff;
            }

            /* ── Sliders ── */
            QSlider::groove:horizontal {
                height: 5px;
                background: #2e3058;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #3949ab;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                background: #7986cb;
                border-radius: 8px;
                margin: -6px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #9fa8da;
            }

            /* ── Labels ── */
            QLabel#titleLabel {
                color: #e8eaf6;
            }
            QLabel#connLabel {
                color: #69f0ae;
                font-size: 12px;
            }
            QLabel#hintLabel {
                color: #454878;
                font-size: 11px;
                padding-top: 6px;
            }
            QLabel#valLabel {
                color: #7986cb;
                font-weight: bold;
                font-family: 'Ubuntu Mono', monospace;
                min-width: 44px;
            }
            QLabel#telLabel {
                color: #80cbc4;
                font-family: 'Ubuntu Mono', monospace;
                font-size: 12px;
            }

            /* ── Header separator ── */
            QFrame#headerFrame {
                border: none;
                border-bottom: 1px solid #2e3058;
            }
        """)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    rclpy.init()
    app = QApplication(sys.argv)
    app.setApplicationName('Rover Control')

    ros = RosNode()
    window = ControlWindow(ros)
    window.show()

    exit_code = app.exec()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
