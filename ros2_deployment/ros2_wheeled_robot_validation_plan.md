# ROS2 Wheeled Robot Validation Plan

## Positioning

A ROS2 wheeled robot is appropriate for this paper as scaled real-robot closed-loop validation. It should be described as evidence that the POP/NIS-gated tracking and safety-filtered MPC stack works with real sensors, real ROS2 timing, and real actuator dynamics.

It must not be described as a full-scale L4 ACC validation.

Recommended wording:

> We further validate the proposed POP/NIS-gated safety stack on a ROS2 wheeled robot platform under real sensor dropout, delay, occlusion, and closed-loop control.

Avoid:

> We validate full-scale L4 ACC on a real vehicle.

## What The Robot Experiment Validates

The experiment is well matched to the paper because it tests:

1. Whether leader state can be maintained during perception loss.
2. Whether NIS gating detects abnormal observations.
3. Whether tracking recovers after short dropouts.
4. Whether the MPC/safety filter avoids dangerous commands.
5. Whether the full stack runs under real ROS2 timing.

## Minimum Hardware

| Module | Minimum | Stronger |
| --- | --- | --- |
| Base | Differential, Ackermann, or four-wheel wheeled robot | Ackermann robot closer to ACC |
| Control | `/cmd_vel` or Ackermann command | Low-level velocity closed loop |
| Ego state | `/odom` plus optional IMU | wheel odom + IMU + SLAM |
| Front perception | 2D LiDAR, RGB-D, or RGB camera | RGB-D + LiDAR |
| Leader | second robot, RC car, pushed tag target | second ROS2 robot |
| Compute | laptop / Jetson / NUC | Jetson Orin / GPU laptop |
| Safety | E-stop, speed limit, watchdog | independent safety supervisor |

If only one robot is available, the leader may be a pushed target board, RC car, or mobile platform with AprilTag/ArUco markers. A second wheeled robot as leader is more convincing.

## ROS2 System Mapping

| Paper module | ROS2 implementation |
| --- | --- |
| FiLM-GNN / query-guided perception | leader selection from `/detections` |
| POP / NIS-gated KF | node maintaining `[px, py, vx, vy]` and covariance |
| Lattice MPC | `/cmd_vel` or Ackermann speed/steering output |
| Failure injection | drop, delay, noise, false positive on detection topic |
| Fail-safe stop | zero velocity or controlled braking |
| CARLA collision metric | near-miss, E-stop, soft contact, intervention |

## Recommended Three-Stage Experiment

### Stage 0: Real-Log Offline Replay

Record real sensor data without closed-loop control.

Example topics:

```bash
ros2 bag record /camera/image_raw /camera/depth/image_rect_raw /scan /odom /tf /detections /cmd_vel
```

Scenarios:

- leader constant-speed straight motion.
- stop-and-go leader.
- short physical occlusion.
- camera light interference or camera cover.
- adjacent distractor target.
- detection delay injection.

Metrics:

- leader selection accuracy.
- tracking RMSE.
- NIS distribution.
- dropout recovery time.
- ID switch count.
- ghost prediction error.

### Stage 1: Hardware-In-The-Loop Real-Time Replay

Replay rosbag at real rate and let the system output commands, but do not drive the robot.

```bash
ros2 bag play <bag_dir> --clock
```

Report:

- latency mean, p95, p99.
- missed frame rate.
- watchdog trigger count.
- CPU/GPU load.
- message delay.

### Stage 2: Low-Speed Closed-Loop Trials

Run in a closed area: lab corridor, indoor hall, closed parking area, or controlled outdoor space.

Speed range:

- low: 0.2 m/s.
- medium: 0.5 m/s.
- optional high for scale robot only after safety checks: 0.8 m/s.

Minimum target:

- 60-100 closed-loop trials.

Stronger target:

- 120-180 closed-loop trials.

## Parameter Scaling

| Parameter | Vehicle-scale paper | ROS2 wheeled robot |
| --- | ---: | ---: |
| Control frequency | 20 Hz | 10-30 Hz |
| Safety distance | `10 + 1.5v` m | `0.3-0.8 + 1.0v` m |
| Max speed | vehicle scale | 0.2 / 0.5 / 0.8 m/s |
| Ghost horizon | 1.5 s | 0.5-1.5 s |
| Blackout duration | 0.5-2.0 s | 0.3-1.5 s |
| Lateral envelope | vehicle width | robot radius + 0.1-0.2 m |
| Collision | CARLA event | intervention, TTC violation, soft contact |

## Closed-Loop Trial Matrix

Use `real_robot_trials_matrix.csv` as the operational trial sheet.

Minimum scenarios:

- straight following.
- leader braking.
- curved following.
- adjacent distractor.
- stop-and-go.
- long occlusion recovery.

## Failure Injection

### Software Injection

Place a fault node between raw detections and the QGIP/POP stack:

```text
/detections_raw -> fault_injection_node -> /detections_faulty
```

Supported faults:

- detection dropout.
- position noise.
- false positive.
- ID switch.
- timestamp delay.
- confidence drop.

### Physical Injection

Use a small number of physical faults for realism:

- board covering the camera.
- LED glare into the camera.
- partial LiDAR cover.
- object crossing between follower and leader.
- adjacent similar target.
- low-contrast tag or target.

## Required Baselines

Minimum real-robot baselines:

- PID following.
- Rule + safety MPC.
- Standard KF + MPC.
- Full QGIP/POP/NIS + MPC.

If time allows:

- no-POP.
- no-NIS.
- no-query.
- IMM-KF + MPC.
- pure detector following.

## Real-Robot Metrics

Main table columns:

| Method | Trials | Contact | Safety stop | Near-miss | Completion | Lost | Min distance | Recovery time | ID switch | Latency p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

Definitions:

- Contact: soft contact or contact with leader/obstacle.
- Near-miss: distance below a safety threshold, e.g. 0.25 m.
- Safety stop: safety layer or watchdog stops the robot.
- Lost: target lost longer than ghost horizon.
- Completion: designated route/episode completed.
- Recovery time: time after dropout ends until stable following resumes.
- NIS violation rate: fraction of updates above NIS threshold.
- Latency p95/p99: ROS2 end-to-end pipeline latency.

## Differential-Drive Adaptation

If the robot is differential-drive, do not force a vehicle Frenet lattice. Use a velocity lattice:

- sample candidate linear velocity `v`.
- sample candidate angular velocity `omega`.
- roll out 1-2 seconds.
- reject trajectories whose footprint violates the safety envelope.
- minimize tracking, smoothness, and safety costs.

This preserves the core idea: filter unsafe candidate trajectories before optimizing task performance.

## Paper Subsection Title

Recommended subsection:

> Real-Robot Validation on a ROS2 Wheeled Platform

Core caveat:

> This platform is not intended to replicate full-scale vehicle dynamics; instead, it validates real-sensor perception degradation, ROS2 timing, state-estimation recovery, and closed-loop fail-safe behavior.
