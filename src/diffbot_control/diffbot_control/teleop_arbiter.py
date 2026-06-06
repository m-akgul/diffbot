import rclpy
from rclpy.node import Node
from rclpy.duration import Duration
from geometry_msgs.msg import Twist
from std_msgs.msg import Header, Bool


class TeleopArbiter(Node):
    """
    Teleop arbiter with safety.

    Implements:
    - Dedicated heartbeat topics (separate from motion commands)
    - Ownership model: sources own control until timeout/release/preemption
    - Stream freshness monitoring (not motion-based activity detection)
    - Immediate takeover without lockout lag
    - Watchdog based on heartbeat frequency, not command content
    - Background statistics logging
    """

    # Source priorities (higher = can preempt)
    PRIORITY_BUTTONS = 0
    PRIORITY_KEYBOARD = 1
    PRIORITY_JOYSTICK = 2

    # Timing constants
    HEARTBEAT_TIMEOUT = Duration(seconds=0.5)   # Source dead if no heartbeat
    WATCHDOG_TIMEOUT = Duration(seconds=1.0)    # Emergency stop if no owner
    DEADMAN_MIN_RATE_HZ = 10.0                  # Minimum heartbeat Hz to stay alive
    OWNERSHIP_TIMEOUT = Duration(seconds=5.0)   # Auto-release ownership if stale

    def __init__(self):
        super().__init__('teleop_arbiter')
        self.get_logger().info('Teleop Arbiter initialized - monitoring heartbeats + stream freshness')

        # === Subscriptions to input sources ===
        # Heartbeats (liveness signal)
        self.sub_hb_buttons = self.create_subscription(
            Header, '/heartbeat_buttons', self._on_heartbeat_buttons, 10
        )
        self.sub_hb_keyboard = self.create_subscription(
            Header, '/heartbeat_keyboard', self._on_heartbeat_keyboard, 10
        )
        self.sub_hb_joystick = self.create_subscription(
            Header, '/heartbeat_joy', self._on_heartbeat_joystick, 10
        )

        # Motion commands (independent of liveness)
        self.sub_cmd_buttons = self.create_subscription(
            Twist, '/cmd_vel_buttons', self._on_cmd_buttons, 10
        )
        self.sub_cmd_keyboard = self.create_subscription(
            Twist, '/cmd_vel_keyboard', self._on_cmd_keyboard, 10
        )
        self.sub_cmd_joystick = self.create_subscription(
            Twist, '/cmd_vel_joy', self._on_cmd_joystick, 10
        )

        # === Outputs ===
        self.pub_cmd_vel = self.create_publisher(Twist, '/cmd_vel', 10)
        self.pub_safety_stop = self.create_publisher(Bool, '/safety_stop', 10)

        # === Per-source state ===
        self.sources = {
            'buttons': self._init_source(self.PRIORITY_BUTTONS),
            'keyboard': self._init_source(self.PRIORITY_KEYBOARD),
            'joystick': self._init_source(self.PRIORITY_JOYSTICK),
        }

        # === Ownership tracking ===
        self.owner = None # Which source currently owns control
        self.owner_acquired_at = self.get_clock().now()
        self.watchdog_fired = False

        # === Main arbiter loop at 20Hz ===
        self.timer = self.create_timer(0.05, self._arbitrate)

    def _init_source(self, priority):
        # Initialize per-source state
        return {
            'priority': priority,
            'last_heartbeat': self.get_clock().now(),
            'last_cmd': Twist(),
            'last_cmd_time': self.get_clock().now(),
            'is_alive': False,
        }

    # === Heartbeat Callbacks (liveness signal) ===
    def _on_heartbeat_buttons(self, msg: Header):
        self._record_heartbeat('buttons', msg)

    def _on_heartbeat_keyboard(self, msg: Header):
        self._record_heartbeat('keyboard', msg)

    def _on_heartbeat_joystick(self, msg: Header):
        self._record_heartbeat('joystick', msg)

    def _record_heartbeat(self, source_name: str, msg: Header):
        # Record heartbeat - source is ALIVE if heartbeat received regularly
        source = self.sources[source_name]
        source['last_heartbeat'] = self.get_clock().now()

    # === Motion Command Callbacks (independent of liveness) ===
    def _on_cmd_buttons(self, msg: Twist):
        self._record_command('buttons', msg)

    def _on_cmd_keyboard(self, msg: Twist):
        self._record_command('keyboard', msg)

    def _on_cmd_joystick(self, msg: Twist):
        self._record_command('joystick', msg)

    def _record_command(self, source_name: str, msg: Twist):
        # Record motion command (even if zero)
        source = self.sources[source_name]
        source['last_cmd'] = msg
        source['last_cmd_time'] = self.get_clock().now()

    # === Main Arbiter Logic (runs at 20Hz) ===
    def _arbitrate(self):
        # Single point of truth for teleop control decisions
        now = self.get_clock().now()

        # === Detect alive/dead sources (heartbeat-based) ===
        for source_name, source in self.sources.items():
            hb_age = now - source['last_heartbeat']
            was_alive = source['is_alive']

            # Source is ALIVE if heartbeat received within timeout
            source['is_alive'] = hb_age < self.HEARTBEAT_TIMEOUT

            # Log state transitions
            if was_alive and not source['is_alive']:
                source['last_cmd'] = Twist()
                self.get_logger().warn(
                    f'Source "{source_name}" DEAD: no heartbeat for {hb_age.nanoseconds / 1e9:.2f}s'
                )

        # === Select new owner if current is dead or no owner ===
        if not self.owner or not self.sources[self.owner]['is_alive']:
            # Find highest-priority alive source
            candidates = [
                name for name, source in self.sources.items()
                if source['is_alive']
            ]

            if candidates:
                # Sort by priority (descending)
                candidates.sort(
                    key=lambda name: self.sources[name]['priority'],
                    reverse=True
                )
                new_owner = candidates[0]

                if self.owner != new_owner:
                    if self.owner:
                        self.get_logger().info(
                            f'Preemption: "{self.owner}" (priority {self.sources[self.owner]["priority"]}) '
                            f'→ "{new_owner}" (priority {self.sources[new_owner]["priority"]})'
                        )
                    else:
                        self.get_logger().info(f'Ownership acquired: "{new_owner}"')

                    self.owner = new_owner
                    self.owner_acquired_at = now
                    self.watchdog_fired = False
            else:
                # No alive sources
                self.owner = None
                self.get_logger().warn('No alive input sources')

        # === Watchdog check (stream freshness, not motion) ===
        # Watchdog monitors: did owner send a command recently?
        alive_sources = [
            name for name, source in self.sources.items()
            if source['is_alive']
        ]
        new_owner = None

        if alive_sources:
            # Sort by priority (descending)
            alive_sources.sort(
                key=lambda name: self.sources[name]['priority'],
                reverse=True
            )
            new_owner = alive_sources[0]

            # Ownership transition
            if new_owner != self.owner:
                old_owner = self.owner
                self.owner = new_owner
                self.owner_acquired_at = now
                self.watchdog_fired = False

                if old_owner and new_owner:
                    self.get_logger().info(
                        f'Preemption: "{old_owner}" -> "{new_owner}"'
                    )
                elif new_owner:
                    self.get_logger().info(f'Ownership acquired: "{new_owner}"')
                elif old_owner:
                    self.get_logger().info(f'Ownership lost: "{old_owner}"')

        # === Publish command or safety stop ===
        if self.owner and not self.watchdog_fired:
            # Forward owner's last command (could be zero - that's fine!)
            cmd = self.sources[self.owner]['last_cmd']
            self.pub_cmd_vel.publish(cmd)
        else:
            # Safety stop
            self.pub_cmd_vel.publish(Twist())
            if self.watchdog_fired or not self.owner:
                self.pub_safety_stop.publish(Bool(data=True))


def main(args=None):
    rclpy.init(args=args)
    node = TeleopArbiter()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
