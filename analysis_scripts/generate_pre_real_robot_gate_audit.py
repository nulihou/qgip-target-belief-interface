#!/usr/bin/env python3
"""Generate a pre-real-robot go/no-go gate audit from staged protocol artifacts."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL_ROBOT = ROOT / "03_real_robot"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
TABLES = ROOT / "08_paper_ready_outputs" / "tables"
PACKAGE = ROOT / "06_submission_package"
MANUSCRIPT = ROOT / "01_manuscript" / "manuscript_current.tex"

OUT_CSV = SOURCE / "pre_real_robot_gate_audit.csv"
OUT_TABLE = TABLES / "table_pre_real_robot_gate_audit.tex"
OUT_REPORT = PACKAGE / "pre_real_robot_gate_audit_report_20260604.md"


@dataclass
class GateRow:
    gate_id: str
    stage: str
    decision: str
    requirement: str
    evidence: str
    status: str
    source_artifacts: str
    next_required_evidence: str
    boundary: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def all_pass(path: Path, expected_rows: int | None = None) -> tuple[bool, str]:
    rows = read_csv(path) if path.exists() else []
    statuses = {row.get("status", "") for row in rows}
    count_ok = expected_rows is None or len(rows) == expected_rows
    ok = count_ok and statuses == {"PASS"}
    return ok, f"{path.name}={len(rows)} rows; statuses={','.join(sorted(statuses)) or 'none'}"


def has_terms(path: Path, terms: tuple[str, ...]) -> tuple[bool, str]:
    body = text(path) if path.exists() else ""
    missing = [term for term in terms if term not in body]
    return not missing, "missing=" + ("; ".join(missing) if missing else "none")


def csv_count(path: Path, expected: int) -> tuple[bool, str]:
    rows = read_csv(path) if path.exists() else []
    return len(rows) == expected, f"{path.name}={len(rows)} rows"


def csv_min_count(path: Path, minimum: int) -> tuple[bool, str]:
    rows = read_csv(path) if path.exists() else []
    return len(rows) >= minimum, f"{path.name}={len(rows)} rows; min={minimum}"


def add(
    rows: list[GateRow],
    gate_id: str,
    stage: str,
    decision: str,
    requirement: str,
    ok: bool,
    evidence: str,
    source_artifacts: str,
    next_required_evidence: str,
    boundary: str,
) -> None:
    rows.append(
        GateRow(
            gate_id=gate_id,
            stage=stage,
            decision=decision,
            requirement=requirement,
            evidence=evidence,
            status="PASS" if ok else "FAIL",
            source_artifacts=source_artifacts,
            next_required_evidence=next_required_evidence,
            boundary=boundary,
        )
    )


def esc(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}")
        .replace("_", "\\_")
        .replace("%", "\\%")
        .replace("&", "\\&")
        .replace("#", "\\#")
    )


def build_rows() -> list[GateRow]:
    rows: list[GateRow] = []

    checklist = REAL_ROBOT / "pre_real_robot_checklist.md"
    ok, evidence = has_terms(
        checklist,
        ("ROS_DOMAIN_ID", "/robot_1", "/robot_2", "/robot_3", "base_link", "Clocks", "rosbag2"),
    )
    add(
        rows,
        "A_network_namespace_clock_checklist",
        "A network/TF dry run",
        "READY_FOR_STAGE_A_EXECUTION",
        "Operator checklist covers ROS domain, namespaces, TF frames, logger visibility, clocks, and storage.",
        ok,
        evidence,
        "03_real_robot/pre_real_robot_checklist.md",
        "Signed Stage A checklist plus `ros2 topic list` and `tf2_echo` logs.",
        "Checklist readiness is not evidence that robots have been powered or synchronized.",
    )

    ok, evidence = has_terms(
        REAL_ROBOT / "multi_ros2_car_preflight_plan.md",
        ("Stage A: Network and TF Dry Run", "tf2_echo", "at least 10 Hz", "no duplicated frame ids"),
    )
    add(
        rows,
        "A_tf_pass_criteria",
        "A network/TF dry run",
        "READY_FOR_STAGE_A_EXECUTION",
        "Stage A defines executable TF commands and pass criteria.",
        ok,
        evidence,
        "03_real_robot/multi_ros2_car_preflight_plan.md",
        "Recorded TF update-rate evidence for follower-leader and follower-distractor transforms.",
        "Documented commands do not prove runtime TF health.",
    )

    ok, evidence = csv_count(REAL_ROBOT / "ros2_topic_contract.csv", 13)
    topics = read_csv(REAL_ROBOT / "ros2_topic_contract.csv") if (REAL_ROBOT / "ros2_topic_contract.csv").exists() else []
    topic_set = {row.get("topic", "") for row in topics}
    required_topics = {
        "/tf",
        "/tf_static",
        "/robot_1/odom",
        "/robot_2/odom",
        "/robot_3/odom",
        "/robot_1/detections_raw",
        "/robot_1/detections_faulty",
        "/robot_1/qgip/selected_leader",
        "/robot_1/qgip/pop_state",
        "/robot_1/qgip/mpc_debug",
        "/robot_1/qgip/trial_status",
        "/robot_1/cmd_vel_safe",
        "/robot_1/safety_state",
    }
    ok = ok and required_topics.issubset(topic_set) and all(row.get("log_in_bag") == "true" for row in topics)
    add(
        rows,
        "A_topic_contract_logging",
        "A network/TF dry run",
        "READY_FOR_STAGE_A_EXECUTION",
        "Topic contract covers TF, odometry, detections, POP/NIS state, controller debug, trial status, and safe command logging.",
        ok,
        evidence + f"; missing_topics={sorted(required_topics - topic_set)}",
        "03_real_robot/ros2_topic_contract.csv",
        "A rosbag showing all required topics at the minimum rates.",
        "Topic contract presence does not prove publishers exist at runtime.",
    )

    ok, evidence = all_pass(SOURCE / "ros2_workspace_ci_audit.csv", 11)
    add(
        rows,
        "A_ros2_workspace_ci_assets",
        "A network/TF dry run",
        "READY_FOR_ROS2_WORKSPACE_CI",
        "ROS2 workspace CI assets cover colcon build/test commands, launch-argument parsing, pure-core pytest, and no-actuator-bridge safety boundaries.",
        ok,
        evidence,
        "ros2_workspace_ci_audit.csv; ros2_workspace_ci_audit_report_20260604.md; ros2_workspace_ci_manifest.yaml; run_ros2_workspace_preflight.sh",
        "Executed colcon build/test logs, launch --show-args output, and archived pytest output from a ROS2 workspace.",
        "CI asset audit includes local pure-core pytest but does not prove colcon build/test execution in ROS2.",
    )

    ok, evidence = all_pass(SOURCE / "real_robot_preflight_validation.csv", 41)
    add(
        rows,
        "B_static_preflight_validation",
        "B detection/fault dry run",
        "READY_FOR_STAGE_B_EXECUTION",
        "Offline static validator passes package structure, launch, parameter, topic, JSON, metric, manifest, and documentation checks.",
        ok,
        evidence,
        "08_paper_ready_outputs/source_data/real_robot_preflight_validation.csv",
        "Stage B rosbag containing raw/faulty detections and shadow safe commands.",
        "Static validation does not prove ROS2 build, launch, rosbag, timing, or robot motion.",
    )

    ok, evidence = has_terms(
        REAL_ROBOT / "rosbag_commands.md",
        (
            "Multi-Robot Preflight Logging",
            "/robot_1/detections_raw",
            "/robot_1/detections_faulty",
            "/robot_1/qgip/pop_state",
            "/robot_1/qgip/mpc_debug",
            "/robot_1/qgip/trial_status",
            "/robot_1/cmd_vel_safe",
        ),
    )
    add(
        rows,
        "B_rosbag_topic_plan",
        "B detection/fault dry run",
        "READY_FOR_STAGE_B_EXECUTION",
        "ROS2 bag command records the complete preflight topic bundle.",
        ok,
        evidence,
        "03_real_robot/rosbag_commands.md",
        "Completed ros2 bag record directory and metadata.yaml for each Stage B condition.",
        "Recording command text is not recorded data.",
    )

    ok, evidence = all_pass(SOURCE / "real_robot_offline_dryrun_summary.csv", 12)
    trace_ok, trace_evidence = csv_count(SOURCE / "real_robot_offline_dryrun_trace.csv", 90)
    fig_ok, fig_evidence = csv_min_count(SOURCE / "fig13_offline_dryrun_contract_timeline_v2_source_data.csv", 90)
    add(
        rows,
        "B_offline_behavior_dryrun",
        "B detection/fault dry run",
        "PASS_PREPARED",
        "ROS2-less dry run exercises selected-leader continuity, software dropout, GHOST/LOST, hard NIS gate, and safety-stop proxy.",
        ok and trace_ok and fig_ok,
        f"{evidence}; {trace_evidence}; {fig_evidence}",
        "real_robot_offline_dryrun_summary.csv; real_robot_offline_dryrun_trace.csv; fig13_offline_dryrun_contract_timeline_v2_source_data.csv",
        "Stage B ROS2 bag with the same event sequence and topic timestamps.",
        "Desktop dry run is not a ROS2 launch or hardware timing result.",
    )

    ok, evidence = all_pass(SOURCE / "real_robot_software_smoke_test.csv", 17)
    add(
        rows,
        "B_executable_software_smoke_test",
        "B detection/fault dry run",
        "PASS_PREPARED",
        "Executable pure-Python smoke test covers POP/NIS core parity, fault injection, JSON payload contracts, and controller-proxy invariants.",
        ok,
        evidence,
        "real_robot_software_smoke_test.csv; real_robot_software_smoke_test_report_20260604.md",
        "Run the same core path inside ROS2 nodes with bagged topic timestamps and HIL shadow-control logs.",
        "Software smoke testing does not prove ROS2 node launch, DDS transport, timing latency, or robot actuation.",
    )

    ok, evidence = has_terms(
        REAL_ROBOT / "multi_ros2_car_preflight_plan.md",
        ("Stage C: HIL Shadow Control", "ros2 bag play", "p95 command latency below 100 ms", "same bags"),
    )
    add(
        rows,
        "C_hil_shadow_protocol",
        "C HIL shadow control",
        "READY_FOR_STAGE_C_EXECUTION",
        "HIL protocol requires bag replay, actuator bridge disabled, latency logging, and paired method comparison.",
        ok,
        evidence,
        "03_real_robot/multi_ros2_car_preflight_plan.md",
        "Per-frame HIL CSVs with command latency, stale-command checks, and paired method outputs.",
        "HIL protocol text does not prove real-time execution.",
    )

    ok, evidence = has_terms(
        REAL_ROBOT / "baseline_launch_profiles.md",
        ("Full POP/NIS", "Std-KF-like", "No-POP", "same rosbag"),
    )
    add(
        rows,
        "C_baseline_replay_profiles",
        "C HIL shadow control",
        "READY_FOR_STAGE_C_EXECUTION",
        "Baseline launch profiles support paired replay of proposed and comparator policies on the same bag.",
        ok,
        evidence,
        "03_real_robot/baseline_launch_profiles.md",
        "A replay manifest linking each bag to each method profile and output CSV.",
        "Profile definitions do not prove comparator parity until replayed.",
    )

    ok, evidence = csv_count(REAL_ROBOT / "preflight_trials_matrix.csv", 12)
    matrix_rows = read_csv(REAL_ROBOT / "preflight_trials_matrix.csv") if (REAL_ROBOT / "preflight_trials_matrix.csv").exists() else []
    stages = {row.get("stage", "") for row in matrix_rows}
    ok = ok and {"A", "B", "C", "D"}.issubset(stages)
    add(
        rows,
        "C_preflight_matrix_stage_coverage",
        "C HIL shadow control",
        "READY_FOR_STAGE_C_EXECUTION",
        "Preflight trial matrix covers stages A-D with method and fault diversity.",
        ok,
        evidence + f"; stages={','.join(sorted(stages))}",
        "03_real_robot/preflight_trials_matrix.csv",
        "Completed rows with bag paths, metric summaries, and operator sign-off.",
        "Planned matrix rows are not completed trials.",
    )

    ok, evidence = all_pass(SOURCE / "ros2_hil_replay_manifest_audit.csv", 17)
    add(
        rows,
        "C_hil_replay_manifest_audit",
        "C HIL shadow control",
        "READY_FOR_STAGE_C_EXECUTION",
        "Machine-readable HIL replay manifest audit covers rosbag topics, ROS clock replay, safety-state logging, and disabled actuator bridge before Stage D.",
        ok,
        evidence,
        "ros2_hil_replay_manifest_audit.csv; ros2_hil_replay_manifest_audit_report_20260604.md; hil_replay_manifest_template.yaml",
        "Filled HIL replay manifest, ros2 bag info, topic hz logs, and latency output CSVs from an executed Stage C replay.",
        "Manifest audit is pre-execution evidence; it does not prove live HIL timing or physical robot motion.",
    )

    ok, evidence = all_pass(SOURCE / "ros2_runtime_telemetry_audit.csv", 15)
    add(
        rows,
        "C_runtime_telemetry_schema_audit",
        "C HIL shadow control",
        "READY_FOR_TIMING_INSTRUMENTATION",
        "Runtime telemetry audit covers latency mean/p95/p99, frame drops, watchdog reasons, command age, clock drift, and CPU/GPU load before embedded-feasibility or HIL timing claims.",
        ok,
        evidence,
        "ros2_runtime_telemetry_audit.csv; ros2_runtime_telemetry_audit_report_20260604.md; ros2_runtime_telemetry_schema.csv; runtime_telemetry_manifest_template.yaml",
        "Filled runtime telemetry CSV, rosbag metadata, topic hz logs, system-load logs, and robot-specific threshold manifest from executed Stage C-D runs.",
        "Telemetry instrumentation readiness does not prove HIL timing, embedded feasibility, actuator bridge behavior, or physical robot motion.",
    )

    ok, evidence = all_pass(SOURCE / "ros2_runtime_telemetry_dryrun_summary.csv", 16)
    report_ok, report_evidence = has_terms(
        PACKAGE / "ros2_runtime_telemetry_dryrun_report_20260604.md",
        ("All runtime telemetry dry-run summary checks passed", "does not prove live ROS2 timing", "physical robot motion"),
    )
    add(
        rows,
        "C_runtime_telemetry_parser_dryrun",
        "C HIL shadow control",
        "READY_FOR_TELEMETRY_SUMMARY_QA",
        "Runtime telemetry dry-run validates the CSV parser and summary chain for latency, frame-drop, watchdog, command-age, clock-drift, and CPU/GPU fields before real logs are collected.",
        ok and report_ok,
        f"{evidence}; {report_evidence}",
        "ros2_runtime_telemetry_dryrun_trace.csv; ros2_runtime_telemetry_dryrun_summary.csv; ros2_runtime_telemetry_dryrun_report_20260604.md",
        "Execute the same summary path on actual rosbag-derived telemetry CSVs and archive robot-computer system-load logs.",
        "Synthetic parser QA does not prove live ROS2 timing, HIL timing, embedded feasibility, actuator bridge behavior, or physical robot motion.",
    )

    ok, evidence = has_terms(
        REAL_ROBOT / "multi_ros2_car_preflight_plan.md",
        ("Stage D: Low-Speed Closed-Loop Gate", "/robot_1/cmd_vel_safe -> safety bridge", "distance below 0.25 m", "estimated TTC below 0.8 s", "manual E-stop"),
    )
    add(
        rows,
        "D_closed_loop_gate_abort_rules",
        "D low-speed closed-loop gate",
        "READY_FOR_OPERATOR_REVIEW",
        "Closed-loop gate defines a shadow-to-bridge transition and explicit abort rules.",
        ok,
        evidence,
        "03_real_robot/multi_ros2_car_preflight_plan.md",
        "Signed operator approval, E-stop test evidence, and first 0.2 m/s closed-loop rosbag.",
        "Abort rules must be executed by operators and supervisors before physical claims.",
    )

    manifest = REAL_ROBOT / "real_robot_run_manifest_template.yaml"
    ok, evidence = has_terms(
        manifest,
        (
            "physical_estop_checked",
            "cmd_vel_shadow_mode_first",
            "max_speed_mps",
            "min_headway_abort_m",
            "min_ttc_abort_s",
            "operator_line_of_sight",
            "test_area_clear",
        ),
    )
    add(
        rows,
        "D_manifest_safety_gate_fields",
        "D low-speed closed-loop gate",
        "READY_FOR_OPERATOR_REVIEW",
        "Run manifest requires E-stop, shadow-mode, speed, headway/TTC abort, line-of-sight, and clear-area fields.",
        ok,
        evidence,
        "03_real_robot/real_robot_run_manifest_template.yaml",
        "Filled manifest per trial with non-empty safety gate values.",
        "Blank template fields do not prove the safety gate was satisfied.",
    )

    ok, evidence = has_terms(
        REAL_ROBOT / "incident_report_template.md",
        ("autonomous abort", "abort reason", "rosbag", "CSV evidence"),
    )
    add(
        rows,
        "D_incident_and_abort_template",
        "D low-speed closed-loop gate",
        "READY_FOR_OPERATOR_REVIEW",
        "Incident template requires autonomous abort and evidence links for post-run review.",
        ok,
        evidence,
        "03_real_robot/incident_report_template.md",
        "Incident report for any abort, contact, near-miss, or operator stop.",
        "Template readiness does not imply that an incident occurred or was resolved.",
    )

    ok, evidence = csv_count(REAL_ROBOT / "real_robot_metric_schema.csv", 29)
    template_ok, template_evidence = csv_count(REAL_ROBOT / "real_robot_results_template.csv", 1)
    add(
        rows,
        "E_metric_schema_and_template",
        "E publication evidence package",
        "PASS_PREPARED",
        "Metric schema and result template cover trial identity, safety, tracking, timing, and reporting fields.",
        ok and template_ok,
        f"{evidence}; {template_evidence}",
        "03_real_robot/real_robot_metric_schema.csv; 03_real_robot/real_robot_results_template.csv",
        "Completed per-trial CSVs plus aggregate summary from real robot or HIL replay.",
        "Schema and template rows are not measured results.",
    )

    publication_rows = read_csv(SOURCE / "publication_figure_qa.csv") if (SOURCE / "publication_figure_qa.csv").exists() else []
    fig13_rows = [row for row in publication_rows if row.get("figure_id") == "fig13_offline_dryrun_contract_timeline_v2"]
    fig13_statuses = {row.get("status", "") for row in fig13_rows}
    ok = len(fig13_rows) == 9 and fig13_statuses == {"PASS"}
    evidence = f"fig13 publication QA rows={len(fig13_rows)}; statuses={','.join(sorted(fig13_statuses)) or 'none'}"
    access_ok, access_evidence = csv_min_count(SOURCE / "figure_accessibility_metrics.csv", 30)
    add(
        rows,
        "E_figure_qa_for_preflight_diagnostic",
        "E publication evidence package",
        "PASS_PREPARED",
        "The offline dry-run figure is included in the publication-figure and accessibility QA bundle.",
        ok and access_ok,
        f"{evidence}; {access_evidence}",
        "publication_figure_qa.csv; figure_accessibility_metrics.csv",
        "Replace or supplement offline figure with HIL/robot time-series figure after Stage C-D data are collected.",
        "Figure QA proves export quality, not physical validation.",
    )

    ok, evidence = csv_min_count(SOURCE / "source_data_provenance_audit.csv", 96)
    deposit_ok, deposit_evidence = csv_min_count(PACKAGE / "repository_deposit_manifest_20260603.csv", 223)
    add(
        rows,
        "E_provenance_and_deposit_readiness",
        "E publication evidence package",
        "PASS_PREPARED",
        "Source-data provenance and local deposit manifest are internally consistent for the current simulation-first package.",
        ok and deposit_ok,
        f"{evidence}; {deposit_evidence}",
        "source_data_provenance_audit.csv; repository_deposit_manifest_20260603.csv",
        "DOI-backed public repository with final metadata, licence, and reviewer link.",
        "Local manifest is not a public DOI-backed repository.",
    )

    ok, evidence = csv_min_count(PACKAGE / "reproducibility_command_manifest_20260604.csv", 30)
    add(
        rows,
        "E_reproducibility_command_map",
        "E publication evidence package",
        "PASS_PREPARED",
        "Command manifest lists the current regeneration, audit, deposit, and verification commands.",
        ok,
        evidence,
        "06_submission_package/reproducibility_command_manifest_20260604.csv",
        "Rerun on a clean machine or CI container once repository metadata are final.",
        "Command listing is a replay guide, not an executed independent reproduction.",
    )

    ok, evidence = has_terms(
        MANUSCRIPT,
        ("CARLA-first", "not included in the present evaluation", "not a ROS2 launch, HIL timing, rosbag, or physical-robot result"),
    )
    add(
        rows,
        "F_manuscript_nonclaim_boundary",
        "F negative-claim boundary",
        "NO_PHYSICAL_CLAIM",
        "Manuscript explicitly states the simulation-only and ROS2-less dry-run boundaries.",
        ok,
        evidence,
        "01_manuscript/manuscript_current.tex",
        "Physical robot evidence can be claimed only after Stage D trial bags, manifests, metrics, and incident reports exist.",
        "This gate intentionally prevents overclaiming.",
    )

    ok, evidence = has_terms(
        PACKAGE / "full_goal_completion_audit_20260603.md",
        ("Remaining Non-Completion Items", "DOI-backed data/code record", "physical"),
    )
    add(
        rows,
        "F_goal_audit_remaining_items",
        "F negative-claim boundary",
        "NO_PHYSICAL_CLAIM",
        "Goal-level audit retains DOI-backed repository and physical validation as remaining non-completion items.",
        ok,
        evidence,
        "06_submission_package/full_goal_completion_audit_20260603.md",
        "Public DOI record and completed audited robot trials.",
        "The full user objective remains incomplete until those external artifacts exist.",
    )

    return rows


def write_csv(rows: list[GateRow]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(GateRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])


def stage_summary(rows: list[GateRow]) -> list[dict[str, str]]:
    specs = [
        ("A network/TF dry run", "Network/TF", "Topic discovery and TF health"),
        ("B detection/fault dry run", "Detection/fault", "Shadow command and software faults"),
        ("C HIL shadow control", "HIL shadow", "Bag replay without actuator bridge"),
        ("D low-speed closed-loop gate", "Closed-loop gate", "0.2 m/s operator-supervised bridge"),
        ("E publication evidence package", "Evidence package", "Metrics, figures, provenance, deposit draft"),
        ("F negative-claim boundary", "Claim boundary", "Explicit no-physical-claim language"),
    ]
    output: list[dict[str, str]] = []
    for stage, label, purpose in specs:
        stage_rows = [row for row in rows if row.stage == stage]
        failed = [row for row in stage_rows if row.status != "PASS"]
        decisions = sorted({row.decision for row in stage_rows})
        next_items = sorted({row.next_required_evidence for row in stage_rows})
        if failed:
            decision_display = "FAIL"
        elif "NO_PHYSICAL_CLAIM" in decisions:
            decision_display = "No physical claim"
        else:
            decision_display = "Prepared"
        output.append(
            {
                "stage": label,
                "purpose": purpose,
                "decision": decision_display,
                "gate_count": f"{len(stage_rows) - len(failed)}/{len(stage_rows)}",
                "decision_labels": "; ".join(decisions),
                "next_evidence": next_items[0] if next_items else "",
            }
        )
    return output


def write_table(rows: list[GateRow]) -> None:
    summary = stage_summary(rows)
    lines = [
        "% Auto-generated by generate_pre_real_robot_gate_audit.py",
        "\\setlength{\\tabcolsep}{2pt}",
        "\\renewcommand{\\arraystretch}{1.05}",
        "\\begin{tabular}{@{}>{\\raggedright\\arraybackslash}p{0.15\\linewidth} >{\\raggedright\\arraybackslash}p{0.20\\linewidth} >{\\raggedright\\arraybackslash}p{0.13\\linewidth} >{\\raggedright\\arraybackslash}p{0.18\\linewidth} >{\\raggedright\\arraybackslash}p{0.25\\linewidth}@{}}",
        "\\toprule",
        "\\textbf{Gate} & \\textbf{Purpose} & \\textbf{Checks} & \\textbf{Decision} & \\textbf{Next evidence required} \\\\",
        "\\midrule",
    ]
    for row in summary:
        lines.append(
            f"{esc(row['stage'])} & {esc(row['purpose'])} & {esc(row['gate_count'])} & {esc(row['decision'])} & {esc(row['next_evidence'])} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    OUT_TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_report(rows: list[GateRow]) -> None:
    failed = [row for row in rows if row.status != "PASS"]
    summary = stage_summary(rows)
    summary_lines = "\n".join(
        f"- {row['stage']}: {row['gate_count']} checks, {row['decision_labels']}" for row in summary
    )
    OUT_REPORT.write_text(
        f"""# Pre-Real-Robot Gate Audit Report, 2026-06-04

## Decision

The pre-real-robot gate audit checks {len(rows)} network/TF, detection/fault, HIL shadow-control, low-speed closed-loop, publication-evidence, and negative-claim gates.

Passed: {len(rows) - len(failed)}
Failed: {len(failed)}

All audited pre-real-robot gates are prepared for the next supervised execution stage. The package remains below ROS2 build/launch evidence, rosbag evidence, timing evidence, and physical robot validation.

## Gate Summary

{summary_lines}

## Boundary

This audit is a go/no-go preparation layer. It does not prove ROS2 build success, does not prove ros2 launch success, does not contain a rosbag, does not measure real-time latency, does not command hardware, and does not contain completed physical robot trial data. Physical claims require filled run manifests, bags, per-frame CSVs, metric summaries, videos, and incident reports collected under operator supervision.
""",
        encoding="utf-8",
        newline="\n",
    )
    if failed:
        with OUT_REPORT.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n## Failed Gates\n\n")
            for row in failed:
                handle.write(f"- `{row.gate_id}`: {row.evidence}\n")


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)
    rows = build_rows()
    write_csv(rows)
    write_table(rows)
    write_report(rows)
    failed = [row for row in rows if row.status != "PASS"]
    print(OUT_CSV)
    print(OUT_TABLE)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
