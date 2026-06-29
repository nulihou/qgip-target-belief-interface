# Multi-ROS2-Car Preflight Plan

This plan makes the real-robot section publishable before the first risky
closed-loop run. It uses multiple ROS2 wheeled robots as a scaled real-robot
validation platform for POP, NIS-gated KF, fault injection, and safety control.

## Platform Roles

| Role | Robot | Required output |
| --- | --- | --- |
| Follower under test | `/robot_1` | `/robot_1/odom`, `robot_1/base_link`, optional camera/LiDAR |
| Primary leader | `/robot_2` | `/robot_2/odom`, `robot_2/base_link` |
| Distractor | `/robot_3` | `/robot_3/odom`, `robot_3/base_link` |
| Logger station | laptop/NUC | rosbag2, video, CSV summaries |

Rotate the roles after the stack works so robot-specific odometry bias is not
confounded with method performance.

## Stage A: Network and TF Dry Run

Goal: verify that multiple robots can be seen consistently before perception or
control is enabled.

Required checks:

- same `ROS_DOMAIN_ID` across robots and logger;
- synchronized clocks through NTP/chrony or a single router clock source;
- unique namespaces: `/robot_1`, `/robot_2`, `/robot_3`;
- unique TF frames: `robot_i/base_link`, `robot_i/odom`;
- stable TF echo for follower-to-leader and follower-to-distractor transforms.

Commands:

```bash
ros2 topic list
ros2 run tf2_ros tf2_echo robot_1/base_link robot_2/base_link
ros2 run tf2_ros tf2_echo robot_1/base_link robot_3/base_link
```

Pass criteria:

- transform update rate is at least 10 Hz;
- follower-to-leader relative position is physically plausible;
- no duplicated frame ids or namespace collisions.

## Stage B: Detection Stream and Fault Injection

Goal: generate a reproducible detection stream without relying on a neural
detector yet.

Run the package dry, with `/robot_1/cmd_vel_safe` disconnected from the base:

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link,robot_3/base_link \
  leader_ids:=robot_2,robot_3 \
  max_speed_mps:=0.3
```

Record:

```bash
ros2 bag record -o preflight_tf_faults \
  /tf /tf_static \
  /robot_1/odom /robot_2/odom /robot_3/odom \
  /robot_1/detections_raw /robot_1/detections_faulty \
  /robot_1/qgip/pop_state /robot_1/qgip/mpc_debug \
  /robot_1/qgip/trial_status /robot_1/cmd_vel_safe
```

Fault conditions for paper preflight:

| Condition | Launch override |
| --- | --- |
| no fault | `dropout_duration_s:=0.0` |
| short dropout | `dropout_duration_s:=0.3` |
| paper-aligned dropout | `dropout_duration_s:=0.5` |
| long dropout | `dropout_duration_s:=1.0` |
| noisy detections | `position_noise_std_m:=0.05` |
| delayed detections | `delay_s:=0.1` |

## Stage C: HIL Shadow Control

Goal: prove the stack runs at real timing and outputs safe commands without
driving a robot.

Procedure:

1. Replay Stage B bags with `ros2 bag play <bag_dir> --clock`.
2. Launch POP/NIS and controller nodes with actuator bridge disabled.
3. Record command latency, safety stops, near-miss flags, and lost periods.
4. Compare `Std KF + controller` against `POP/NIS + controller` on the same bags.

Pass criteria:

- p95 command latency below 100 ms;
- no stale-state command beyond the watchdog timeout;
- dropout periods lead to GHOST or LOST, not aggressive acceleration;
- recovery time after dropout is measurable and logged.

Baseline profiles:

- `Full POP/NIS`: proposed method.
- `Std-KF-like`: disable effective NIS gating with very large NIS thresholds and no R inflation.
- `No-POP`: set `ghost_horizon_s=0.0` and `lost_timeout_s=0.1`.

Use `baseline_launch_profiles.md` for exact commands. The same rosbag must be
replayed for every method profile.

## Stage D: Low-Speed Closed-Loop Gate

Goal: enable physical closed-loop only after Stage A-C pass.

Start with one follower and one leader at 0.2 m/s. Keep the distractor stopped
until the basic follower-leader run is stable.

Enable base control only through a separate bridge:

```text
/robot_1/cmd_vel_safe -> safety bridge -> /robot_1/cmd_vel
```

Abort rules:

- distance below 0.25 m;
- estimated TTC below 0.8 s;
- command timeout above 100 ms;
- manual E-stop or operator call;
- robot leaves the marked corridor.

## Minimal Publishable Pre-Real-Car Dataset

Before full closed-loop trials, collect:

| Dataset | Repeats | Output |
| --- | ---: | --- |
| TF dry runs, no fault | 10 | detection and POP consistency |
| offline fault bags | 30 | dropout/noise/delay recovery |
| HIL shadow-control bags | 30 | latency and fail-safe behavior |
| closed-loop gate at 0.2 m/s | 20 | conservative control sanity |

This does not replace the full real-robot trial matrix, but it makes the
transition to real closed-loop experiments controlled and defensible.

The concrete starter matrix is in `preflight_trials_matrix.csv`.
