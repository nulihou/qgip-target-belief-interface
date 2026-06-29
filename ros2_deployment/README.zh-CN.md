# QGIP ROS2 预验证部署仓库

本仓库只放小车端需要的 ROS2 部署文件，不放论文、图、投稿包和大体积数据。

详细步骤、命令用途和证据保存要求见：[RUNBOOK.zh-CN.md](RUNBOOK.zh-CN.md)。

## 快速开始

```bash
mkdir -p ~/qgip_ws/src
cd ~/qgip_ws/src
git clone https://github.com/nulihou/qgip-target-belief-interface.git
cd ~/qgip_ws
rosdep install --from-paths src -y --ignore-src
colcon build --packages-select ros2_qgip_stack --event-handlers console_direct+
source install/setup.bash
colcon test --packages-select ros2_qgip_stack --event-handlers console_direct+
colcon test-result --verbose
```

Linux:

```bash
cp src/qgip-target-belief-interface/run_ros2_workspace_preflight.sh .
bash run_ros2_workspace_preflight.sh
```

Windows/PowerShell:

```powershell
Copy-Item src\qgip-target-belief-interface\run_ros2_workspace_preflight.ps1 .
powershell -ExecutionPolicy Bypass -File .\run_ros2_workspace_preflight.ps1
```

首次启动必须保持 shadow mode，不要把 `/robot_1/cmd_vel_safe` 直接接到底盘控制器。
需要先保存 build/test/launch、topic、TF、rosbag 和 runtime telemetry 证据。
