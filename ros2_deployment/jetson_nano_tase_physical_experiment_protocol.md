# Jetson Nano ROS2 小车实机实验执行手册

目标稿件：IEEE Transactions on Automation Science and Engineering, T-ASE  
实验定位：低速 ROS2 小车实机验证，不是全尺寸道路车辆验证  
当前日期：2026-06-10  
当前 ROS2 包：`ros2_qgip_stack 0.1.0`

## 0. 这组实机实验要补齐什么证据

### 0.1 论文当前缺口

当前论文的主证据来自 CARLA 仿真，已经证明 QGIP-Net 在 object-list ambiguity 下能提高 controller-facing target consistency，并且 POP/NIS belief mode 能把 TRACK、GHOST、DEGRADED、LOST 暴露给控制器。T-ASE 审稿人最可能追问的是：这些接口机制在真实 ROS2 系统里是否能按实时频率运行，是否能在真实执行器、真实时延、真实安全停止约束下保持可解释行为。

因此实机实验不是重新做一套完整自动驾驶 benchmark，而是补齐这四类证据：

1. ROS2 topic contract 是否能在 Jetson Nano 上稳定运行。
2. POP/NIS 在真实运行时序下是否能对 dropout、delay、ID switch、false leader 做出正确 mode response。
3. `/robot_1/cmd_vel_safe` 是否能通过安全桥接驱动小车，并在 LOST、watchdog 或近距离风险下停止。
4. 真实 rosbag、telemetry、manifest、CSV 是否足以支撑论文中的一张实机图和一张实机表。

### 0.2 论文中应当怎样表述

可写：

> We further validate the target-belief interface on a Jetson-Nano ROS2 wheeled robot at low speed. The experiment tests ROS2 timing, POP/NIS mode transitions, safe-command generation, and conservative stop behavior under controlled object-list perturbations.

不要写：

> We validate full real-world autonomous driving safety.

也不要把当前 `ros2_qgip_stack` 的预飞 TF selector 直接说成完整学习版 QGIP-Net。当前最稳妥表述是：

> Low-speed physical validation of the target-belief interface.

如果后续把学习版 selector 也部署到 Jetson，并保证 `/robot_1/qgip/selected_leader` 只有一个 publisher，才可以进一步写：

> Low-speed physical validation of the QGIP-Net selector plus POP/NIS control interface.

### 0.3 轮式机器人不是车形是否影响实验

不影响当前实机实验的核心目标。我们要证明的不是汽车外形、真实道路 ACC 或全尺寸车辆动力学，而是低速物理平台上的 target-belief interface：

```text
候选目标 / 干扰目标 / 丢失目标
        ↓
selected leader
        ↓
POP/NIS mode: TRACK / GHOST / DEGRADED / LOST
        ↓
cmd_vel_safe: 跟随 / 减速 / 停车
```

因此，普通轮式机器人、差速轮机器人、四轮底盘或小型 Ackermann 底盘都可以做本实验。视频里需要清楚展示的是 follower、leader、干扰目标、目标丢失或错误目标扰动，以及机器人在 POP/NIS mode 改变后的保守跟随、减速或停车行为。

论文和视频标题建议使用：

> Low-speed physical validation on a ROS2 wheeled robot.

不要使用：

> Real-vehicle autonomous driving validation.

## 1. 实验总体路线

实验分四个阶段。不要跳阶段，因为每一阶段都在消除一种潜在失败来源。

| 阶段 | 名称 | 是否驱动车轮 | 目的 | 为什么必须做 |
| --- | --- | --- | --- | --- |
| A | Workspace 和 topic preflight | 否 | 确认 ROS2 包能编译、topic 存在、TF/odom 稳定 | 防止把网络、namespace、TF 错误误判成算法失败 |
| B | Shadow rosbag / 实时预飞 | 否 | 只发布 `/robot_1/cmd_vel_safe`，不接底盘 | 验证 POP/NIS 和 controller 在 Jetson Nano 上能实时输出安全命令 |
| C | 架空轮或低风险 HIL | 车轮可空转，不接地 | 允许底盘控制链路运行，但不产生实际位移 | 先验证 actuator bridge、watchdog、限速和 E-stop |
| D | 低速闭环实机 | 是 | 采集论文用实机结果 | 证明接口机制在真实执行器和真实机器人运动下仍可工作 |

最小可投稿实机矩阵建议：

| 条件 | repeats 最低值 | repeats 推荐值 | 论文作用 |
| --- | ---: | ---: | --- |
| Nominal following | 5 | 10 | 证明正常跟车和 ROS2 实时运行 |
| Short dropout, 0.5 s | 5 | 10 | 证明 GHOST 和 recovery |
| Sustained dropout, 1.0 s | 5 | 10 | 证明 LOST 和 safe stop |
| Adjacent distractor | 5 | 10 | 证明 wrong-leader exposure 可被记录和诊断 |
| Dropout during lead braking | 5 | 5-10 | 证明 stale leader 时不会危险加速 |

如果时间有限，先完成每个条件 5 次，并在论文中称为 controlled low-speed physical validation。若想更稳，做到每个主条件 10 次。

## 2. 实验角色和硬件准备

### 2.1 机器人角色

当前仓库的 topic contract 默认三台 ROS2 小车：

