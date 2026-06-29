# QGIP ROS2 Robot Deployment Runbook

This runbook explains what to run, where to run it, why it matters, and what
evidence to archive. Start on one ROS2 workstation, then repeat on the 2-3 robot
machines.

## 0. Goal and Boundary

The goal is to upgrade paper-level `ROS2 readiness` into real ROS2 software
execution evidence:

- Show that the package builds in a ROS2 workspace.
- Show that the pure-Python contract tests pass.
- Show that launch arguments are exposed and inspectable.
- Inspect topics, TF, selected-leader messages, POP/NIS state, and safe commands
  in shadow mode.
- Record rosbag and runtime telemetry evidence for later HIL or robot trials.

Boundary:

- `colcon build/test` proves software build/test execution, not physical safety.
- `ros2 launch --show-args` proves launch interface availability, not live node execution.
- Shadow mode checks message flow and must not drive the real base controller.
- Physical claims require supervised low-speed trials, rosbags, manifests, and incident logs.

## 1. Prepare the Machine

Run on each ROS2 machine:

```bash
git --version
ros2 --help
colcon --help
python3 --version
```

Purpose:

- Confirm that the machine can clone the Gitee repository.
- Confirm that ROS2 and colcon are installed.
- Confirm that build/test/launch commands are available.

Archive:

```bash
mkdir -p ~/qgip_ws/evidence
git --version | tee ~/qgip_ws/evidence/00_git_version.log
ros2 --help | head -n 20 | tee ~/qgip_ws/evidence/00_ros2_help_head.log
colcon --help | head -n 20 | tee ~/qgip_ws/evidence/00_colcon_help_head.log
python3 --version | tee ~/qgip_ws/evidence/00_python_version.log
```

## 2. Clone the Repository

```bash
mkdir -p ~/qgip_ws/src
cd ~/qgip_ws/src
git clone https://github.com/nulihou/qgip-target-belief-interface.git
cd qgip-target-belief-interface
git log --oneline -1
```

Purpose:

- Download the deployment package into the ROS2 workspace `src/` directory.
- Record the exact commit used by each robot.

Archive:

```bash
git log --oneline -1 | tee ~/qgip_ws/evidence/01_deploy_commit.log
git remote -v | tee ~/qgip_ws/evidence/01_git_remote.log
```

## 3. Install Dependencies

```bash
cd ~/qgip_ws
rosdep update
rosdep install --from-paths src -y --ignore-src
```

Purpose:

- Install ROS2 runtime dependencies declared in `package.xml`.
- Main dependencies include `rclpy`, `std_msgs`, `geometry_msgs`, `nav_msgs`, and `tf2_ros`.

Archive:

```bash
rosdep install --from-paths src -y --ignore-src 2>&1 | tee ~/qgip_ws/evidence/02_rosdep_install.log
```

## 4. Build the ROS2 Package

```bash
cd ~/qgip_ws
colcon build --packages-select ros2_qgip_stack --event-handlers console_direct+ 2>&1 | tee evidence/03_colcon_build.log
```

Purpose:

- Prove that `ros2_qgip_stack` builds with colcon/ament_python.
- Generate the `install/` workspace used by ROS2.

Success criteria:

- Return code is 0.
- No failed package appears in the log.
- The install artifact for `ros2_qgip_stack` exists.

## 5. Source the Workspace

```bash
cd ~/qgip_ws
source install/setup.bash
ros2 pkg prefix ros2_qgip_stack | tee evidence/04_ros2_pkg_prefix.log
```

Purpose:

- Add the built package to the current ROS2 shell.
- Confirm that `ros2` can find `ros2_qgip_stack`.

On Windows/PowerShell ROS2:

```powershell
cd ~/qgip_ws
.\install\setup.ps1
ros2 pkg prefix ros2_qgip_stack | Tee-Object evidence\04_ros2_pkg_prefix.log
```

## 6. Run Tests

