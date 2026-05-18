"""
Launch the robot health monitor system.

This launch file starts the nodes required to monitor the robot health.
"""

import os
import sys

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import LogInfo, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_name = 'robot_health_monitor'

    try:
        pkg_share = get_package_share_directory(pkg_name)
    except Exception as e:
        print(f'[FATAL] No se encuentra el paquete "{pkg_name}": {e}')
        sys.exit(1)

    default_config_path = os.path.join(pkg_share, 'config', 'health_config.yaml')
    config_file = LaunchConfiguration('config_file')

    declare_config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=default_config_path,
        description='Ruta al fichero YAML de configuración del sistema de monitorización'
    )

    system_metrics_node = Node(
        package=pkg_name,
        executable='system_metrics_node',
        name='system_metrics_node',
        parameters=[config_file],
        output='screen',
    )

    ros_metrics_node = Node(
        package=pkg_name,
        executable='ros_metrics_node',
        name='ros_metrics_node',
        parameters=[config_file],
        output='screen',
    )

    health_aggregator_node = Node(
        package=pkg_name,
        executable='health_aggregator_node',
        name='health_aggregator_node',
        parameters=[config_file],
        output='screen',
    )

    web_dashboard_node = Node(
        package=pkg_name,
        executable='web_dashboard_node',
        name='web_dashboard_node',
        parameters=[config_file],
        output='screen',
    )

    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=[{'port': 9090}],
        output='screen',
    )

    return LaunchDescription([
        declare_config_file_arg,
        LogInfo(msg=['[health_monitor] Cargando configuración desde: ', config_file]),
        system_metrics_node,
        ros_metrics_node,
        health_aggregator_node,
        web_dashboard_node,
        rosbridge_node,
    ])
