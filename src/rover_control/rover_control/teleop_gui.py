import sys
import threading
import rclpy
import math

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QPushButton,
    QGridLayout,
    QSlider,
    QLabel,
    QVBoxLayout,
    QHBoxLayout
)

from teleop_node import TeleopNode


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

        from PyQt6.QtCore import QTimer
        self.command_timer = QTimer()
        self.command_timer.timeout.connect(self.send_current_command)
        self.command_timer.start(100)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        slider_layout = QVBoxLayout()
        
        self.linear_label = QLabel('Linear Speed')
        self.linear_slider = QSlider(Qt.Orientation.Horizontal)
        self.linear_slider.setMinimum(0)
        self.linear_slider.setMaximum(100)
        self.linear_slider.setValue(50)
        self.linear_slider.valueChanged.connect(self.update_linear_speed)

        slider_layout.addWidget(self.linear_label)
        slider_layout.addWidget(self.linear_slider)

        self.angular_label = QLabel('Angular Speed')
        self.angular_slider = QSlider(Qt.Orientation.Horizontal)
        self.angular_slider.setMinimum(0)
        self.angular_slider.setMaximum(200)
        self.angular_slider.setValue(100)
        self.angular_slider.valueChanged.connect(self.update_angular_speed)

        slider_layout.addWidget(self.angular_label)
        slider_layout.addWidget(self.angular_slider)

        layout = QGridLayout()

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

        layout.addWidget(self.forward_left_button, 0, 0)
        layout.addWidget(self.forward_button, 0, 1)
        layout.addWidget(self.forward_right_button, 0, 2)
        layout.addWidget(self.left_button, 1, 0)
        layout.addWidget(self.right_button, 1, 2)
        layout.addWidget(self.backward_left_button, 2, 0)
        layout.addWidget(self.backward_button, 2, 1)
        layout.addWidget(self.backward_right_button, 2, 2)

        main_layout = QVBoxLayout()
        main_layout.addLayout(slider_layout)
        main_layout.addLayout(layout)
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

    def update_linear_speed(self, value):
        self.max_linear_speed = value / 100.0

    def update_angular_speed(self, value):
        self.max_angular_speed = value / 100.0

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
        # Smoothing (Incremental velocity change 0.0 → 0.2 → 0.4)
        if abs(linear) < 0.01 and abs(angular) < 0.01:
            self.smoothed_linear = 0.0
            self.smoothed_angular = 0.0
        else:
            self.smoothed_linear = (
                self.alpha * linear + (1 - self.alpha) * self.smoothed_linear
            )
            self.smoothed_angular = (
                self.alpha * angular + (1 - self.alpha) * self.smoothed_angular
            )
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