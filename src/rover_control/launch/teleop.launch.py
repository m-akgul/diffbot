from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    
    teleop_gui = Node(
        package='rover_control',
        executable='teleop_gui',
        name='teleop_gui',
        output='screen'
    )

    teleop_arbiter = Node(
        package='rover_control',
        executable='teleop_arbiter',
        name='teleop_arbiter',
        output='screen'
    )

    return LaunchDescription([
        teleop_gui,
        teleop_arbiter
    ])