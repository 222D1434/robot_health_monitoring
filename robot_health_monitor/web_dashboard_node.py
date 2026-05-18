#!/usr/bin/env python3
"""
Serve the web dashboard for the robot health monitor.

This module starts a simple HTTP server to provide the dashboard interface.
"""

import http.server
import os
import sys
import threading

import rclpy
from ament_index_python.packages import get_package_share_directory
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.node import Node


class WebDashboardNode(Node):
    """Nodo ROS 2 encargado de servir el dashboard web."""

    REQUIRED_PARAMS = [
        'port',
        'web_dir',
    ]

    def __init__(self):
        """Inicializa el nodo y arranca el servidor HTTP."""
        super().__init__('web_dashboard_node')

        descr = ParameterDescriptor(dynamic_typing=True)
        for param_name in self.REQUIRED_PARAMS:
            self.declare_parameter(param_name, descriptor=descr)

        self.cfg = {
            param_name: self.get_parameter(param_name).value
            for param_name in self.REQUIRED_PARAMS
        }

        if any(value is None for value in self.cfg.values()):
            missing = [
                key for key, value in self.cfg.items()
                if value is None
            ]
            self.get_logger().fatal(
                f'CRITICAL: Faltan parámetros en YAML: {missing}'
            )
            sys.exit(1)

        port = int(self.cfg['port'])
        web_dir = str(self.cfg['web_dir'])

        if not web_dir:
            try:
                pkg_share = get_package_share_directory(
                    'robot_health_monitor'
                )
                web_dir = os.path.join(pkg_share, 'web')
            except Exception as exc:
                self.get_logger().fatal(
                    f'CRITICAL: No se encuentra carpeta web/: {exc}'
                )
                sys.exit(1)

        if not os.path.isdir(web_dir):
            self.get_logger().fatal(
                f'CRITICAL: Directorio no existe: {web_dir}'
            )
            sys.exit(1)

        def handler(*args, **kwargs):
            return http.server.SimpleHTTPRequestHandler(
                *args,
                directory=web_dir,
                **kwargs
            )

        try:
            self.server = http.server.HTTPServer(
                ('0.0.0.0', port),
                handler
            )
            self.server_thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True
            )
            self.server_thread.start()
            self.get_logger().info(
                f'WebDashboardNode: http://0.0.0.0:{port} -> {web_dir}'
            )
        except Exception as exc:
            self.get_logger().fatal(
                f'No se pudo iniciar el servidor web: {exc}'
            )
            sys.exit(1)


def main(args=None):
    """Punto de entrada principal del nodo."""
    rclpy.init(args=args)
    node = None

    try:
        node = WebDashboardNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
