#!/usr/bin/env python3

import cv2
import numpy as np

import rclpy
from rclpy.node import Node

from cv_bridge import CvBridge

from sensor_msgs.msg import Image, CameraInfo

from std_msgs.msg import Int32MultiArray


class ArucoDetector(Node):

    def __init__(self):

        super().__init__('aruco_detector')

        self.bridge = CvBridge()

        ##################################################
        # Parameters
        ##################################################

        self.declare_parameter(
            'image_topic',
            '/camera/image_raw'
        )

        self.declare_parameter(
            'camera_info_topic',
            '/camera/camera_info'
        )

        self.declare_parameter(
            'marker_length',
            0.10
        )

        image_topic = self.get_parameter(
            'image_topic'
        ).value

        camera_info_topic = self.get_parameter(
            'camera_info_topic'
        ).value

        self.marker_length = self.get_parameter(
            'marker_length'
        ).value

        ##################################################
        # Subscribers
        ##################################################

        self.image_sub = self.create_subscription(
            Image,
            image_topic,
            self.image_callback,
            10
        )

        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            camera_info_topic,
            self.camera_info_callback,
            10
        )

        ##################################################
        # Publishers
        ##################################################

        self.marker_pub = self.create_publisher(
            Int32MultiArray,
            '/aruco/markers',
            10
        )

        ##################################################
        # Camera calibration
        ##################################################

        self.camera_matrix = None
        self.dist_coeffs = None

        ##################################################
        # ArUco
        ##################################################

        self.dictionary = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50
        )

        self.detector_params = (
            cv2.aruco.DetectorParameters_create()
        )

        ##################################################
        # State
        ##################################################

        self.last_ids = []

        ##################################################

        self.get_logger().info(
            'ArUco detector started.'
        )

    ##################################################

    def camera_info_callback(self, msg):

        if self.camera_matrix is not None:
            return

        self.camera_matrix = np.array(
            msg.k,
            dtype=np.float64
        ).reshape((3, 3))

        self.dist_coeffs = np.array(
            msg.d,
            dtype=np.float64
        )

        self.get_logger().info(
            'Camera calibration received.'
        )

    ##################################################

    def image_callback(self, msg):

        frame = self.convert_image(msg)

        corners, ids = self.detect_markers(frame)

        rvecs, tvecs = self.estimate_pose(corners)

        self.publish_markers(ids)

        self.draw_overlay(
            frame,
            corners,
            ids,
            rvecs,
            tvecs
        )

        self.display_image(frame)

    ##################################################

    def convert_image(self, msg):

        return self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding='bgr8'
        )

    ##################################################

    def detect_markers(self, frame):

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        corners, ids, _ = cv2.aruco.detectMarkers(
            gray,
            self.dictionary,
            parameters=self.detector_params
        )

        return corners, ids

    ##################################################

    def estimate_pose(self, corners):

        if self.camera_matrix is None:
            return None, None

        if len(corners) == 0:
            return None, None

        rvecs, tvecs, _ = (
            cv2.aruco.estimatePoseSingleMarkers(
                corners,
                self.marker_length,
                self.camera_matrix,
                self.dist_coeffs
            )
        )

        return rvecs, tvecs

    ##################################################

    def publish_markers(self, ids):

        current_ids = []

        if ids is not None:

            current_ids = ids.flatten().tolist()

        msg = Int32MultiArray()

        msg.data = current_ids

        self.marker_pub.publish(msg)

        if current_ids != self.last_ids:

            self.get_logger().info(
                f'Visible markers: {current_ids}'
            )

            self.last_ids = current_ids

    ##################################################

    def draw_overlay(self, frame, corners, ids, rvecs, tvecs):

        if ids is None:
            return

        cv2.aruco.drawDetectedMarkers(
            frame,
            corners,
            ids
        )

        if (
            self.camera_matrix is None or
            rvecs is None
        ):
            return

        for i in range(len(ids)):

            cv2.drawFrameAxes(
                frame,
                self.camera_matrix,
                self.dist_coeffs,
                rvecs[i],
                tvecs[i],
                self.marker_length * 0.5
            )

    ##################################################

    def display_image(self, frame):

        cv2.imshow(
            'ArUco Detector',
            frame
        )

        cv2.waitKey(1)


######################################################


def main():

    rclpy.init()

    node = ArucoDetector()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    cv2.destroyAllWindows()

    node.destroy_node()

    rclpy.shutdown()


if __name__ == '__main__':

    main()