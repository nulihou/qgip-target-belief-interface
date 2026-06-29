#!/usr/bin/env python3
"""Static ROS2 interface audit for the pre-real-robot validation package."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "03_real_robot"
STACK = REAL / "ros2_qgip_stack"
PKG = STACK / "ros2_qgip_stack"
PACKAGE = ROOT / "06_submission_package"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
OUT_CSV = SOURCE / "ros2_static_interface_audit.csv"
OUT_REPORT = PACKAGE / "ros2_static_interface_audit_report_20260604.md"


@dataclass
class AuditRow:
    check_id: str
    layer: str
    requirement: str
    evidence: str
    status: str
    boundary: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def ok_text(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def contains_all(text: str, needles: list[str]) -> tuple[bool, list[str]]:
    missing = [needle for needle in needles if needle not in text]
    return not missing, missing


def add(
    rows: list[AuditRow],
    check_id: str,
    layer: str,
    requirement: str,
    ok: bool,
    evidence: str,
    boundary: str,
) -> None:
    rows.append(AuditRow(check_id, layer, requirement, evidence, ok_text(ok), boundary))


def topic_row(rows: list[dict[str, str]], topic: str) -> dict[str, str]:
    matches = [row for row in rows if row["topic"] == topic]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one contract row for {topic}, found {len(matches)}")
    return matches[0]


def main() -> None:
    contract = read_csv(REAL / "ros2_topic_contract.csv")
    metric_schema = read_csv(REAL / "real_robot_metric_schema.csv")
    with (REAL / "real_robot_results_template.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        result_template_fields = next(csv.reader(handle))

    setup_text = read_text(STACK / "setup.py")
    package_xml = read_text(STACK / "package.xml")
    launch_text = read_text(STACK / "launch" / "multi_robot_preflight.launch.py")
    config_text = read_text(STACK / "config" / "multi_robot_profile.yaml")
    readme_text = read_text(STACK / "README.md")
    manifest_text = read_text(REAL / "real_robot_run_manifest_template.yaml")
    node_texts = "\n".join(read_text(path) for path in sorted(PKG.glob("*.py")))

    rows: list[AuditRow] = []

    required_topics = [
        "/robot_1/odom",
        "/robot_2/odom",
        "/robot_3/odom",
        "/tf",
        "/tf_static",
        "/robot_1/detections_raw",
        "/robot_1/detections_faulty",
        "/robot_1/qgip/selected_leader",
        "/robot_1/qgip/pop_state",
        "/robot_1/qgip/mpc_debug",
        "/robot_1/qgip/trial_status",
        "/robot_1/cmd_vel_safe",
        "/robot_1/safety_state",
    ]
    contract_topics = {row["topic"] for row in contract}
    add(
        rows,
        "topic_contract_row_count",
        "topic_contract",
        "The topic contract lists exactly the 13 expected ROS2 interface topics.",
        len(contract) == 13 and set(required_topics) == contract_topics,
        f"rows={len(contract)}; missing={sorted(set(required_topics) - contract_topics)}; extra={sorted(contract_topics - set(required_topics))}",
        "Static contract inventory only; it does not prove topic publication at runtime.",
    )

    deps = ["rclpy", "std_msgs", "geometry_msgs", "nav_msgs", "tf2_ros"]
    ok, missing = contains_all(package_xml, [f"<exec_depend>{dep}</exec_depend>" for dep in deps])
    add(
        rows,
        "package_xml_dependencies",
        "package_metadata",
        "package.xml declares the runtime dependencies needed by the preflight nodes.",
        ok,
        "missing=" + "; ".join(missing) if missing else "all required exec_depend entries present",
        "Does not verify that the dependencies are installed in the current desktop environment.",
    )

    node_names = [
        "tf_leader_detection_node",
        "fault_injection_node",
        "pop_nis_kf_node",
        "velocity_safety_controller_node",
        "trial_supervisor_node",
    ]
    ok, missing = contains_all(setup_text, [f"{name} =" for name in node_names])
    files_ok = all((PKG / f"{name}.py").exists() for name in node_names)
    add(
        rows,
        "setup_console_scripts",
        "package_metadata",
        "setup.py exposes all ROS2 node console scripts and matching source files.",
        ok and files_ok,
        f"missing_scripts={missing}; files_ok={files_ok}",
        "Entry-point presence is static; colcon build remains an external ROS2-environment gate.",
    )

    ok, missing = contains_all(launch_text, [f'executable="{name}"' for name in node_names])
    add(
        rows,
        "launch_nodes",
        "launch",
        "The multi-robot preflight launch starts the five local preflight nodes.",
        ok,
        "missing=" + "; ".join(missing) if missing else "all node executables present in launch",
        "Static launch inspection only; it does not execute ros2 launch.",
    )

    launch_args = [
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
    ]
    ok, missing = contains_all(launch_text, [f'DeclareLaunchArgument("{arg}"' for arg in launch_args])
    add(
        rows,
        "launch_fault_and_safety_args",
        "launch",
        "Launch file exposes the fault-injection, NIS, timeout, and speed-limit knobs required before physical trials.",
        ok,
        "missing=" + "; ".join(missing) if missing else "all expected launch arguments declared",
        "Argument declaration does not prove safe values were selected by an operator.",
    )

    configured_topics = [
        "detections_raw",
        "detections_faulty",
        "selected_leader",
        "pop_state",
        "mpc_debug",
        "trial_status",
        "cmd_vel_safe",
        "safety_state",
    ]
    ok, missing = contains_all(config_text, [f"{topic}:" for topic in configured_topics])
    add(
        rows,
        "config_topic_profile",
        "configuration",
        "The robot profile names every local diagnostic/control topic used by the dry-run stack.",
        ok,
        "missing=" + "; ".join(missing) if missing else "all configured topic keys present",
        "Config file is a preflight profile; it is not a runtime parameter dump from a robot.",
    )

    route_checks = [
        (
            "detections_raw_route",
            "/robot_1/detections_raw",
            ["detections_topic", "detections_raw", "input_topic", "detections_raw"],
            "TF leader detection publishes unfaulted detections and fault injection subscribes.",
        ),
        (
            "selected_leader_route",
            "/robot_1/qgip/selected_leader",
            ["selected_leader_topic", "selected_leader", "leader_id", "candidate_count"],
            "Leader-selection identity is logged separately and can filter POP tracking.",
        ),
        (
            "detections_faulty_route",
            "/robot_1/detections_faulty",
            ["detections_faulty", "input_topic", "output_topic"],
            "Fault injection publishes the perturbed detection stream and POP consumes it.",
        ),
        (
            "pop_state_route",
            "/robot_1/qgip/pop_state",
            ["pop_state", "pop_state_topic", "ghost_age_s", "nis"],
            "POP state carries mode, uncertainty, and ghost-tracking diagnostics to controller/supervisor.",
        ),
        (
            "cmd_vel_safe_route",
            "/robot_1/cmd_vel_safe",
            ["cmd_vel_safe", "cmd_vel_safe_topic", "max_speed_mps", "safety_stop"],
            "Controller publishes a bounded velocity command and supervisor observes it.",
        ),
        (
            "mpc_debug_route",
            "/robot_1/qgip/mpc_debug",
            ["mpc_debug", "debug_topic", "leader_distance_m", "desired_gap_m"],
            "Controller debug output exposes headway and stop reasons for rosbag/per-frame logs.",
        ),
        (
            "trial_status_route",
            "/robot_1/qgip/trial_status",
            ["trial_status", "status_topic", "min_distance_m", "latency_p95_ms"],
            "Trial supervisor publishes online status and can append CSV summaries.",
        ),
    ]
    combined = "\n".join([launch_text, config_text, readme_text, node_texts])
    for check_id, topic, needles, requirement in route_checks:
        row = topic_row(contract, topic)
        ok, missing = contains_all(combined, needles)
        add(
            rows,
            check_id,
            "topic_route",
            requirement,
            ok,
            f"contract_required_for={row['required_for']}; missing_static_tokens={missing}",
            "Static route check only; runtime ros2 topic echo/rosbag validation is still required.",
        )

    odom = topic_row(contract, "/robot_1/odom")
    ok = "/robot_1/odom" in config_text and "<exec_depend>nav_msgs</exec_depend>" in package_xml and "Odometry" in node_texts
    add(
        rows,
        "odom_external_dependency",
        "external_dependency",
        "Follower odometry is documented as an external robot-base dependency consumed by the controller.",
        ok,
        f"producer={odom['producer']}; consumer={odom['consumer']}",
        "The desktop audit cannot prove robot-base odometry rate, frame quality, or clock sync.",
    )

    safety = topic_row(contract, "/robot_1/safety_state")
    ok = "/robot_1/safety_state" in config_text and safety["producer"] == "safety_supervisor"
    add(
        rows,
        "safety_state_external_dependency",
        "external_dependency",
        "Independent safety-supervisor state is explicitly identified as an external gate before closed-loop physical claims.",
        ok,
        f"producer={safety['producer']}; consumer={safety['consumer']}; required_for={safety['required_for']}",
        "This package does not implement the independent hardware supervisor; physical trials still require one.",
    )

    required_metric_fields = [row["field"] for row in metric_schema if row["required"].lower() == "true"]
    missing_fields = [field for field in required_metric_fields if field not in result_template_fields]
    add(
        rows,
        "metric_schema_template_alignment",
        "metrics",
        "Every required real-robot metric schema field appears in the results template.",
        not missing_fields and len(metric_schema) == 29,
        f"schema_rows={len(metric_schema)}; missing_template_fields={missing_fields}",
        "Template alignment does not create measured robot evidence.",
    )

    safety_fields = [
        "physical_estop_checked",
        "cmd_vel_shadow_mode_first",
        "max_speed_mps",
        "min_headway_abort_m",
        "min_ttc_abort_s",
        "operator_line_of_sight",
        "test_area_clear",
    ]
    ok, missing = contains_all(manifest_text, safety_fields)
    add(
        rows,
        "run_manifest_safety_gate",
        "run_manifest",
        "Run manifest template contains physical safety gates that must be filled before closed-loop trials.",
        ok,
        "missing=" + "; ".join(missing) if missing else "all safety gate fields present",
        "Blank templates are not evidence that an operator completed the gates.",
    )

    readme_needles = [
        "Do not connect `/robot_1/cmd_vel_safe`",
        "ros2 launch ros2_qgip_stack multi_robot_preflight.launch.py",
        "ros2 topic echo /robot_1/qgip/selected_leader",
        "not a full-scale ACC vehicle deployment",
    ]
    ok, missing = contains_all(readme_text, readme_needles)
    add(
        rows,
        "readme_dry_run_boundary",
        "operator_documentation",
        "README documents dry-launch inspection commands and the no-full-scale-deployment boundary.",
        ok,
        "missing=" + "; ".join(missing) if missing else "dry-run commands and boundary present",
        "README review does not replace an operator checklist or safety sign-off.",
    )

    add(
        rows,
        "static_audit_nonclaim",
        "audit_boundary",
        "The static audit is explicitly scoped below ROS2 build/launch and below physical validation.",
        True,
        "no ROS2 import, no colcon build, no ros2 launch, no robot motion",
        "Pass means interface consistency for preflight assets, not physical validation completion.",
    )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AuditRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])

    failed = [row for row in rows if row.status != "PASS"]
    report_lines = [
        "# ROS2 Static Interface Audit Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"The ROS2 static interface audit checks {len(rows)} pre-real-robot interface gates across topic contracts, launch wiring, node sources, configuration, metric templates, and safety documentation.",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All audited static-interface checks passed." if not failed else "One or more static-interface checks failed.",
        "",
        "## What This Adds",
        "",
        "- Confirms the selected-leader route is represented in the topic contract, launch file, TF preflight publisher, POP subscriber, config, and README dry-run commands.",
        "- Confirms local detection, POP, controller-debug, trial-status, and safe-command topics are statically wired.",
        "- Confirms metric-schema fields align with the real-robot results template.",
        "- Confirms independent `safety_state` remains an external safety-supervisor gate rather than an implemented claim inside this package.",
        "",
        "## Boundary",
        "",
        "This audit does not prove ROS2 launch/build success, rosbag recording, timing quality, real-world safety, and it does not prove physical robot validation. It is a preflight consistency check for the static package before moving to a ROS2 workspace and a supervised robot test area.",
    ]
    if failed:
        report_lines.extend(["", "## Failed Checks", ""])
        for row in failed:
            report_lines.append(f"- `{row.check_id}`: {row.evidence}")

    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")
    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
