import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    default_world = os.path.join(
        get_package_share_directory('main'), 'worlds', 'maze.world.yaml'
    )
    world_path = LaunchConfiguration('world_path')
    use_sim_time = LaunchConfiguration('use_sim_time')

    return LaunchDescription([
        DeclareLaunchArgument('world_path', default_value=default_world),
        DeclareLaunchArgument('use_sim_time', default_value='True'),
        Node(
            package='flatland_server',
            executable='flatland_server',
            name='flatland_server',
            output='screen',
            parameters=[{
                'world_path': world_path,
                'update_rate': 50.0,
                'step_size': 0.02,
                'show_viz': 0.0,
                'viz_pub_rate': 30.0,
                'use_sim_time': False,  # flatland_server publishes /clock
            }],
        ),
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='laser_static_tf',
            arguments=[
                '--x', '0', '--y', '0', '--z', '0',
                '--roll', '0', '--pitch', '0', '--yaw', '0',
                '--frame-id', 'base_link', '--child-frame-id', 'laser_link',
            ],
            parameters=[{'use_sim_time': ParameterValue(use_sim_time, value_type=bool)}],
        ),
    ])
