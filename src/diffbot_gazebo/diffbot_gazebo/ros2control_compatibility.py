#!/usr/bin/env python3

from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry

import rclpy
from rclpy.node import Node


class CompatibilityNode(Node):
    def __init__(self):
        super().__init__('compatibility_node')

        self.declare_parameter('twist_to_stamped', False)
        self.declare_parameter('odom_relay', False)

        if self.get_parameter('twist_to_stamped').value:
            self.cmd_sub = self.create_subscription(
                Twist,
                '/cmd_vel',
                self.cmd_callback,
                10
            )

            self.cmd_pub = self.create_publisher(
                TwistStamped,
                '/diff_drive_base_controller/cmd_vel',
                10
            )

        if self.get_parameter('odom_relay').value:
            self.odom_sub = self.create_subscription(
                Odometry,
                '/diff_drive_base_controller/odom',
                self.odom_callback,
                30
            )

            self.odom_pub = self.create_publisher(
                Odometry,
                '/odom',
                30
            )

    def cmd_callback(self, msg):
        stamped = TwistStamped()

        stamped.header.stamp = self.get_clock().now().to_msg()
        stamped.header.frame_id = 'base_footprint'

        stamped.twist = msg

        self.cmd_pub.publish(stamped)

    def odom_callback(self, msg):
        self.odom_pub.publish(msg)


def main():
    rclpy.init()
    node = CompatibilityNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()