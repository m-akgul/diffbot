from launch import LaunchDescription

from launch_ros.actions import Node


def generate_launch_description():

    image_viewer = Node(
        package='diffbot_vision',
        executable='image_viewer',
        output='screen',
        parameters=[{
            'image_topic': '/camera/image_raw'
        }]
    )

    aruco_detector = Node(
        package='diffbot_vision',
        executable='aruco_detector',
        output='screen',
        parameters=[{
            'image_topic': '/camera/image_raw'
        }]
    )

    return LaunchDescription([
        image_viewer,
        aruco_detector
    ])