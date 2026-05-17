import math
from PyQt6.QtCore import Qt
from .base_handler import BaseInputHandler


class KeyboardInputHandler(BaseInputHandler):
    def __init__(self, publisher, session_id: str):
        super().__init__(publisher, session_id)
        self.keys_pressed = set()
        self.max_linear_speed = 0.5
        self.max_angular_speed = 1.0
        self.smoothed_linear = 0.0
        self.smoothed_angular = 0.0

    def on_key_press(self, key: int):
        if not self.is_active:
            return
        self.keys_pressed.add(key)

    def on_key_release(self, key: int):
        self.keys_pressed.discard(key)
        if not self.keys_pressed:
            self.clear_state()

    def on_focus_lost(self):
        self.keys_pressed.clear()
        self.clear_state()

    def set_max_speeds(self, linear: float, angular: float):
        self.max_linear_speed = linear
        self.max_angular_speed = angular

    def update(self):
        if not self.is_active:
            return

        # Map keyboard keys to raw commands
        linear = 0.0
        angular = 0.0

        if Qt.Key.Key_W in self.keys_pressed:
            linear = 1.0
        if Qt.Key.Key_S in self.keys_pressed:
            linear = -1.0
        if Qt.Key.Key_A in self.keys_pressed:
            angular = 1.0
        if Qt.Key.Key_D in self.keys_pressed:
            angular = -1.0

        self.current_linear = linear
        self.current_angular = angular

        # When moving backward, invert angular direction so turning feels natural
        if linear < 0:
            angular *= -1

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
        self.keys_pressed.clear()

    def deactivate(self):
        self.keys_pressed.clear()
        self.smoothed_linear = 0.0
        self.smoothed_angular = 0.0
        super().deactivate()
