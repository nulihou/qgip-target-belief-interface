#!/usr/bin/env python3
"""Publish leader/distractor detections from multi-robot TF frames."""

from __future__ import annotations

import math
from typing import Any

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener

from .json_contract import dumps_payload


class TFLeaderDetectionNode(Node):
    def __init__(self) -> None:
        super().__init__("tf_leader_detection_node")
        self.declare_parameter("follower_frame", "robot_1/base_link")
        self.declare_parameter("leader_frames", "robot_2/base_link")
        self.declare_parameter("leader_ids", "")
        self.declare_parameter("detections_topic", "/robot_1/detections_raw")
        self.declare_parameter("selected_leader_topic", "/robot_1/qgip/selected_leader")
        self.declare_parameter("publish_hz", 20.0)
        self.declare_parameter("confidence", 0.95)
        self.declare_parameter("max_detection_range_m", 4.0)
        self.declare_parameter("leader_class_name", "leader")

        self.follower_frame = str(self.get_parameter("follower_frame").value)
        self.leader_frames = _as_list(self.get_parameter("leader_frames").value)
        self.leader_ids = _as_list(self.get_parameter("leader_ids").value)
        topic = str(self.get_parameter("detections_topic").value)
        selected_topic = str(self.get_parameter("selected_leader_topic").value)
        hz = max(1.0, float(self.get_parameter("publish_hz").value))

        self.confidence = float(self.get_parameter("confidence").value)
        self.max_detection_range_m = float(self.get_parameter("max_detection_range_m").value)
        self.leader_class_name = str(self.get_parameter("leader_class_name").value)
        self.prev_pose: dict[str, tuple[float, float, float]] = {}

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.publisher = self.create_publisher(String, topic, 10)
        self.selected_publisher = self.create_publisher(String, selected_topic, 10)
        self.timer = self.create_timer(1.0 / hz, self._on_timer)

        self.get_logger().info(
            f"TF detections: follower={self.follower_frame}, leaders={self.leader_frames}, topic={topic}, selected={selected_topic}"
        )

    def _on_timer(self) -> None:
        stamp_s = self.get_clock().now().nanoseconds * 1e-9
        detections: list[dict[str, Any]] = []
        for index, frame in enumerate(self.leader_frames):
            leader_id = self.leader_ids[index] if index < len(self.leader_ids) else _id_from_frame(frame)
            try:
                transform = self.tf_buffer.lookup_transform(self.follower_frame, frame, Time())
            except TransformException as exc:
                self.get_logger().debug(f"TF unavailable for {frame}: {exc}")
                continue

            translation = transform.transform.translation
            x = float(translation.x)
            y = float(translation.y)
            distance = math.hypot(x, y)
            if distance > self.max_detection_range_m:
                continue

            vx, vy = self._estimate_velocity(leader_id, x, y, stamp_s)
            detections.append(
                {
                    "id": leader_id,
                    "class_name": self.leader_class_name if index == 0 else "distractor",
                    "x": x,
                    "y": y,
                    "vx": vx,
                    "vy": vy,
                    "confidence": self.confidence,
                    "stamp_s": stamp_s,
                }
            )

        self.publisher.publish(String(data=dumps_payload({"stamp_s": stamp_s, "detections": detections})))
        selected = _selected_leader_payload(detections)
        selected["stamp_s"] = stamp_s
        self.selected_publisher.publish(String(data=dumps_payload(selected)))

    def _estimate_velocity(self, leader_id: str, x: float, y: float, stamp_s: float) -> tuple[float, float]:
        previous = self.prev_pose.get(leader_id)
        self.prev_pose[leader_id] = (x, y, stamp_s)
        if previous is None:
            return 0.0, 0.0
        px, py, pt = previous
        dt = max(1e-3, stamp_s - pt)
        return (x - px) / dt, (y - py) / dt


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return []


def _id_from_frame(frame: str) -> str:
    clean = frame.strip("/")
    return clean.split("/")[0] if "/" in clean else clean


def _selected_leader_payload(detections: list[dict[str, Any]]) -> dict[str, Any]:
    if not detections:
        return {"leader_id": None, "confidence": 0.0, "rank": None, "candidate_count": 0}
    ordered = sorted(detections, key=lambda item: (item["x"] < 0.0, abs(item["y"]), item["x"]))
    leader = ordered[0]
    return {
        "leader_id": leader["id"],
        "confidence": leader["confidence"],
        "rank": 1,
        "candidate_count": len(detections),
    }


def main() -> None:
    rclpy.init()
    node = TFLeaderDetectionNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
