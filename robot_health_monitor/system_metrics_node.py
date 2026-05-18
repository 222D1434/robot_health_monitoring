#!/usr/bin/env python3
"""
Monitor system metrics for the robot health monitor.

This module checks CPU, memory, disk, temperature, battery and network status.
"""

import sys
import psutil
import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import ParameterDescriptor
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue


class SystemMetricsNode(Node):

    # Parámetros requeridos (deben estar todos en el YAML)
    REQUIRED_PARAMS = [
        'publish_rate',
        'cpu_warn_threshold',
        'cpu_error_threshold',
        'mem_warn_threshold',
        'mem_error_threshold',
        'disk_warn_threshold',
        'disk_error_threshold',
        'disk_path',
        'temp_warn_threshold',
        'temp_error_threshold',
        'temp_enabled',
        'net_interface',
        'net_min_bytes_per_sec',
    ]

    def __init__(self):
        super().__init__('system_metrics_node')

        # ── 1. DECLARACIÓN DE PARÁMETROS ─────────────────────────────────────
        descr = ParameterDescriptor(dynamic_typing=True)
        # Declaramos sin valor por defecto para forzar lectura de YAML
        for p in self.REQUIRED_PARAMS:
            self.declare_parameter(p, descriptor=descr)

        # ── 2. CARGAR Y VALIDAR ──────────────────────────────────────────────
        self.cfg = {
            p: self.get_parameter(p).value for p in self.REQUIRED_PARAMS
        }

        if any(v is None for v in self.cfg.values()):
            missing = [k for k, v in self.cfg.items() if v is None]
            self.get_logger().fatal(
                f'CRITICAL: Faltan parámetros en el YAML: {missing}. '
                f'Revisa health_config.yaml.'
            )
            sys.exit(1)

        self.get_logger().info('Parámetros cargados correctamente.')

        # ── 3. PUBLISHER Y ESTADO ────────────────────────────────────────────
        self.diag_pub = self.create_publisher(
            DiagnosticArray, '/diagnostics', 10)
        self._prev_net_bytes = None
        self._prev_net_time = None

        # ── 4. TIMER ─────────────────────────────────────────────────────────
        period = 1.0 / float(self.cfg['publish_rate'])
        self.timer = self.create_timer(period, self._timer_callback)

    def _timer_callback(self):
        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()

        msg.status.append(self._check_cpu())
        msg.status.append(self._check_memory())
        msg.status.append(self._check_disk())
        msg.status.append(self._check_network())

        if self.cfg['temp_enabled']:
            temp_status = self._check_temperature()
            if temp_status:
                msg.status.append(temp_status)

        self.diag_pub.publish(msg)

    def _level_for_value(
            self,
            value: float,
            warn_key: str,
            error_key: str) -> int:
        if value >= float(self.cfg[error_key]):
            return DiagnosticStatus.ERROR
        if value >= float(self.cfg[warn_key]):
            return DiagnosticStatus.WARN
        return DiagnosticStatus.OK

    def _check_cpu(self) -> DiagnosticStatus:
        cpu_pct = psutil.cpu_percent(interval=None)
        status = DiagnosticStatus(name='system/cpu', hardware_id='rpi4')
        status.level = self._level_for_value(
            cpu_pct, 'cpu_warn_threshold', 'cpu_error_threshold')
        status.message = f'CPU: {cpu_pct:.1f}%'
        status.values = [KeyValue(key='cpu_percent', value=f'{cpu_pct:.1f}')]
        return status

    def _check_memory(self) -> DiagnosticStatus:
        vm = psutil.virtual_memory()
        status = DiagnosticStatus(name='system/memory', hardware_id='rpi4')
        status.level = self._level_for_value(
            vm.percent, 'mem_warn_threshold', 'mem_error_threshold')
        status.message = f'RAM: {vm.percent:.1f}%'
        status.values = [KeyValue(key='mem_percent', value=str(vm.percent))]
        return status

    def _check_disk(self) -> DiagnosticStatus:
        du = psutil.disk_usage(self.cfg['disk_path'])
        status = DiagnosticStatus(name='system/disk', hardware_id='rpi4')
        status.level = self._level_for_value(
            du.percent, 'disk_warn_threshold', 'disk_error_threshold')
        status.message = f'Disco: {du.percent:.1f}%'
        status.values = [KeyValue(key='disk_percent', value=str(du.percent))]
        return status

    def _check_network(self) -> DiagnosticStatus:
        iface = self.cfg['net_interface']
        min_bps = float(self.cfg['net_min_bytes_per_sec'])
        status = DiagnosticStatus(name='system/network', hardware_id='rpi4')

        try:
            counters = psutil.net_io_counters(pernic=True).get(iface)
            if not counters:
                status.level = DiagnosticStatus.ERROR
                status.message = f'Iface {iface} no encontrada'
                return status

            now = self.get_clock().now().nanoseconds * 1e-9
            total_bytes = counters.bytes_sent + counters.bytes_recv

            bps = 0.0
            if self._prev_net_bytes is not None:
                dt = now - self._prev_net_time
                bps = (total_bytes - self._prev_net_bytes) / \
                    dt if dt > 0 else 0.0

            self._prev_net_bytes, self._prev_net_time = total_bytes, now
            status.level = DiagnosticStatus.OK if bps >= min_bps else DiagnosticStatus.WARN
            status.message = f'Red: {bps:.0f} B/s'
            status.values = [KeyValue(key='bytes_per_sec', value=f'{bps:.1f}')]
        except Exception as e:
            status.level, status.message = DiagnosticStatus.ERROR, str(e)
        return status

    def _check_temperature(self):
        # Implementación simplificada (depende del hardware)
        status = DiagnosticStatus(
            name='system/temperature',
            hardware_id='rpi4')
        try:
            temps = psutil.sensors_temperatures()
            # Busca 'cpu_thermal' o similar según el hardware
            t = temps.get('cpu_thermal', temps.get('coretemp', []))
            if t:
                cur = t[0].current
                status.level = self._level_for_value(
                    cur, 'temp_warn_threshold', 'temp_error_threshold')
                status.message = f'Temp: {cur:.1f}C'
                return status
        except BaseException:
            pass
        return None


def main(args=None):
    rclpy.init(args=args)
    node = SystemMetricsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
