# Pre-Real-Robot Checklist

Use this checklist before any closed-loop run with multiple ROS2 wheeled robots.

## System

- [ ] All robots use the same `ROS_DOMAIN_ID`.
- [ ] Each robot has a unique namespace: `/robot_1`, `/robot_2`, `/robot_3`.
- [ ] Each robot publishes a unique `base_link` frame under its robot prefix.
- [ ] Logger machine can see `/tf`, `/odom`, and robot command topics.
- [ ] Clocks are synchronized closely enough for latency measurements.
- [ ] rosbag2 storage path has enough disk space for video/sensor logs.

## Safety

- [ ] Physical E-stop works and is assigned to one operator.
- [ ] Software bridge from `/cmd_vel_safe` to the real base can be disabled.
- [ ] First dry run publishes `/cmd_vel_safe` only, not `/cmd_vel`.
- [ ] Speed limit starts at 0.2 m/s.
- [ ] Marked test area has no pedestrians or hard obstacles.
- [ ] Soft bumper or buffer space is available between follower and leader.
- [ ] Abort thresholds are visible to the operators.

## Data Contract

- [ ] `/robot_1/detections_raw` publishes JSON `detections`.
- [ ] `/robot_1/detections_faulty` changes as expected under injected faults.
- [ ] `/robot_1/qgip/pop_state` reports `TRACKING`, `DEGRADED`, `GHOST`, or `LOST`.
- [ ] `/robot_1/qgip/mpc_debug` reports selected speed and safety stop reason.
- [ ] `/robot_1/qgip/trial_status` reports min distance, lost, near-miss, and latency.

## Preflight Pass Criteria

- [ ] TF follower-to-leader transform is stable at 10 Hz or higher.
- [ ] No-fault detection follows the physical leader with plausible distance.
- [ ] 0.5 s dropout produces GHOST then recovery.
- [ ] 1.0 s dropout produces conservative slow/stop behavior.
- [ ] Delayed detections do not produce sudden acceleration.
- [ ] HIL p95 latency is below 100 ms.
- [ ] All trial metadata are recorded in CSV and rosbag.

## Paper Artifacts

- [ ] One table for offline/HIL preflight metrics.
- [ ] One table for closed-loop scaled robot trials.
- [ ] One time-series figure with dropout, NIS, POP state, headway, and command.
- [ ] One video split screen: raw scene, leader state, POP/NIS mode, command.
