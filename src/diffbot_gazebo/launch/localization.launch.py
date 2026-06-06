from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument

from launch.substitutions import (
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution
)

from launch_ros.actions import LifecycleNode, Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    # ========== Package paths ==========
    pkg_share = FindPackageShare('diffbot_gazebo')

    # ========== File paths ==========
    map_file = PathJoinSubstitution([
        EnvironmentVariable('HOME'),
        'diffbot_ws',
        'slam',
        'savemap',
        '21-05-2026.yaml'
    ])

    amcl_config = PathJoinSubstitution([
        pkg_share,
        'config',
        'amcl.yaml'
    ])

    # ========== Launch arguments ==========
    autostart = LaunchConfiguration('autostart')

    declare_autostart = DeclareLaunchArgument(
        'autostart',
        default_value='true'
    )

    declare_map_file = DeclareLaunchArgument(
        'map_file',
        default_value=map_file
    )

    # === MAP SERVER ===
    map_server = LifecycleNode(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[
            {'yaml_filename': LaunchConfiguration('map_file')},
            {'use_sim_time': True}
        ],
        namespace=''
    )

    # === AMCL ===
    amcl = LifecycleNode(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[
            amcl_config,
            {'use_sim_time': True}
        ],
        namespace=''
    )

    # === LIFECYCLE MANAGER ===
    lifecycle_manager = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'autostart': autostart,
            'node_names': ['map_server', 'amcl']
        }]
    )

    return LaunchDescription([
        declare_autostart,
        declare_map_file,

        map_server,
        amcl,

        lifecycle_manager
    ])