| 角色 | namespace | 必需 topic / frame | 说明 |
| --- | --- | --- | --- |
| follower | `/robot_1` | `/robot_1/odom`, `robot_1/base_link` | 被测小车，Jetson Nano 上运行 QGIP/POP/NIS/controller |
| leader | `/robot_2` | `/robot_2/odom`, `robot_2/base_link` | 前车目标 |
| distractor | `/robot_3` | `/robot_3/odom`, `robot_3/base_link` | 邻近干扰目标，用于 adjacent distractor |
| logger | laptop 或 Jetson | rosbag2, video, telemetry | 记录全部证据 |

如果只有两台车，可以先不做 adjacent distractor，或者用固定移动目标板替代 `/robot_3`。如果只有一台车，实机实验只能作为 target-board / replay validation，证据强度会低于多车实机。

### 2.2 场地要求

建议使用室内走廊、实验室空地或封闭室外平地：

- 直线有效距离至少 6 m，推荐 8-10 m。
- follower 和 leader 初始间距 0.6-1.0 m。
- 地面贴出左右边界，宽度建议 1.0-1.5 m。
- 附近不能有行人、硬障碍、玻璃门、台阶。
- 每次 trial 只允许一名安全员下达开始和停止口令。

为什么这样做：论文需要证明低速实机闭环，不需要高风险高速场景。清晰的 ODD 边界能减少不可控变量，并且让 near-miss、corridor exit、manual intervention 可重复定义。

### 2.3 速度和安全阈值

初始值建议：

| 参数 | 建议值 | 说明 |
| --- | ---: | --- |
| low speed | 0.20 m/s | 第一批闭环 trial |
| medium speed | 0.35-0.50 m/s | 仅在 low speed 全部通过后做 |
| min headway abort | 0.25 m | 小车和目标的最近安全距离 |
| min TTC abort | 0.8 s | 低速保守停止阈值 |
| POP lost timeout | 1.5 s | 与论文当前 POP/NIS 设置一致 |
| ghost horizon | 1.0 s | 短时遮挡预测窗口 |
| latency p95 target | < 100 ms | Jetson Nano 实时运行目标 |
| latency p99 hard review | < 200 ms 或解释 | 超过则不能直接作强实时 claim |

为什么这样做：T-ASE 审稿人关心系统是否可靠，而不是小车速度多快。低速阈值可以把风险压低，同时仍然测试 mode transition、safe command 和 watchdog。

## 3. Jetson Nano 和工作区部署

以下命令分为 Windows 主机和 Jetson Nano 两端。尖括号内容需要替换，例如 `<JETSON_IP>`。

### 3.1 在 Jetson Nano 上记录系统版本

在 Jetson Nano 终端执行：

```bash
hostname
lsb_release -a
uname -a
echo "ROS_DISTRO=$ROS_DISTRO"
python3 --version
which ros2
which colcon
df -h
free -h
```

为什么这样做：Jetson Nano 常见 JetPack 和 ROS2 版本差异很大。论文和补充材料中需要能说明实验环境；如果之后复现实验失败，也能先排查系统版本。

通过标准：

- `ros2` 和 `colcon` 能找到。
- 磁盘剩余空间至少 20 GB，推荐 50 GB。
- 内存压力可控。Jetson Nano 内存小，rosbag、camera、Python 节点同时运行时容易掉帧。

### 3.2 配置 ROS2 网络

所有机器人和 logger 使用同一个 ROS domain：

```bash
export ROS_DOMAIN_ID=36
export ROS_LOCALHOST_ONLY=0
echo "export ROS_DOMAIN_ID=36" >> ~/.bashrc
echo "export ROS_LOCALHOST_ONLY=0" >> ~/.bashrc
```

如果你们已经统一使用别的 `ROS_DOMAIN_ID`，改成现场值，但三台车和 logger 必须一致。

检查网络：

```bash
ip addr
ping -c 3 <LOGGER_IP>
ping -c 3 <LEADER_IP>
```

为什么这样做：多车实验最常见失败不是算法，而是 ROS discovery 找不到 topic 或 TF。固定 domain 和网络连通性可以减少现场排查时间。

### 3.3 从 Windows 主机复制 ROS2 包和模板

在 Windows PowerShell 执行：

```powershell
$JETSON = "jetson@<JETSON_IP>"
$SRC = "<REPO_ROOT>\\ros2_deployment"

ssh $JETSON "mkdir -p ~/qgip_ws/src ~/qgip_templates ~/qgip_runs"
scp -r "$SRC\ros2_qgip_stack" "${JETSON}:~/qgip_ws/src/"
scp "$SRC\real_robot_run_manifest_template.yaml" "${JETSON}:~/qgip_templates/"
scp "$SRC\real_robot_results_template.csv" "${JETSON}:~/qgip_templates/"
scp "$SRC\real_robot_metric_schema.csv" "${JETSON}:~/qgip_templates/"
scp "$SRC\ros2_runtime_telemetry_schema.csv" "${JETSON}:~/qgip_templates/"
scp "$SRC\ros2_topic_contract.csv" "${JETSON}:~/qgip_templates/"
scp "$SRC\robot_profile_template.yaml" "${JETSON}:~/qgip_templates/"
```

