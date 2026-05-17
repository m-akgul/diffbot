import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from geometry_msgs.msg import Twist


class CommandMux(Node):
    """
    Priority-based command multiplexer for multiple input sources.

    Priority order (highest to lowest): Joystick > Keyboard > Buttons
    Uses timestamps to detect stale commands and only forwards active sources.
    """

    def __init__(self):
        super().__init__('command_mux')

        # === Subscribe to all input sources ===
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

        # === State: last command from each source ===
        self.buttons_cmd = Twist()
        self.keyboard_cmd = Twist()
        self.joy_cmd = Twist()

        now = self.get_clock().now()
        self.buttons_time = now
        self.keyboard_time = now
        self.joy_time = now

        # Timeout for stale command detection (0.5s = assume source died)
        self.command_timeout = Duration(seconds=0.5)
        self.activity_threshold = 0.01

        # Update at 20Hz to forward commands from active source
        self.timer = self.create_timer(0.05, self.update)

    # === Subscription Callbacks ===
    def cb_buttons(self, msg):
        self.buttons_cmd = msg
        self.buttons_time = self.get_clock().now()

    def cb_keyboard(self, msg):
        self.keyboard_cmd = msg
        self.keyboard_time = self.get_clock().now()

    def cb_joy(self, msg):
        self.joy_cmd = msg
        self.joy_time = self.get_clock().now()

    # === Priority Selection Logic ===
    def source_active(self, msg, timestamp):
        # Check if source is actively commanding (not timed out and non-zero)
        now = self.get_clock().now()
        age = now - timestamp

        # Command is stale if not received recently
        if age > self.command_timeout:
            return False

        # Source is active only if publishing non-zero velocity
        return (abs(msg.linear.x) > self.activity_threshold or
                abs(msg.angular.z) > self.activity_threshold)

    def update(self):
        # Select highest-priority active source and publish its command
        cmd = Twist()

        # Priority: Joystick > Keyboard > Buttons
        if self.source_active(self.joy_cmd, self.joy_time):
            cmd = self.joy_cmd
        elif self.source_active(self.keyboard_cmd, self.keyboard_time):
            cmd = self.keyboard_cmd
        elif self.source_active(self.buttons_cmd, self.buttons_time):
            cmd = self.buttons_cmd
        else:
            # No active source: send stop command
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0

        self.pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = CommandMux()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
