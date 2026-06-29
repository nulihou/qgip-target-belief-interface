# QGIP ROS2 Preflight Deployment

This repository contains only the ROS2 deployment files needed by the robot
machines. It excludes manuscript files, figures, submission packages, and large
datasets.

For detailed steps, command purposes, and evidence-archiving instructions, see
[RUNBOOK.en.md](RUNBOOK.en.md).

## Quick Start

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

Keep the first launch in shadow mode. Do not connect `/robot_1/cmd_vel_safe` to
the real base controller until build/test/launch, topic, TF, rosbag, and runtime
telemetry evidence has been archived.