为什么这样做：Jetson 端必须有与论文版本一致的 ROS2 包、manifest 和 schema。不要现场临时改字段名，否则后处理脚本和论文表格会对不上。

如果你们用 Git 管理，也可以在 Jetson 上 clone 固定 commit，但必须记录 commit hash：

```bash
cd ~/qgip_ws/src
git clone <YOUR_REPO_URL> qgip_repo
git -C qgip_repo rev-parse HEAD
```

### 3.4 在 Jetson 上编译和测试

在 Jetson Nano 执行：

```bash
cd ~/qgip_ws
source /opt/ros/$ROS_DISTRO/setup.bash
rosdep update
rosdep install --from-paths src --ignore-src -r -y
colcon build --packages-select ros2_qgip_stack --event-handlers console_direct+
source install/setup.bash
ros2 pkg prefix ros2_qgip_stack
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py --show-args
```

如果包内测试依赖齐全，继续执行：

```bash
colcon test --packages-select ros2_qgip_stack --event-handlers console_direct+
colcon test-result --verbose
```

为什么这样做：编译通过只说明包能安装；`--show-args` 能确认 launch 支持本实验需要的参数，包括 `dropout_duration_s`、`position_noise_std_m`、`delay_s`、`id_switch_probability`、`nis_soft_threshold`、`nis_hard_threshold`、`results_csv_path`。

通过标准：

- `ros2 pkg prefix ros2_qgip_stack` 返回安装路径。
- `ros2 launch ... --show-args` 能列出 launch 参数。
- 测试失败必须记录，不能忽略。

## 4. 每次 trial 的目录和记录规范

### 4.1 创建 run directory

在 Jetson 或 logger 上执行：

```bash
export RUN_ROOT=$HOME/qgip_runs/$(date +%Y%m%d)_jetson_nano_tase
export RUN_ID=$(date +%Y%m%d_%H%M%S)_stageB_nominal_R01
export RUN_DIR=$RUN_ROOT/$RUN_ID
mkdir -p "$RUN_DIR"
cp ~/qgip_templates/real_robot_run_manifest_template.yaml "$RUN_DIR/manifest.yaml"
touch "$RUN_DIR/operator_notes.md"
touch "$RUN_DIR/incident_report.md"
```

然后编辑 manifest：

```bash
nano "$RUN_DIR/manifest.yaml"
```

至少填这些字段：

- `trial.trial_id`
- `trial.scenario`
- `trial.method`
- `trial.speed_level`
- `trial.repeat_id`
- `hardware.follower_profile`
- `software.ros2_distribution`
- `software.qgip_commit_or_archive_id`
- `fault_profile.fault_type`
- `fault_profile.fault_level`
- `logging.rosbag_path`
- `safety_gate.max_speed_mps`
- `safety_gate.min_headway_abort_m`
- `safety_gate.min_ttc_abort_s`

为什么这样做：manifest 是后续论文表格、补充材料、数据可追溯性的主索引。没有 manifest 的 rosbag 不能作为正式结果，只能作为调试记录。

### 4.2 每次 trial 必录 topic

二车版本：

```bash
ros2 bag record -o "$RUN_DIR/bag" \
  /tf /tf_static \
  /robot_1/odom /robot_2/odom \
  /robot_1/detections_raw /robot_1/detections_faulty \
  /robot_1/qgip/selected_leader \
  /robot_1/qgip/pop_state \
  /robot_1/qgip/mpc_debug \
  /robot_1/qgip/trial_status \
  /robot_1/cmd_vel_safe \
  /robot_1/safety_state
```

三车版本增加 `/robot_3/odom`：

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

为什么这样做：

- `/robot_1/detections_raw` 和 `/robot_1/detections_faulty` 说明故障注入前后 object list 的变化。
- `/robot_1/qgip/selected_leader` 支撑 LeaderAcc、wrong-leader exposure、ID switch。
- `/robot_1/qgip/pop_state` 支撑 TRACK/GHOST/DEGRADED/LOST 和 NIS trace。
- `/robot_1/qgip/mpc_debug` 和 `/robot_1/cmd_vel_safe` 支撑 safe command 结论。
- `/robot_1/safety_state` 支撑 stop reason 和 watchdog 结论。

### 4.3 记录 Jetson Nano 负载

Jetson Nano 上执行：

```bash
sudo tegrastats --interval 1000 --logfile "$RUN_DIR/tegrastats.log" &
echo $! > "$RUN_DIR/tegrastats.pid"
```

trial 结束后停止：

```bash
kill "$(cat "$RUN_DIR/tegrastats.pid")"
```

为什么这样做：Jetson Nano 算力有限，掉帧和延迟可能来自 CPU/GPU/内存/温度，而不是算法本身。T-ASE 审稿人会接受诚实的 runtime telemetry，但不会接受只给成功率不解释实时负载。

### 4.4 记录 topic rate 和单条样例

每次正式 trial 前或每组 trial 第一轮前执行：

```bash
ros2 topic hz /robot_1/odom > "$RUN_DIR/topic_hz_robot1_odom.txt"
ros2 topic hz /robot_1/qgip/pop_state > "$RUN_DIR/topic_hz_pop_state.txt"
ros2 topic hz /robot_1/cmd_vel_safe > "$RUN_DIR/topic_hz_cmd_vel_safe.txt"
```

