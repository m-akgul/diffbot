import sys
import threading
import uuid

from PyQt6 import QtCore
import rclpy
import math
import signal

from rclpy.executors import MultiThreadedExecutor

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
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
    QComboBox
)

from std_msgs.msg import Header
from rover_control.teleop_node import TeleopPublisher
from rover_control.input_handlers.keyboard_handler import KeyboardInputHandler
from rover_control.input_handlers.button_handler import ButtonInputHandler
from rover_control.input_handlers.joystick_handler import JoystickInputHandler


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
        self.resize(400, 300)

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

        # === UI Layout: Speed Control Sliders ===
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
        self.angular_label = QLabel('Angular Speed: 100%')
        self.angular_slider = QSlider(Qt.Orientation.Horizontal)
        self.angular_slider.setMinimum(0)
        self.angular_slider.setMaximum(200)
        self.angular_slider.setValue(100)  # Initialize to max (100%)
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

        self.button_layout.addWidget(self.forward_left_button, 0, 0)
        self.button_layout.addWidget(self.forward_button, 0, 1)
        self.button_layout.addWidget(self.forward_right_button, 0, 2)
        self.button_layout.addWidget(self.left_button, 1, 0)
        self.button_layout.addWidget(self.right_button, 1, 2)
        self.button_layout.addWidget(self.backward_left_button, 2, 0)
        self.button_layout.addWidget(self.backward_button, 2, 1)
        self.button_layout.addWidget(self.backward_right_button, 2, 2)

        main_layout = QVBoxLayout()

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

        main_layout.addWidget(mode_label)
        main_layout.addWidget(self.mode_selector)

        main_layout.addLayout(slider_layout)
        main_layout.addLayout(self.button_layout)

        main_layout.addWidget(self.joystick_widget)
        self.joystick_widget.hide()

        central_widget.setLayout(main_layout)

        self.change_input_mode('Buttons')

    # === Button Control Handlers ===
    def connect_motion_button(self, button, linear, angular):
        button.pressed.connect(
            lambda: self.button_handler.on_button_press(linear, angular)
        )
        button.released.connect(self.button_handler.on_button_release)

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

        elif mode == 'Keyboard':
            self.current_handler = self.keyboard_handler
            self.hide_button_controls()
            self.joystick_widget.hide()

        elif mode == 'Joystick':
            self.current_handler = self.joystick_handler
            self.hide_button_controls()
            self.joystick_widget.show()

        self.current_handler.activate()
        self.activateWindow()
        self.raise_()
        self.setFocus()

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

    def closeEvent(self, event):
        # Stop all handlers when closing window
        for handler in self.all_handlers:
            handler.deactivate()
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

    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
