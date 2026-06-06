from abc import ABC, abstractmethod
from geometry_msgs.msg import Twist
from std_msgs.msg import Header


class BaseInputHandler(ABC):
    """
    Base class for all input handlers (keyboard, buttons, joystick).

    Manages state lifecycle: activation, deactivation, and command publishing.
    Each handler publishes to its own topic to avoid cross-mode conflicts.

    Note: Handlers do NOT publish immediately on deactivate. The teleop_arbiter
    detects stale commands via heartbeat timeout and ensures safety.
    """

    def __init__(self, publisher, heartbeat_publisher, ros_node, session_id: str):
        self.publisher = publisher
        self.heartbeat_pub = heartbeat_publisher
        self.ros_node = ros_node  # For clock access
        self.session_id = session_id
        self.is_active = False
        self.current_linear = 0.0
        self.current_angular = 0.0
        self.heartbeat_seq = 0

    def publish_velocity(self, linear: float, angular: float):
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.publisher.publish(msg)

    def publish_heartbeat(self):
        # Publish liveness heartbeat (separate from motion command)
        hb = Header()
        hb.stamp = self.ros_node.get_clock().now().to_msg()
        hb.frame_id = self.session_id
        self.heartbeat_pub.publish(hb)
        self.heartbeat_seq += 1

    def activate(self):
        # Activate this input handler and clear any stale state
        self.is_active = True
        self.clear_state()

    def deactivate(self):
        # Deactivate handler without publishing (arbiter timeout handles safety)
        self.is_active = False
        self.clear_state()

    def clear_state(self):
        # Reset internal state (do not publish - let arbiter handle timeout)
        self.current_linear = 0.0
        self.current_angular = 0.0

    @abstractmethod
    def update(self):
        # Process current input state and publish velocity command
        pass
