#!/usr/bin/env python3

import cv2

from cv_bridge import CvBridge

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image


class ImageViewer(Node):

    def __init__(self):

        super().__init__('image_viewer')

        self.bridge = CvBridge()

        self.declare_parameter(
            'image_topic',
            '/camera/image_raw'
        )

        image_topic = self.get_parameter('image_topic').value

        self.subscription = self.create_subscription(
            Image,
            image_topic,
            self.image_callback,
            10
        )

        self.get_logger().info(
            f'Subscribed to {image_topic}. Waiting for camera images...'
        )

    def image_callback(self, msg):

        try:
            frame = self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding='bgr8'
            )

            cv2.imshow(
                'DiffBot Camera',
                frame
            )

            cv2.waitKey(1)

        except Exception as e:

            self.get_logger().error(
                str(e)
            )


def main():

    rclpy.init()

    node = ImageViewer()

    rclpy.spin(node)

    cv2.destroyAllWindows()

    node.destroy_node()

    rclpy.shutdown()


if __name__ == '__main__':
    main()