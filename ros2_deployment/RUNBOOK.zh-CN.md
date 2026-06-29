# QGIP ROS2 小车部署详细操作手册

本文档说明每一步命令怎么做、为什么做、成功后需要保存什么证据。建议先在一台
ROS2 工作站完成 build/test，再同步到 2-3 台小车。

## 0. 目标和边界

目标是把论文中的 `ROS2 readiness` 升级成真实软件执行证据：

- 证明 package 可以在 ROS2 workspace 中构建。
- 证明纯 Python 合约测试可以通过。
- 证明 launch 参数完整可见。
- 在 shadow mode 下检查 topic、TF、selected leader、POP/NIS 状态和安全命令。
- 录制 rosbag 和 runtime telemetry，为 HIL/真实小车实验做准备。

边界：

- `colcon build/test` 只证明软件能构建和测试，不证明小车安全。
- `ros2 launch --show-args` 只证明 launch 接口完整，不证明节点已经在线运行。
- shadow mode 只检查消息链路，不应该直接驱动真实底盘。
- 真实物理 claim 必须等低速人工监管试验、rosbag、manifest 和 incident log 完成后再写。

## 1. 准备机器

在每台 ROS2 机器上检查基础命令：

```bash
git --version
ros2 --help
colcon --help
python3 --version
```

用途：

- 确认机器可以拉取 Gitee 仓库。
- 确认 ROS2 和 colcon 已安装。
- 确认后续 build/test/launch 命令可用。

需要保存的证据：

```bash
mkdir -p ~/qgip_ws/evidence
git --version | tee ~/qgip_ws/evidence/00_git_version.log
ros2 --help | head -n 20 | tee ~/qgip_ws/evidence/00_ros2_help_head.log
colcon --help | head -n 20 | tee ~/qgip_ws/evidence/00_colcon_help_head.log
python3 --version | tee ~/qgip_ws/evidence/00_python_version.log
```

## 2. 克隆仓库

```bash
mkdir -p ~/qgip_ws/src
cd ~/qgip_ws/src
git clone https://github.com/nulihou/qgip-target-belief-interface.git
cd qgip-target-belief-interface
git log --oneline -1
```

用途：

- 在 ROS2 workspace 的 `src/` 目录中下载部署包。
- 记录当前使用的 commit，保证每台小车用同一版本。

保存证据：

```bash
git log --oneline -1 | tee ~/qgip_ws/evidence/01_deploy_commit.log
git remote -v | tee ~/qgip_ws/evidence/01_git_remote.log
```

## 3. 安装依赖

```bash
cd ~/qgip_ws
rosdep update
rosdep install --from-paths src -y --ignore-src
```

用途：

- 根据 `package.xml` 安装 ROS2 runtime 依赖。
- 主要依赖包括 `rclpy`、`std_msgs`、`geometry_msgs`、`nav_msgs`、`tf2_ros`。

保存证据：

```bash
rosdep install --from-paths src -y --ignore-src 2>&1 | tee ~/qgip_ws/evidence/02_rosdep_install.log
```

如果 `rosdep update` 很慢，可以先只保存 `rosdep install` 输出。

## 4. 构建 ROS2 package

```bash
cd ~/qgip_ws
colcon build --packages-select ros2_qgip_stack --event-handlers console_direct+ 2>&1 | tee evidence/03_colcon_build.log
```

用途：

- 证明 `ros2_qgip_stack` 可以被 colcon/ament_python 构建。
- 生成 `install/` 目录，使 ROS2 能找到 package 和 console scripts。

成功标准：

- 命令返回码为 0。
- 日志中没有 failed package。
- `install/ros2_qgip_stack` 或对应 install 产物存在。

## 5. Source 工作区

```bash
cd ~/qgip_ws
source install/setup.bash
ros2 pkg prefix ros2_qgip_stack | tee evidence/04_ros2_pkg_prefix.log
```

用途：

- 把新构建的 package 加入当前 shell 的 ROS2 环境。
- 确认 `ros2` 能找到 `ros2_qgip_stack`。

如果是 Windows/PowerShell ROS2：

```powershell
cd ~/qgip_ws
.\install\setup.ps1
ros2 pkg prefix ros2_qgip_stack | Tee-Object evidence\04_ros2_pkg_prefix.log
```

## 6. 运行测试

```bash
cd ~/qgip_ws
colcon test --packages-select ros2_qgip_stack --event-handlers console_direct+ 2>&1 | tee evidence/05_colcon_test.log
colcon test-result --verbose 2>&1 | tee evidence/05_colcon_test_result.log
```

用途：

- 运行 package 测试。
- 证明 JSON contract、fault injection、POP/NIS core 的纯 Python 合约没有破坏。

成功标准：

- `colcon test` 返回码为 0。
- `colcon test-result --verbose` 显示 0 failures。

可以额外运行：

```bash
python3 -m pytest src/qgip-target-belief-interface/ros2_qgip_stack/test -q 2>&1 | tee evidence/05_pytest_core.log
```

## 7. 检查 launch 参数

```bash
cd ~/qgip_ws
source install/setup.bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py --show-args 2>&1 | tee evidence/06_launch_show_args.log
```

用途：

- 不启动节点，只检查 launch 文件公开了哪些参数。
- 确认 follower namespace、leader frames、fault knobs、NIS gates、results CSV 等参数都存在。

必须能看到的参数：

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

## 8. 使用预验证脚本一键跑 build/test/show-args

