import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from rclpy.duration import Duration

class TeleopNode(Node):
    def __init__(self):
        super().__init__('teleop_node')

        self.pub_buttons = self.create_publisher(
            Twist, '/cmd_vel_buttons', 10
        )
        self.pub_keyboard = self.create_publisher(
            Twist, '/cmd_vel_keyboard', 10
        )
        self.pub_joy = self.create_publisher(
            Twist, '/cmd_vel_joy', 10
        )

        self.current_mode = 'Buttons'
        
        self.linear_velocity = 0.0
        self.angular_velocity = 0.0

        self.command_timeout = Duration(seconds=0.5)
        self.last_command_time = self.get_clock().now()
        self.timer = self.create_timer(
            0.1,
            self.publish_current_velocity
        )

    
    def set_mode(self, mode):
        self.current_mode = mode
    
    def set_velocity(self, linear_x, angular_z):
        self.linear_velocity = linear_x
        self.angular_velocity = angular_z
        self.last_command_time = self.get_clock().now()

    def publish_current_velocity(self):
        now = self.get_clock().now()
        if now - self.last_command_time > self.command_timeout:
            self.linear_velocity = 0.0
            self.angular_velocity = 0.0

        msg = Twist()
        msg.linear.x = self.linear_velocity
        msg.angular.z = self.angular_velocity

        if self.current_mode == 'Buttons':
            self.pub_buttons.publish(msg)
        elif self.current_mode == 'Keyboard':
            self.pub_keyboard.publish(msg)
        elif self.current_mode == 'Joystick':
            self.pub_joy.publish(msg)


# def main(args=None):
#     rclpy.init(args=args)
#     node = TeleopNode()
#     node.publish_velocity(0.5, 0.0)
#     rclpy.spin_once(node, timeout_sec=1.0)
#     node.destroy_node()
#     rclpy.shutdown()