from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


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
            'robot_description': ParameterValue(
                Command(['xacro ', urdf_path]),
                value_type=str
            )
        }]
    )

    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher'
    )

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        name="spawn_robot",
        arguments=[
            '-name', 'rover_bot',
            '-topic', 'robot_description'
        ],
        output='screen'
    )

    cmd_vel_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='cmd_vel_bridge',
        arguments=[
            '/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist'
        ],
        output='screen'
    )

    lidar_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='scan_bridge',
        arguments=[
            '/scan@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan'
        ],
        output='screen'
    )

    return LaunchDescription([
        gazebo,
        rsp_node,
        jsp_node,
        spawn_robot,
        cmd_vel_bridge,
        lidar_bridge
    ])
