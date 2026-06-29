# Real-Robot Deployment Plan

## Purpose

Add real-system evidence suitable for a strict RA-L review. The goal is not public-road autonomy; it is controlled closed-loop validation under real sensor delay, tracking noise, and induced perception degradation.

## Recommended Platform

Start with a 1/10 or 1/5 Ackermann robot platform. If a full-size low-speed drive-by-wire platform is available, use it as a stronger follow-up.

Minimum hardware:

- Ackermann chassis with speed and steering control.
- Jetson Orin Nano / Xavier / small GPU laptop.
- Front RGB-D camera, preferably Intel RealSense.
- Optional 2D LiDAR.
- Wheel odometry and IMU.
- Remote E-stop.
- Soft target or safety bumper for low-speed tests.

## ROS2 Node Contract

### Inputs

- `/camera/color/image_raw`
- `/camera/depth/image_rect_raw`
- `/odom`
- `/imu`
- Optional `/scan` or `/points`

### Internal Topics

- `/qgip/detections`: detected candidate objects with relative pose, confidence, and class.
- `/qgip/graph`: scene graph node features.
- `/qgip/leader`: selected leader candidate.
- `/qgip/pop_state`: NIS-gated POP state, covariance, mode.
- `/qgip/mpc_debug`: selected trajectory, costs, feasibility status.
- `/qgip/safety_state`: watchdog, near-miss, E-stop, timeout status.

### Output

- `/drive`: `ackermann_msgs/AckermannDriveStamped`

## Minimal Real Perception Strategy

Use AprilTag or ArUco on the leader vehicle for the first hardware experiment. This is acceptable if the paper states that the real-robot experiment validates closed-loop timing, tracking, dropout recovery, and control stability, while CARLA covers broader detection complexity.

Optional upgrade:

- YOLO + depth for leader detection.
- LiDAR clustering for leader range.
- Sensor fusion between RGB-D and LiDAR.

## Integration With Existing Code

The existing `MPCController.solve(...)` returns `[accel, steer]`. For the robot:

- Set the controller wheelbase to the measured robot wheelbase.
- Set max steering to the physical steering limit.
- Convert acceleration to target speed:
  - `v_cmd = clip(v_current + accel * dt, 0, v_max)`
  - `steering_angle = clip(steer, -delta_max, delta_max)`
- Publish `AckermannDriveStamped`.

Do not use CARLA semantic segmentation in real-robot experiments. Replace it with RGB-D/AprilTag or detector outputs.

## Real-Robot Experiment Matrix

Minimum publishable target: 80-120 closed-loop trials.

Stronger target: about 180 trials.

| Scenario | Speed | Fault | Repeats |
| --- | --- | --- | --- |
| Straight following | low / medium | none, 0.5 s dropout, 1.0 s dropout | 5 each |
| Lead braking | low / medium | blackout during braking | 5 each |
| Curved following | low / medium | camera occlusion or detector dropout | 5 each |
| Adjacent-lane distractor | low / medium | false leader plus dropout | 5 each |
| Cut-in / cut-out | low / medium | ID switch or partial occlusion | 5 each |
| Stop-and-go | low / medium | frequent dropout | 5 each |

## Safety Rules

Every trial must have pre-defined abort rules:

- TTC below threshold.
- Headway below threshold.
- Lateral deviation outside lane/test corridor.
- Controller timeout above threshold.
- Remote E-stop.
- Software safety supervisor override.

Dangerous baselines should run in shadow mode, HIL replay, or with a safety supervisor. Do not allow unprotected collision trials.

## Required Real-Robot Metrics

- Trials.
- Contact/collision.
- Safety intervention.
- Near-miss.
- Completion.
- Min TTC.
- Min headway.
- Dropout recovery time.
- Leader ID switch count.
- Headway RMSE.
- Jerk p95.
- Latency p99.
- CPU/GPU load.

## Paper Wording

Use:

"Controlled low-speed Ackermann robot trials."

Avoid:

"Full real-vehicle deployment" unless a full-size platform is actually used.
