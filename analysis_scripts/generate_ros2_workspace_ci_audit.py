#!/usr/bin/env python3
"""Audit ROS2 workspace CI/preflight assets before HIL or robot execution."""

from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "03_real_robot"
STACK = REAL / "ros2_qgip_stack"
PKG = STACK / "ros2_qgip_stack"
TEST_DIR = STACK / "test"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"
OUT_CSV = SOURCE / "ros2_workspace_ci_audit.csv"
OUT_REPORT = PACKAGE / "ros2_workspace_ci_audit_report_20260604.md"


@dataclass
class AuditRow:
    check_id: str
    layer: str
    requirement: str
    evidence: str
    status: str
    source_artifacts: str
    boundary: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def add(
    rows: list[AuditRow],
    check_id: str,
    layer: str,
    requirement: str,
    ok: bool,
    evidence: str,
    source_artifacts: str,
    boundary: str,
) -> None:
    rows.append(
        AuditRow(
            check_id=check_id,
            layer=layer,
            requirement=requirement,
            evidence=evidence,
            status="PASS" if ok else "FAIL",
            source_artifacts=source_artifacts,
            boundary=boundary,
        )
    )


def missing_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term not in text]


def run_pytest() -> tuple[bool, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(STACK)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(TEST_DIR), "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
    )
    output = proc.stdout.strip().replace("\n", " | ")
    return proc.returncode == 0 and "7 passed" in proc.stdout, output[:500]


