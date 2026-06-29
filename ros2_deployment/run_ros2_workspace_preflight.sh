#!/usr/bin/env bash
set -euo pipefail

# Run from a ROS2 workspace root that contains ros2_qgip_stack under src/.
# This script prepares build/test evidence only; it does not command hardware.

PACKAGE_NAME="ros2_qgip_stack"
FOLLOWER_NS="/robot_1"

command -v ros2 >/dev/null
command -v colcon >/dev/null

colcon build --packages-select "${PACKAGE_NAME}" --event-handlers console_direct+
colcon test --packages-select "${PACKAGE_NAME}" --event-handlers console_direct+
colcon test-result --verbose

if [ -f "install/setup.bash" ]; then
  # shellcheck disable=SC1091
  source "install/setup.bash"
fi

ros2 pkg prefix "${PACKAGE_NAME}" >/dev/null
ros2 launch "${PACKAGE_NAME}" multi_robot_preflight.launch.py --show-args >/tmp/qgip_launch_args.txt

grep -q "follower_ns" /tmp/qgip_launch_args.txt
grep -q "max_speed_mps" /tmp/qgip_launch_args.txt
grep -q "nis_hard_threshold" /tmp/qgip_launch_args.txt
grep -q "results_csv_path" /tmp/qgip_launch_args.txt

python3 -m pytest "src/${PACKAGE_NAME}/test" -q

cat <<EOF
ROS2 workspace preflight completed for ${PACKAGE_NAME}.
No actuator bridge was enabled by this script.
Before Stage C/D evidence claims, record rosbag topics for ${FOLLOWER_NS},
archive ros2 bag info/topic hz outputs, and fill hil_replay_manifest_template.yaml.
EOF
