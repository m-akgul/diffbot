from launch import LaunchDescription

from launch_ros.actions import Node


def generate_launch_description():

    image_viewer = Node(
        package='diffbot_vision',
        executable='image_viewer',
        output='screen'
    )

    return LaunchDescription([
        image_viewer
    ])