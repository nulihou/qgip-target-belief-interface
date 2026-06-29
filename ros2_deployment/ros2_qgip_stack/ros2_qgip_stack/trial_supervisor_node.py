#!/usr/bin/env python3
"""Online trial monitor for ROS2 robot preflight and closed-loop trials."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String

from .json_contract import dumps_payload, loads_payload


class TrialSupervisorNode(Node):
    def __init__(self) -> None:
        super().__init__("trial_supervisor_node")
        self.declare_parameter("pop_state_topic", "/robot_1/qgip/pop_state")
        self.declare_parameter("cmd_vel_safe_topic", "/robot_1/cmd_vel_safe")
        self.declare_parameter("status_topic", "/robot_1/qgip/trial_status")
        self.declare_parameter("safety_state_topic", "/robot_1/safety_state")
        self.declare_parameter("publish_hz", 2.0)
        self.declare_parameter("trial_id", "preflight_trial")
        self.declare_parameter("method", "full_qgip_pop_nis")
        self.declare_parameter("scenario", "preflight")
        self.declare_parameter("fault_type", "none")
        self.declare_parameter("speed_level", "low")
        self.declare_parameter("near_miss_distance_m", 0.25)
        self.declare_parameter("results_csv_path", "")

        self.trial_id = str(self.get_parameter("trial_id").value)
        self.method = str(self.get_parameter("method").value)
        self.scenario = str(self.get_parameter("scenario").value)
        self.fault_type = str(self.get_parameter("fault_type").value)
        self.speed_level = str(self.get_parameter("speed_level").value)
        self.near_miss_distance_m = float(self.get_parameter("near_miss_distance_m").value)
        self.results_csv_path = str(self.get_parameter("results_csv_path").value)

        self.started_s = self._now_s()
        self.min_distance_m = float("inf")
        self.min_ttc_s = float("inf")
        self.near_miss = False
        self.lost = False
        self.safety_stop = False
        self.last_cmd_v = 0.0
        self.state_count = 0
        self.latencies_ms: list[float] = []
        self.last_mode = "NO_STATE"
        self.last_safety_reason = "none"
        self.safety_state_count = 0
        self._wrote_summary = False

        pop_topic = str(self.get_parameter("pop_state_topic").value)
        cmd_topic = str(self.get_parameter("cmd_vel_safe_topic").value)
        status_topic = str(self.get_parameter("status_topic").value)
        safety_topic = str(self.get_parameter("safety_state_topic").value)
        hz = max(0.5, float(self.get_parameter("publish_hz").value))
        self.status_pub = self.create_publisher(String, status_topic, 10)
        self.state_sub = self.create_subscription(String, pop_topic, self._on_state, 10)
        self.cmd_sub = self.create_subscription(Twist, cmd_topic, self._on_cmd, 10)
        self.safety_sub = self.create_subscription(String, safety_topic, self._on_safety_state, 10)
        self.timer = self.create_timer(1.0 / hz, self._publish_status)
        self.get_logger().info(f"Trial supervisor: {pop_topic}, {cmd_topic}, {safety_topic} -> {status_topic}")

    def _on_state(self, msg: String) -> None:
        now_s = self._now_s()
        try:
            state = loads_payload(msg.data)
        except Exception as exc:  # pragma: no cover - online guardrail
            self.get_logger().warning(f"Ignoring malformed POP state: {exc}")
            return
        self.state_count += 1
        self.last_mode = str(state.get("mode", "NO_STATE"))
        x = float(state.get("x", 0.0))
        y = float(state.get("y", 0.0))
        vx = float(state.get("vx", 0.0))
        distance = math.hypot(x, y)
        if distance > 0.0:
            self.min_distance_m = min(self.min_distance_m, distance)
        if distance <= self.near_miss_distance_m:
            self.near_miss = True
        if self.last_mode == "LOST":
            self.lost = True
        if vx < -1e-3 and distance > 0.0:
            self.min_ttc_s = min(self.min_ttc_s, max(0.0, distance / abs(vx)))
        stamp_s = float(state.get("stamp_s", now_s))
        self.latencies_ms.append(max(0.0, (now_s - stamp_s) * 1000.0))

    def _on_cmd(self, msg: Twist) -> None:
        self.last_cmd_v = float(msg.linear.x)
        if abs(self.last_cmd_v) < 1e-3 and self.last_mode in {"GHOST", "LOST", "NO_STATE"}:
            self.safety_stop = True

    def _on_safety_state(self, msg: String) -> None:
        try:
            state = loads_payload(msg.data)
        except Exception as exc:  # pragma: no cover - online guardrail
            self.get_logger().warning(f"Ignoring malformed safety state: {exc}")
            return
        self.safety_state_count += 1
        self.last_safety_reason = str(state.get("reason", "unspecified"))
        if bool(state.get("safety_stop", False)):
            self.safety_stop = True

    def _publish_status(self) -> None:
        status = self._summary_payload(completion=None)
        self.status_pub.publish(String(data=dumps_payload(status)))

    def _summary_payload(self, completion: bool | None) -> dict:
        latency_mean = sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else None
        latency_p95 = _percentile(self.latencies_ms, 95.0)
        latency_p99 = _percentile(self.latencies_ms, 99.0)
        return {
            "trial_id": self.trial_id,
            "method": self.method,
            "scenario": self.scenario,
            "fault_type": self.fault_type,
            "speed_level": self.speed_level,
            "duration_s": self._now_s() - self.started_s,
            "state_count": self.state_count,
            "last_mode": self.last_mode,
            "completion": completion,
            "near_miss": self.near_miss,
            "lost": self.lost,
            "safety_stop": self.safety_stop,
            "safety_state_count": self.safety_state_count,
            "last_safety_reason": self.last_safety_reason,
            "min_distance_m": None if math.isinf(self.min_distance_m) else self.min_distance_m,
            "min_ttc_s": None if math.isinf(self.min_ttc_s) else self.min_ttc_s,
            "latency_mean_ms": latency_mean,
            "latency_p95_ms": latency_p95,
            "latency_p99_ms": latency_p99,
        }

    def destroy_node(self) -> bool:
        self._append_summary_once()
        return super().destroy_node()

    def _append_summary_once(self) -> None:
        if self._wrote_summary or not self.results_csv_path:
            return
        self._wrote_summary = True
        path = Path(self.results_csv_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists()
        row = self._summary_payload(completion=not (self.near_miss or self.lost))
        fieldnames = [
            "trial_id",
            "method",
            "scenario",
            "speed_level",
            "fault_type",
            "completion",
            "safety_stop",
            "near_miss",
            "lost",
            "min_distance_m",
            "min_ttc_s",
            "latency_mean_ms",
            "latency_p95_ms",
            "latency_p99_ms",
            "state_count",
            "duration_s",
        ]
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow({key: row.get(key) for key in fieldnames})

    def _now_s(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q / 100.0
    lo = int(math.floor(position))
    hi = int(math.ceil(position))
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def main() -> None:
    rclpy.init()
    node = TrialSupervisorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
