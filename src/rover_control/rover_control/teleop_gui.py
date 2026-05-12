import sys
import threading
import rclpy

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QPushButton,
    QVBoxLayout
)

from teleop_node import TeleopNode


class MainWindow(QMainWindow):
    def __init__(self, ros_node):
        super().__init__()
        self.ros_node = ros_node
        self.setWindowTitle('Rover Control')
        self.resize(400, 300)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.forward_button = QPushButton('Forward')
        self.stop_button = QPushButton('Stop')
        self.forward_button.clicked.connect(
            self.move_forward
        )
        self.stop_button.clicked.connect(
            self.stop_robot
        )

        layout = QVBoxLayout()
        layout.addWidget(self.forward_button)
        layout.addWidget(self.stop_button)

        central_widget.setLayout(layout)

    def move_forward(self):
        self.ros_node.set_velocity(0.5, 0.0)

    def stop_robot(self):
        self.ros_node.set_velocity(0.0, 0.0)


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
    ros_node.destroy_node()
    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()