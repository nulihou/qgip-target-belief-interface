#!/usr/bin/env python3
"""ROS2 wrapper around the pure Python detection fault injector."""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from .json_contract import dumps_payload, loads_payload, normalize_detections
from .fault_injection_core import Detection, DetectionFaultInjector, FaultConfig


class FaultInjectionNode(Node):
    def __init__(self) -> None:
        super().__init__("fault_injection_node")
        self.declare_parameter("input_topic", "/robot_1/detections_raw")
        self.declare_parameter("output_topic", "/robot_1/detections_faulty")
        self.declare_parameter("dropout_period_s", 5.0)
        self.declare_parameter("dropout_duration_s", 0.0)
        self.declare_parameter("position_noise_std_m", 0.0)
        self.declare_parameter("velocity_noise_std_mps", 0.0)
        self.declare_parameter("false_positive_rate", 0.0)
        self.declare_parameter("false_negative_rate", 0.0)
        self.declare_parameter("confidence_scale", 1.0)
        self.declare_parameter("delay_s", 0.0)
        self.declare_parameter("id_switch_probability", 0.0)
        self.declare_parameter("random_seed", 7)

        self.injector = DetectionFaultInjector(
            FaultConfig(
                dropout_period_s=float(self.get_parameter("dropout_period_s").value),
                dropout_duration_s=float(self.get_parameter("dropout_duration_s").value),
                position_noise_std_m=float(self.get_parameter("position_noise_std_m").value),
                velocity_noise_std_mps=float(self.get_parameter("velocity_noise_std_mps").value),
                false_positive_rate=float(self.get_parameter("false_positive_rate").value),
                false_negative_rate=float(self.get_parameter("false_negative_rate").value),
                confidence_scale=float(self.get_parameter("confidence_scale").value),
                delay_s=float(self.get_parameter("delay_s").value),
                id_switch_probability=float(self.get_parameter("id_switch_probability").value),
                random_seed=int(self.get_parameter("random_seed").value),
            )
        )
        input_topic = str(self.get_parameter("input_topic").value)
        output_topic = str(self.get_parameter("output_topic").value)
        self.publisher = self.create_publisher(String, output_topic, 10)
        self.subscription = self.create_subscription(String, input_topic, self._on_msg, 10)
        self.get_logger().info(f"Fault injection: {input_topic} -> {output_topic}")

    def _on_msg(self, msg: String) -> None:
        try:
            payload = loads_payload(msg.data)
            stamp_s = float(payload.get("stamp_s", self.get_clock().now().nanoseconds * 1e-9))
            detections = [
                Detection(
                    object_id=det["id"],
                    x=det["x"],
                    y=det["y"],
                    vx=det["vx"],
                    vy=det["vy"],
                    confidence=det["confidence"],
                    class_name=det["class_name"],
                    stamp_s=det["stamp_s"],
                )
                for det in normalize_detections(payload)
            ]
            faulty = self.injector.apply(detections, stamp_s)
            output = {
                "stamp_s": stamp_s,
                "detections": [
                    {
                        "id": det.object_id,
                        "class_name": det.class_name,
                        "x": det.x,
                        "y": det.y,
                        "vx": det.vx,
                        "vy": det.vy,
                        "confidence": det.confidence,
                        "stamp_s": det.stamp_s,
                    }
                    for det in faulty
                ],
            }
            self.publisher.publish(String(data=dumps_payload(output)))
        except Exception as exc:  # pragma: no cover - online guardrail
            self.get_logger().warning(f"Dropping malformed detection payload: {exc}")


def main() -> None:
    rclpy.init()
    node = FaultInjectionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
