from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, RegisterEventHandler
from launch.event_handlers import OnProcessExit, OnProcessStart
from launch_ros.actions import Node
from launch.substitutions import Command, LaunchConfiguration, OrSubstitution, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.conditions import IfCondition


def generate_launch_description():

    # ========== Package paths ==========
    pkg_gz_sim = FindPackageShare('diffbot_gazebo')
    pkg_robot = FindPackageShare('diffbot_description')
    pkg_control = FindPackageShare('diffbot_control')

    # ========== File paths ==========
    world_path = PathJoinSubstitution([
        pkg_gz_sim,
        'worlds',
        'empty.sdf'
    ])

    urdf_path = PathJoinSubstitution([
        pkg_robot,
        'urdf',
        'diffbot.urdf.xacro'
    ])

    rviz_conf = PathJoinSubstitution([
        pkg_gz_sim,
        'config',
        'diffbot.rviz'
    ])

    bridge_conf = PathJoinSubstitution([
        pkg_gz_sim,
        'config',
        'bridge.yaml'
    ])

    ekf_conf = PathJoinSubstitution([
        pkg_gz_sim,
        'config',
        'ekf.yaml'
    ])

    controller_conf = PathJoinSubstitution([
        pkg_gz_sim,
        'config',
        'controller.yaml'
    ])

    # ========== Launch Arguments ==========
    declare_rviz = DeclareLaunchArgument(
        'rviz',
        default_value='true',
        description='Launch RViz2'
    )

    declare_slam = DeclareLaunchArgument(
        'slam',
        default_value='false',
        description='Launch SLAM Toolbox'
    )

    declare_teleop = DeclareLaunchArgument(
        'teleop',
        default_value='true',
        description='Launch Teleop'
    )
    
    declare_twist_to_stamped = DeclareLaunchArgument(
        'twist_to_stamped',
        default_value='true',
        description='Convert Twist to TwistStamped'
    )

    declare_odom_relay = DeclareLaunchArgument(
        'odom_relay',
        default_value='true',
        description='Relay Odometry'
    )

    # ========== Other Launch Files ==========
    slam_launch = PythonLaunchDescriptionSource(
        PathJoinSubstitution([
            pkg_gz_sim,
            'launch',
            'slam.launch.py'
        ])
    )

    teleop_launch = PythonLaunchDescriptionSource(
        PathJoinSubstitution([
            pkg_control,
            'launch',
            'teleop.launch.py'
        ])
    )

    # ========== SLAM Toolbox ==========
    slam = IncludeLaunchDescription(
        slam_launch,
        condition=IfCondition(LaunchConfiguration('slam'))
    )

    # ========== Teleop ==========
    # command path:
    #
    #   teleop_gui
    #       ↓
    #   teleop_arbiter  /   nav2_controller
    #                   ↓
    #               /cmd_vel
    #                   ↓
    #               twist_to_stamped (if compatibility node enabled)
    #                   ↓
    #               /diff_drive_base_controller/cmd_vel
    #                   ↓
    #               diff_drive_controller
    #                   ↓
    #               gz_ros2_control
    #                   ↓
    #               wheel joints
    teleop = IncludeLaunchDescription(
        teleop_launch,
        condition=IfCondition(LaunchConfiguration('teleop'))
    )

    # ========== ROS2 Control Compatibility Node ==========
    ros2_control_compatibility = Node(
        package='diffbot_gazebo',
        executable='ros2control_compatibility',
        name='ros2_control_compatibility',
        output='screen',
        condition=IfCondition(
            OrSubstitution(
                LaunchConfiguration('twist_to_stamped'),
                LaunchConfiguration('odom_relay')
            )
        ),
        parameters=[{
            'twist_to_stamped': LaunchConfiguration('twist_to_stamped'),
            'odom_relay': LaunchConfiguration('odom_relay')
        }]
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

    # ========== Spawn Robot into Gazebo ==========
    # Reads /robot_description, converts URDF to SDF internally
    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_robot',
        arguments=[
            '-name', 'diffbot',
            '-topic', 'robot_description'
        ],
        output='screen',
    )

    delayed_spawn = RegisterEventHandler(
        OnProcessStart(
            target_action=rsp_node,
            on_start=[spawn_robot]
        )
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

    # ========== EKF ==========
    ekf = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[
            ekf_conf, 
            {'use_sim_time': True}
        ]
    )

    # ========== Controller Spawners ==========
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        output='screen',
        arguments=[
            'joint_state_broadcaster'
        ]
    )
    diff_drive_base_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        output='screen',
        arguments=[
            'diff_drive_base_controller',
            '--param-file',
            controller_conf
        ]
    )

    delayed_joint_state_broadcaster_spawner = RegisterEventHandler(
        OnProcessExit(
            target_action=spawn_robot,
            on_exit=[joint_state_broadcaster_spawner]
        )
    )
    delayed_diff_drive_spawner = RegisterEventHandler(
        OnProcessExit(
            target_action=joint_state_broadcaster_spawner,
            on_exit=[diff_drive_base_controller_spawner]
        )
    )

    return LaunchDescription([
        declare_rviz,
        declare_slam,
        declare_teleop,
        declare_twist_to_stamped,
        declare_odom_relay,
        teleop,
        ros2_control_compatibility,
        slam,
        gazebo,
        rsp_node,
        delayed_spawn,
        bridge,
        rviz,
        ekf,
        delayed_joint_state_broadcaster_spawner,
        delayed_diff_drive_spawner
    ])
