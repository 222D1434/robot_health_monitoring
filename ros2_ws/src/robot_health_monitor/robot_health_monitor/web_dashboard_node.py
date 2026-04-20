#!/usr/bin/env python3
"""
web_dashboard_node.py
Nodo ROS2 que sirve el Dashboard estático mediante http.server.
"""

import sys
import os
import http.server
import threading

import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import ParameterDescriptor
from ament_index_python.packages import get_package_share_directory


class WebDashboardNode(Node):

    REQUIRED_PARAMS = [
        'port',
        'web_dir',
    ]

    def __init__(self):
        super().__init__('web_dashboard_node')

        # ── 1. DECLARACIÓN DE PARÁMETROS ──────────────────────────────────────
        descr = ParameterDescriptor(dynamic_typing=True)
        for p in self.REQUIRED_PARAMS:
            self.declare_parameter(p, descriptor=descr)

        # ── 2. CARGAR Y VALIDAR ────────────────────────────────────────────────
        self.cfg = {p: self.get_parameter(p).value for p in self.REQUIRED_PARAMS}
        
        # Validación estricta: si falta algún parámetro, el nodo muere
        if any(v is None for v in self.cfg.values()):
            missing = [k for k, v in self.cfg.items() if v is None]
            self.get_logger().fatal(f'CRITICAL: Faltan parámetros en YAML: {missing}')
            sys.exit(1)

        port = int(self.cfg['port'])
        web_dir = str(self.cfg['web_dir'])

        # Resolución automática del directorio web si está vacío en el YAML
        if not web_dir:
            try:
                pkg_share = get_package_share_directory('robot_health_monitor')
                # Intentamos buscar en el share (instalado) o en el source
                web_dir = os.path.join(pkg_share, 'web')
            except Exception as e:
                self.get_logger().fatal(f'CRITICAL: No se encuentra carpeta web/: {e}')
                sys.exit(1)

        if not os.path.isdir(web_dir):
            self.get_logger().fatal(f'CRITICAL: Directorio no existe: {web_dir}')
            sys.exit(1)

        # ── 3. SERVIDOR HTTP EN HILO DAEMON ────────────────────────────────────
        # Usamos un lambda para inyectar el directorio en el handler
        handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
            *args, directory=web_dir, **kwargs
        )
        
        try:
            self.server = http.server.HTTPServer(('0.0.0.0', port), handler)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            self.get_logger().info(f'WebDashboardNode: http://0.0.0.0:{port} -> {web_dir}')
        except Exception as e:
            self.get_logger().fatal(f'No se pudo iniciar el servidor web: {e}')
            sys.exit(1)

def main(args=None):
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

