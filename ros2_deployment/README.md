# QGIP-Net Jetson Nano ROS2 小车实机复现实验

本仓库是 QGIP-Net / POP-NIS target-belief interface 的 ROS2 小车复现实验仓库，面向 Jetson Nano 平台和多台 ROS2 小车。它用于帮助实验人员复现论文中需要补充的低速实机实验，并采集可写入 IEEE T-ASE 论文的 rosbag、运行遥测、trial manifest 和结果表。

当前推荐分支：

```bash
main
```

Gitee 仓库：

```bash
https://github.com/nulihou/qgip-target-belief-interface.git
```

## 1. 项目目的

论文当前主证据来自 CARLA 仿真，已经验证 QGIP-Net 在 object-list ambiguity 下可以提高 controller-facing target consistency，并通过 POP/NIS belief mode 将 TRACK、GHOST、DEGRADED、LOST 暴露给控制器。

本仓库要补充的是实机侧证据：

1. 在 Jetson Nano + ROS2 小车上验证目标信念接口能实时运行。
2. 在真实 ROS2 topic、TF、odom、执行器时延下检查 POP/NIS mode transition。
3. 在 dropout、delay、false leader、ID switch 等扰动下记录 selected leader、NIS、safe command 和 stop reason。
4. 为论文生成一张低速实机验证图和一张实机结果表。

本仓库不用于证明全尺寸车辆道路安全，也不用于做自动驾驶安全认证。

### 1.1 机器人形态说明

实验平台不要求是汽车外形。普通轮式机器人、差速轮机器人、四轮底盘或小型 Ackermann 底盘都可以作为本实验的 scaled physical robot platform。

本实验真正验证的是：

```text
目标列表是否稳定
leader 选择是否可记录
目标丢失时是否进入 GHOST / LOST
目标不可信时是否减速或停车
ROS2 实时链路是否能闭环运行
```

因此，机器人是不是“车的形状”不会影响当前论文需要补充的核心证据。需要避免的只是过度表述：论文中不要写成 full-scale vehicle validation、real-road ACC validation 或 physical safety certification，而应写成 low-speed ROS2 wheeled-robot validation 或 physical validation of the target-belief interface。

## 2. 实现了什么

仓库核心是 `ros2_qgip_stack/`，包含以下 ROS2 节点：

| 节点 | 功能 |
| --- | --- |
| `tf_leader_detection_node` | 将多台小车的 TF/odom 转换为 object-list 风格的 leader / distractor detections |
| `fault_injection_node` | 注入 dropout、noise、delay、false positive、false negative、ID switch |
| `pop_nis_kf_node` | 运行 POP/NIS-gated Kalman filter，并输出 TRACK、GHOST、DEGRADED、LOST |
| `velocity_safety_controller_node` | 根据 POP state 生成低速安全速度命令 `/robot_1/cmd_vel_safe` |
| `trial_supervisor_node` | 在线记录 trial 状态、min distance、lost、near-miss、latency 等指标 |

当前接口使用 `std_msgs/String` JSON payload，便于快速部署、录包和排查。后续如果冻结接口，可以替换为自定义 ROS2 message。

## 3. 能实现的实验效果

实验人员按本仓库流程执行后，应能得到以下结果：

| 实验阶段 | 是否驱动车 | 预期效果 |
| --- | --- | --- |
| Stage A: topic / TF preflight | 否 | 确认 `/robot_i/odom`、`/tf`、detections、POP state 和 safe command 正常发布 |
| Stage B: shadow rosbag | 否 | 在不接底盘的情况下验证 dropout、delay、ID switch 下的 POP/NIS response |
| Stage C: 架空轮或 HIL | 车轮空转或不接地 | 验证 actuator bridge、限速、watchdog 和 E-stop |
| Stage D: 低速闭环实机 | 是 | 采集论文用 nominal、dropout、distractor、lead braking 等实机 trial |

论文中可以用这些实验说明：

- 短时缺测时系统进入 GHOST / DEGRADED，而不是静默切换错误目标。
- 长时缺测时系统进入 LOST 或触发保守停止。
- selected leader、POP/NIS state、MPC debug 和 safety_state 能被完整记录。
- Jetson Nano 上的延迟、掉帧、CPU/GPU 负载可以被量化。

### 3.1 当前实机进度

截至 2026-06-12，已完成架空轮预飞：

- nominal：正确选择 `robot_2`；
- 0.5 s dropout：出现 TRACKING 与 GHOST/DEGRADED 行为；
- 1.8 s dropout：出现 TRACKING -> GHOST -> LOST -> TRACKING；
- 安全桥限制：0.05 m/s；
- watchdog：0.20 s；
- 后车最终确认四轮 0 rps。