另开终端检查一次 payload：

```bash
ros2 topic echo /robot_1/detections_raw --once
ros2 topic echo /robot_1/qgip/selected_leader --once
ros2 topic echo /robot_1/qgip/pop_state --once
ros2 topic echo /robot_1/qgip/mpc_debug --once
ros2 topic echo /robot_1/safety_state --once
```

为什么这样做：论文需要的是可解释接口。只看视频不能证明 POP/NIS mode、selected leader、NIS 值和 stop reason 是否正确。

## 5. Stage A：Workspace、网络、TF 和 topic preflight

### 5.1 启动机器人底层 bringup

在每台机器人上启动自己的底盘驱动和 odom/TF。命令按你们小车实际包替换：

```bash
source /opt/ros/$ROS_DISTRO/setup.bash
source ~/qgip_ws/install/setup.bash
export ROS_DOMAIN_ID=36

# 示例。替换成你们小车自己的 bringup。
ros2 launch <robot_bringup_pkg> <bringup.launch.py> namespace:=robot_1
```

leader 和 distractor 分别用 `namespace:=robot_2`、`namespace:=robot_3`。

为什么这样做：`ros2_qgip_stack` 当前基于 `/robot_i/odom` 和 `robot_i/base_link` 生成 object-list 式 detections。如果 odom/TF 不稳定，后续 dropout、NIS、MPC 结果都没有意义。

### 5.2 检查 topic 和 TF

在 Jetson 或 logger 上执行：

```bash
source /opt/ros/$ROS_DISTRO/setup.bash
source ~/qgip_ws/install/setup.bash
export ROS_DOMAIN_ID=36

ros2 topic list | sort
ros2 topic hz /robot_1/odom
ros2 topic hz /robot_2/odom
ros2 run tf2_ros tf2_echo robot_1/base_link robot_2/base_link
```

如果有 distractor：

```bash
ros2 topic hz /robot_3/odom
ros2 run tf2_ros tf2_echo robot_1/base_link robot_3/base_link
```

通过标准：

- `/robot_1/odom`、`/robot_2/odom` 至少 20 Hz，最低不低于 10 Hz。
- TF echo 中 follower 到 leader 的距离和现场量尺距离接近。
- 没有重复 frame id。
- `/tf` 更新不卡顿。

### 5.3 启动 QGIP preflight stack，不接底盘

二车版本：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=0.0 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

三车版本：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link,robot_3/base_link \
  leader_ids:=robot_2,robot_3 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=0.0 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

注意：这一步只允许发布 `/robot_1/cmd_vel_safe`，不要把它桥接到真实底盘命令。

为什么这样做：先证明算法节点能读到 object list、发布 selected leader、生成 POP state 和 safe command。此时小车不动，任何错误都不会造成物理风险。

### 5.4 检查 selected leader 只有一个 publisher

```bash
ros2 topic info /robot_1/qgip/selected_leader -v
```

通过标准：

- preflight 模式下通常只有 `tf_leader_detection_node` 发布 selected leader。
- 如果你额外部署学习版 `qgip_selector`，必须保证 `/robot_1/qgip/selected_leader` 只有一个 publisher。

为什么这样做：两个 publisher 同时写 selected leader 会造成 ID 抖动，后续所有 ID-switch 指标都会失真。

## 6. Stage B：Shadow rosbag 和故障注入，不驱动车

Stage B 的目的：让 Jetson Nano 真实运行节点并输出 `/robot_1/cmd_vel_safe`，但不接到底盘。它验证实时性和 mode response，不验证物理执行。

### 6.1 Nominal following shadow

创建目录：

```bash
export RUN_ID=$(date +%Y%m%d_%H%M%S)_stageB_nominal_R01
export RUN_DIR=$RUN_ROOT/$RUN_ID
mkdir -p "$RUN_DIR"
cp ~/qgip_templates/real_robot_run_manifest_template.yaml "$RUN_DIR/manifest.yaml"
```

启动 rosbag 记录：

```bash
ros2 bag record -o "$RUN_DIR/bag" \
  /tf /tf_static \
  /robot_1/odom /robot_2/odom \
  /robot_1/detections_raw /robot_1/detections_faulty \
  /robot_1/qgip/selected_leader \
  /robot_1/qgip/pop_state \
  /robot_1/qgip/mpc_debug \
  /robot_1/qgip/trial_status \
  /robot_1/cmd_vel_safe \
  /robot_1/safety_state
```

另开终端启动 stack：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=0.0 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

现场操作：

1. follower 静止。
2. leader 在前方 0.6-1.0 m 处低速移动，或人工缓慢推动 leader。
3. 记录 60 s。
4. 停止 rosbag 和 launch。

为什么这样做：先采集无扰动基线。只有基线稳定，dropout、distractor、ID switch 的结果才可解释。

通过标准：

- `pop_state.mode` 大部分时间为 `TRACKING` 或等价正常 mode。
- `cmd_vel_safe` 没有异常跳变。
- `trial_status` 没有 near-miss、watchdog、lost。

### 6.2 Short dropout shadow, 0.5 s

