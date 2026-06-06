import math
from .base_handler import BaseInputHandler


class ButtonInputHandler(BaseInputHandler):
    """Button input handler with heartbeat for liveness detection."""

    def __init__(self, publisher, heartbeat_publisher, ros_node, session_id: str):
        super().__init__(publisher, heartbeat_publisher, ros_node, session_id)
        self.max_linear_speed = 0.5
        self.max_angular_speed = 1.0
        self.smoothed_linear = 0.0
        self.smoothed_angular = 0.0

    def set_max_speeds(self, linear: float, angular: float):
        self.max_linear_speed = linear
        self.max_angular_speed = angular

    def on_button_press(self, linear: float, angular: float):
        if not self.is_active:
            return
        self.current_linear = linear
        self.current_angular = angular

    def on_button_release(self):
        self.current_linear = 0.0
        self.current_angular = 0.0
        self.clear_state()

    def update(self):
        # Update motion command and publish heartbeat
        if not self.is_active:
            return

        # Publish heartbeat (liveness signal) every update
        self.publish_heartbeat()

        linear = self.current_linear
        angular = self.current_angular

        # Normalize diagonal movement to prevent exceeding max speed
        magnitude = math.sqrt(linear**2 + angular**2)
        if magnitude > 1.0:
            linear /= magnitude
            angular /= magnitude

        # Scale to robot's max speeds
        linear *= self.max_linear_speed
        angular *= self.max_angular_speed

        # Apply exponential smoothing for natural acceleration/deceleration
        if abs(linear) < 0.01 and abs(angular) < 0.01:
            self.smoothed_linear = 0.0
            self.smoothed_angular = 0.0
        else:
            accel_alpha = 0.15
            decel_alpha = 0.35

            def smooth(current, target):
                if abs(target) > abs(current):
                    a = accel_alpha
                else:
                    a = decel_alpha
                return a * target + (1 - a) * current

            self.smoothed_linear = smooth(self.smoothed_linear, linear)
            self.smoothed_angular = smooth(self.smoothed_angular, angular)

        self.publish_velocity(self.smoothed_linear, self.smoothed_angular)

    def activate(self):
        super().activate()
        self.smoothed_linear = 0.0
        self.smoothed_angular = 0.0

    def deactivate(self):
        self.smoothed_linear = 0.0
        self.smoothed_angular = 0.0
        super().deactivate()
