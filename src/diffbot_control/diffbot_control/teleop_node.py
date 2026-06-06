from rclpy.node import Node
from geometry_msgs.msg import Twist


class TeleopPublisher(Node):
    def __init__(self, topic_name: str, node_name: str):
        super().__init__(node_name)
        self.publisher = self.create_publisher(Twist, topic_name, 10)

    def publish_velocity(self, linear_x: float, angular_z: float):
        msg = Twist()
        msg.linear.x = linear_x
        msg.angular.z = angular_z
        self.publisher.publish(msg)