```bash
export RUN_ID=$(date +%Y%m%d_%H%M%S)_stageB_dropout05_R01
export RUN_DIR=$RUN_ROOT/$RUN_ID
mkdir -p "$RUN_DIR"
cp ~/qgip_templates/real_robot_run_manifest_template.yaml "$RUN_DIR/manifest.yaml"
```

启动 stack：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=0.5 \
  ghost_horizon_s:=1.0 \
  lost_timeout_s:=1.5 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

为什么这样做：0.5 s dropout 对应论文中 object-list 短时缺测。期望行为不是立刻换目标，也不是继续盲目加速，而是进入 GHOST 或 DEGRADED，并在观测恢复后回到 TRACKING。

通过标准：

- dropout 期间 `/robot_1/detections_faulty` 出现缺测。
- `/robot_1/qgip/pop_state` 中 `ghost_age` 增加。
- 观测恢复后 mode 回到 TRACKING。
- 没有 safety_state 中的危险 stop，除非 leader 距离确实太近。

### 6.3 Sustained dropout shadow, 1.0 s 到 1.5 s

```bash
export RUN_ID=$(date +%Y%m%d_%H%M%S)_stageB_dropout10_R01
export RUN_DIR=$RUN_ROOT/$RUN_ID
mkdir -p "$RUN_DIR"
cp ~/qgip_templates/real_robot_run_manifest_template.yaml "$RUN_DIR/manifest.yaml"
```

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=1.0 \
  ghost_horizon_s:=1.0 \
  lost_timeout_s:=1.5 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

为什么这样做：sustained dropout 是论文故事闭环中的 fail-safe 证据。短缺测应该预测和恢复，长缺测必须 LOST 或 stop，不能把 stale target 当成真实目标持续跟随。

通过标准：

- 如果 dropout 超过 ghost horizon，mode 应转向 LOST 或 safety stop。
- `/robot_1/cmd_vel_safe` 应降到 0 或保守低速。
- `/robot_1/qgip/mpc_debug` 中 `safety_stop` 或 stop reason 可解释。

### 6.4 Adjacent distractor shadow

三车版本：

```bash
export RUN_ID=$(date +%Y%m%d_%H%M%S)_stageB_distractor_R01
export RUN_DIR=$RUN_ROOT/$RUN_ID
mkdir -p "$RUN_DIR"
cp ~/qgip_templates/real_robot_run_manifest_template.yaml "$RUN_DIR/manifest.yaml"
```

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link,robot_3/base_link \
  leader_ids:=robot_2,robot_3 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=0.0 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

现场操作：

1. `/robot_2` 在 follower 前方作为正确 leader。
2. `/robot_3` 在旁边 0.3-0.6 m lateral offset，速度接近 leader。
3. 记录 selected leader 是否稳定指向正确对象。

为什么这样做：CARLA 主结果强调 wrong-leader exposure 和 ID-switch burden。实机只要能展示相同接口指标可被记录和诊断，就能补齐“真实 object-list ambiguity 可观测”的证据。

通过标准：

- `/robot_1/qgip/selected_leader` 中 `leader_id` 和人工 ground truth 一致。
- 如果发生 wrong leader，必须记录发生时间、持续帧数、现场原因。
- 不要删除失败 trial。失败 trial 是边界证据。

## 7. Stage C：架空轮或低风险 actuator bridge 检查

Stage C 允许底盘控制链路工作，但机器人不接地或处于极低风险状态。

### 7.1 检查 E-stop 和命令通道

先确认真实底盘 command topic。常见是：

- differential drive：`/robot_1/cmd_vel`
- Ackermann：`/robot_1/drive` 或 `/drive`

查看：

```bash
ros2 topic list | grep -E "cmd_vel|drive"
ros2 topic info /robot_1/cmd_vel -v
```

如果是 differential drive，并且已安装 `topic_tools`，可以用 relay 作为临时桥接：

```bash
ros2 run topic_tools relay /robot_1/cmd_vel_safe /robot_1/cmd_vel
```

如果是 Ackermann 小车，不能直接 relay `geometry_msgs/Twist`。需要使用你们底盘的 bridge，将 `/robot_1/cmd_vel_safe` 转换成 Ackermann speed/steering。仓库里有起点文件：

```text
<REPO_ROOT>\\ros2_deployment\ros2_ackermann_bridge_skeleton.py
```

为什么这样做：`/robot_1/cmd_vel_safe` 是经过安全过滤的命令。不要把未过滤的 raw MPC 命令或调试命令直接接到底盘。

### 7.2 架空轮测试

把 follower 车轮架空，或放到不会前进的滚筒/支架上。然后启动 QGIP stack 和 bridge：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.10 \
  dropout_duration_s:=0.0 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

另开终端启动 bridge：

```bash
# differential drive 示例，按现场底盘替换
ros2 run topic_tools relay /robot_1/cmd_vel_safe /robot_1/cmd_vel
```

检查：

```bash
ros2 topic echo /robot_1/cmd_vel_safe --once
ros2 topic echo /robot_1/safety_state --once
```

为什么这样做：这一步验证 command path，不验证跟车效果。若轮子方向、速度符号、角速度方向错了，必须在架空状态发现。

通过标准：

- E-stop 能立即让轮子停止。
- `max_speed_mps:=0.10` 时轮速不会超过限制。
- 当关闭 QGIP launch 或断开输入时，watchdog 能停止底盘。
- 没有持续 stale command。

