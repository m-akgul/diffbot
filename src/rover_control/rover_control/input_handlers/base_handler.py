from abc import ABC, abstractmethod
from geometry_msgs.msg import Twist


class BaseInputHandler(ABC):
    """
    Base class for all input handlers (keyboard, buttons, joystick).

    Manages state lifecycle: activation, deactivation, and command publishing.
    Each handler publishes to its own topic to avoid cross-mode conflicts.
    """

    def __init__(self, publisher, session_id: str):
        self.publisher = publisher
        self.session_id = session_id
        self.is_active = False
        self.current_linear = 0.0
        self.current_angular = 0.0

    def publish_velocity(self, linear: float, angular: float):
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.publisher.publish(msg)

    def activate(self):
        # Activate this input handler and clear any stale state
        self.is_active = True
        self.clear_state()

    def deactivate(self):
        # Deactivate handler and send stop command to ensure robot stops
        self.is_active = False
        self.clear_state()
        self.publish_velocity(0.0, 0.0)

    def clear_state(self):
        # Reset internal state and publish zero velocity
        self.current_linear = 0.0
        self.current_angular = 0.0
        self.publish_velocity(0.0, 0.0)

    @abstractmethod
    def update(self):
        # Process current input state and publish velocity command
        pass
