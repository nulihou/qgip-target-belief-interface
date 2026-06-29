#!/usr/bin/env python3
"""ROS2 POP/NIS tracker node for selected leader state estimation."""

from __future__ import annotations

import math

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .json_contract import dumps_payload, loads_payload, normalize_detections, select_front_leader
from .pop_nis_kf_core import NISGatedPOP, POPConfig, TrackMode


class POPNISKFNode(Node):
    def __init__(self) -> None:
        super().__init__("pop_nis_kf_node")
        self.declare_parameter("input_topic", "/robot_1/detections_faulty")
        self.declare_parameter("selected_leader_topic", "/robot_1/qgip/selected_leader")
        self.declare_parameter("output_topic", "/robot_1/qgip/pop_state")
        self.declare_parameter("dt", 0.05)
        self.declare_parameter("confidence_threshold", 0.5)
        self.declare_parameter("high_confidence_threshold", 0.85)
        self.declare_parameter("nis_soft_threshold", 12.0)
        self.declare_parameter("nis_hard_threshold", 20.0)
        self.declare_parameter("r_inflation", 10.0)
        self.declare_parameter("ghost_horizon_s", 1.0)
        self.declare_parameter("lost_timeout_s", 1.5)
        self.declare_parameter("leader_id_filter", "")
        self.declare_parameter("max_abs_y_m", 1.5)

        cfg = POPConfig(
            dt=float(self.get_parameter("dt").value),
            confidence_threshold=float(self.get_parameter("confidence_threshold").value),
            high_confidence_threshold=float(self.get_parameter("high_confidence_threshold").value),
            nis_soft_threshold=float(self.get_parameter("nis_soft_threshold").value),
            nis_hard_threshold=float(self.get_parameter("nis_hard_threshold").value),
            r_inflation=float(self.get_parameter("r_inflation").value),
            ghost_horizon_s=float(self.get_parameter("ghost_horizon_s").value),
            lost_timeout_s=float(self.get_parameter("lost_timeout_s").value),
        )
        self.tracker = NISGatedPOP(cfg)
        self.initialized = False
        self.leader_id_filter = str(self.get_parameter("leader_id_filter").value)
        self.selected_leader_id: str | None = None
        self.max_abs_y_m = float(self.get_parameter("max_abs_y_m").value)

        input_topic = str(self.get_parameter("input_topic").value)
        selected_topic = str(self.get_parameter("selected_leader_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        self.publisher = self.create_publisher(String, output_topic, 10)
        self.subscription = self.create_subscription(String, input_topic, self._on_msg, 10)
        self.selected_subscription = self.create_subscription(String, selected_topic, self._on_selected, 10)
        self.get_logger().info(f"POP/NIS: {input_topic}, selected={selected_topic} -> {output_topic}")

    def _on_selected(self, msg: String) -> None:
        try:
            payload = loads_payload(msg.data)
            leader_id = payload.get("leader_id")
            self.selected_leader_id = str(leader_id) if leader_id else None
        except Exception as exc:  # pragma: no cover - online guardrail
            self.get_logger().warning(f"Ignoring malformed selected-leader payload: {exc}")

    def _on_msg(self, msg: String) -> None:
        stamp_s = self.get_clock().now().nanoseconds * 1e-9
        try:
            payload = loads_payload(msg.data)
            stamp_s = float(payload.get("stamp_s", stamp_s))
            detections = normalize_detections(payload)
            leader_id_filter = self.leader_id_filter or self.selected_leader_id or ""
            leader = select_front_leader(
                detections,
                leader_id_filter=leader_id_filter,
                min_confidence=0.0,
                max_abs_y_m=self.max_abs_y_m,
                front_only=True,
            )
            if leader is None:
                state = self.tracker.update(None, confidence=0.0) if self.initialized else self.tracker.state()
            else:
                measurement = np.array([leader["x"], leader["y"], leader["vx"], leader["vy"]], dtype=float)
                if not self.initialized or self.tracker.mode == TrackMode.LOST:
                    state = self.tracker.reset(measurement, leader_id=leader["id"])
                    self.initialized = True
                else:
                    state = self.tracker.update(measurement, confidence=leader["confidence"], leader_id=leader["id"])
        except Exception as exc:  # pragma: no cover - online guardrail
            self.get_logger().warning(f"POP/NIS update failed: {exc}")
            state = self.tracker.update(None, confidence=0.0) if self.initialized else self.tracker.state()

        self.publisher.publish(String(data=dumps_payload(self._state_payload(state, stamp_s))))

    @staticmethod
    def _state_payload(state, stamp_s: float) -> dict:
        nis = None if isinstance(state.nis, float) and math.isnan(state.nis) else state.nis
        return {
            "stamp_s": stamp_s,
            "mode": state.mode.value if hasattr(state.mode, "value") else str(state.mode),
            "leader_id": state.leader_id,
            "x": float(state.x[0]),
            "y": float(state.x[1]),
            "vx": float(state.x[2]),
            "vy": float(state.x[3]),
            "covariance_diag": [float(v) for v in np.diag(state.P)],
            "cov_diag": [float(v) for v in np.diag(state.P)],
            "nis": nis,
            "ghost_age_s": float(state.ghost_age_s),
        }


def main() -> None:
    rclpy.init()
    node = POPNISKFNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