## 8. Stage D：低速闭环实机实验

Stage D 是论文中可写的 physical robot validation。所有 Stage D trial 必须有 manifest、rosbag、telemetry、operator notes 和 incident report。

### 8.1 通用闭环启动顺序

每次 trial 前：

```bash
export RUN_ID=$(date +%Y%m%d_%H%M%S)_stageD_<SCENARIO>_R<REPEAT>
export RUN_DIR=$RUN_ROOT/$RUN_ID
mkdir -p "$RUN_DIR"
cp ~/qgip_templates/real_robot_run_manifest_template.yaml "$RUN_DIR/manifest.yaml"
nano "$RUN_DIR/manifest.yaml"
```

启动 telemetry：

```bash
sudo tegrastats --interval 1000 --logfile "$RUN_DIR/tegrastats.log" &
echo $! > "$RUN_DIR/tegrastats.pid"
```

启动 rosbag：

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

如果没有 `/robot_3`，把 `/robot_3/odom` 删除。

启动 QGIP stack：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.20 \
  nis_soft_threshold:=12.0 \
  nis_hard_threshold:=20.0 \
  r_inflation:=10.0 \
  ghost_horizon_s:=1.0 \
  lost_timeout_s:=1.5 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

最后才启动 actuator bridge：

```bash
# differential drive 示例。Ackermann 车请替换为你们的 bridge。
ros2 run topic_tools relay /robot_1/cmd_vel_safe /robot_1/cmd_vel
```

为什么最后才启动 bridge：先确认所有诊断 topic 正常，再允许真实执行器动。这样可以防止 launch 参数错误时小车突然运动。

### 8.2 D1 Nominal following

参数：

```bash
dropout_duration_s:=0.0
position_noise_std_m:=0.0
delay_s:=0.0
id_switch_probability:=0.0
false_positive_rate:=0.0
```

现场步骤：

1. follower 和 leader 排成直线，初始距离 0.8 m。
2. leader 以 0.15-0.20 m/s 前进。
3. follower 使用 `/robot_1/cmd_vel_safe` 跟随。
4. 每次 trial 30-60 s。
5. 重复至少 5 次，推荐 10 次。

为什么这样做：nominal 是实机基线，用来证明 Jetson Nano、ROS2、底盘、odom、TF 和 safety command 在无扰动下稳定。

记录重点：

- completion
- min_distance_m
- tracking_rmse_m
- jerk_p95
- latency_p95_ms / latency_p99_ms
- frame_drop_count

### 8.3 D2 Short dropout, 0.5 s

启动 QGIP stack 时加入：

```bash
dropout_duration_s:=0.5
ghost_horizon_s:=1.0
lost_timeout_s:=1.5
```

完整示例：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=0.5 \
  ghost_horizon_s:=1.0 \
  lost_timeout_s:=1.5 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

现场步骤：

1. 先按 nominal 条件跑 10 s。
2. 保持 leader 低速前进。
3. 让软件 fault injection 周期性造成 0.5 s 缺测。
4. 观察 POP mode 是否进入 GHOST 或 DEGRADED。
5. 观测恢复后继续跟车。

为什么用软件 dropout：当前 `ros2_qgip_stack` 的 detections 默认来自 TF/odom，不来自相机，因此真实遮挡不会自动导致 detection 消失。软件 dropout 能精确、可重复地模拟 object-list 缺测。如果后续接入 AprilTag/RGB-D detector，再增加人工遮挡作为物理 dropout。

通过标准：

- dropout 期间不发生危险加速。
- mode trace 中能看到 GHOST/DEGRADED。
- recovery_time_s 可计算。
- 没有 contact 或 near-miss。

### 8.4 D3 Sustained dropout, 1.0 s

启动 QGIP stack：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=1.0 \
  ghost_horizon_s:=1.0 \
  lost_timeout_s:=1.5 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

现场步骤：

1. 初始距离加大到 1.0 m。
2. leader 低速前进。
3. dropout 期间安全员准备 E-stop。
4. 观察 `cmd_vel_safe` 是否减速或停止。
5. 每次 trial 30-45 s。

为什么这样做：这是 fail-safe 证据。论文的核心不是“任何时候都成功跟随”，而是“target belief 不可靠时控制器能看到 LOST/DEGRADED 并保守处理”。

通过标准：

- LOST 或 safety_stop 能在长期缺测后出现。
- `cmd_vel_safe.linear.x` 不应持续维持高速度。
- incident report 中记录任何人工介入。

### 8.5 D4 Adjacent distractor

三车启动：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link,robot_3/base_link \
  leader_ids:=robot_2,robot_3 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=0.0 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

现场步骤：

1. `/robot_2` 在 follower 正前方作为 leader。
2. `/robot_3` 与 leader 平行或稍前，横向距离 0.3-0.6 m。
3. 两个目标速度接近。
4. 安全员观察 selected leader 是否跳到 distractor。
5. 每个 trial 30-60 s，至少 5 次。

为什么这样做：这是把 CARLA 中 false positive / wrong leader 的主叙事迁移到实机。即使当前先用 TF-derived object list，也能证明接口日志能记录 wrong-leader exposure 和 ID switch。

