#!/usr/bin/env python3
"""Launch the multi-robot preflight stack for one follower robot."""

from __future__ import annotations

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    return LaunchDescription(
        [
            DeclareLaunchArgument("follower_ns", default_value="/robot_1"),
            DeclareLaunchArgument("follower_frame", default_value="robot_1/base_link"),
            DeclareLaunchArgument("leader_frames", default_value="robot_2/base_link,robot_3/base_link"),
            DeclareLaunchArgument("leader_ids", default_value="robot_2,robot_3"),
            DeclareLaunchArgument("max_speed_mps", default_value="0.5"),
            DeclareLaunchArgument("dropout_duration_s", default_value="0.0"),
            DeclareLaunchArgument("position_noise_std_m", default_value="0.0"),
            DeclareLaunchArgument("delay_s", default_value="0.0"),
            DeclareLaunchArgument("false_positive_rate", default_value="0.0"),
            DeclareLaunchArgument("false_negative_rate", default_value="0.0"),
            DeclareLaunchArgument("confidence_scale", default_value="1.0"),
            DeclareLaunchArgument("id_switch_probability", default_value="0.0"),
            DeclareLaunchArgument("confidence_threshold", default_value="0.5"),
            DeclareLaunchArgument("nis_soft_threshold", default_value="12.0"),
            DeclareLaunchArgument("nis_hard_threshold", default_value="20.0"),
            DeclareLaunchArgument("r_inflation", default_value="10.0"),
            DeclareLaunchArgument("ghost_horizon_s", default_value="1.0"),
            DeclareLaunchArgument("lost_timeout_s", default_value="1.5"),
            DeclareLaunchArgument("leader_id_filter", default_value=""),
            DeclareLaunchArgument("results_csv_path", default_value=""),
            OpaqueFunction(function=_launch_nodes),
        ]
    )


def _launch_nodes(context, *args, **kwargs):
    follower_ns = LaunchConfiguration("follower_ns").perform(context).strip("/")
    prefix = f"/{follower_ns}" if follower_ns else ""
    detections_raw = f"{prefix}/detections_raw"
    detections_faulty = f"{prefix}/detections_faulty"
    selected_leader = f"{prefix}/qgip/selected_leader"
    pop_state = f"{prefix}/qgip/pop_state"
    cmd_vel_safe = f"{prefix}/cmd_vel_safe"
    mpc_debug = f"{prefix}/qgip/mpc_debug"
    trial_status = f"{prefix}/qgip/trial_status"
    safety_state = f"{prefix}/safety_state"
    odom_topic = f"{prefix}/odom"

    return [
        Node(
            package="ros2_qgip_stack",
            executable="tf_leader_detection_node",
            name="tf_leader_detection_node",
            output="screen",
            parameters=[
                {
                    "follower_frame": LaunchConfiguration("follower_frame"),
                    "leader_frames": LaunchConfiguration("leader_frames"),
                    "leader_ids": LaunchConfiguration("leader_ids"),
                    "detections_topic": detections_raw,
                    "selected_leader_topic": selected_leader,
                    "publish_hz": 20.0,
                }
            ],
        ),
        Node(
            package="ros2_qgip_stack",
            executable="fault_injection_node",
            name="fault_injection_node",
            output="screen",
            parameters=[
                {
                    "input_topic": detections_raw,
                    "output_topic": detections_faulty,
                    "dropout_duration_s": _float_param("dropout_duration_s"),
                    "position_noise_std_m": _float_param("position_noise_std_m"),
                    "delay_s": _float_param("delay_s"),
                    "false_positive_rate": _float_param("false_positive_rate"),
                    "false_negative_rate": _float_param("false_negative_rate"),
                    "confidence_scale": _float_param("confidence_scale"),
                    "id_switch_probability": _float_param("id_switch_probability"),
                }
            ],
        ),
        Node(
            package="ros2_qgip_stack",
            executable="pop_nis_kf_node",
            name="pop_nis_kf_node",
            output="screen",
            parameters=[
                {
                    "input_topic": detections_faulty,
                    "selected_leader_topic": selected_leader,
                    "output_topic": pop_state,
                    "max_abs_y_m": 1.5,
                    "leader_id_filter": LaunchConfiguration("leader_id_filter"),
                    "confidence_threshold": _float_param("confidence_threshold"),
                    "nis_soft_threshold": _float_param("nis_soft_threshold"),
                    "nis_hard_threshold": _float_param("nis_hard_threshold"),
                    "r_inflation": _float_param("r_inflation"),
                    "ghost_horizon_s": _float_param("ghost_horizon_s"),
                    "lost_timeout_s": _float_param("lost_timeout_s"),
                }
            ],
        ),
        Node(
            package="ros2_qgip_stack",
            executable="velocity_safety_controller_node",
            name="velocity_safety_controller_node",
            output="screen",
            parameters=[
                {
                    "pop_state_topic": pop_state,
                    "odom_topic": odom_topic,
                    "cmd_vel_safe_topic": cmd_vel_safe,
                    "debug_topic": mpc_debug,
                    "safety_state_topic": safety_state,
                    "max_speed_mps": _float_param("max_speed_mps"),
                }
            ],
        ),
        Node(
            package="ros2_qgip_stack",
            executable="trial_supervisor_node",
            name="trial_supervisor_node",
            output="screen",
            parameters=[
                {
                    "pop_state_topic": pop_state,
                    "cmd_vel_safe_topic": cmd_vel_safe,
                    "status_topic": trial_status,
                    "safety_state_topic": safety_state,
                    "results_csv_path": LaunchConfiguration("results_csv_path"),
                }
            ],
        ),
    ]


def _float_param(name: str) -> ParameterValue:
    return ParameterValue(LaunchConfiguration(name), value_type=float)
