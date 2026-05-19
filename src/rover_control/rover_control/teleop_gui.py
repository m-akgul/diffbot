import sys
import threading
import uuid

from PyQt6 import QtCore
import rclpy
import math
import signal

from rclpy.executors import MultiThreadedExecutor

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QPushButton,
    QGridLayout,
    QSlider,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QGroupBox
)

from std_msgs.msg import Header
from rover_control.teleop_node import TeleopPublisher
from rover_control.input_handlers.keyboard_handler import KeyboardInputHandler
from rover_control.input_handlers.button_handler import ButtonInputHandler
from rover_control.input_handlers.joystick_handler import JoystickInputHandler
from rover_control.ros_telemetry import RosTelemetry


class VirtualJoystick(QWidget):
    """
    Virtual on-screen joystick widget with visual feedback.

    Maps mouse position within a circular base to linear/angular velocity values.
    """

    def __init__(self, parent=None, joystick_handler=None):
        super().__init__(parent)
        self.setFixedSize(220, 220)
        self.joystick_handler = joystick_handler

        self.knob_radius = 30
        self.base_radius = 90

        self.center = QPointF(110, 110)
        self.knob_position = QPointF(110, 110)

    def paintEvent(self, event):
        # Draw joystick base and movable knob
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.setBrush(QBrush(QColor(220, 220, 220)))

        painter.drawEllipse(
            self.center,
            self.base_radius,
            self.base_radius
        )

        painter.setBrush(QBrush(QColor(80, 120, 255)))

        painter.drawEllipse(
            self.knob_position,
            self.knob_radius,
            self.knob_radius
        )

    def mouseMoveEvent(self, event):
        if not self.joystick_handler:
            return

        position = event.position()
        dx = position.x() - self.center.x()
        dy = position.y() - self.center.y()

        distance = math.sqrt(dx**2 + dy**2)
        max_distance = self.base_radius

        # Clamp knob position to circular base boundary
        if distance > max_distance:
            scale = max_distance / distance
            dx *= scale
            dy *= scale

        self.knob_position = QPointF(
            self.center.x() + dx,
            self.center.y() + dy
        )

        # Convert position to normalized velocity values [-1.0, 1.0]
        linear_value = -dy / max_distance
        angular_value = -dx / max_distance
        if linear_value < 0:
            angular_value *= -1

        self.joystick_handler.on_joystick_move(linear_value, angular_value)
        self.update()

    def mouseReleaseEvent(self, event):
        # Reset to center and stop robot on release
        self.knob_position = QPointF(
            self.center.x(),
            self.center.y()
        )

        if self.joystick_handler:
            self.joystick_handler.on_joystick_release()

        self.update()


