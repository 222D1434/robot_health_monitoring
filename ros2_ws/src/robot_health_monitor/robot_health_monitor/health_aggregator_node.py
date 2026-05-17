#!/usr/bin/env python3
"""
health_aggregator_node.py
Nodo que centraliza diagnósticos y aplica histéresis.
"""

import sys
import json
from collections import defaultdict, deque

import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import ParameterDescriptor
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from std_msgs.msg import String

# Mapa para texto legible
LEVEL_STR = {
    DiagnosticStatus.OK:    'OK',
    DiagnosticStatus.WARN:  'WARN',
    DiagnosticStatus.ERROR: 'ERROR',
    DiagnosticStatus.STALE: 'STALE',
}

class HealthAggregatorNode(Node):

    REQUIRED_PARAMS = [
        'publish_rate',
        'hysteresis_cycles',
        'window_size',
    ]

    def __init__(self):
        super().__init__('health_aggregator_node')

        # 1. Parámetros
        descr = ParameterDescriptor(dynamic_typing=True)
        for p in self.REQUIRED_PARAMS:
            self.declare_parameter(p, descriptor=descr)

        self.cfg = {p: self.get_parameter(p).value for p in self.REQUIRED_PARAMS}
        if any(v is None for v in self.cfg.values()):
            self.get_logger().fatal(f'Faltan parámetros en YAML: {[k for k,v in self.cfg.items() if v is None]}')
            sys.exit(1)

        self._hysteresis = int(self.cfg['hysteresis_cycles'])
        self._window_size = int(self.cfg['window_size'])

        # 2. Estado interno
        self._history = defaultdict(lambda: deque(maxlen=self._window_size))
        self._latest = {}
        self._stable_level = {}
        self._change_counter = defaultdict(int)

        # 3. Suscripción y Publishers
        self.create_subscription(DiagnosticArray, '/diagnostics', self._diag_callback, 10)
        self.health_pub = self.create_publisher(DiagnosticArray, '/health_status', 10)
        self.health_json_pub = self.create_publisher(String, '/health_status_json', 10)

        # 4. Timer
        period = 1.0 / float(self.cfg['publish_rate'])
        self.timer = self.create_timer(period, self._publish_health)
        self.get_logger().info('HealthAggregatorNode iniciado.')

    def _diag_callback(self, msg: DiagnosticArray):
        for status in msg.status:
            self._latest[status.name] = status
            self._history[status.name].append(status.level)

    def _compute_stable_level(self, name: str) -> int:
        history = list(self._history[name])
        if not history:
            return DiagnosticStatus.STALE

        current = history[-1]
        if name not in self._stable_level:
            self._stable_level[name] = current
            return current

        if current != self._stable_level[name]:
            self._change_counter[name] += 1
            if self._change_counter[name] >= self._hysteresis:
                self._stable_level[name] = current
                self._change_counter[name] = 0
            return self._stable_level[name]
        
        self._change_counter[name] = 0
        return self._stable_level[name]

    def _publish_health(self):
        if not self._latest:
            return

        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        subsystems = defaultdict(list)

        for name, status in self._latest.items():
            stable = self._compute_stable_level(name)
            s_copy = DiagnosticStatus(
                name=status.name,
                hardware_id=status.hardware_id,
                message=status.message,
                level=stable,
                values=status.values
            )
            msg.status.append(s_copy)
            subsystem = name.split('/')[0] if '/' in name else name
            subsystems[subsystem].append(stable)

        # Resumen global
        global_level = DiagnosticStatus.OK
        subsys_summary = {}
        for sub, levels in subsystems.items():
            worst = max(levels)
            subsys_summary[sub] = worst
            if worst > global_level:
                global_level = worst

        # Publicar DiagnosticArray
        self.health_pub.publish(msg)

        # Publicar JSON para Dashboard
        json_data = {
            'global_status': LEVEL_STR.get(global_level, 'UNKNOWN'),
            'subsystems': {s: LEVEL_STR.get(l, 'UNKNOWN') for s, l in subsys_summary.items()},
            'components': {n: {'level': LEVEL_STR.get(self._stable_level.get(n, 3), 'STALE'), 
                               'message': s.message} for n, s in self._latest.items()}
        }
        self.health_json_pub.publish(String(data=json.dumps(json_data)))

def main(args=None):
    rclpy.init(args=args)
    node = HealthAggregatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()

