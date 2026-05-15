import sys
import threading
import rclpy

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QPushButton,
    QGridLayout
)

from teleop_node import TeleopNode


class MainWindow(QMainWindow):
    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node
        self.setWindowTitle('Rover Control')
        self.resize(400, 300)

        from PyQt6.QtCore import QTimer
        self.current_linear = 0.0
        self.current_angular = 0.0
        self.command_timer = QTimer()
        self.command_timer.timeout.connect(self.send_current_command)
        self.command_timer.start(100)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.forward_button = QPushButton('↑')
        self.backward_button = QPushButton('↓')
        self.left_button = QPushButton('←')
        self.right_button = QPushButton('→')
        self.forward_left_button = QPushButton('↖')
        self.forward_right_button = QPushButton('↗')
        self.backward_left_button = QPushButton('↙')
        self.backward_right_button = QPushButton('↘')
        
        self.connect_motion_button(self.forward_button, 0.5, 0.0)
        self.connect_motion_button(self.backward_button, -0.5, 0.0)
        self.connect_motion_button(self.forward_left_button, 0.5, 1.0)
        self.connect_motion_button(self.forward_right_button, 0.5, -1.0)
        self.connect_motion_button(self.left_button, 0.0, 1.0)
        self.connect_motion_button(self.right_button, 0.0, -1.0)
        self.connect_motion_button(self.backward_left_button, -0.5, 1.0)
        self.connect_motion_button(self.backward_right_button, -0.5, -1.0)

        layout = QGridLayout()
        layout.addWidget(self.forward_left_button, 0, 0)
        layout.addWidget(self.forward_button, 0, 1)
        layout.addWidget(self.forward_right_button, 0, 2)
        layout.addWidget(self.left_button, 1, 0)
        layout.addWidget(self.right_button, 1, 2)
        layout.addWidget(self.backward_left_button, 2, 0)
        layout.addWidget(self.backward_button, 2, 1)
        layout.addWidget(self.backward_right_button, 2, 2)

        central_widget.setLayout(layout)

    def connect_motion_button(self, button, linear, angular):
        button.pressed.connect(
            lambda: self.set_motion(linear, angular)
        )
        button.released.connect(self.stop_motion)

    def set_motion(self, linear, angular):
        self.current_linear = linear
        self.current_angular = angular

    def stop_motion(self):
        self.current_linear = 0.0
        self.current_angular = 0.0

    def send_current_command(self):
        self.ros_node.set_velocity(self.current_linear, self.current_angular)


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