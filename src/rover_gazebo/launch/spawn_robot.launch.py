from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction
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
        cmd=['gz', 'sim', world_path, '-r'],
        output='screen'
    )

    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{
            'robot_description': ParameterValue(
                Command(['xacro ', urdf_path]),
                value_type=str
            ),
            'use_sim_time': True
        }],
        output='screen'
    )

    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        parameters=[{
            'use_sim_time': True
        }]
    )

    spawn_robot = Node(
                package='ros_gz_sim',
                executable='create',
                name='spawn_robot',
                arguments=[
                    '-name', 'rover_bot',
                    '-topic', 'robot_description'
                ],
                output='screen',
            )

    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{
            'config_file': PathJoinSubstitution([
                FindPackageShare('rover_gazebo'),
                'config',
                'bridge.yaml'
            ]),
            'use_sim_time': True
        }],
        output='screen'
    )

    return LaunchDescription([
        gazebo,
        rsp_node,
        jsp_node,
        bridge,
        spawn_robot
    ])