```bash
cd ~/qgip_ws
colcon test --packages-select ros2_qgip_stack --event-handlers console_direct+ 2>&1 | tee evidence/05_colcon_test.log
colcon test-result --verbose 2>&1 | tee evidence/05_colcon_test_result.log
```

Purpose:

- Run package tests.
- Validate JSON contracts, fault injection, and POP/NIS pure-Python core behavior.

Success criteria:

- `colcon test` returns 0.
- `colcon test-result --verbose` reports zero failures.

Optional direct pytest:

```bash
python3 -m pytest src/qgip-target-belief-interface/ros2_qgip_stack/test -q 2>&1 | tee evidence/05_pytest_core.log
```

## 7. Inspect Launch Arguments

```bash
cd ~/qgip_ws
source install/setup.bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py --show-args 2>&1 | tee evidence/06_launch_show_args.log
```

Purpose:

- Inspect the launch interface without starting nodes.
- Confirm that follower namespace, leader frames, fault knobs, NIS gates, and
  result CSV options exist.

Required arguments:

- `follower_ns`
- `follower_frame`
- `leader_frames`
- `leader_ids`
- `max_speed_mps`
- `dropout_duration_s`
- `position_noise_std_m`
- `delay_s`
- `false_positive_rate`
- `false_negative_rate`
- `id_switch_probability`
- `nis_soft_threshold`
- `nis_hard_threshold`
- `results_csv_path`

## 8. Run the One-Command Preflight

Linux:

```bash
cd ~/qgip_ws
cp src/qgip-target-belief-interface/run_ros2_workspace_preflight.sh .
bash run_ros2_workspace_preflight.sh
```

Purpose:

- Run build, test, test-result, launch show-args, and pure pytest in one pass.
- Useful after every `git pull` on each robot.

Windows/PowerShell:

```powershell
cd ~/qgip_ws
Copy-Item src\qgip-target-belief-interface\run_ros2_workspace_preflight.ps1 .
powershell -ExecutionPolicy Bypass -File .\run_ros2_workspace_preflight.ps1
```

Purpose:

- Run the same build/test/show-args checks in a Windows ROS2 environment.
- Logs are written to `ros2_preflight_logs_<timestamp>/`.

## 9. Shadow-Mode Launch

Important: do not connect `/robot_1/cmd_vel_safe` to the real base controller
during the first launch.

```bash
cd ~/qgip_ws
source install/setup.bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link,robot_3/base_link \
  leader_ids:=robot_2,robot_3 \
  max_speed_mps:=0.3 \
  results_csv_path:=/tmp/qgip_shadow_results.csv
```

Purpose:

- Start the follower-side QGIP preflight nodes.
- Generate detections from TF, inject software faults, run POP/NIS, and publish
  shadow safe commands.
- Inspect message flow without driving hardware.

## 10. Inspect Topics and Rates

Open another terminal:

```bash
source ~/qgip_ws/install/setup.bash
ros2 topic list | tee ~/qgip_ws/evidence/07_topic_list.log
ros2 topic hz /robot_1/qgip/selected_leader | tee ~/qgip_ws/evidence/07_hz_selected_leader.log
ros2 topic hz /robot_1/qgip/pop_state | tee ~/qgip_ws/evidence/07_hz_pop_state.log
ros2 topic hz /robot_1/cmd_vel_safe | tee ~/qgip_ws/evidence/07_hz_cmd_vel_safe.log
```

Purpose:

- Confirm that key topics exist.
- Record runtime message rates for paper evidence.

Sample messages:

```bash
ros2 topic echo /robot_1/qgip/selected_leader --once | tee ~/qgip_ws/evidence/08_echo_selected_leader.log
ros2 topic echo /robot_1/qgip/pop_state --once | tee ~/qgip_ws/evidence/08_echo_pop_state.log
ros2 topic echo /robot_1/qgip/mpc_debug --once | tee ~/qgip_ws/evidence/08_echo_mpc_debug.log
ros2 topic echo /robot_1/safety_state --once | tee ~/qgip_ws/evidence/08_echo_safety_state.log
```

