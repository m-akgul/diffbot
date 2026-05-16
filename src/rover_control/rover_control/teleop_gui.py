import sys
import threading
import rclpy
import math

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

from teleop_node import TeleopNode

class VirtualJoystick(QWidget):
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setFixedSize(220, 220)

        self.knob_radius = 30
        self.base_radius = 90

        self.center = QPointF(110, 110)
        self.knob_position = QPointF(110, 110)

        self.linear_value = 0.0
        self.angular_value = 0.0

        self.main_window = None

    def paintEvent(self, event):
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
        position = event.position()
        dx = position.x() - self.center.x()
        dy = position.y() - self.center.y()

        distance = math.sqrt(dx**2 + dy**2)
        max_distance = self.base_radius

        if distance > max_distance:
            scale = max_distance / distance
            dx *= scale
            dy *= scale
        
        self.knob_position = QPointF(
            self.center.x() + dx,
            self.center.y() + dy
        )

        self.linear_value = -dy / max_distance
        self.angular_value = -dx / max_distance
        if self.linear_value < 0:
            self.angular_value *= -1

        if self.main_window is not None:
            self.main_window.set_motion(
                self.linear_value,
                self.angular_value
            )
        
        self.update()

    def mouseReleaseEvent(self, event):
        self.knob_position = QPointF(
            self.center.x(),
            self.center.y()
        )

        self.linear_value = 0.0
        self.angular_value = 0.0

        if self.main_window is not None:
            self.main_window.stop_motion()

        self.update()


class MainWindow(QMainWindow):
    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node
        self.setWindowTitle('Rover Control')
        self.resize(400, 300)

        self.raw_linear = 0.0
        self.raw_angular = 0.0

        self.max_linear_speed = 0.5
        self.max_angular_speed = 1.0

        self.smoothed_linear = 0.0
        self.smoothed_angular = 0.0
        self.alpha = 0.2

        self.key_linear = 0.0
        self.key_angular = 0.0
        self.keys_pressed = set()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        from PyQt6.QtCore import QTimer
        self.command_timer = QTimer()
        self.command_timer.timeout.connect(self.send_current_command)
        self.command_timer.start(100)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

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
        self.angular_slider.setValue(100)
        self.angular_slider.valueChanged.connect(self.update_angular_speed)

        angular_row.addWidget(self.angular_label)
        angular_row.addWidget(self.angular_slider)
        slider_layout.addLayout(angular_row)

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

        mode_label = QLabel('Input Mode')
        self.mode_selector = QComboBox()
        self.mode_selector.addItems([
            'Buttons',
            'Joystick'
        ])
        self.mode_selector.currentTextChanged.connect(
            self.change_input_mode
        )

        self.joystick_widget = VirtualJoystick()
        self.joystick_widget.main_window = self

        main_layout.addWidget(mode_label)
        main_layout.addWidget(self.mode_selector)

        main_layout.addLayout(slider_layout)
        main_layout.addLayout(self.button_layout)

        main_layout.addWidget(self.joystick_widget)
        self.joystick_widget.hide()

        central_widget.setLayout(main_layout)

    def connect_motion_button(self, button, linear, angular):
        button.pressed.connect(
            lambda: self.set_motion(linear, angular)
        )
        button.released.connect(self.stop_motion)

    def set_motion(self, linear, angular):
        self.raw_linear = linear
        self.raw_angular = angular

    def stop_motion(self):
        self.raw_linear = 0.0
        self.raw_angular = 0.0

    def change_input_mode(self, mode):
        if mode == 'Buttons':
            self.show_button_controls()
            self.joystick_widget.hide()
        
        elif mode == 'Joystick':
            self.hide_button_controls()
            self.joystick_widget.show()

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

    def keyPressEvent(self, event):
        key = event.key()
        self.keys_pressed.add(key)

        if key == Qt.Key.Key_W:
            self.key_linear = 1.0
        elif key == Qt.Key.Key_S:
            self.key_linear = -1.0
        elif key == Qt.Key.Key_A:
            self.key_angular = 1.0
        elif key == Qt.Key.Key_D:
            self.key_angular = -1.0

        self.set_motion(self.key_linear, self.key_angular)

    def keyReleaseEvent(self, event):
        key = event.key()
        if key in self.keys_pressed:
            self.keys_pressed.remove(key)

        if key in (Qt.Key.Key_W, Qt.Key.Key_S):
            self.key_linear = 0.0
        if key in (Qt.Key.Key_A, Qt.Key.Key_D):
            self.key_angular = 0.0

        self.set_motion(self.key_linear, self.key_angular)

    def update_linear_speed(self, value):
        self.max_linear_speed = value / 100.0
        self.linear_label.setText(f'Linear Speed: {value}%')

    def update_angular_speed(self, value):
        self.max_angular_speed = value / 100.0
        self.angular_label.setText(f'Angular Speed: {value}%')

    def send_current_command(self):
        linear = self.raw_linear
        angular = self.raw_angular
        # Normalize diagonal movement
        magnitude = math.sqrt(linear**2 + angular**2)
        if magnitude > 1.0:
            linear /= magnitude
            angular /= magnitude
        # Scale to real robot
        linear *= self.max_linear_speed
        angular *= self.max_angular_speed
        # Deadzone Filter
        deadzone_linear = 0.13
        deadzone_angular = 0.25
        if abs(linear) < deadzone_linear:
            linear = 0.0
        if abs(angular) < deadzone_angular:
            angular = 0.0
        # Smoothing (Incremental velocity change 0.0 → 0.2 → 0.4)
        if abs(linear) < 0.1 and abs(angular) < 0.1:
            self.smoothed_linear = 0.0
            self.smoothed_angular = 0.0
        else:
            accel_alpha = 0.15
            decel_alpha = 0.35
            def smooth(current, target):
                if abs(target) > abs(current):
                    a = accel_alpha
                else:
                    a = decel_alpha

                return a * target + (1 - a) * current
            
            self.smoothed_linear = smooth(self.smoothed_linear, linear)
            self.smoothed_angular = smooth(self.smoothed_angular, angular)

        self.ros_node.set_velocity(self.smoothed_linear, self.smoothed_angular)


def ros_spin(node):
    rclpy.spin(node)


def main():
    rclpy.init()
    ros_node = TeleopNode()
    ros_thread = threading.Thread(
        target=ros_spin,
        args=(ros_node,),
        daemon=True
    )
    ros_thread.start()

    app = QApplication(sys.argv)
    window = MainWindow(ros_node)
    window.show()

    exit_code = app.exec()

    ros_node.set_velocity(0.0, 0.0)
    ros_node.publish_current_velocity()

    ros_node.destroy_node()
    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()