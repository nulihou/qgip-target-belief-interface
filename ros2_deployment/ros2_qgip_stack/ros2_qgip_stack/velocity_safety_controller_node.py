#!/usr/bin/env python3
"""Low-speed velocity safety controller for wheeled robot following."""

from __future__ import annotations

import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from std_msgs.msg import String

from .json_contract import dumps_payload, loads_payload


class VelocitySafetyControllerNode(Node):
    def __init__(self) -> None:
        super().__init__("velocity_safety_controller_node")
        self.declare_parameter("pop_state_topic", "/robot_1/qgip/pop_state")
        self.declare_parameter("odom_topic", "/robot_1/odom")
        self.declare_parameter("cmd_vel_safe_topic", "/robot_1/cmd_vel_safe")
        self.declare_parameter("debug_topic", "/robot_1/qgip/mpc_debug")
        self.declare_parameter("safety_state_topic", "/robot_1/safety_state")
        self.declare_parameter("control_hz", 20.0)
        self.declare_parameter("state_timeout_s", 0.3)
        self.declare_parameter("max_speed_mps", 0.5)
        self.declare_parameter("max_angular_radps", 1.0)
        self.declare_parameter("max_accel_mps2", 0.6)
        self.declare_parameter("safety_distance_base_m", 0.35)
        self.declare_parameter("time_headway_s", 1.0)
        self.declare_parameter("near_miss_distance_m", 0.25)
        self.declare_parameter("kp_gap", 0.8)
        self.declare_parameter("kp_lateral", 1.2)
        self.declare_parameter("kv_rel", 0.2)
        self.declare_parameter("degraded_speed_scale", 0.7)
        self.declare_parameter("ghost_speed_scale", 0.35)

        self.state_timeout_s = float(self.get_parameter("state_timeout_s").value)
        self.max_speed_mps = float(self.get_parameter("max_speed_mps").value)
        self.max_angular_radps = float(self.get_parameter("max_angular_radps").value)
        self.max_accel_mps2 = float(self.get_parameter("max_accel_mps2").value)
        self.safety_distance_base_m = float(self.get_parameter("safety_distance_base_m").value)
        self.time_headway_s = float(self.get_parameter("time_headway_s").value)
        self.near_miss_distance_m = float(self.get_parameter("near_miss_distance_m").value)
        self.kp_gap = float(self.get_parameter("kp_gap").value)
        self.kp_lateral = float(self.get_parameter("kp_lateral").value)
        self.kv_rel = float(self.get_parameter("kv_rel").value)
        self.degraded_speed_scale = float(self.get_parameter("degraded_speed_scale").value)
        self.ghost_speed_scale = float(self.get_parameter("ghost_speed_scale").value)

        self.latest_state: dict | None = None
        self.current_speed_mps = 0.0
        self.last_cmd_v = 0.0
        self.last_update_s = self._now_s()

        pop_topic = str(self.get_parameter("pop_state_topic").value)
        odom_topic = str(self.get_parameter("odom_topic").value)
        cmd_topic = str(self.get_parameter("cmd_vel_safe_topic").value)
        debug_topic = str(self.get_parameter("debug_topic").value)
        safety_topic = str(self.get_parameter("safety_state_topic").value)
        hz = max(1.0, float(self.get_parameter("control_hz").value))

        self.cmd_pub = self.create_publisher(Twist, cmd_topic, 10)
        self.debug_pub = self.create_publisher(String, debug_topic, 10)
        self.safety_pub = self.create_publisher(String, safety_topic, 10)
        self.state_sub = self.create_subscription(String, pop_topic, self._on_state, 10)
        self.odom_sub = self.create_subscription(Odometry, odom_topic, self._on_odom, 10)
        self.timer = self.create_timer(1.0 / hz, self._on_timer)
        self.get_logger().info(f"Velocity safety controller: {pop_topic} -> {cmd_topic}, {safety_topic}")

    def _on_state(self, msg: String) -> None:
        try:
            self.latest_state = loads_payload(msg.data)
        except Exception as exc:  # pragma: no cover - online guardrail
            self.get_logger().warning(f"Ignoring malformed POP state: {exc}")

    def _on_odom(self, msg: Odometry) -> None:
        vx = msg.twist.twist.linear.x
        vy = msg.twist.twist.linear.y
        self.current_speed_mps = math.hypot(vx, vy)

    def _on_timer(self) -> None:
        now_s = self._now_s()
        dt = max(1e-3, now_s - self.last_update_s)
        self.last_update_s = now_s

        cmd = Twist()
        debug = {
            "stamp_s": now_s,
            "mode": "NO_STATE",
            "selected_speed_mps": 0.0,
            "selected_v_mps": 0.0,
            "selected_w_radps": 0.0,
            "safety_stop": True,
            "reason": "missing_state",
        }

        state = self.latest_state
        if state is not None:
            age_s = now_s - float(state.get("stamp_s", now_s))
            mode = str(state.get("mode", "LOST"))
            x = float(state.get("x", 0.0))
            y = float(state.get("y", 0.0))
            vx = float(state.get("vx", 0.0))
            distance = math.hypot(x, y)
            desired_gap = self.safety_distance_base_m + self.time_headway_s * max(0.0, self.current_speed_mps)
            headway_m = max(0.0, x)
            ttc_s = distance / abs(vx) if vx < -1e-3 and distance > 0.0 else None
            stop = age_s > self.state_timeout_s or mode == "LOST" or x <= self.near_miss_distance_m

            if not stop:
                v = self.kp_gap * (x - desired_gap) + self.kv_rel * vx
                if mode == "DEGRADED":
                    v *= self.degraded_speed_scale
                elif mode == "GHOST":
                    v *= self.ghost_speed_scale
                v = _clip(v, 0.0, self.max_speed_mps)
                w = _clip(self.kp_lateral * y, -self.max_angular_radps, self.max_angular_radps)
                cmd.linear.x = self._rate_limit(v, self.last_cmd_v, self.max_accel_mps2, dt)
                cmd.angular.z = w
                debug.update(
                    {
                        "mode": mode,
                        "selected_speed_mps": cmd.linear.x,
                        "selected_v_mps": cmd.linear.x,
                        "selected_w_radps": cmd.angular.z,
                        "safety_stop": False,
                        "reason": "tracking",
                        "leader_x_m": x,
                        "leader_y_m": y,
                        "leader_distance_m": distance,
                        "headway_m": headway_m,
                        "ttc_s": ttc_s,
                        "desired_gap_m": desired_gap,
                        "state_age_s": age_s,
                    }
                )
            else:
                debug.update(
                    {
                        "mode": mode,
                        "safety_stop": True,
                        "reason": "lost_or_unsafe" if mode == "LOST" or x <= self.near_miss_distance_m else "stale_state",
                        "leader_x_m": x,
                        "leader_y_m": y,
                        "leader_distance_m": distance,
                        "headway_m": headway_m,
                        "ttc_s": ttc_s,
                        "state_age_s": age_s,
                    }
                )

        self.last_cmd_v = cmd.linear.x
        self.cmd_pub.publish(cmd)
        self.debug_pub.publish(String(data=dumps_payload(debug)))
        self.safety_pub.publish(String(data=dumps_payload(_safety_state_payload(debug))))

    def _rate_limit(self, desired: float, previous: float, max_accel: float, dt: float) -> float:
        delta = _clip(desired - previous, -max_accel * dt, max_accel * dt)
        return previous + delta

    def _now_s(self) -> float:
        return self.get_clock().now().nanoseconds * 1e-9


def _clip(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def _safety_state_payload(debug: dict) -> dict:
    keys = [
        "stamp_s",
        "mode",
        "selected_speed_mps",
        "selected_v_mps",
        "selected_w_radps",
        "safety_stop",
        "reason",
        "leader_distance_m",
        "headway_m",
        "ttc_s",
        "desired_gap_m",
        "state_age_s",
    ]
    return {key: debug.get(key) for key in keys if key in debug}


def main() -> None:
    rclpy.init()
    node = VelocitySafetyControllerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