Linux：

```bash
cd ~/qgip_ws
cp src/qgip-target-belief-interface/run_ros2_workspace_preflight.sh .
bash run_ros2_workspace_preflight.sh
```

用途：

- 自动跑 build、test、test-result、launch show-args 和 pure pytest。
- 适合每台小车同步代码后快速确认环境。

Windows/PowerShell：

```powershell
cd ~/qgip_ws
Copy-Item src\qgip-target-belief-interface\run_ros2_workspace_preflight.ps1 .
powershell -ExecutionPolicy Bypass -File .\run_ros2_workspace_preflight.ps1
```

用途：

- 在 Windows ROS2 环境里做同样的 build/test/show-args 检查。
- 日志会写入 `ros2_preflight_logs_<timestamp>/`。

## 9. Shadow-mode 启动

重要：第一次启动不要把 `/robot_1/cmd_vel_safe` 接到底盘控制器。

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

用途：

- 启动 follower 的 QGIP preflight 节点。
- 用 TF 生成 detections，注入软件故障，运行 POP/NIS，发布 shadow safe command。
- 检查消息链路，不直接控制硬件。

## 10. 检查 topic 和频率

另开一个终端：

```bash
source ~/qgip_ws/install/setup.bash
ros2 topic list | tee ~/qgip_ws/evidence/07_topic_list.log
ros2 topic hz /robot_1/qgip/selected_leader | tee ~/qgip_ws/evidence/07_hz_selected_leader.log
ros2 topic hz /robot_1/qgip/pop_state | tee ~/qgip_ws/evidence/07_hz_pop_state.log
ros2 topic hz /robot_1/cmd_vel_safe | tee ~/qgip_ws/evidence/07_hz_cmd_vel_safe.log
```

用途：

- 确认关键 topic 真的存在。
- 记录消息频率，后续论文可作为 ROS2 runtime evidence。

抽样 echo：

```bash
ros2 topic echo /robot_1/qgip/selected_leader --once | tee ~/qgip_ws/evidence/08_echo_selected_leader.log
ros2 topic echo /robot_1/qgip/pop_state --once | tee ~/qgip_ws/evidence/08_echo_pop_state.log
ros2 topic echo /robot_1/qgip/mpc_debug --once | tee ~/qgip_ws/evidence/08_echo_mpc_debug.log
ros2 topic echo /robot_1/safety_state --once | tee ~/qgip_ws/evidence/08_echo_safety_state.log
```

用途：

- 保存 JSON payload 样例。
- 证明 selected leader、POP/NIS 状态、安全状态不是空 topic。

## 11. 检查 TF

```bash
ros2 run tf2_ros tf2_echo robot_1/base_link robot_2/base_link | tee ~/qgip_ws/evidence/09_tf_robot1_robot2.log
ros2 run tf2_ros tf2_echo robot_1/base_link robot_3/base_link | tee ~/qgip_ws/evidence/09_tf_robot1_robot3.log
```

用途：

- 确认 follower 能看到 leader 和 distractor 的 TF。
- 没有 TF，`tf_leader_detection_node` 无法生成真实 detections。

## 12. 录制 rosbag

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

用途：

- 保存可回放的 ROS2 运行证据。
- 后续可计算 latency、frame drop、watchdog reason、mode transition。

录制结束后：

```bash
ros2 bag info ~/qgip_ws/bags/qgip_shadow_001 | tee ~/qgip_ws/evidence/10_bag_info_qgip_shadow_001.log
```

## 13. 运行软件故障场景

Dropout：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  dropout_duration_s:=0.5 \
  max_speed_mps:=0.3 \
  results_csv_path:=/tmp/qgip_dropout_results.csv
```

Delay + noise：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  delay_s:=0.1 \
  position_noise_std_m:=0.05 \
  max_speed_mps:=0.3 \
  results_csv_path:=/tmp/qgip_delay_noise_results.csv
```

False positive / ID switch：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  false_positive_rate:=0.1 \
  id_switch_probability:=0.2 \
  max_speed_mps:=0.3 \
  results_csv_path:=/tmp/qgip_fp_id_results.csv
```

用途：

- 对应论文里的 dropout、delay、false positive、ID switch stress。
- 在真实 ROS2 topic/TF 链路下检查 POP/NIS 和安全命令响应。

## 14. 三台小车分工

推荐配置：

- `robot_1`：follower，运行本 package。
- `robot_2`：leader，低速前车。
- `robot_3`：distractor，旁车或相邻目标。

每台小车都可以 clone 同一个 Gitee 仓库。区别通过 launch 参数、namespace 和 TF frame
配置，不需要每台小车维护不同代码。

## 15. 同步更新代码

每台小车更新：

```bash
cd ~/qgip_ws/src/qgip-target-belief-interface
git pull
cd ~/qgip_ws
colcon build --packages-select ros2_qgip_stack --event-handlers console_direct+
source install/setup.bash
colcon test --packages-select ros2_qgip_stack --event-handlers console_direct+
```

用途：

- 保证三台小车使用同一版本。
- 每次更新后必须重新 build/test。

## 16. 最终要交回论文项目的证据

请从 ROS2 机器拷回这些文件：

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
- 填写后的 `real_robot_run_manifest_template.yaml`
- 如有异常，填写 `incident_report_template.md`

这些文件可以把当前论文中的 readiness boundary 升级为真实 ROS2 execution evidence。
