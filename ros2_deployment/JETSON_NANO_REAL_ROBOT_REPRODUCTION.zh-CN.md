# Jetson Nano ROS2 小车复现实验分支说明

本分支用于实验人员下载并复现 QGIP/POP/NIS 低速 ROS2 小车实机实验。它只包含小车端和实验复现需要的部署文件，不包含论文 LaTeX、投稿压缩包、大体积 rosbag 或仿真原始数据。

## 0. 平台形态说明

本实验不要求机器人是汽车外形。普通轮式机器人、差速轮机器人、四轮底盘或小型 Ackermann 小车都可以用于复现实验。

当前实机实验要证明的是：

- selected leader 是否稳定记录；
- POP/NIS 是否能输出 TRACK、GHOST、DEGRADED、LOST；
- dropout 或目标不可信时机器人是否减速或停车；
- ROS2 topic、TF、odom、rosbag 和 Jetson runtime telemetry 是否完整。

因此视频中最重要的是看到 follower、leader、distractor 或 dropout 扰动，以及机器人在系统状态变化后的低速跟随、减速或停车行为。不要把实验描述成 full-scale vehicle validation 或真实道路 ACC 验证。

## 1. 分支信息

Gitee 仓库：

```bash
https://github.com/nulihou/qgip-target-belief-interface.git
```

实验分支：

```bash
main
```

实验人员在 Jetson Nano 或 ROS2 工作站上下载：

```bash
mkdir -p ~/qgip_ws/src
cd ~/qgip_ws/src
git clone https://github.com/nulihou/qgip-target-belief-interface.git
```

如果已经 clone 过：

```bash
cd ~/qgip_ws/src/qgip-target-belief-interface
git fetch origin
git switch main
git pull
```

## 2. 实验人员先读哪个文件

按顺序读：

1. `jetson_nano_tase_physical_experiment_protocol.md`
   - 主执行手册，包含每一步为什么做、在哪台机器执行、具体命令、通过标准和论文证据要求。
2. `pre_real_robot_checklist.md`
   - 闭环实机前检查清单。
3. `ros2_topic_contract.csv`
   - 必须录制的 topic、message type、producer/consumer 和 bag 记录要求。
4. `real_robot_run_manifest_template.yaml`
   - 每次 trial 必填的 manifest 模板。
5. `real_robot_results_template.csv`
   - 每次 trial 后汇总到结果表的字段模板。

## 3. Jetson Nano 最小编译流程

在 Jetson Nano 上执行：

```bash
cd ~/qgip_ws
source /opt/ros/$ROS_DISTRO/setup.bash
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select ros2_qgip_stack --event-handlers console_direct+
source install/setup.bash
colcon test --packages-select ros2_qgip_stack --event-handlers console_direct+
colcon test-result --verbose
```

然后查看 launch 参数：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py --show-args
```

## 4. 第一次启动只允许 shadow mode

第一次运行时，不要把 `/robot_1/cmd_vel_safe` 接到底盘控制器。先只启动 ROS2 stack 并检查 topic：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link,robot_3/base_link \
  leader_ids:=robot_2,robot_3 \
  max_speed_mps:=0.20
```

另开终端检查：

```bash
ros2 topic echo /robot_1/detections_raw --once
ros2 topic echo /robot_1/qgip/selected_leader --once
ros2 topic echo /robot_1/qgip/pop_state --once
ros2 topic echo /robot_1/qgip/mpc_debug --once
ros2 topic echo /robot_1/safety_state --once
```

原因：这个分支准备的是实机实验软件和证据链，不等同于物理安全认证。闭环驱车前必须先通过 topic、TF、rosbag、watchdog、E-stop 和架空轮检查。

## 5. 本分支包含的关键文件

| 路径 | 用途 |
| --- | --- |
| `ros2_qgip_stack/` | ROS2 包，包含 fault injection、POP/NIS KF、safe velocity controller、trial supervisor |
| `jetson_nano_tase_physical_experiment_protocol.md` | Jetson Nano 实机实验主执行手册 |
| `pre_real_robot_checklist.md` | 闭环前检查清单 |
| `ros2_topic_contract.csv` | topic 合约和录包要求 |
| `real_robot_trials_matrix.csv` | 建议实机 trial 矩阵 |
| `real_robot_run_manifest_template.yaml` | 单次 trial manifest 模板 |
| `real_robot_results_template.csv` | 结果 CSV 模板 |
| `ros2_runtime_telemetry_schema.csv` | Jetson runtime telemetry 字段 |
| `rosbag_commands.md` | rosbag 采集命令 |
| `ros2_ackermann_bridge_skeleton.py` | Ackermann 小车桥接骨架，仅作实现起点 |
| `analysis_scripts/summarize_real_robot_trials.py` | 主机端结果汇总脚本 |

## 6. 结果回传给论文端

实验人员完成 trial 后，需要把这些文件夹或文件回传：

```text
qgip_runs/
  <date>_jetson_nano_tase/
    <trial_id>/
      manifest.yaml
      bag/
      bag_info.txt
      trial_status.csv
      tegrastats.log
      topic_hz_robot1_odom.txt
      topic_hz_pop_state.txt
      topic_hz_cmd_vel_safe.txt
      operator_notes.md
      incident_report.md
    real_robot_results_filled.csv
    real_robot_results_summary.csv
```

不要把 rosbag 直接提交到 Gitee。rosbag 应通过网盘、实验室 NAS 或独立数据仓库交付。
