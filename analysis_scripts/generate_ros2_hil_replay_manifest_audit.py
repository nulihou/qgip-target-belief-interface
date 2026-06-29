#!/usr/bin/env python3
"""Audit the ROS2/HIL replay manifest before physical robot trials."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "03_real_robot"
STACK = REAL / "ros2_qgip_stack"
PKG = STACK / "ros2_qgip_stack"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"
OUT_CSV = SOURCE / "ros2_hil_replay_manifest_audit.csv"
OUT_REPORT = PACKAGE / "ros2_hil_replay_manifest_audit_report_20260604.md"


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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


def manifest_topics(text: str) -> list[str]:
    topics: list[str] = []
    in_required_topics = False
    for line in text.splitlines():
        if re.match(r"^\s*required_topics:\s*$", line):
            in_required_topics = True
            continue
        if in_required_topics and line and not line.startswith("    "):
            break
        if in_required_topics:
            match = re.match(r"^\s*-\s+(/[A-Za-z0-9_/]+)\s*$", line)
            if match:
                topics.append(match.group(1))
    return topics


def stage_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        stage = row["stage"]
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def repeat_sum(rows: list[dict[str, str]], stage: str) -> int:
    return sum(int(row["repeats"]) for row in rows if row["stage"] == stage)


def max_speed(rows: list[dict[str, str]], stage: str) -> float:
    speeds = [float(row["speed_mps"]) for row in rows if row["stage"] == stage]
    return max(speeds) if speeds else float("nan")


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)

    manifest_path = REAL / "hil_replay_manifest_template.yaml"
    rosbag_path = REAL / "rosbag_commands.md"
    launch_path = STACK / "launch" / "multi_robot_preflight.launch.py"
    controller_path = PKG / "velocity_safety_controller_node.py"
    supervisor_path = PKG / "trial_supervisor_node.py"

    manifest_text = read_text(manifest_path)
    rosbag_text = read_text(rosbag_path)
    launch_text = read_text(launch_path)
    controller_text = read_text(controller_path)
    supervisor_text = read_text(supervisor_path)
    metric_rows = read_csv(REAL / "real_robot_metric_schema.csv")
    preflight_rows = read_csv(REAL / "preflight_trials_matrix.csv")
    contract_rows = read_csv(REAL / "ros2_topic_contract.csv")
    results_fields = list(read_csv(REAL / "real_robot_results_template.csv")[0].keys())
    run_manifest_text = read_text(REAL / "real_robot_run_manifest_template.yaml")

    contract_topics = [row["topic"] for row in contract_rows]
    manifest_required_topics = manifest_topics(manifest_text)
    metric_fields = {row["field"] for row in metric_rows}
    counts = stage_counts(preflight_rows)

    rows: list[AuditRow] = []

    required_manifest_terms = [
        "manifest_version: 2026-06-04-pre-real-hil-v1",
        "Shadow replay only",
        "clock_required: true",
        "use_sim_time: true",
        "bridge_enabled: false",
        "operator_enable_required_for_stage_d: true",
        "archive_completeness",
    ]
    missing = missing_terms(manifest_text, required_manifest_terms)
    add(
        rows,
        "hil_manifest_boundary_and_gates",
        "manifest",
        "The HIL replay manifest declares shadow-only scope, ROS clock replay, actuator-bridge disablement, and archive gates.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/hil_replay_manifest_template.yaml",
        "Template audit only; it does not prove a bag has been recorded or replayed.",
    )

    missing_topics = sorted(set(contract_topics) - set(manifest_required_topics))
    extra_topics = sorted(set(manifest_required_topics) - set(contract_topics))
    add(
        rows,
        "manifest_required_topics_match_contract",
        "manifest",
        "The HIL manifest requires the same 13 preflight topics listed in the ROS2 topic contract.",
        len(manifest_required_topics) == 13 and not missing_topics and not extra_topics,
        f"manifest_topics={len(manifest_required_topics)}; missing={missing_topics}; extra={extra_topics}",
        "03_real_robot/hil_replay_manifest_template.yaml; 03_real_robot/ros2_topic_contract.csv",
        "Topic-name agreement is static; runtime topic discovery remains required in ROS2.",
    )

    missing_record = [topic for topic in contract_topics if topic not in rosbag_text]
    add(
        rows,
        "rosbag_record_command_covers_contract",
        "rosbag",
        "The multi-robot rosbag record command includes every required contract topic.",
        not missing_record,
        "missing=" + ("; ".join(missing_record) if missing_record else "none"),
        "03_real_robot/rosbag_commands.md; 03_real_robot/ros2_topic_contract.csv",
        "Command text coverage is not evidence that the topics were present in a recorded bag.",
    )

    add(
        rows,
        "rosbag_play_clock_replay",
        "rosbag",
        "HIL replay command uses ROS clock playback.",
        "ros2 bag play <bag_dir> --clock" in rosbag_text and "play_command: ros2 bag play <bag_dir> --clock" in manifest_text,
        "rosbag command and manifest both contain --clock",
        "03_real_robot/rosbag_commands.md; 03_real_robot/hil_replay_manifest_template.yaml",
        "Clock replay command presence does not prove node use_sim_time was enabled at runtime.",
    )

    forbidden_topics = ["/cmd_vel", "/drive", "/ackermann_cmd"]
    add(
        rows,
        "actuator_bridge_disabled_before_gate",
        "actuator_safety",
        "The manifest keeps the actuator bridge disabled through Stage C and lists physical command topics as forbidden before the gate.",
        "bridge_enabled: false" in manifest_text and all(topic in manifest_text for topic in forbidden_topics),
        f"forbidden_topics={forbidden_topics}",
        "03_real_robot/hil_replay_manifest_template.yaml",
        "This is an operator/process gate, not a physical interlock measurement.",
    )

    launch_terms = [
        "safety_state_topic",
        'safety_state = f"{prefix}/safety_state"',
        '"selected_leader_topic": selected_leader',
        '"results_csv_path": LaunchConfiguration("results_csv_path")',
    ]
    missing = missing_terms(launch_text, launch_terms)
    add(
        rows,
        "launch_wires_hil_logging_topics",
        "launch",
        "The launch file wires selected-leader, safety-state, and results-CSV topics needed for HIL replay logs.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/ros2_qgip_stack/launch/multi_robot_preflight.launch.py",
        "Launch wiring is static; ros2 launch execution remains a ROS2-environment gate.",
    )

    controller_terms = [
        'self.declare_parameter("safety_state_topic"',
        "self.safety_pub = self.create_publisher(String, safety_topic, 10)",
        "self.safety_pub.publish",
        "_safety_state_payload",
        "safety_stop",
        "reason",
    ]
    missing = missing_terms(controller_text, controller_terms)
    add(
        rows,
        "controller_publishes_safety_state",
        "node_source",
        "The velocity safety controller publishes a JSON safety-state stream alongside bounded shadow commands.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/ros2_qgip_stack/ros2_qgip_stack/velocity_safety_controller_node.py",
        "Static source inspection does not prove message publication rate or ROS2 serialization.",
    )

    supervisor_terms = [
        'self.declare_parameter("safety_state_topic"',
        "self.safety_sub = self.create_subscription(String, safety_topic, self._on_safety_state, 10)",
        "def _on_safety_state",
        "safety_state_count",
        "last_safety_reason",
    ]
    missing = missing_terms(supervisor_text, supervisor_terms)
    add(
        rows,
        "supervisor_consumes_safety_state",
        "node_source",
        "The trial supervisor consumes safety-state JSON and carries the safety-stop reason into status summaries.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/ros2_qgip_stack/ros2_qgip_stack/trial_supervisor_node.py",
        "Static source inspection does not prove online safety-supervisor behaviour.",
    )

    add(
        rows,
        "preflight_trial_stage_coverage",
        "trial_matrix",
        "The preflight trial matrix covers TF dry-run, offline bag replay, HIL shadow replay, and closed-loop gate stages.",
        counts == {"A": 1, "B": 5, "C": 4, "D": 2},
        f"stage_counts={counts}",
        "03_real_robot/preflight_trials_matrix.csv",
        "Planned trial coverage is not evidence that any trial has been executed.",
    )

    add(
        rows,
        "hil_shadow_repeat_budget",
        "trial_matrix",
        "Stage C HIL shadow replay includes 20 planned repeats across baseline, full, timeout-ablation, and full dropout-brake cases.",
        repeat_sum(preflight_rows, "C") == 20,
        f"stage_C_repeats={repeat_sum(preflight_rows, 'C')}",
        "03_real_robot/preflight_trials_matrix.csv",
        "Repeat budget is a protocol plan, not collected HIL evidence.",
    )

    add(
        rows,
        "closed_loop_gate_low_speed",
        "trial_matrix",
        "Stage D closed-loop gate remains low speed and follows HIL shadow evidence.",
        repeat_sum(preflight_rows, "D") == 20 and max_speed(preflight_rows, "D") <= 0.2,
        f"stage_D_repeats={repeat_sum(preflight_rows, 'D')}; stage_D_max_speed={max_speed(preflight_rows, 'D')}",
        "03_real_robot/preflight_trials_matrix.csv",
        "The row plan does not prove operator supervision or robot motion.",
    )

    timing_fields = {
        "latency_mean_ms",
        "latency_p95_ms",
        "latency_p99_ms",
        "watchdog_triggers",
        "frame_drop_count",
        "clock_drift_p95_ms",
        "cmd_vel_safe_age_p95_ms",
        "cpu_load_mean_percent",
        "gpu_load_mean_percent",
        "gpu_memory_peak_mb",
    }
    add(
        rows,
        "metric_schema_hil_timing_fields",
        "metrics",
        "Metric schema includes timing, frame-drop, watchdog, command-age, clock-drift, and CPU/GPU fields required before real-world claims.",
        timing_fields.issubset(metric_fields),
        f"missing={sorted(timing_fields - metric_fields)}",
        "03_real_robot/real_robot_metric_schema.csv",
        "Metric schema presence does not supply measured latency values.",
    )

    safety_fields = {"completion", "contact", "safety_stop", "near_miss", "lost", "min_distance_m", "min_ttc_s"}
    add(
        rows,
        "results_template_safety_fields",
        "metrics",
        "Results CSV template includes completion, contact, stop, near-miss, lost, distance, and TTC fields.",
        safety_fields.issubset(set(results_fields)),
        f"missing={sorted(safety_fields - set(results_fields))}",
        "03_real_robot/real_robot_results_template.csv",
        "Template fields do not prove filled per-trial results.",
    )

    run_manifest_terms = ["rosbag_path", "clock_sync_method", "cmd_vel_shadow_mode_first: true", "physical_estop_checked: false"]
    missing = missing_terms(run_manifest_text, run_manifest_terms)
    add(
        rows,
        "run_manifest_logging_and_safety_fields",
        "manifest",
        "Run-manifest template captures rosbag path, clock-sync method, and shadow-command-first safety gate.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/real_robot_run_manifest_template.yaml",
        "A blank manifest template must be filled during a real HIL or robot run.",
    )

    acceptance_terms = [
        "topic_completeness",
        "clock_sync",
        "shadow_command_only",
        "safety_state_logged",
        "command_safety",
        "timing_evidence",
        "contact_boundary",
        "archive_completeness",
    ]
    missing = missing_terms(manifest_text, acceptance_terms)
    add(
        rows,
        "acceptance_criteria_complete",
        "manifest",
        "HIL acceptance criteria cover topic completeness, clock sync, shadow command, safety-state logs, command safety, timing, contact boundary, and archival.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/hil_replay_manifest_template.yaml",
        "Acceptance criteria are predeclared; they do not certify that evidence exists yet.",
    )

    archive_terms = [
        "rosbag2 metadata.yaml",
        "ros2 bag info text export",
        "ros2 topic list text export",
        "ros2 topic hz text exports",
        "launch command and argument record",
        "real_robot_results_template-compatible CSV",
        "incident_report_template.md",
    ]
    missing = missing_terms(manifest_text, archive_terms)
    add(
        rows,
        "archive_artifact_list_complete",
        "manifest",
        "HIL manifest lists the minimum raw evidence artifacts required for later repository deposit.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/hil_replay_manifest_template.yaml",
        "Archive checklist is not a DOI-backed repository deposit.",
    )

    report_terms = ["Bridge it to the real", "shadow command", "/robot_1/cmd_vel_safe", "ros2 bag record", "ros2 bag play"]
    missing = missing_terms(rosbag_text, report_terms)
    add(
        rows,
        "rosbag_commands_preserve_shadow_boundary",
        "rosbag",
        "Rosbag command notes preserve a shadow-command-first boundary before physical base control.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/rosbag_commands.md",
        "Operator compliance still has to be observed during real HIL setup.",
    )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AuditRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])

    failed = [row for row in rows if row.status != "PASS"]
    report_lines = [
        "# ROS2/HIL Replay Manifest Audit Report",
        "",
        f"Rows: {len(rows)}",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "",
        "This audit strengthens the pre-real-robot evidence package by checking that HIL replay, rosbag logging, ROS clock playback, safety-state logging, and actuator-bridge disablement are specified before any Stage D physical-motion claim.",
        "",
        "It remains a pre-execution audit: it does not prove colcon build success, ros2 launch execution, live rosbag timing, HIL replay measurements, actuator bridge behavior, or physical robot motion.",
        "",
        "| status | check | evidence |",
        "|---|---|---|",
    ]
    report_lines.extend(f"| {row.status} | {row.check_id} | {row.evidence} |" for row in rows)
    if not failed:
        report_lines.extend(["", "All ROS2/HIL replay manifest audit checks passed."])
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
