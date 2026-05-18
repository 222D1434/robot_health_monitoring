#!/usr/bin/env python3
"""
Monitor ROS 2 metrics for the robot health monitor.

This module checks ROS 2 nodes, topics, frequencies and TF availability.
"""

import sys
import time
from collections import deque

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from rcl_interfaces.msg import ParameterDescriptor
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

# Tipos de mensajes conocidos
from sensor_msgs.msg import LaserScan, Imu
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist


class TopicRateMonitor:
    """Mide la tasa real de publicación de un tópico."""

    WINDOW = 20

    def __init__(
            self,
            node,
            topic,
            expected_hz,
            tolerance,
            msg_type,
            callback_group):
        self.topic = topic
        self.expected_hz = expected_hz
        self.tolerance = tolerance
        self._stamps = deque(maxlen=self.WINDOW)
        self._last_msg_time = 0.0

        qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )

        node.create_subscription(
            msg_type, topic, self._cb, qos, callback_group=callback_group
        )

    def _cb(self, msg):
        now = time.time()
        self._stamps.append(now)
        self._last_msg_time = now

    def get_status(self) -> DiagnosticStatus:
        status = DiagnosticStatus(
            name=f'ros/topic_hz{self.topic}',
            hardware_id='ros2')
        stamps = list(self._stamps)

        if len(stamps) < 2:
            status.level, status.message = DiagnosticStatus.STALE, f'{self.topic}: sin datos'
            return status

        intervals = [stamps[i + 1] - stamps[i] for i in range(len(stamps) - 1)]
        avg_interval = sum(intervals) / len(intervals)
        measured_hz = 1.0 / avg_interval if avg_interval > 0 else 0.0
        age = time.time() - self._last_msg_time
        timeout = 3.0 / self.expected_hz if self.expected_hz > 0 else 5.0

        if age > timeout:
            status.level, status.message = DiagnosticStatus.STALE, f'{self.topic}: timeout'
        elif self.expected_hz <= 0:
            status.level, status.message = DiagnosticStatus.OK, f'{self.topic}: activo'
        else:
            ratio = measured_hz / self.expected_hz
            if ratio < (1.0 - self.tolerance):
                status.level, status.message = DiagnosticStatus.WARN, f'{self.topic}: Hz bajo'
            else:
                status.level, status.message = DiagnosticStatus.OK, f'{self.topic}: OK'

        status.values = [
            KeyValue(
                key='measured_hz',
                value=f'{measured_hz:.2f}')]
        return status


class RosMetricsNode(Node):
    REQUIRED_PARAMS = [
        'publish_rate',
        'topics_to_monitor',
        'expected_hz_list',
        'tolerance_list',
        'tf_parent_frames',
        'tf_child_frames',
        'tf_timeouts',
        'expected_nodes',
        'node_check_interval']

    TOPIC_TYPE_MAP = {
        '/scan': LaserScan, '/odom': Odometry, '/imu': Imu, '/cmd_vel': Twist
    }

    def __init__(self):
        super().__init__('ros_metrics_node')
        self._cb_group = ReentrantCallbackGroup()

        # 1. Parámetros
        descr = ParameterDescriptor(dynamic_typing=True)
        for p in self.REQUIRED_PARAMS:
            self.declare_parameter(p, descriptor=descr)

        self.cfg = {p: self.get_parameter(
            p).value for p in self.REQUIRED_PARAMS}
        if any(v is None for v in self.cfg.values()):
            self.get_logger().fatal(
                f'Faltan parámetros en YAML: {[k for k,v in self.cfg.items() if v is None]}')
            sys.exit(1)

        # 2. Monitores de Tópicos
        self._topic_monitors = []
        for t, hz, tol in zip(self.cfg['topics_to_monitor'],
                              self.cfg['expected_hz_list'], self.cfg['tolerance_list']):
            m_type = self.TOPIC_TYPE_MAP.get(t)
            if m_type:
                self._topic_monitors.append(
                    TopicRateMonitor(
                        self,
                        t,
                        float(hz),
                        float(tol),
                        m_type,
                        self._cb_group))

        # 3. TF Listener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # 4. Publisher y Timers
        self.diag_pub = self.create_publisher(
            DiagnosticArray, '/diagnostics', 10)
        rate = 1.0 / float(self.cfg['publish_rate'])
        self.timer = self.create_timer(rate, self._timer_callback)

    def _timer_callback(self):
        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()

        # Check Tópicos
        for monitor in self._topic_monitors:
            msg.status.append(monitor.get_status())

        # Check TFs
        for p, c, t in zip(self.cfg['tf_parent_frames'],
                           self.cfg['tf_child_frames'], self.cfg['tf_timeouts']):
            status = DiagnosticStatus(
                name=f'ros/tf/{p}_to_{c}', hardware_id='ros2')
            try:
                if self.tf_buffer.can_transform(
                    p, c, rclpy.time.Time(), timeout=rclpy.duration.Duration(
                        seconds=float(t))):
                    status.level, status.message = DiagnosticStatus.OK, 'TF OK'
                else:
                    status.level, status.message = DiagnosticStatus.ERROR, 'TF No disponible'
            except Exception as e:
                status.level, status.message = DiagnosticStatus.ERROR, str(e)
            msg.status.append(status)

        # Check Nodos
        node_names = self.get_node_names()
        for expected in self.cfg['expected_nodes']:
            status = DiagnosticStatus(
                name=f"ros/node/{expected.lstrip('/')}",
                hardware_id='ros2')
            if expected in node_names:
                status.level, status.message = DiagnosticStatus.OK, 'Nodo activo'
            else:
                status.level, status.message = DiagnosticStatus.ERROR, 'Nodo no encontrado'
            msg.status.append(status)

        self.diag_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RosMetricsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
