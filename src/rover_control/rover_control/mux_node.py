import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

class CommandMux(Node):
    def __init__(self):
        super().__init__('command_mux')

        self.sub_buttons = self.create_subscription(
            Twist, '/cmd_vel_buttons', self.cb_buttons, 10
        )
        self.sub_keyboard = self.create_subscription(
            Twist, '/cmd_vel_keyboard', self.cb_keyboard, 10
        )
        self.sub_joy = self.create_subscription(
            Twist, '/cmd_vel_joy', self.cb_joy, 10
        )

        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)

        self.buttons_cmd = Twist()
        self.keyboard_cmd = Twist()
        self.joy_cmd = Twist()

        now = self.get_clock().now()
        self.buttons_time = now
        self.keyboard_time = now
        self.joy_time = now

        self.timeout_sec = 0.5
        self.timer = self.create_timer(0.05, self.update)

    def cb_buttons(self, msg):
        self.buttons_cmd = msg
        self.buttons_time = self.get_clock().now()
    
    def cb_keyboard(self, msg):
        self.keyboard_cmd = msg
        self.keyboard_time = self.get_clock().now()
    
    def cb_joy(self, msg):
        self.joy_cmd = msg
        self.joy_time = self.get_clock().now()

    def source_active(self, msg, timestamp):
        now = self.get_clock().now()
        age = (now - timestamp).nanoseconds / 1e9
        if age > self.timeout_sec:
            return False
        
        return (abs(msg.linear.x) > 0.01 or abs(msg.angular.z) > 0.01)

    def update(self):
        cmd = Twist()

        if self.source_active(self.joy_cmd, self.joy_time):
            cmd = self.joy_cmd
        elif self.source_active(self.keyboard_cmd, self.keyboard_time):
            cmd = self.keyboard_cmd
        elif self.source_active(self.buttons_cmd, self.buttons_time):
            cmd = self.buttons_cmd

        self.pub.publish(cmd)

def main():
    rclpy.init()
    node = CommandMux()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()