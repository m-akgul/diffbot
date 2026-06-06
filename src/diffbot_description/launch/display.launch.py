from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():

    urdf_path = PathJoinSubstitution([
        FindPackageShare('diffbot_description'),
        'urdf',
        'diffbot.urdf'
    ])

    rviz_config = PathJoinSubstitution([
        FindPackageShare('diffbot_description'),
        'rviz',
        'diffbot.rviz'
    ])

    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': Command(['cat ', urdf_path])
        }]
    )

    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher'
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        arguments=['-d', rviz_config]
    )

    return LaunchDescription([
        jsp_node,
        rsp_node,
        rviz_node
    ])