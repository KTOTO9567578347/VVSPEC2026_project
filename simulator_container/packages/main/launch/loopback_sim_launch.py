import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch.conditions import IfCondition


def generate_launch_description():
    params_file = LaunchConfiguration('params_file')
    declare_params_file_cmd = DeclareLaunchArgument(
        'params_file',
        description='Full path to the ROS2 parameters file to use for all launched nodes',
    )

    use_slam = LaunchConfiguration('use_slam')
    declare_use_slam_cmd = DeclareLaunchArgument('use_slam', default_value='False')

    loopback_sim_group = GroupAction([
        Node(
            condition=IfCondition(PythonExpression(['not ', use_slam])),
            package='nav2_loopback_sim',
            executable='loopback_simulator',
            name='loopback_simulator',
            output='screen',
            parameters=[
                params_file,
                {'publish_map_odom_tf': True}
            ],
        ),
        Node(
            condition=IfCondition(use_slam),
            package='nav2_loopback_sim',
            executable='loopback_simulator',
            name='loopback_simulator',
            output='screen',
            parameters=[
                params_file,
                {'publish_map_odom_tf': False}
            ],
        ),
    ])    

    ld = LaunchDescription()
    ld.add_action(declare_use_slam_cmd)
    ld.add_action(declare_params_file_cmd)
    ld.add_action(loopback_sim_group)
    return ld
