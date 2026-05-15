import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from rclpy.duration import Duration

class TeleopNode(Node):
    def __init__(self):
        super().__init__('teleop_node')
        self.cmd_vel_publisher = self.create_publisher(
            Twist,
            '/cmd_vel',
            10
        )
        
        self.linear_velocity = 0.0
        self.angular_velocity = 0.0

        self.timer = self.create_timer(
            0.1,
            self.publish_current_velocity
        )

        self.command_timeout = Duration(seconds=0.5)
        self.last_command_time = self.get_clock().now()
    
    def publish_velocity(self, linear_x, angular_z):
        msg = Twist()
        msg.linear.x = linear_x
        msg.angular.z = angular_z
        self.cmd_vel_publisher.publish(msg)

    def publish_current_velocity(self):
        now = self.get_clock().now()
        if now - self.last_command_time > self.command_timeout:
            self.linear_velocity = 0.0
            self.angular_velocity = 0.0
            
        self.publish_velocity(
            self.linear_velocity,
            self.angular_velocity
        )

    def set_velocity(self, linear_x, angular_z):
        self.linear_velocity = linear_x
        self.angular_velocity = angular_z
        self.last_command_time = self.get_clock().now()

# def main(args=None):
#     rclpy.init(args=args)
#     node = TeleopNode()
#     node.publish_velocity(0.5, 0.0)
#     rclpy.spin_once(node, timeout_sec=1.0)
#     node.destroy_node()
#     rclpy.shutdown()