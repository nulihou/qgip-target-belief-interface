from glob import glob
from setuptools import find_packages, setup

package_name = "ros2_qgip_stack"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="QGIP RA-L Experiment Team",
    maintainer_email="maintainer@example.com",
    description="ROS2 preflight stack for multi-robot POP/NIS validation.",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "tf_leader_detection_node = ros2_qgip_stack.tf_leader_detection_node:main",
            "fault_injection_node = ros2_qgip_stack.fault_injection_node:main",
            "pop_nis_kf_node = ros2_qgip_stack.pop_nis_kf_node:main",
            "velocity_safety_controller_node = ros2_qgip_stack.velocity_safety_controller_node:main",
            "trial_supervisor_node = ros2_qgip_stack.trial_supervisor_node:main",
        ],
    },
)
