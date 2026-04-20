"""
health_monitor.launch.py
Launch file unificado para el paquete robot_health_monitor.
Incluye rosbridge_websocket para comunicación con el dashboard web.
"""

import os
import sys
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import LogInfo


def generate_launch_description():
    # 1. RESOLVER RUTA AL CONFIG YAML
    pkg_name = 'robot_health_monitor'

    try:
        pkg_share = get_package_share_directory(pkg_name)
    except Exception as e:
        print(f'[FATAL] No se encuentra el paquete "{pkg_name}": {e}')
        sys.exit(1)

    config_path = os.path.join(pkg_share, 'config', 'health_config.yaml')

    if not os.path.isfile(config_path):
        print(f'[FATAL] Fichero de configuración no encontrado: {config_path}')
        sys.exit(1)

    # 2. DEFINICIÓN DE NODOS
    system_metrics_node = Node(
        package=pkg_name,
        executable='system_metrics_node',
        name='system_metrics_node',
        parameters=[config_path],
        output='screen',
    )

    ros_metrics_node = Node(
        package=pkg_name,
        executable='ros_metrics_node',
        name='ros_metrics_node',
        parameters=[config_path],
        output='screen',
    )

    health_aggregator_node = Node(
        package=pkg_name,
        executable='health_aggregator_node',
        name='health_aggregator_node',
        parameters=[config_path],
        output='screen',
    )

    web_dashboard_node = Node(
        package=pkg_name,
        executable='web_dashboard_node',
        name='web_dashboard_node',
        parameters=[config_path],
        output='screen',
    )

    # 3. ROSBRIDGE WEBSOCKET (puerto 9090)
    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=[{'port': 9090}],
        output='screen',
    )

    # 4. LAUNCH DESCRIPTION
    return LaunchDescription([
        LogInfo(msg=f'[health_monitor] Cargando configuración desde: {config_path}'),
        system_metrics_node,
        ros_metrics_node,
        health_aggregator_node,
        web_dashboard_node,
        rosbridge_node,
    ])

