import threading
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from PyQt6.QtCore import pyqtSignal, QObject


class RosTelemetry(QObject):
    odom_received = pyqtSignal(float, float, float, float)
    vel_received = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        # single node for telemetry subscriptions to avoid multiple nodes with similar names
        self._node = Node('teleop_gui_telemetry')
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        self._sub = self._node.create_subscription(
            Odometry, '/odom', self._odom_cb, 10
        )
        self._vel_sub = self._node.create_subscription(
            Twist, '/cmd_vel', self._vel_cb, 10
        )

        self._thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._thread.start()

    def _odom_cb(self, msg: Odometry):
        try:
            self.odom_received.emit(
                float(msg.pose.pose.position.x),
                float(msg.pose.pose.position.y),
                float(msg.twist.twist.linear.x),
                float(msg.twist.twist.angular.z),
            )
        except Exception:
            pass

    def _vel_cb(self, msg: Twist):
        try:
            self.vel_received.emit(float(msg.linear.x), float(msg.angular.z))
        except Exception:
            pass

    def shutdown(self):
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
        try:
            self._node.destroy_node()
        except Exception:
            pass
