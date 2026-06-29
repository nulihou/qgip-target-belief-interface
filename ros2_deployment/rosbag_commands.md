# ROS2 Bag Commands

## Offline Replay Data Collection

Adjust topic names to match the robot profile.

```bash
ros2 bag record \
  /camera/image_raw \
  /camera/depth/image_rect_raw \
  /scan \
  /odom \
  /tf \
  /detections_raw \
  /detections_faulty \
  /qgip/selected_leader \
  /qgip/pop_state \
  /qgip/mpc_debug \
  /cmd_vel \
  /cmd_vel_safe \
  /drive
```

## Hardware-In-The-Loop Replay

```bash
ros2 bag play <bag_dir> --clock
```

Recommended HIL setup:

- Run detection replay or detection node.
- Run fault injection node.
- Run POP/NIS node.
- Run safety MPC node.
- Disable actuator output or redirect to a shadow command topic.

## Closed-Loop Trial Logging

Use one bag per trial:

```bash
ros2 bag record -o trial_<scenario>_<method>_<seed> \
  /camera/image_raw /scan /odom /tf \
  /detections_raw /detections_faulty \
  /qgip/selected_leader /qgip/pop_state /qgip/mpc_debug \
  /cmd_vel_safe /drive /safety_state
```

## Required Metadata Per Trial

Create one row in `real_robot_results_template.csv` for each trial:

- method.
- scenario.
- fault type.
- speed level.
- repeat id.
- completion.
- near-miss.
- safety stop.
- contact.
- lost.
- min distance.
- recovery time.
- latency p95.

## Multi-Robot Preflight Logging

For the ROS2 wheeled-robot preflight stack, record follower, leader, distractor,
faulted detections, POP/NIS state, shadow commands, and trial status together:

```bash
ros2 bag record -o preflight_robot1_leader2_distractor3 \
  /tf /tf_static \
  /robot_1/odom /robot_2/odom /robot_3/odom \
  /robot_1/detections_raw /robot_1/detections_faulty \
  /robot_1/qgip/selected_leader \
  /robot_1/qgip/pop_state /robot_1/qgip/mpc_debug \
  /robot_1/qgip/trial_status /robot_1/cmd_vel_safe \
  /robot_1/safety_state
```

Suggested launch before enabling physical base control:

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link,robot_3/base_link \
  leader_ids:=robot_2,robot_3 \
  max_speed_mps:=0.3
```

Use `/robot_1/cmd_vel_safe` as a shadow command first. Bridge it to the real
base command topic only after TF, fault injection, POP/NIS, and HIL replay pass.
