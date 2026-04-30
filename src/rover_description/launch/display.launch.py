from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import Command
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():

    urdf_path = PathJoinSubstitution([
        FindPackageShare('rover_description'),
        'urdf',
        'rover.urdf'
    ])

    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': Command(['cat ', urdf_path])
        }]
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2'
    )

    return LaunchDescription([
        rsp_node,
        rviz_node
    ])