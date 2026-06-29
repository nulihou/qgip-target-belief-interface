#!/usr/bin/env python3
"""ROS2 skeleton for bridging QGIP/MPC output to Ackermann drive.

This is a starting point, not a complete deployable node. It documents the
runtime contract needed to move from CARLA control to a small Ackermann robot.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AckermannCommand:
    speed_mps: float
    steering_rad: float
    acceleration_mps2: float


@dataclass
class RobotLimits:
    wheelbase_m: float = 0.33
    max_speed_mps: float = 2.0
    max_steer_rad: float = 0.45
    max_accel_mps2: float = 1.0
    max_decel_mps2: float = 2.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def mpc_to_ackermann(
    current_speed_mps: float,
    accel_mps2: float,
    steer_rad: float,
    dt_s: float,
    limits: RobotLimits,
) -> AckermannCommand:
    """Convert `[accel, steer]` from the existing MPC into Ackermann command values."""
    accel = clamp(accel_mps2, -limits.max_decel_mps2, limits.max_accel_mps2)
    speed = clamp(current_speed_mps + accel * dt_s, 0.0, limits.max_speed_mps)
    steering = clamp(steer_rad, -limits.max_steer_rad, limits.max_steer_rad)
    return AckermannCommand(speed_mps=speed, steering_rad=steering, acceleration_mps2=accel)


def example() -> None:
    limits = RobotLimits()
    command = mpc_to_ackermann(
        current_speed_mps=0.6,
        accel_mps2=-0.5,
        steer_rad=0.2,
        dt_s=0.05,
        limits=limits,
    )
    print(command)


if __name__ == "__main__":
    example()
