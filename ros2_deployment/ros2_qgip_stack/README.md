# ROS2 QGIP Preflight Stack

This package prepares the real-robot validation before closed-loop trials. It
targets multiple ROS2 wheeled robots and keeps interfaces simple by using
`std_msgs/String` JSON payloads until custom messages are frozen.

## Intended Robot Roles

- `/robot_1`: follower under test.
- `/robot_2`: primary leader.
- `/robot_3`: adjacent-lane or nearby distractor.

The stack can be launched for any follower namespace as long as TF frames are
available, for example `robot_1/base_link`, `robot_2/base_link`, and
`robot_3/base_link`.

## Nodes

| Node | Role |
| --- | --- |
| `tf_leader_detection_node` | Converts multi-robot TF transforms into leader/distractor detections. |
| `fault_injection_node` | Injects dropout, noise, delay, false negatives, false positives, and ID switch. |
| `pop_nis_kf_node` | Runs the 4D POP/NIS-gated Kalman filter. |
| `velocity_safety_controller_node` | Publishes low-speed safe `geometry_msgs/Twist` commands. |
| `trial_supervisor_node` | Publishes online trial status and can append trial summaries to CSV. |

## Build

From a ROS2 workspace that contains this package under `src`:

```bash
colcon build --packages-select ros2_qgip_stack
source install/setup.bash
```

## Dry Launch

Do not connect `/robot_1/cmd_vel_safe` to the real base controller during the
first dry run.

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link,robot_3/base_link \
  leader_ids:=robot_2,robot_3 \
  max_speed_mps:=0.3
```

Inspect:

```bash
ros2 topic echo /robot_1/detections_raw
ros2 topic echo /robot_1/detections_faulty
ros2 topic echo /robot_1/qgip/selected_leader
ros2 topic echo /robot_1/qgip/pop_state
ros2 topic echo /robot_1/qgip/mpc_debug
ros2 topic echo /robot_1/qgip/trial_status
ros2 topic echo /robot_1/safety_state
```

For ROS2 workspace CI before HIL replay, copy or symlink
`03_real_robot/run_ros2_workspace_preflight.sh` into a ROS2 workspace root that
contains this package at `src/ros2_qgip_stack`, then run:

```bash
bash run_ros2_workspace_preflight.sh
```

On Windows/PowerShell ROS2 installations, copy
`03_real_robot/run_ros2_workspace_preflight.ps1` into the same workspace root,
then run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_ros2_workspace_preflight.ps1
```

## Fault Examples

Controlled dropout:

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  dropout_duration_s:=0.5 \
  max_speed_mps:=0.3
```

Noisy and delayed detections:

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  position_noise_std_m:=0.05 \
  delay_s:=0.1 \
  max_speed_mps:=0.3
```

## Safety Positioning

This package prepares the ROS2 timing, real sensor/TF degradation, POP/NIS
recovery, and conservative closed-loop command checks that must be executed on
scaled robots before any physical-validation claim is made. It is not a full-scale ACC vehicle deployment by itself.

The `/robot_1/qgip/selected_leader` topic is published during the TF-based dry
run so the leader-selection decision is logged separately from the POP state.
The `/robot_1/safety_state` topic records stop reasons and should be included in
all HIL and closed-loop bags. Runtime timing claims also require
`runtime_telemetry.csv` following
`03_real_robot/ros2_runtime_telemetry_schema.csv`, with latency mean/p95/p99,
frame drops, watchdog reasons, clock drift, safe-command age, and CPU/GPU load
summarized in the trial metric CSV. A future learned QGIP selector can replace
this preflight selector while preserving the same JSON contract.
