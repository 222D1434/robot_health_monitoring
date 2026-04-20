from setuptools import setup
import os
from glob import glob

package_name = 'robot_health_monitor'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Incluir launch files
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        # Incluir configuración
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'web'), glob('web/*')),
    ],
    install_requires=['setuptools', 'psutil', 'pyyaml', 'flask'],
    zip_safe=True,
    maintainer='ramyelias',
    maintainer_email='tucorreo@ejemplo.com',
    description='Sistema de monitorización de salud para TurtleBot3 en ROS 2',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'system_metrics_node = robot_health_monitor.system_metrics_node:main',
            'ros_metrics_node = robot_health_monitor.ros_metrics_node:main',
            'health_aggregator_node = robot_health_monitor.health_aggregator_node:main',
            'web_dashboard_node = robot_health_monitor.web_dashboard_node:main',
        ],
    },
)