这组结果只作为 suspended-wheel readiness evidence，不计入 on-ground physical-trial denominator。由于悬空轮 odom 会虚拟积分，near-miss、最小距离、TTC、completion 等物理指标必须排除。详见 `evidence_records/suspended_preflight_20260612.md`。

## 4. 实验人员如何下载

在 Jetson Nano 或 ROS2 工作站上执行：

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

## 5. 最小编译和测试流程

在 Jetson Nano 或 ROS2 工作站上执行：

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

查看 launch 参数：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py --show-args
```

如果只是做软件预飞检查，也可以运行：

```bash
cp src/qgip-target-belief-interface/run_ros2_workspace_preflight.sh .
bash run_ros2_workspace_preflight.sh
```

## 6. 第一次启动必须是 shadow mode

第一次启动时只允许发布 `/robot_1/cmd_vel_safe`，不要把它接到真实底盘控制器。

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
ros2 topic echo /robot_1/detections_faulty --once
ros2 topic echo /robot_1/qgip/selected_leader --once
ros2 topic echo /robot_1/qgip/pop_state --once
ros2 topic echo /robot_1/qgip/mpc_debug --once
ros2 topic echo /robot_1/safety_state --once
```

确认无误后，再按 `jetson_nano_tase_physical_experiment_protocol.md` 进入 rosbag、架空轮和低速闭环阶段。

## 7. 必须采集的数据

实验人员不只是运行程序，还必须采集数据。每个 trial 至少需要：

```text
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
```

每个 rosbag 建议记录：

```bash
ros2 bag record -o "$RUN_DIR/bag" \
  /tf /tf_static \
  /robot_1/odom /robot_2/odom /robot_3/odom \
  /robot_1/detections_raw /robot_1/detections_faulty \
  /robot_1/qgip/selected_leader \
  /robot_1/qgip/pop_state \
  /robot_1/qgip/mpc_debug \
  /robot_1/qgip/trial_status \
  /robot_1/cmd_vel_safe \
  /robot_1/safety_state
```

如果没有第三台干扰车，删除 `/robot_3/odom`。

rosbag 文件不要提交到 Gitee。大文件通过网盘、NAS 或移动硬盘回传。

## 8. 结果汇总

实验结束后填写：

```text
real_robot_results_filled.csv
```

字段格式参考：

```text
real_robot_results_template.csv
real_robot_metric_schema.csv
```

在主机端运行汇总脚本：

```bash
python analysis_scripts/summarize_real_robot_trials.py \
  real_robot_results_filled.csv \
  --group-by method,scenario,fault_type \
  --output real_robot_results_summary.csv
```

汇总结果用于论文中的实机结果表。

## 9. 仓库文件说明

| 路径 | 用途 |
| --- | --- |
| `JETSON_NANO_REAL_ROBOT_REPRODUCTION.zh-CN.md` | 实验人员入口说明 |
| `jetson_nano_tase_physical_experiment_protocol.md` | Jetson Nano 实机实验完整执行手册 |
| `ros2_qgip_stack/` | ROS2 包源码、launch、配置和测试 |
| `pre_real_robot_checklist.md` | 闭环实机前检查清单 |
| `ros2_topic_contract.csv` | 必录 topic、message type、producer、consumer、bag 规则 |
| `real_robot_trials_matrix.csv` | 推荐实机 trial 矩阵 |
| `real_robot_run_manifest_template.yaml` | 单次 trial manifest 模板 |
| `real_robot_results_template.csv` | 单次 trial 结果表模板 |
| `ros2_runtime_telemetry_schema.csv` | Jetson runtime telemetry 字段 |
| `rosbag_commands.md` | 常用 rosbag 采集命令 |
| `ros2_ackermann_bridge_skeleton.py` | Ackermann 小车桥接骨架 |
| `analysis_scripts/summarize_real_robot_trials.py` | 结果汇总脚本 |

## 10. 安全边界

本仓库用于准备和执行低速 ROS2 小车实机实验。它本身不等于：

- 物理安全认证；
- 全尺寸自动驾驶道路验证；
- HIL timing 已完成证明；
- 学习版 QGIP selector 已经完成实机验证。

闭环驱车前必须完成：

- E-stop 检查；
- `/robot_1/cmd_vel_safe` shadow mode；
- topic / TF / odom 检查；
- rosbag 记录检查；
- 架空轮或低风险 actuator bridge 检查；
- 操作员人工监控和停止权限确认。

任何 contact、near-miss、manual intervention、watchdog trigger 都必须写入 `incident_report.md`，不能删除失败 trial。

## 11. 推荐阅读顺序

1. `JETSON_NANO_REAL_ROBOT_REPRODUCTION.zh-CN.md`
2. `jetson_nano_tase_physical_experiment_protocol.md`
3. `pre_real_robot_checklist.md`
4. `ros2_topic_contract.csv`
5. `real_robot_run_manifest_template.yaml`
6. `real_robot_results_template.csv`