注意：

- 如果当前 preflight selector 不是学习版 QGIP selector，则论文中不要写“learned selector 已在实机中优于 baseline”。
- 若要验证学习版 selector，必须单独部署 `qgip_selector`，并避免两个 publisher 同时写 `/robot_1/qgip/selected_leader`。

### 8.6 D5 Dropout during lead braking

启动参数：

```bash
dropout_duration_s:=1.0
max_speed_mps:=0.20
```

现场步骤：

1. leader 先以 0.15-0.20 m/s 前进。
2. 10 s 后 leader 缓慢刹停。
3. 刹停期间触发 1.0 s dropout。
4. follower 应减速或停止，不应撞上 leader。
5. 每次 trial 后测量最小距离。

为什么这样做：这是最能说服审稿人的安全行为检查。stale leader 最危险的情况是前车减速但观测缺失，系统不能继续按旧速度追上去。

通过标准：

- no contact。
- min_distance_m 不低于 abort 阈值。
- safety_stop 或 conservative command 有可解释原因。

## 9. Baseline 和 ablation 怎么做才安全

### 9.1 推荐策略

实机闭环中优先只让 full target-belief interface 直接驱动车。危险 baseline 先用 shadow 或 rosbag replay 比较，不直接接底盘。

| 方法 | 闭环驱车 | shadow / replay | 原因 |
| --- | --- | --- | --- |
| Full QGIP/POP/NIS + safe controller | 可以 | 必做 | 论文主方法 |
| Std-KF-like + controller | 谨慎，低速 | 推荐 | NIS/POP 弱化后可能更容易 stale tracking |
| No-POP / no-NIS | 不推荐 | 必须先 shadow | 可能不安全 |
| Rule + MPC | 可低速，但先 shadow | 推荐 | baseline 可解释 |
| PID / raw detector following | 不推荐 | 可选 | 不是论文重点，风险高 |

### 9.2 Std-KF-like shadow profile

仅用于 replay 或 shadow，不建议直接闭环：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.20 \
  nis_soft_threshold:=1000000.0 \
  nis_hard_threshold:=1000000.0 \
  r_inflation:=1.0 \
  ghost_horizon_s:=0.0 \
  lost_timeout_s:=0.1 \
  results_csv_path:=$RUN_DIR/trial_status.csv
```

为什么这样做：这个 profile 近似去掉 NIS gating 和 object permanence。它可以说明 POP/NIS 的作用，但如果直接驱车，风险高。

### 9.3 Replay 同一 rosbag 比较方法

先播放已记录 bag：

```bash
ros2 bag play "$RUN_DIR/bag" --clock
```

另开终端启动不同 profile，并输出到不同 CSV：

```bash
ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py \
  follower_ns:=/robot_1 \
  follower_frame:=robot_1/base_link \
  leader_frames:=robot_2/base_link \
  leader_ids:=robot_2 \
  max_speed_mps:=0.20 \
  dropout_duration_s:=0.5 \
  results_csv_path:=$RUN_DIR/replay_full_qgip.csv
```

为什么这样做：同一 bag 上比较 baseline 能消除场地和人工操作差异。T-ASE 审稿人更容易接受 paired evidence。

## 10. 如果要部署学习版 QGIP selector

当前 `multi_robot_preflight.launch.py` 会启动 `tf_leader_detection_node`，该节点会发布 `/robot_1/qgip/selected_leader`。如果再启动学习版 `qgip_selector`，必须解决 publisher 冲突。

推荐两种方式：

### 10.1 方式一：保留 preflight selector，只做接口实机验证

这是最稳妥的 T-ASE 初稿方案。论文标题和 caption 写：

> Low-speed physical validation of the target-belief interface.

不要写：

> Learned QGIP selector is physically validated.

### 10.2 方式二：学习版 selector 替换 selected_leader publisher

要求：

1. 学习版 selector 订阅 `/robot_1/detections_faulty` 或 graph topic。
2. 学习版 selector 发布 `/robot_1/qgip/selected_leader`，JSON 字段至少包括 `leader_id`、`confidence`、`rank`、`candidate_count`。
3. preflight 的 selected leader publisher 必须改名或关闭。
4. 执行：

```bash
ros2 topic info /robot_1/qgip/selected_leader -v
```

通过标准：只有学习版 selector 一个 publisher。

为什么这样做：论文中的 LeaderAcc 和 wrong-leader exposure 是 selected leader 的函数。如果两个 selector 同时发布，实验结果不可用。

## 11. Trial 结束后的检查

每次 trial 结束后立即执行：

```bash
ros2 bag info "$RUN_DIR/bag" > "$RUN_DIR/bag_info.txt"
kill "$(cat "$RUN_DIR/tegrastats.pid")"
```

检查 bag 是否包含必需 topic：

```bash
grep -E "detections_raw|detections_faulty|selected_leader|pop_state|mpc_debug|trial_status|cmd_vel_safe|safety_state" "$RUN_DIR/bag_info.txt"
```

记录现场结论：

```bash
nano "$RUN_DIR/operator_notes.md"
nano "$RUN_DIR/incident_report.md"
```

operator notes 必须写：

- trial 是否按计划完成。
- 是否 E-stop。
- 是否接触。
- 是否 near-miss。
- 如果 selected leader 明显错误，写时间点和现场原因。
- 如果延迟、掉帧、热降频，写现象。

为什么这样做：失败 trial 不应该被删除。T-ASE 更看重边界清楚和日志完整，删除失败会破坏证据可信度。

## 12. 结果汇总和论文表格

### 12.1 整理 per-trial summary CSV

以仓库模板为准：

```text
~/qgip_templates/real_robot_results_template.csv
```

每一行对应一个 trial。字段必须符合：

```text
~/qgip_templates/real_robot_metric_schema.csv
```

关键字段：

- `trial_id`
- `method`
- `scenario`
- `fault_type`
- `repeat_id`
- `completion`
- `contact`
- `safety_stop`
- `near_miss`
- `lost`
- `min_distance_m`
- `min_ttc_s`
- `recovery_time_s`
- `id_switch_count`
- `tracking_rmse_m`
- `jerk_p95`
- `latency_p95_ms`
- `latency_p99_ms`
- `frame_drop_count`
- `cmd_vel_safe_age_p95_ms`
- `cpu_load_mean_percent`
- `gpu_load_mean_percent`
- `gpu_memory_peak_mb`

为什么这样做：论文正文不需要放全部 rosbag，但表格中的每个数字必须能追溯到 manifest、bag、telemetry 和 operator notes。

### 12.2 在 Windows 主机上运行汇总脚本

把 filled CSV 从 Jetson 拷回 Windows：

```powershell
$JETSON = "jetson@<JETSON_IP>"
scp "${JETSON}:~/qgip_runs/<DATE>_jetson_nano_tase/real_robot_results_filled.csv" `
  "<REPO_ROOT>\\ros2_deployment\real_robot_results_filled.csv"
```