def pytest_test_count(path: Path) -> int:
    text = read_text(path)
    return len(re.findall(r"^def test_", text, flags=re.MULTILINE))


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)

    ci_manifest = REAL / "ros2_workspace_ci_manifest.yaml"
    preflight_script = REAL / "run_ros2_workspace_preflight.sh"
    test_file = TEST_DIR / "test_core_contracts.py"
    package_xml = STACK / "package.xml"
    setup_py = STACK / "setup.py"
    readme = STACK / "README.md"
    launch_file = STACK / "launch" / "multi_robot_preflight.launch.py"
    hil_manifest = REAL / "hil_replay_manifest_template.yaml"

    ci_text = read_text(ci_manifest)
    script_text = read_text(preflight_script)
    test_text = read_text(test_file)
    package_text = read_text(package_xml)
    setup_text = read_text(setup_py)
    readme_text = read_text(readme)
    launch_text = read_text(launch_file)
    hil_text = read_text(hil_manifest)

    rows: list[AuditRow] = []

    add(
        rows,
        "ci_asset_files_present",
        "ci_assets",
        "ROS2 workspace CI manifest, preflight shell script, and pytest contract file are present.",
        all(path.exists() and path.stat().st_size > 0 for path in (ci_manifest, preflight_script, test_file)),
        f"manifest={ci_manifest.exists()}; script={preflight_script.exists()}; tests={test_file.exists()}",
        "03_real_robot/ros2_workspace_ci_manifest.yaml; 03_real_robot/run_ros2_workspace_preflight.sh; 03_real_robot/ros2_qgip_stack/test/test_core_contracts.py",
        "File presence does not prove CI was executed in a ROS2 workspace.",
    )

    manifest_terms = [
        "colcon build --packages-select ros2_qgip_stack",
        "colcon test --packages-select ros2_qgip_stack",
        "colcon test-result --verbose",
        "ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py --show-args",
        "python3 -m pytest src/ros2_qgip_stack/test -q",
        "actuator_bridge_enabled_by_ci: false",
        "/robot_1/cmd_vel_safe",
        "/robot_1/safety_state",
    ]
    missing = missing_terms(ci_text, manifest_terms)
    add(
        rows,
        "ci_manifest_command_coverage",
        "ci_manifest",
        "CI manifest covers colcon build/test, test-result, launch argument parsing, pure-core pytest, and actuator-disabled safety boundary.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/ros2_workspace_ci_manifest.yaml",
        "Command coverage is a plan until run in a ROS2 workspace.",
    )

    script_terms = [
        "set -euo pipefail",
        "command -v ros2",
        "command -v colcon",
        "colcon build --packages-select",
        "colcon test --packages-select",
        "colcon test-result --verbose",
        "--show-args",
        "python3 -m pytest",
        "No actuator bridge was enabled",
    ]
    missing = missing_terms(script_text, script_terms)
    add(
        rows,
        "preflight_script_fail_fast_commands",
        "ci_script",
        "Preflight script fails fast, checks ROS2/colcon availability, builds, tests, parses launch args, and states that no actuator bridge is enabled.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/run_ros2_workspace_preflight.sh",
        "The shell script is not executed in this local non-ROS2 desktop environment.",
    )

    required_launch_args = [
        "follower_ns",
        "follower_frame",
        "leader_frames",
        "leader_ids",
        "max_speed_mps",
        "dropout_duration_s",
        "position_noise_std_m",
        "delay_s",
        "false_positive_rate",
        "false_negative_rate",
        "id_switch_probability",
        "confidence_threshold",
        "nis_soft_threshold",
        "nis_hard_threshold",
        "ghost_horizon_s",
        "lost_timeout_s",
        "results_csv_path",
    ]
    missing = [arg for arg in required_launch_args if arg not in ci_text or f'DeclareLaunchArgument("{arg}"' not in launch_text]
    add(
        rows,
        "launch_argument_ci_coverage",
        "ci_manifest",
        "CI manifest launch-argument list matches the safety, fault, timeout, and output arguments declared by the launch file.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/ros2_workspace_ci_manifest.yaml; 03_real_robot/ros2_qgip_stack/launch/multi_robot_preflight.launch.py",
        "Launch-argument coverage does not prove the nodes can run against live TF.",
    )

    test_terms = [
        "test_json_contract_normalizes_nonfinite_and_clamps_confidence",
        "test_fault_injector_dropout_delay_and_id_switch",
        "test_pop_tracker_progresses_tracking_to_ghost_to_lost",
        "test_pop_soft_and_hard_nis_gates",
        "test_pop_covariance_remains_finite_symmetric_psd",
    ]
    missing = missing_terms(test_text, test_terms)
    add(
        rows,
        "pytest_contract_scope",
        "pytest",
        "Pure-core pytest file covers JSON normalization, fault injection, POP dropout, NIS gates, and covariance hygiene.",
        not missing and pytest_test_count(test_file) == 7,
        f"test_count={pytest_test_count(test_file)}; missing={missing}",
        "03_real_robot/ros2_qgip_stack/test/test_core_contracts.py",
        "Pure-core pytest does not import rclpy or test ROS2 message transport.",
    )

    pytest_ok, pytest_output = run_pytest()
    add(
        rows,
        "local_pure_core_pytest_execution",
        "pytest",
        "Pure-core pytest suite executes successfully in the local desktop Python environment without ROS2.",
        pytest_ok,
        pytest_output,
        "03_real_robot/ros2_qgip_stack/test/test_core_contracts.py",
        "Local pytest success proves core contracts only; it is not colcon test or ROS2 node execution.",
    )

    add(
        rows,
        "package_xml_test_dependencies",
        "package_metadata",
        "package.xml declares pytest and ament test/lint dependencies for future colcon test.",
        all(term in package_text for term in ("<test_depend>python3-pytest</test_depend>", "<test_depend>ament_flake8</test_depend>", "<test_depend>ament_pep257</test_depend>")),
        "python3-pytest, ament_flake8, and ament_pep257 dependencies checked",
        "03_real_robot/ros2_qgip_stack/package.xml",
        "Test dependency declaration does not prove dependencies are installed.",
    )

    add(
        rows,
        "setup_excludes_test_package",
        "package_metadata",
        "setup.py keeps tests out of installable runtime packages while leaving them available for colcon/pytest.",
        'find_packages(exclude=["test"])' in setup_text,
        "setup.py uses find_packages(exclude=[\"test\"])",
        "03_real_robot/ros2_qgip_stack/setup.py",
        "Packaging policy does not prove wheel or ament install execution.",
    )

    add(
        rows,
        "readme_build_and_dry_launch_instructions",
        "documentation",
        "README documents colcon build, source install, dry launch, and shadow command boundary.",
        all(term in readme_text for term in ("colcon build --packages-select ros2_qgip_stack", "source install/setup.bash", "ros2 launch ros2_qgip_stack", "/robot_1/cmd_vel_safe", "/robot_1/safety_state")),
        "README build, source, launch, and shadow-command terms checked",
        "03_real_robot/ros2_qgip_stack/README.md",
        "README instructions do not prove operator execution.",
    )

    add(
        rows,
        "hil_manifest_links_after_ci",
        "hil_bridge",
        "CI manifest and HIL manifest link build/test readiness to Stage C replay evidence without enabling the actuator bridge.",
        all(term in ci_text + hil_text for term in ("hil_replay", "bridge_enabled: false", "ros2_hil_replay_manifest_audit.csv", "ros2 bag info")),
        "HIL manifest and CI archive terms checked",
        "03_real_robot/ros2_workspace_ci_manifest.yaml; 03_real_robot/hil_replay_manifest_template.yaml",
        "A linked manifest still needs executed bag metadata and timing logs.",
    )

    add(
        rows,
        "artifact_archive_requirements",
        "ci_manifest",
        "CI manifest archives build log, test log, launch-argument output, pytest output, environment audit, and HIL audit.",
        all(term in ci_text for term in ("colcon build log", "colcon test log", "ros2 launch --show-args output", "pytest output", "software_environment_audit_20260604.csv", "ros2_hil_replay_manifest_audit.csv")),
        "archive_after_success terms checked",
        "03_real_robot/ros2_workspace_ci_manifest.yaml",
        "Archive requirements are not a public repository deposit by themselves.",
    )

    failed = [row for row in rows if row.status != "PASS"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AuditRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])

    report_lines = [
        "# ROS2 Workspace CI Audit Report",
        "",
        f"Rows: {len(rows)}",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "",
        "This audit adds a ROS2 workspace build/test readiness layer: colcon build/test commands, launch-argument parsing, pure-core pytest, and no-actuator-bridge safety boundaries are specified before HIL or physical robot trials.",
        "",
        "The local executable evidence is limited to the pure-core pytest suite. This report does not prove colcon build success, colcon test success in a ROS2 workspace, live ros2 launch execution, rosbag timing, HIL replay, actuator bridge behavior, or physical robot motion.",
        "",
        "| status | check | evidence |",
        "|---|---|---|",
    ]
    report_lines.extend(f"| {row.status} | {row.check_id} | {row.evidence} |" for row in rows)
    if not failed:
        report_lines.extend(["", "All ROS2 workspace CI audit checks passed."])
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
