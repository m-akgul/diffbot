from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    world_path = PathJoinSubstitution([
        FindPackageShare('rover_gazebo'),
        'worlds',
        'empty.sdf'
    ])

    urdf_path = PathJoinSubstitution([
        FindPackageShare('rover_description'),
        'urdf',
        'rover.urdf'
    ])
    
    gazebo = ExecuteProcess(
        cmd=['gz', 'sim', world_path],
        output='screen'
    )

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

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'rover_bot',
            '-topic', 'robot_description'
        ],
        output='screen'
    )

    return LaunchDescription([
        rsp_node,
        jsp_node,
        gazebo,
        spawn_robot
    ])