运行汇总：

```powershell
python "<REPO_ROOT>\\analysis_scripts\summarize_real_robot_trials.py" `
  "<REPO_ROOT>\\ros2_deployment\real_robot_results_filled.csv" `
  --group-by method,scenario,fault_type `
  --output "<REPO_ROOT>\\ros2_deployment\real_robot_results_summary.csv"
```

为什么这样做：主文表格应按 method、scenario、fault_type 聚合，而不是罗列每个 trial。已有脚本会给 rate 指标生成 Wilson CI，适合写 T-ASE 的有限样本边界。

### 12.3 论文需要的实机图

建议正文只放一张实机图，命名为：

> Low-speed physical validation of the target-belief interface.

四个 panel：

1. 小车和场地照片，标注 follower、leader、distractor、test corridor。
2. headway vs time，叠加 dropout 区间。
3. POP/NIS mode trace，显示 TRACK/GHOST/DEGRADED/LOST。
4. 每个实机条件的 summary bar：N、success、lost、safety stop、contact。

为什么这样做：正文图要完成叙事闭环，而不是堆表。实机图的任务是证明仿真中的 belief interface 能在真实 ROS2 小车上产生可审计行为。

## 13. 实验通过和失败判定

### 13.1 可作为论文证据的最低标准

一组 trial 可进入论文结果表，需要满足：

- rosbag 完整，必需 topic 没缺。
- manifest 完整。
- trial outcome 明确。
- operator notes 完整。
- contact、near-miss、manual intervention 均被如实记录。
- telemetry 有 Jetson 负载或至少 topic rate / latency 证据。

### 13.2 必须停止当天实机实验的情况

任一情况出现，停止闭环实机，退回 Stage B 或 Stage C：

- E-stop 失效。
- `/robot_1/cmd_vel_safe` 持续发布陈旧命令。
- p95 latency 超过 200 ms 且无法解释。
- `/robot_1/safety_state` 不更新。
- 小车实际运动方向和命令方向不一致。
- 发生硬接触。
- follower 离开测试走廊。
- Jetson Nano 频繁热降频或内存耗尽。

为什么这样做：实机实验的目标是补证据，不是冒险追求完成率。任何无法解释的安全链路异常都会削弱论文可信度。

## 14. 最终交付物清单

完成实机实验后，实验人员应交付：

```text
qgip_runs/
  20260610_jetson_nano_tase/
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

论文写作端需要：

- 一张实机场地图或照片。
- 每个 trial 的 rosbag 和 manifest。
- `real_robot_results_summary.csv`。
- 一条代表性 dropout trial 的 time-series 数据，用于画 headway、NIS、mode、cmd_vel_safe。
- 所有 contact、near-miss、E-stop 的 incident note。

## 15. 推荐先执行的最短路线

如果今天只想快速推进，按这个顺序做：

1. Jetson 编译 `ros2_qgip_stack`。
2. 三台车或两台车的 `/odom`、`/tf` preflight。
3. Stage B nominal 3 次，每次 60 s。
4. Stage B dropout 0.5 s 3 次。
5. Stage C 架空轮 bridge 1 次。
6. Stage D nominal 5 次。
7. Stage D dropout 0.5 s 5 次。
8. 如果安全，Stage D sustained dropout 1.0 s 5 次。
9. 如果有第三台车，Stage D adjacent distractor 5 次。

这条路线能最快得到论文中可用的低速实机证据。后续再补 lead braking 和更多 repeats，提高 T-ASE 说服力。
