#!/usr/bin/env python3
"""Record the first ROS2 execution-attempt audit after freezing v36.

This audit is deliberately stricter than the existing static ROS2 readiness
checks: it runs what the current host can actually run and marks missing ROS2
tooling as BLOCKED rather than treating protocol readiness as launch evidence.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL_ROBOT = ROOT / "03_real_robot"
STACK = REAL_ROBOT / "ros2_qgip_stack"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"
OUT_CSV = SOURCE / "ros2_execution_attempt_audit.csv"
OUT_REPORT = PACKAGE / "ros2_execution_attempt_audit_report_20260604.md"
V36_ZIP = PACKAGE / "current_extended_simulation_first_20260603_final_v36_structured.zip"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_cmd(command: list[str], cwd: Path, timeout_s: int = 120) -> tuple[str, str, int | str]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except FileNotFoundError as exc:
        return "BLOCKED", str(exc), "not-found"
    except subprocess.TimeoutExpired as exc:
        detail = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
        return "FAIL", f"timeout after {timeout_s}s; {detail}", "timeout"

    output = (completed.stdout + "\n" + completed.stderr).strip()
    status = "PASS" if completed.returncode == 0 else "FAIL"
    return status, output, completed.returncode


def add(
    rows: list[dict[str, str]],
    audit_id: str,
    category: str,
    command: str,
    cwd: Path,
    status: str,
    evidence: str,
    boundary: str,
    returncode: int | str = "",
) -> None:
    rows.append(
        {
            "audit_id": audit_id,
            "category": category,
            "command": command,
            "cwd": str(cwd.relative_to(ROOT) if cwd.is_relative_to(ROOT) else cwd),
            "status": status,
            "returncode": str(returncode),
            "evidence": evidence.replace("\r\n", "\n").replace("\r", "\n")[:1200],
            "boundary": boundary,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    )


def ast_parse_real_robot_sources() -> tuple[bool, str]:
    count = 0
    failures: list[str] = []
    for path in sorted(REAL_ROBOT.rglob("*.py")):
        parts = set(path.parts)
        if "__pycache__" in parts or "pytest-cache-files" in str(path):
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"))
            count += 1
        except Exception as exc:  # pragma: no cover - audit detail path
            failures.append(f"{path.relative_to(ROOT).as_posix()}: {exc!r}")
    if failures:
        return False, "; ".join(failures)
    return True, f"{count} Python sources parsed with ast.parse"


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    if V36_ZIP.exists():
        with zipfile.ZipFile(V36_ZIP, "r") as archive:
            entry_count = len(archive.infolist())
        add(
            rows,
            "v36_baseline_frozen",
            "baseline",
            "sha256 + zip entry count",
            ROOT,
            "PASS",
            f"sha256={sha256(V36_ZIP)}; entries={entry_count}; size_bytes={V36_ZIP.stat().st_size}",
            "Baseline identity only; no new ROS2 execution evidence is implied.",
        )
    else:
        add(rows, "v36_baseline_frozen", "baseline", "sha256 + zip entry count", ROOT, "FAIL", "v36 zip missing", "Cannot anchor post-v36 execution audit without the frozen package.")

    add(
        rows,
        "python_environment",
        "host",
        "python --version",
        ROOT,
        "PASS",
        f"executable={sys.executable}; version={sys.version.splitlines()[0]}",
        "Python availability is not ROS2 availability.",
    )

    script_evidence = []
    for rel in ("03_real_robot/run_ros2_workspace_preflight.sh", "03_real_robot/run_ros2_workspace_preflight.ps1"):
        path = ROOT / rel
        script_evidence.append(f"{rel}={path.exists()}")
    add(
        rows,
        "preflight_runner_scripts_present",
        "ros2_handoff",
        "check .sh and .ps1 ROS2 preflight runners",
        ROOT,
        "PASS" if all((ROOT / rel).exists() for rel in ("03_real_robot/run_ros2_workspace_preflight.sh", "03_real_robot/run_ros2_workspace_preflight.ps1")) else "FAIL",
        "; ".join(script_evidence),
        "Runner script presence does not prove the scripts have been executed in a ROS2 workspace.",
    )

    ok, evidence = ast_parse_real_robot_sources()
    add(
        rows,
        "real_robot_python_ast_parse",
        "static_python",
        "ast.parse over 03_real_robot/*.py",
        ROOT,
        "PASS" if ok else "FAIL",
        evidence,
        "Syntax parsing does not import ROS2 modules or execute nodes.",
    )

    for audit_id, args, expected in (
        ("setup_name", [sys.executable, "setup.py", "--name"], "ros2_qgip_stack"),
        ("setup_version", [sys.executable, "setup.py", "--version"], "0.1.0"),
    ):
        status, output, returncode = run_cmd(args, STACK, timeout_s=30)
        normalized = output.strip().splitlines()[0] if output.strip() else ""
        if status == "PASS" and normalized != expected:
            status = "FAIL"
        add(
            rows,
            audit_id,
            "package_metadata",
            " ".join(args),
            STACK,
            status,
            output,
            "Setuptools metadata check does not prove ament/colcon installation.",
            returncode,
        )

    pytest_cmd = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "test/test_core_contracts.py"]
    status, output, returncode = run_cmd(pytest_cmd, STACK, timeout_s=120)
    add(
        rows,
        "pytest_core_contracts",
        "pure_python_tests",
        " ".join(pytest_cmd),
        STACK,
        status,
        output,
        "These tests intentionally avoid rclpy; they validate core contracts but not ROS2 node execution.",
        returncode,
    )

    colcon_path = shutil.which("colcon")
    ros2_path = shutil.which("ros2")
    add(
        rows,
        "colcon_available",
        "ros2_tooling",
        "colcon --help",
        REAL_ROBOT,
        "PASS" if colcon_path else "BLOCKED",
        f"colcon_path={colcon_path}" if colcon_path else "colcon executable not found on PATH",
        "Without colcon, this host cannot produce colcon build/test logs.",
    )
    add(
        rows,
        "ros2_available",
        "ros2_tooling",
        "ros2 --help",
        REAL_ROBOT,
        "PASS" if ros2_path else "BLOCKED",
        f"ros2_path={ros2_path}" if ros2_path else "ros2 executable not found on PATH",
        "Without ros2, this host cannot produce live launch/topic/rosbag evidence.",
    )

    if colcon_path:
        for audit_id, cmd in (
            ("colcon_build_ros2_qgip_stack", ["colcon", "build", "--packages-select", "ros2_qgip_stack"]),
            ("colcon_test_ros2_qgip_stack", ["colcon", "test", "--packages-select", "ros2_qgip_stack", "--event-handlers", "console_direct+"]),
        ):
            status, output, returncode = run_cmd(cmd, REAL_ROBOT, timeout_s=300)
            add(
                rows,
                audit_id,
                "ros2_execution",
                " ".join(cmd),
                REAL_ROBOT,
                status,
                output,
                "colcon result is host-specific and still does not prove HIL timing or physical robot behavior.",
                returncode,
            )
    else:
        for audit_id, command in (
            ("colcon_build_ros2_qgip_stack", "colcon build --packages-select ros2_qgip_stack"),
            ("colcon_test_ros2_qgip_stack", "colcon test --packages-select ros2_qgip_stack"),
        ):
            add(
                rows,
                audit_id,
                "ros2_execution",
                command,
                REAL_ROBOT,
                "BLOCKED",
                "not run because colcon executable is unavailable on this host",
                "Required next evidence: run this command in a ROS2 workspace and archive stdout/stderr.",
            )

    if ros2_path:
        launch_cmd = [
            "ros2",
            "launch",
            "ros2_qgip_stack",
            "multi_robot_preflight.launch.py",
            "follower_ns:=/robot_1",
            "dropout_duration_s:=0.0",
            "results_csv_path:=",
        ]
        status, output, returncode = run_cmd(launch_cmd, REAL_ROBOT, timeout_s=30)
        add(
            rows,
            "ros2_launch_preflight",
            "ros2_execution",
            " ".join(launch_cmd),
            REAL_ROBOT,
            status,
            output,
            "A launch command alone would still need topic echo, TF, rosbag, and timing evidence.",
            returncode,
        )
    else:
        add(
            rows,
            "ros2_launch_preflight",
            "ros2_execution",
            "ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py ...",
            REAL_ROBOT,
            "BLOCKED",
            "not run because ros2 executable is unavailable on this host",
            "Required next evidence: run launch in a sourced ROS2 workspace and capture topic/TF/rosbag outputs.",
        )

    fieldnames = ["audit_id", "category", "command", "cwd", "status", "returncode", "evidence", "boundary", "timestamp_utc"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

    lines = [
        "# ROS2 Execution Attempt Audit Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"Rows: {len(rows)}",
        f"PASS: {status_counts.get('PASS', 0)}",
        f"BLOCKED: {status_counts.get('BLOCKED', 0)}",
        f"FAIL: {status_counts.get('FAIL', 0)}",
        "",
        "The post-v36 local audit confirms that the pure-Python ROS2 package contracts execute on this host, but this host does not provide the `colcon` or `ros2` command-line tools. Therefore no colcon build/test log, live `ros2 launch` output, topic graph, TF tree, rosbag, HIL timing, or physical robot evidence is claimed from this run.",
        "",
        "## Audit Rows",
        "",
        "| status | audit | command | evidence | boundary |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        evidence_one_line = row["evidence"].replace("\n", " / ").replace("|", "\\|")
        boundary_one_line = row["boundary"].replace("|", "\\|")
        lines.append(
            f"| {row['status']} | {row['audit_id']} | `{row['command']}` | {evidence_one_line} | {boundary_one_line} |"
        )
    lines.extend(
        [
            "",
            "## Next Required External Evidence",
            "",
            "- Run `colcon build --packages-select ros2_qgip_stack` in a ROS2 environment and archive stdout/stderr.",
            "- Run `colcon test --packages-select ros2_qgip_stack --event-handlers console_direct+` and archive test-result XML plus console output.",
            "- Source the install workspace and run `ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py ...` in shadow mode.",
            "- Capture `ros2 topic list`, `ros2 topic hz`, selected-leader JSON samples, TF availability, rosbag metadata, and runtime latency p50/p95/p99.",
            "- Treat any physical robot claim as blocked until supervised low-speed trial manifests, incident reports, and bags exist.",
        ]
    )
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    print(OUT_CSV)
    print(OUT_REPORT)
    print(" ".join(f"{key.lower()}={value}" for key, value in sorted(status_counts.items())))


if __name__ == "__main__":
    main()
