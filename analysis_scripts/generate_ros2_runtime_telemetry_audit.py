#!/usr/bin/env python3
"""Audit runtime telemetry instrumentation before HIL or robot execution."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "03_real_robot"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"
MANUSCRIPT = ROOT / "01_manuscript" / "RA_L_extended_working.tex"
SCRIPT = ROOT / "05_analysis_scripts" / "summarize_real_robot_trials.py"
DRYRUN_SCRIPT = ROOT / "05_analysis_scripts" / "generate_ros2_runtime_telemetry_dryrun.py"

OUT_CSV = SOURCE / "ros2_runtime_telemetry_audit.csv"
OUT_REPORT = PACKAGE / "ros2_runtime_telemetry_audit_report_20260604.md"


@dataclass
class AuditRow:
    check_id: str
    layer: str
    requirement: str
    evidence: str
    status: str
    source_artifacts: str
    boundary: str


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


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


def missing_terms(body: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term not in body]


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)

    schema_path = REAL / "ros2_runtime_telemetry_schema.csv"
    manifest_path = REAL / "runtime_telemetry_manifest_template.yaml"
    metric_schema_path = REAL / "real_robot_metric_schema.csv"
    results_template_path = REAL / "real_robot_results_template.csv"
    hil_manifest_path = REAL / "hil_replay_manifest_template.yaml"
    run_manifest_path = REAL / "real_robot_run_manifest_template.yaml"

    telemetry_rows = read_csv(schema_path)
    metric_rows = read_csv(metric_schema_path)
    result_header = csv_header(results_template_path)
    manifest_text = text(manifest_path)
    hil_text = text(hil_manifest_path)
    run_text = text(run_manifest_path)
    manuscript_text = text(MANUSCRIPT)
    summarizer_text = text(SCRIPT)
    dryrun_script_text = text(DRYRUN_SCRIPT)
    dryrun_trace_path = SOURCE / "ros2_runtime_telemetry_dryrun_trace.csv"
    dryrun_summary_path = SOURCE / "ros2_runtime_telemetry_dryrun_summary.csv"
    dryrun_report_path = PACKAGE / "ros2_runtime_telemetry_dryrun_report_20260604.md"
    dryrun_trace_rows = read_csv(dryrun_trace_path) if dryrun_trace_path.exists() else []
    dryrun_summary_rows = read_csv(dryrun_summary_path) if dryrun_summary_path.exists() else []
    dryrun_report_text = text(dryrun_report_path) if dryrun_report_path.exists() else ""

    rows: list[AuditRow] = []

    files = [schema_path, manifest_path, metric_schema_path, results_template_path, hil_manifest_path, run_manifest_path]
    add(
        rows,
        "telemetry_asset_files_present",
        "files",
        "Runtime telemetry schema and manifest files are present and linked to existing run/HIL templates.",
        all(path.exists() and path.stat().st_size > 0 for path in files),
        "; ".join(f"{path.name}={path.exists()}" for path in files),
        "03_real_robot/ros2_runtime_telemetry_schema.csv; 03_real_robot/runtime_telemetry_manifest_template.yaml",
        "File presence does not prove telemetry was collected.",
    )

    telemetry_fields = {row["field"] for row in telemetry_rows}
    required_telemetry = {
        "trial_id",
        "ros_time_s",
        "wall_time_s",
        "latency_ms",
        "interarrival_ms",
        "frame_drop_count",
        "clock_drift_ms",
        "tf_age_ms",
        "selected_leader_age_ms",
        "cmd_vel_safe_age_ms",
        "watchdog_trigger",
        "watchdog_reason",
        "safety_state",
        "cpu_percent",
        "gpu_percent",
        "gpu_memory_mb",
        "rosbag_path",
        "telemetry_source",
    }
    add(
        rows,
        "telemetry_schema_required_fields",
        "schema",
        "Telemetry schema covers timestamps, message latency, frame drops, TF/leader/command age, watchdog, safety state, CPU/GPU load, and rosbag linkage.",
        len(telemetry_rows) == 24 and required_telemetry.issubset(telemetry_fields),
        f"rows={len(telemetry_rows)}; missing={sorted(required_telemetry - telemetry_fields)}",
        "03_real_robot/ros2_runtime_telemetry_schema.csv",
        "A schema does not create measured timing data.",
    )

    metric_fields = {row["field"] for row in metric_rows}
    required_summary = {
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
    required_metric_rows = [row for row in metric_rows if row["required"].lower() == "true"]
    add(
        rows,
        "metric_schema_runtime_summary_alignment",
        "metric_summary",
        "Real-robot metric schema contains runtime summary fields needed before embedded-feasibility or timing claims.",
        len(metric_rows) == 29 and len(required_metric_rows) == 28 and required_summary.issubset(metric_fields),
        f"metric_rows={len(metric_rows)}; required_rows={len(required_metric_rows)}; missing={sorted(required_summary - metric_fields)}",
        "03_real_robot/real_robot_metric_schema.csv",
        "Metric-schema readiness does not prove runtime latency or load.",
    )

    missing_result = [field for field in required_summary if field not in result_header]
    add(
        rows,
        "results_template_runtime_columns",
        "metric_summary",
        "Real-robot results template includes every runtime telemetry summary field.",
        not missing_result,
        "missing_result_fields=" + ("; ".join(sorted(missing_result)) if missing_result else "none"),
        "03_real_robot/real_robot_results_template.csv",
        "The example template row is not physical trial evidence.",
    )

    manifest_terms = [
        "ros2 bag record",
        "ros2 topic hz",
        "ros2 bag info",
        "tegrastats",
        "nvidia-smi",
        "collect_runtime_telemetry.py",
        "runtime_telemetry.csv",
        "latency_p95_ms_max",
        "latency_p99_ms_max",
        "clock_drift_p95_ms_max",
        "cmd_vel_safe_age_p95_ms_max",
        "frame_drop_count_max",
        "cpu_load_mean_percent_max",
        "gpu_load_mean_percent_max",
        "gpu_memory_peak_mb_max",
    ]
    missing = missing_terms(manifest_text, manifest_terms)
    add(
        rows,
        "runtime_manifest_collection_and_thresholds",
        "manifest",
        "Telemetry manifest specifies collection commands, runtime summary, timing thresholds, frame-drop gate, and CPU/GPU thresholds.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/runtime_telemetry_manifest_template.yaml",
        "Template thresholds remain TBD until the robot computer is selected.",
    )

    required_topics = [
        "/robot_1/qgip/selected_leader",
        "/robot_1/qgip/pop_state",
        "/robot_1/qgip/mpc_debug",
        "/robot_1/cmd_vel_safe",
        "/robot_1/safety_state",
    ]
    missing = missing_terms(manifest_text, required_topics)
    add(
        rows,
        "runtime_manifest_topic_coverage",
        "manifest",
        "Telemetry manifest records target selection, POP/NIS, MPC, safe-command, and safety-state topics.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/runtime_telemetry_manifest_template.yaml",
        "Topic coverage must still be verified from rosbag metadata.",
    )

    hil_terms = [
        "runtime_telemetry.csv",
        "ros2_runtime_telemetry_schema.csv",
        "frame_drop_count",
        "clock_drift_p95_ms",
        "cpu_load_mean_percent",
        "gpu_load_mean_percent",
        "gpu_memory_peak_mb",
    ]
    missing = missing_terms(hil_text, hil_terms)
    add(
        rows,
        "hil_manifest_runtime_telemetry_link",
        "hil_manifest",
        "HIL replay manifest links timing evidence to the runtime telemetry schema and summary fields.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/hil_replay_manifest_template.yaml",
        "A linked manifest still requires executed bag replay and telemetry extraction.",
    )

    run_terms = ["runtime_telemetry_csv_path", "runtime_telemetry_manifest_path", "metric_summary_csv_path"]
    missing = missing_terms(run_text, run_terms)
    add(
        rows,
        "run_manifest_runtime_telemetry_paths",
        "run_manifest",
        "Run manifest includes runtime telemetry CSV and manifest paths alongside the metric summary path.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/real_robot_run_manifest_template.yaml",
        "Path placeholders must be filled during actual trials.",
    )

    script_terms = [
        "latency_p99_ms",
        "frame_drop_count",
        "clock_drift_p95_ms",
        "cmd_vel_safe_age_p95_ms",
        "cpu_load_mean_percent",
        "gpu_load_mean_percent",
        "gpu_memory_peak_mb",
    ]
    missing = missing_terms(summarizer_text, script_terms)
    add(
        rows,
        "summarizer_runtime_metric_support",
        "analysis_script",
        "Real-robot summarizer aggregates latency, frame-drop, clock-drift, command-age, and CPU/GPU telemetry fields.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "05_analysis_scripts/summarize_real_robot_trials.py",
        "Aggregation support does not imply completed robot trials.",
    )

    dryrun_report_terms = [
        "ROS2 Runtime Telemetry Dry-Run Summary",
        "All runtime telemetry dry-run summary checks passed",
        "does not prove live ROS2 timing",
        "physical robot motion",
    ]
    missing = missing_terms(dryrun_report_text, dryrun_report_terms)
    add(
        rows,
        "runtime_dryrun_outputs_present",
        "analysis_script",
        "Runtime telemetry dry-run produces a schema-compatible trace, summary checks, and a non-claim report.",
        len(dryrun_trace_rows) == 320 and len(dryrun_summary_rows) == 16 and not missing,
        f"trace_rows={len(dryrun_trace_rows)}; summary_rows={len(dryrun_summary_rows)}; missing_report_terms={missing or 'none'}",
        "ros2_runtime_telemetry_dryrun_trace.csv; ros2_runtime_telemetry_dryrun_summary.csv; ros2_runtime_telemetry_dryrun_report_20260604.md",
        "Synthetic dry-run outputs validate the parser path only; they are not rosbag or robot data.",
    )

    dryrun_statuses = {row.get("status", "") for row in dryrun_summary_rows}
    dryrun_metrics = {row.get("metric", "") for row in dryrun_summary_rows}
    required_dryrun_metrics = {
        "latency_mean_ms",
        "latency_p95_ms",
        "latency_p99_ms",
        "frame_drop_count",
        "clock_drift_p95_ms",
        "cmd_vel_safe_age_p95_ms",
        "watchdog_triggers_explained",
        "cpu_load_mean_percent",
        "gpu_load_mean_percent",
        "gpu_memory_peak_mb",
        "synthetic_source_declared",
    }
    add(
        rows,
        "runtime_dryrun_summary_metrics_pass",
        "analysis_script",
        "Runtime telemetry dry-run summary exercises latency, frame-drop, watchdog, clock-drift, command-age, and CPU/GPU summary checks.",
        len(dryrun_summary_rows) == 16 and dryrun_statuses == {"PASS"} and required_dryrun_metrics.issubset(dryrun_metrics),
        f"statuses={','.join(sorted(dryrun_statuses)) or 'none'}; missing={sorted(required_dryrun_metrics - dryrun_metrics)}",
        "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_summary.csv",
        "Passing dry-run checks do not prove live ROS2 timing, HIL timing, or embedded feasibility.",
    )

    dryrun_script_terms = [
        "argparse",
        "schema_fields",
        "percentile",
        "synthetic_runtime_telemetry_dryrun",
        "watchdog_reason",
        "gpu_memory_peak_mb",
        "synthetic://runtime_telemetry_dryrun_no_bag",
    ]
    missing = missing_terms(dryrun_script_text, dryrun_script_terms)
    add(
        rows,
        "runtime_dryrun_script_parser_support",
        "analysis_script",
        "Runtime telemetry dry-run script supports both synthetic trace generation and CSV summary validation against schema fields.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "05_analysis_scripts/generate_ros2_runtime_telemetry_dryrun.py",
        "Parser support is not a substitute for actual rosbag extraction or robot-computer monitoring.",
    )

    manuscript_terms = [
        "latency mean/p95/p99",
        "frame drops",
        "watchdog triggers",
        "CPU/GPU load",
        "embedded feasibility is a validation target",
    ]
    missing = missing_terms(manuscript_text, manuscript_terms)
    add(
        rows,
        "manuscript_runtime_boundary_alignment",
        "manuscript",
        "Manuscript frames runtime telemetry as future validation rather than completed deployment evidence.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "01_manuscript/RA_L_extended_working.tex",
        "Narrative alignment is not runtime evidence.",
    )

    archive_terms = [
        "runtime_telemetry.csv",
        "real_robot_results_template-compatible metric summary",
        "rosbag2 metadata.yaml",
        "ros2 bag info text export",
        "ros2 topic hz text exports",
        "tegrastats or nvidia-smi system-load log",
        "safety_state extract with watchdog reasons",
        "incident report",
    ]
    missing = missing_terms(manifest_text, archive_terms)
    add(
        rows,
        "runtime_archive_completeness_requirements",
        "archive",
        "Telemetry manifest states the archive bundle required before timing or embedded-feasibility claims.",
        not missing,
        "missing=" + ("; ".join(missing) if missing else "none"),
        "03_real_robot/runtime_telemetry_manifest_template.yaml",
        "Archive requirements are not collected telemetry.",
    )

    boundary_terms = [
        "does not prove ROS2 launch success",
        "does not prove ROS2 build success",
        "does not contain completed physical robot trial data",
    ]
    linked_reports = "\n".join(
        text(path)
        for path in (
            PACKAGE / "real_robot_preflight_validation_report_20260604.md",
            PACKAGE / "pre_real_robot_gate_audit_report_20260604.md",
        )
        if path.exists()
    )
    linked_reports_lower = linked_reports.lower()
    add(
        rows,
        "runtime_boundary_nonclaim_terms",
        "boundary",
        "Existing pre-real reports retain build, launch, and physical-trial non-claim boundaries.",
        all(term.lower() in linked_reports_lower for term in boundary_terms),
        "boundary terms checked in pre-real reports",
        "real_robot_preflight_validation_report_20260604.md; pre_real_robot_gate_audit_report_20260604.md",
        "Boundary text prevents overclaiming but cannot replace runtime measurements.",
    )

    failed = [row for row in rows if row.status != "PASS"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AuditRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])

    report_lines = [
        "# ROS2 Runtime Telemetry Audit Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"Rows: {len(rows)}",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All ROS2 runtime telemetry audit checks passed." if not failed else "One or more runtime telemetry checks failed.",
        "",
        "## Scope",
        "",
        "The audit links runtime timing, frame-drop, watchdog, command-age, clock-drift, and CPU/GPU telemetry fields to the run manifest, HIL manifest, metric summary, analysis script, and manuscript boundary.",
        "",
        "It does not prove ROS2 launch success, HIL timing, actuator bridge behavior, embedded deployment feasibility, or physical robot motion. Those claims require filled telemetry CSVs, rosbag metadata, system-load logs, and operator-signed run manifests.",
        "",
        "| status | check | evidence |",
        "|---|---|---|",
    ]
    report_lines.extend(f"| {row.status} | {row.check_id} | {row.evidence} |" for row in rows)
    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
