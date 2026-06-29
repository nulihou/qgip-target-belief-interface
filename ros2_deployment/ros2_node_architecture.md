# ROS2 Node Architecture

## Topic Graph

```text
/camera/image_raw
/camera/depth/image_rect_raw
/scan or /points
/odom
/tf
        |
        v
detector_node
        |
        v
/detections_raw
        |
        v
fault_injection_node
        |
        v
/detections_faulty
        |
        v
scene_graph_builder
        |
        v
/qgip/graph
        |
        v
qgip_selector
        |
        v
/qgip/selected_leader
        |
        v
pop_nis_kf_node
        |
        v
/qgip/pop_state
        |
        v
safety_mpc_node
        |
        v
command_filter + watchdog
        |
        v
/cmd_vel_safe or /drive
```

## Minimal Message Contract

Until custom ROS2 messages are created, use simple message conventions:

### Detection Object

Required fields:

- `id`: integer or string.
- `class_name`: string.
- `x`, `y`: leader-relative position in ego frame, meters.
- `vx`, `vy`: relative velocity if available, meters per second.
- `confidence`: detector confidence in `[0, 1]`.
- `stamp`: sensor timestamp.

Implementation options:

- JSON payload in `std_msgs/String` for fast prototyping.
- `vision_msgs/Detection3DArray` for more standard integration.
- Custom message later if the interface stabilizes.

### POP State

Required fields:

- `mode`: TRACKING, DEGRADED, GHOST, LOST.
- `x`, `y`, `vx`, `vy`.
- covariance diagonal.
- NIS value.
- ghost age.
- selected leader id.

### Command Output

Differential-drive:

- `/cmd_vel_safe`: `geometry_msgs/Twist`.

Ackermann:

- `/drive`: `ackermann_msgs/AckermannDriveStamped`.

## Node Responsibilities

### `detector_node`

Input:

- camera, depth, LiDAR, odom, tf.

Output:

- `/detections_raw`.

First implementation:

- AprilTag/ArUco + depth for robust leader pose.

Upgrade:

- detector + depth or LiDAR clustering.

### `fault_injection_node`

Input:

- `/detections_raw`.

Output:

- `/detections_faulty`.

Functions:

- drop detection.
- add pose noise.
- add false positives.
- ID switch.
- delay messages.
- confidence scaling.

### `scene_graph_builder`

Input:

- `/detections_faulty`.
- `/odom`.

Output:

- `/qgip/graph`.

Functions:

- build node features `[px, py, vx, vy, yaw, class, confidence]`.
- attach query vector.
- preserve candidate ids.

### `qgip_selector`

Input:

- `/qgip/graph`.

Output:

- `/qgip/selected_leader`.

Functions:

- run FiLM-GNN or simplified selector.
- output leader candidate and confidence.
- log GS@1/GS@3 when ground truth is available.

### `pop_nis_kf_node`

Input:

- `/qgip/selected_leader`.

Output:

- `/qgip/pop_state`.

Functions:

- predict at control frequency.
- update when confidence is high.
- apply NIS gating.
- enter ghost mode when missing.
- enter lost/fail-safe when ghost horizon is exceeded.

### `safety_mpc_node`

Input:

- `/qgip/pop_state`.
- `/odom`.
- optional obstacles.

Output:

- raw velocity or Ackermann command.

Functions:

- sample candidate trajectories.
- reject unsafe trajectories.
- minimize following, smoothness, and progress costs.
- request emergency stop if no safe candidate exists.

### `command_filter`

Input:

- raw command.
- safety state.

Output:

- `/cmd_vel_safe` or `/drive`.

Functions:

- rate-limit acceleration.
- cap speed.
- apply watchdog timeout.
- enforce E-stop.

## Logging

Record:

```bash
ros2 bag record \
  /detections_raw /detections_faulty \
  /qgip/selected_leader /qgip/pop_state /qgip/mpc_debug \
  /cmd_vel /cmd_vel_safe /drive /odom /tf
```

Video:

- raw camera.
- overlay with selected leader.
- POP ghost position.
- MPC selected trajectory.
- NIS and safety state.