class MainWindow(QMainWindow):
    """
    Main GUI window for rover teleoperation with three input modes.

    Manages mode switching, speed control, and routes commands to the active handler.
    """

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self.setWindowTitle(f'Rover Control ({session_id[:8]})')
        self.resize(640, 440)

        # Initialize ROS2 publishers (one per input mode to avoid topic conflicts)
        safe_session_id = session_id.replace('-', '_')
        self.buttons_pub = TeleopPublisher('/cmd_vel_buttons', f'buttons_teleop_{safe_session_id}')
        self.keyboard_pub = TeleopPublisher('/cmd_vel_keyboard', f'keyboard_teleop_{safe_session_id}')
        self.joystick_pub = TeleopPublisher('/cmd_vel_joy', f'joystick_teleop_{safe_session_id}')

        # Heartbeat publishers (liveness signals)
        self.buttons_hb_pub = self.buttons_pub.create_publisher(Header, '/heartbeat_buttons', 10)
        self.keyboard_hb_pub = self.keyboard_pub.create_publisher(Header, '/heartbeat_keyboard', 10)
        self.joystick_hb_pub = self.joystick_pub.create_publisher(Header, '/heartbeat_joy', 10)

        # Initialize input handlers with both motion command and heartbeat publishers
        # Pass the publisher node as ros_node for clock access
        self.keyboard_handler = KeyboardInputHandler(self.keyboard_pub.publisher, self.keyboard_hb_pub, self.keyboard_pub, session_id)
        self.button_handler = ButtonInputHandler(self.buttons_pub.publisher, self.buttons_hb_pub, self.buttons_pub, session_id)
        self.joystick_handler = JoystickInputHandler(self.joystick_pub.publisher, self.joystick_hb_pub, self.joystick_pub, session_id)

        self.current_handler = None
        self.all_handlers = [self.keyboard_handler, self.button_handler, self.joystick_handler]

        # Timer for periodic handler updates (50ms = 20Hz command rate)
        from PyQt6.QtCore import QTimer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_all_handlers)
        self.update_timer.start(50)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        central_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        central_widget.setFocus()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        # === UI Layout: Header + Speed Control Sliders ===
        header = self._make_header()
        slider_layout = QVBoxLayout()

        linear_row = QHBoxLayout()
        self.linear_label = QLabel('Linear Speed: 50%')
        self.linear_slider = QSlider(Qt.Orientation.Horizontal)
        self.linear_slider.setMinimum(0)
        self.linear_slider.setMaximum(100)
        self.linear_slider.setValue(50)
        self.linear_slider.valueChanged.connect(self.update_linear_speed)
        linear_row.addWidget(self.linear_label)
        linear_row.addWidget(self.linear_slider)
        slider_layout.addLayout(linear_row)

        angular_row = QHBoxLayout()
        self.angular_label = QLabel('Angular Speed: 50%')
        self.angular_slider = QSlider(Qt.Orientation.Horizontal)
        self.angular_slider.setMinimum(0)
        self.angular_slider.setMaximum(200)
        self.angular_slider.setValue(100)
        self.angular_slider.valueChanged.connect(self.update_angular_speed)

        angular_row.addWidget(self.angular_label)
        angular_row.addWidget(self.angular_slider)
        slider_layout.addLayout(angular_row)

        # === UI Layout: Button Controls (directional pad) ===
        self.button_layout = QGridLayout()

        self.forward_button = QPushButton('↑')
        self.backward_button = QPushButton('↓')
        self.left_button = QPushButton('←')
        self.right_button = QPushButton('→')
        self.forward_left_button = QPushButton('↖')
        self.forward_right_button = QPushButton('↗')
        self.backward_left_button = QPushButton('↙')
        self.backward_right_button = QPushButton('↘')

        self.connect_motion_button(self.forward_button, 1.0, 0.0)
        self.connect_motion_button(self.backward_button, -1.0, 0.0)
        self.connect_motion_button(self.forward_left_button, 1.0, 1.0)
        self.connect_motion_button(self.forward_right_button, 1.0, -1.0)
        self.connect_motion_button(self.left_button, 0.0, 1.0)
        self.connect_motion_button(self.right_button, 0.0, -1.0)
        self.connect_motion_button(self.backward_left_button, -1.0, -1.0)
        self.connect_motion_button(self.backward_right_button, -1.0, 1.0)

        # Ensure directional buttons have consistent smaller size and no focus
        for btn in (self.forward_button, self.backward_button,
                self.left_button, self.right_button,
                self.forward_left_button, self.forward_right_button,
                self.backward_left_button, self.backward_right_button):
            btn.setMinimumSize(36, 36)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.button_layout.addWidget(self.forward_left_button, 0, 0)
        self.button_layout.addWidget(self.forward_button, 0, 1)
        self.button_layout.addWidget(self.forward_right_button, 0, 2)
        self.button_layout.addWidget(self.left_button, 1, 0)
        self.button_layout.addWidget(self.right_button, 1, 2)
        self.button_layout.addWidget(self.backward_left_button, 2, 0)
        self.button_layout.addWidget(self.backward_button, 2, 1)
        self.button_layout.addWidget(self.backward_right_button, 2, 2)

        main_layout = QVBoxLayout()
        main_layout.addWidget(header)

        # === Input Mode Selector ===
        mode_label = QLabel('Input Mode')
        self.mode_selector = QComboBox()
        self.mode_selector.addItems([
            'Buttons',
            'Keyboard',
            'Joystick'
        ])
        self.mode_selector.currentTextChanged.connect(
            self.change_input_mode
        )

        self.joystick_widget = VirtualJoystick(joystick_handler=self.joystick_handler)

        # Telemetry ROS helper (runs its own thread)
        try:
            self.ros_telemetry = RosTelemetry()
            self.ros_telemetry.odom_received.connect(self._on_odom)
            self.ros_telemetry.vel_received.connect(self._on_vel)
        except Exception:
            self.ros_telemetry = None

        main_layout.addWidget(mode_label)
        main_layout.addWidget(self.mode_selector)

        # Create grouped panels similar to controll.py: Drive + Speed Limits side-by-side
        drive_box = QGroupBox('Drive')
        drive_outer = QVBoxLayout(drive_box)
        drive_outer.setSpacing(2)

        # Put button grid into a container widget so existing grid layout can be reused
        self.grid_widget = QWidget()
        self.grid_widget.setLayout(self.button_layout)
        drive_outer.addWidget(self.grid_widget)

        # Joystick widget sits in the drive box; hidden by default
        drive_outer.addWidget(self.joystick_widget)
        self.joystick_widget.hide()

        self.hint = QLabel('Keyboard:  W A S D')
        self.hint.setObjectName('hintLabel')
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drive_outer.addWidget(self.hint)

        speed_box = QGroupBox('Speed Limits')
        speed_box.setLayout(slider_layout)

        mid = QHBoxLayout()
        mid.setSpacing(12)
        mid.addWidget(drive_box, stretch=1)
        mid.addWidget(speed_box, stretch=1)

        main_layout.addLayout(mid)

        # Telemetry panel
        telemetry_box = QGroupBox('Telemetry')
        tel_grid = QGridLayout(telemetry_box)
        tel_grid.setSpacing(8)
        tel_grid.setColumnStretch(1, 1)
        tel_grid.setColumnStretch(2, 1)
        tel_grid.setColumnStretch(3, 1)

        tel_grid.addWidget(QLabel('Commanded'), 0, 0)
        self._lbl_cmd_lin = QLabel('Lin   0.000 m/s')
        self._lbl_cmd_ang = QLabel('Ang   0.000 rad/s')
        self._lbl_cmd_lin.setObjectName('telLabel')
        self._lbl_cmd_ang.setObjectName('telLabel')
        tel_grid.addWidget(self._lbl_cmd_lin, 0, 1)
        tel_grid.addWidget(self._lbl_cmd_ang, 0, 2)

        tel_grid.addWidget(QLabel('Odometry'), 1, 0)
        self._lbl_odom_x  = QLabel('X   0.000 m')
        self._lbl_odom_y  = QLabel('Y   0.000 m')
        self._lbl_odom_vx = QLabel('Vx  0.000 m/s')
        self._lbl_odom_x.setObjectName('telLabel')
        self._lbl_odom_y.setObjectName('telLabel')
        self._lbl_odom_vx.setObjectName('telLabel')
        tel_grid.addWidget(self._lbl_odom_x,  1, 1)
        tel_grid.addWidget(self._lbl_odom_y,  1, 2)
        tel_grid.addWidget(self._lbl_odom_vx, 1, 3)

        main_layout.addWidget(telemetry_box)

        central_widget.setLayout(main_layout)

        # Apply styling similar to the legacy controller
        self._apply_stylesheet()

        self.change_input_mode('Buttons')

    # === Button Control Handlers ===
    def connect_motion_button(self, button, linear, angular):
        button.pressed.connect(
            lambda: self.button_handler.on_button_press(linear, angular)
        )
        button.released.connect(self.button_handler.on_button_release)

    def _make_header(self):
        from PyQt6.QtWidgets import QFrame
        frame = QFrame()
        frame.setObjectName('headerFrame')
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(0, 0, 0, 8)

        title = QLabel('ROVER CONTROL')
        title.setObjectName('titleLabel')
        title.setFont(QFont('Ubuntu', 16, QFont.Weight.Bold))

        self._status_dot = QLabel('● CONNECTED')
        self._status_dot.setObjectName('connLabel')
        self._status_dot.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        lay.addWidget(title)
        lay.addStretch()
        lay.addWidget(self._status_dot)
        return frame

    # === Speed Control Sliders ===
    def update_linear_speed(self, value):
        speed = value / 100.0
        self.linear_label.setText(f'Linear Speed: {value}%')
        self.keyboard_handler.set_max_speeds(speed, self.keyboard_handler.max_angular_speed)
        self.button_handler.set_max_speeds(speed, self.button_handler.max_angular_speed)
        self.joystick_handler.set_max_speeds(speed, self.joystick_handler.max_angular_speed)

    def update_angular_speed(self, value):
        speed = value / 100.0
        self.angular_label.setText(f'Angular Speed: {int(value / 2)}%')
        self.keyboard_handler.set_max_speeds(self.keyboard_handler.max_linear_speed, speed)
        self.button_handler.set_max_speeds(self.button_handler.max_linear_speed, speed)
        self.joystick_handler.set_max_speeds(self.joystick_handler.max_linear_speed, speed)

    def change_input_mode(self, mode):
        # Deactivate current handler and clear its state
        if self.current_handler:
            self.current_handler.deactivate()

        if mode == 'Buttons':
            self.current_handler = self.button_handler
            self.show_button_controls()
            self.joystick_widget.hide()
            self.grid_widget.show()
            self.hint.hide()

        elif mode == 'Keyboard':
            self.current_handler = self.keyboard_handler
            self.hide_button_controls()
            self.joystick_widget.hide()
            self.grid_widget.show()
            self.hint.show()

        elif mode == 'Joystick':
            self.current_handler = self.joystick_handler
            self.hide_button_controls()
            self.grid_widget.hide()
            self.joystick_widget.show()
            self.hint.hide()

        self.current_handler.activate()
        self.activateWindow()
        self.raise_()
        self.setFocus()

    # === Styling copied from controll.py ===
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

    def show_button_controls(self):
        for i in range(self.button_layout.count()):
            widget = self.button_layout.itemAt(i).widget()
            if widget is not None:
                widget.show()

    def hide_button_controls(self):
        for i in range(self.button_layout.count()):
            widget = self.button_layout.itemAt(i).widget()
            if widget is not None:
                widget.hide()

    # === Keyboard & Window Events ===
    def keyPressEvent(self, event):
        # Forward key presses to keyboard handler if active
        if self.current_handler == self.keyboard_handler and not event.isAutoRepeat():
            self.keyboard_handler.on_key_press(event.key())

    def keyReleaseEvent(self, event):
        # Forward key releases to keyboard handler if active
        if self.current_handler == self.keyboard_handler and not event.isAutoRepeat():
            self.keyboard_handler.on_key_release(event.key())

    def focusOutEvent(self, event):
        # Clear keyboard state when window loses focus
        if self.current_handler == self.keyboard_handler:
            self.keyboard_handler.on_focus_lost()
        super().focusOutEvent(event)

    def event(self, event):
        # Handle window deactivation to clear keyboard state
        if event.type() == QtCore.QEvent.Type.WindowDeactivate:
            if self.current_handler == self.keyboard_handler:
                self.keyboard_handler.on_focus_lost()
        return super().event(event)

    def update_all_handlers(self):
        # Update active handler at each timer tick (20Hz)
        if self.current_handler:
            self.current_handler.update()

    def _on_odom(self, x, y, vx, wz):
        # Update telemetry labels from ROS callback (Qt signal thread)
        try:
            self._lbl_odom_x.setText(f'X   {x:.3f} m')
            self._lbl_odom_y.setText(f'Y   {y:.3f} m')
            self._lbl_odom_vx.setText(f'Vx  {vx:.3f} m/s')
            # commanded labels will be updated by handlers; keep them in sync if needed
        except Exception:
            pass

    def _on_vel(self, lin, ang):
        # Update telemetry labels from ROS callback (Qt signal thread)
        try:
            self._lbl_cmd_lin.setText(f'Lin   {lin:.3f} m/s')
            self._lbl_cmd_ang.setText(f'Ang   {ang:.3f} rad/s')
        except Exception:
            pass

    def closeEvent(self, event):
        # Stop all handlers when closing window
        for handler in self.all_handlers:
            handler.deactivate()
        # shutdown telemetry helper if present
        try:
            if getattr(self, 'ros_telemetry', None):
                self.ros_telemetry.shutdown()
        except Exception:
            pass
        super().closeEvent(event)


def ros_spin(executor):
    # Background thread for ROS2 node execution
    executor.spin()


def main():
    # Initialize ROS2 and start GUI with publishers for each input mode
    rclpy.init()

    session_id = str(uuid.uuid4())
    safe_session_id = session_id.replace('-', '_')

    executor = MultiThreadedExecutor()

    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    window = MainWindow(session_id)

    # Add window's publisher nodes to executor (avoid creating duplicates)
    executor.add_node(window.buttons_pub)
    executor.add_node(window.keyboard_pub)
    executor.add_node(window.joystick_pub)

    ros_thread = threading.Thread(
        target=ros_spin,
        args=(executor,),
        daemon=True
    )
    ros_thread.start()

    window.show()
    exit_code = app.exec()

    # Send stop commands and cleanup
    window.buttons_pub.publish_velocity(0.0, 0.0)
    window.keyboard_pub.publish_velocity(0.0, 0.0)
    window.joystick_pub.publish_velocity(0.0, 0.0)

    window.buttons_pub.destroy_node()
    window.keyboard_pub.destroy_node()
    window.joystick_pub.destroy_node()

    try:
        if getattr(window, 'ros_telemetry', None):
            window.ros_telemetry.shutdown()
    except Exception:
        pass

    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
