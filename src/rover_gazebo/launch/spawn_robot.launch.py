from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch_ros.actions import Node
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition


def generate_launch_description():

    # ========== Package paths ==========
    pkg_gz_sim = FindPackageShare('rover_gazebo')
    pkg_robot = FindPackageShare('rover_description')

    world_path = PathJoinSubstitution([
        pkg_gz_sim,
        'worlds',
        'empty.sdf'
    ])

    urdf_path = PathJoinSubstitution([
        pkg_robot,
        'urdf',
        'rover.urdf'
    ])

    rviz_conf = PathJoinSubstitution([
        pkg_gz_sim,
        'config',
        'rover.rviz'
    ])

    bridge_conf = PathJoinSubstitution([
        pkg_gz_sim,
        'config',
        'bridge.yaml'
    ])

    # ========== Launch Arguments ==========
    declare_rviz = DeclareLaunchArgument(
        'rviz',
        default_value='true',
        description='Launch RViz2'
    )
    
    # ========== Gazebo Simulation ==========
    # -r -> run simulation immediately
    # -v4 -> verbose logging (drop once stable)
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('ros_gz_sim'),
                'launch',
                'gz_sim.launch.py'
            ])
        ),
        launch_arguments={
            'gz_args': [world_path, ' -r -v4']
        }.items()
    )

    # ========== Robot State Publisher ==========
    # Reads /robot_description (URDF string) and publishes static TF for fixed joints
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

    # ========== Joint State Publisher ==========
    # Animates wheel joints
    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        parameters=[{
            'use_sim_time': True
        }]
    )

    # ========== Spawn Robot into Gazebo ==========
    # Reads /robot_description, converts URDF to SDF internally
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

    # ========== Bridges between ROS and Gazebo ==========
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{
            'config_file': bridge_conf,
            'use_sim_time': True
        }],
        output='screen'
    )

    # ========== RViZ2 ==========
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_conf],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(LaunchConfiguration('rviz'))
    )

    return LaunchDescription([
        declare_rviz,
        gazebo,
        rsp_node,
        jsp_node,
        spawn_robot,
        bridge,
        rviz
    ])