Purpose:

- Archive JSON payload samples.
- Prove that selected-leader, POP/NIS, MPC debug, and safety-state messages are not empty.

## 11. Inspect TF

```bash
ros2 run tf2_ros tf2_echo robot_1/base_link robot_2/base_link | tee ~/qgip_ws/evidence/09_tf_robot1_robot2.log
ros2 run tf2_ros tf2_echo robot_1/base_link robot_3/base_link | tee ~/qgip_ws/evidence/09_tf_robot1_robot3.log
```

Purpose:

- Confirm that the follower can observe leader and distractor TF frames.
- Without TF, `tf_leader_detection_node` cannot produce real detections.

## 12. Record Rosbag Evidence

```bash
mkdir -p ~/qgip_ws/bags
ros2 bag record \
  /tf /tf_static \
  /robot_1/detections_raw \
  /robot_1/detections_faulty \
  /robot_1/qgip/selected_leader \
  /robot_1/qgip/pop_state \
  /robot_1/qgip/mpc_debug \
  /robot_1/qgip/trial_status \
  /robot_1/safety_state \
  /robot_1/cmd_vel_safe \
  -o ~/qgip_ws/bags/qgip_shadow_001
```

Purpose:

- Archive replayable ROS2 execution evidence.
- Enable later analysis of latency, frame drops, watchdog reasons, and mode transitions.

After recording:

```bash
ros2 bag info ~/qgip_ws/bags/qgip_shadow_001 | tee ~/qgip_ws/evidence/10_bag_info_qgip_shadow_001.log
```

## 13. Run Software-Fault Scenarios

Dropout:

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  dropout_duration_s:=0.5 \
  max_speed_mps:=0.3 \
  results_csv_path:=/tmp/qgip_dropout_results.csv
```

Delay + noise:

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  delay_s:=0.1 \
  position_noise_std_m:=0.05 \
  max_speed_mps:=0.3 \
  results_csv_path:=/tmp/qgip_delay_noise_results.csv
```

False positive / ID switch:

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  false_positive_rate:=0.1 \
  id_switch_probability:=0.2 \
  max_speed_mps:=0.3 \
  results_csv_path:=/tmp/qgip_fp_id_results.csv
```

Purpose:

- Mirror the paper's dropout, delay, false-positive, and ID-switch stress logic.
- Check POP/NIS and safe-command behavior through real ROS2 topic/TF paths.

## 14. Three-Robot Roles

Recommended setup:

- `robot_1`: follower running this package.
- `robot_2`: leader vehicle.
- `robot_3`: distractor or adjacent target.

All robots can clone the same Gitee repository. Use launch arguments,
namespaces, and TF frames to distinguish roles; do not maintain separate code
copies per robot.

## 15. Pull Updates on Each Robot

```bash
cd ~/qgip_ws/src/qgip-target-belief-interface
git pull
cd ~/qgip_ws
colcon build --packages-select ros2_qgip_stack --event-handlers console_direct+
source install/setup.bash
colcon test --packages-select ros2_qgip_stack --event-handlers console_direct+
```

Purpose:

- Keep all robots on the same version.
- Rebuild and retest after every update.

## 16. Evidence to Bring Back to the Paper Project

Copy back:

- `evidence/00_*`
- `evidence/03_colcon_build.log`
- `evidence/05_colcon_test.log`
- `evidence/05_colcon_test_result.log`
- `evidence/06_launch_show_args.log`
- `evidence/07_topic_list.log`
- `evidence/07_hz_*.log`
- `evidence/08_echo_*.log`
- `evidence/09_tf_*.log`
- `evidence/10_bag_info_*.log`
- `bags/qgip_shadow_*`
- `/tmp/qgip_*_results.csv`
- filled `real_robot_run_manifest_template.yaml`
- filled `incident_report_template.md` if anything abnormal happened

These artifacts can upgrade the manuscript from readiness-only language to real
ROS2 execution evidence.
