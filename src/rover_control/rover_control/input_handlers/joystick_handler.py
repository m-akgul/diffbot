import math
from .base_handler import BaseInputHandler


class JoystickInputHandler(BaseInputHandler):
    def __init__(self, publisher, session_id: str):
        super().__init__(publisher, session_id)
        self.max_linear_speed = 0.5
        self.max_angular_speed = 1.0

    def set_max_speeds(self, linear: float, angular: float):
        self.max_linear_speed = linear
        self.max_angular_speed = angular

    def on_joystick_move(self, linear: float, angular: float):
        if not self.is_active:
            return
        self.current_linear = linear
        self.current_angular = angular

    def on_joystick_release(self):
        self.current_linear = 0.0
        self.current_angular = 0.0
        self.clear_state()

    def update(self):
        if not self.is_active:
            return

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

        # Filter out noise from joystick center deadzone
        deadzone_linear = 0.13
        deadzone_angular = 0.25
        if abs(linear) < deadzone_linear:
            linear = 0.0
        if abs(angular) < deadzone_angular:
            angular = 0.0

        self.publish_velocity(linear, angular)

    def deactivate(self):
        self.current_linear = 0.0
        self.current_angular = 0.0
        super().deactivate()
