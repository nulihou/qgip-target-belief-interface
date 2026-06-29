#!/usr/bin/env python3
"""Dry-run and summarize the ROS2 runtime telemetry CSV pipeline.

This script deliberately uses synthetic rows when no input CSV is supplied.  It
tests the parser, summary statistics, threshold bookkeeping, and non-claim
boundary before any HIL or physical robot telemetry is available.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "03_real_robot"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"

SCHEMA = REAL / "ros2_runtime_telemetry_schema.csv"
OUT_TRACE = SOURCE / "ros2_runtime_telemetry_dryrun_trace.csv"
OUT_SUMMARY = SOURCE / "ros2_runtime_telemetry_dryrun_summary.csv"
OUT_REPORT = PACKAGE / "ros2_runtime_telemetry_dryrun_report_20260604.md"

TRIAL_ID = "synthetic_runtime_telemetry_dryrun_001"
DT_S = 0.05
STEPS = 32
TOPICS = [
    "/tf",
    "/robot_1/odom",
    "/robot_1/detections_raw",
    "/robot_1/detections_faulty",
    "/robot_1/qgip/selected_leader",
    "/robot_1/qgip/pop_state",
    "/robot_1/qgip/mpc_debug",
    "/robot_1/cmd_vel_safe",
    "/robot_1/safety_state",
    "system_monitor",
]

DRYRUN_THRESHOLDS = {
    "latency_mean_ms": 18.0,
    "latency_p95_ms": 28.0,
    "latency_p99_ms": 32.0,
    "frame_drop_count": 0.0,
    "clock_drift_p95_ms": 4.0,
    "tf_age_p95_ms": 60.0,
    "selected_leader_age_p95_ms": 80.0,
    "cmd_vel_safe_age_p95_ms": 120.0,
    "cpu_load_mean_percent": 75.0,
    "gpu_load_mean_percent": 70.0,
    "gpu_memory_peak_mb": 1024.0,
}


@dataclass
class SummaryRow:
    check_id: str
    metric: str
    value: str
    acceptance: str
    status: str
    source_artifact: str
    boundary: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def schema_fields() -> list[str]:
    with SCHEMA.open("r", encoding="utf-8-sig", newline="") as handle:
        return [row["field"] for row in csv.DictReader(handle)]


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def fnum(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return math.nan


def synthetic_trace() -> list[dict[str, str]]:
    fields = schema_fields()
    rows: list[dict[str, str]] = []
    topic_indices = {topic: -1 for topic in TOPICS}
    previous_time = {topic: None for topic in TOPICS}

    for step in range(STEPS):
        ros_time_s = round(step * DT_S, 4)
        drift_ms = 1.0 + 0.06 * step + 0.35 * math.sin(step / 5.0)
        wall_time_s = ros_time_s + drift_ms / 1000.0
        fault_window = 13 <= step <= 15

        for topic_i, topic in enumerate(TOPICS):
            topic_indices[topic] += 1
            prev = previous_time[topic]
            interarrival_ms = 0.0 if prev is None else (ros_time_s - prev) * 1000.0
            previous_time[topic] = ros_time_s

            latency_ms = 7.5 + 0.30 * topic_i + 1.4 * math.sin((step + topic_i) / 4.0)
            if topic == "/robot_1/cmd_vel_safe" and fault_window:
                latency_ms += 3.0
            latency_ms = max(2.0, latency_ms)

            tf_age_ms = 18.0 + 0.7 * step + 1.2 * math.sin(step / 6.0)
            leader_age_ms = 24.0 + 0.9 * step + 1.5 * math.cos(step / 7.0)
            cmd_age_ms = 28.0 + 1.2 * step
            if fault_window:
                cmd_age_ms += 24.0

            watchdog = topic == "/robot_1/safety_state" and fault_window
            reason = "synthetic_fault_injection_hold" if watchdog else ""
            safety_state = {
                "safety_stop": bool(watchdog),
                "reason": reason or "nominal_shadow_runtime_dryrun",
            }
            cpu = 41.0 + 0.25 * step + 1.2 * math.sin(step / 3.5)
            gpu = 29.0 + 0.18 * step + 0.9 * math.cos(step / 4.5)
            gpu_memory = 612.0 + 2.2 * step + (12.0 if fault_window else 0.0)
            memory = 1880.0 + 5.0 * step

            row = {
                "trial_id": TRIAL_ID,
                "ros_time_s": f"{ros_time_s:.4f}",
                "wall_time_s": f"{wall_time_s:.6f}",
                "topic": topic,
                "message_stamp_s": f"{max(0.0, ros_time_s - latency_ms / 1000.0):.6f}",
                "receive_stamp_s": f"{ros_time_s:.6f}",
                "latency_ms": f"{latency_ms:.6f}",
                "interarrival_ms": f"{interarrival_ms:.6f}",
                "frame_index": str(topic_indices[topic]),
                "frame_drop_count": "0",
                "clock_drift_ms": f"{drift_ms:.6f}",
                "tf_age_ms": f"{tf_age_ms:.6f}",
                "selected_leader_age_ms": f"{leader_age_ms:.6f}",
                "cmd_vel_safe_age_ms": f"{cmd_age_ms:.6f}",
                "watchdog_trigger": str(watchdog).lower(),
                "watchdog_reason": reason,
                "safety_state": json.dumps(safety_state, separators=(",", ":")),
                "cpu_percent": f"{cpu:.6f}",
                "gpu_percent": f"{gpu:.6f}",
                "gpu_memory_mb": f"{gpu_memory:.6f}",
                "memory_mb": f"{memory:.6f}",
                "thermal_state": "nominal_no_throttle",
                "rosbag_path": "synthetic://runtime_telemetry_dryrun_no_bag",
                "telemetry_source": "synthetic_runtime_telemetry_dryrun",
            }
            rows.append({field: row[field] for field in fields})
    return rows


def write_trace(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = schema_fields()
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def add(
    rows: list[SummaryRow],
    check_id: str,
    metric: str,
    value: str,
    ok: bool,
    acceptance: str,
    boundary: str,
) -> None:
    rows.append(
        SummaryRow(
            check_id=check_id,
            metric=metric,
            value=value,
            acceptance=acceptance,
            status="PASS" if ok else "FAIL",
            source_artifact="ros2_runtime_telemetry_dryrun_trace.csv",
            boundary=boundary,
        )
    )


def monotonic_by_trial_topic(rows: list[dict[str, str]], field: str) -> tuple[bool, str]:
    previous: dict[tuple[str, str], float] = {}
    for row in rows:
        key = (row.get("trial_id", ""), row.get("topic", ""))
        value = fnum(row.get(field, ""))
        if math.isnan(value):
            return False, f"{field}=non_finite"
        if key in previous and value < previous[key] - 1e-9:
            return False, f"{field}=decrease at {key}"
        previous[key] = value
    return True, f"{field}=monotonic for {len(previous)} trial-topic streams"


def summarize(rows: list[dict[str, str]]) -> list[SummaryRow]:
    fields = schema_fields()
    summary: list[SummaryRow] = []
    header = set(rows[0].keys()) if rows else set()
    missing_fields = [field for field in fields if field not in header]
    add(
        summary,
        "schema_field_coverage",
        "schema_fields_present",
        f"{len(fields) - len(missing_fields)}/{len(fields)}",
        not missing_fields,
        "all fields from ros2_runtime_telemetry_schema.csv are present",
        "Schema coverage in a synthetic trace does not prove bag extraction.",
    )

    topic_set = {row.get("topic", "") for row in rows}
    missing_topics = [topic for topic in TOPICS if topic not in topic_set]
    add(
        summary,
        "required_topic_coverage",
        "topics_present",
        f"{len(TOPICS) - len(missing_topics)}/{len(TOPICS)}",
        not missing_topics,
        "all dry-run timing and system-monitor topics are represented",
        "Synthetic topic coverage does not prove runtime ROS2 publication.",
    )

    ros_ok, ros_detail = monotonic_by_trial_topic(rows, "ros_time_s")
    wall_ok, wall_detail = monotonic_by_trial_topic(rows, "wall_time_s")
    add(
        summary,
        "monotonic_timestamps",
        "ros_and_wall_time_monotonic",
        f"{ros_detail}; {wall_detail}",
        ros_ok and wall_ok,
        "timestamps must be monotonic by trial and topic",
        "Timestamp monotonicity in dry-run rows does not prove robot clock quality.",
    )

    latency = [fnum(row["latency_ms"]) for row in rows]
    latency_mean = sum(latency) / len(latency)
    latency_p95 = percentile(latency, 0.95)
    latency_p99 = percentile(latency, 0.99)
    for check_id, metric, value in (
        ("latency_mean_gate", "latency_mean_ms", latency_mean),
        ("latency_p95_gate", "latency_p95_ms", latency_p95),
        ("latency_p99_gate", "latency_p99_ms", latency_p99),
    ):
        threshold = DRYRUN_THRESHOLDS[metric]
        add(
            summary,
            check_id,
            metric,
            f"{value:.3f}",
            value <= threshold,
            f"dry-run parser QA threshold <= {threshold:.1f} ms",
            "Synthetic latency thresholds only test the summary path.",
        )

    frame_drops = max(int(fnum(row["frame_drop_count"])) for row in rows)
    add(
        summary,
        "frame_drop_gate",
        "frame_drop_count",
        str(frame_drops),
        frame_drops <= DRYRUN_THRESHOLDS["frame_drop_count"],
        "dry-run trace should contain no unexplained frame drops",
        "A zero dry-run drop count does not prove camera or detector runtime reliability.",
    )

    for check_id, metric, field, q in (
        ("clock_drift_p95_gate", "clock_drift_p95_ms", "clock_drift_ms", 0.95),
        ("tf_age_p95_gate", "tf_age_p95_ms", "tf_age_ms", 0.95),
        ("selected_leader_age_p95_gate", "selected_leader_age_p95_ms", "selected_leader_age_ms", 0.95),
        ("cmd_vel_safe_age_p95_gate", "cmd_vel_safe_age_p95_ms", "cmd_vel_safe_age_ms", 0.95),
    ):
        value = percentile([fnum(row[field]) for row in rows], q)
        threshold = DRYRUN_THRESHOLDS[metric]
        add(
            summary,
            check_id,
            metric,
            f"{value:.3f}",
            value <= threshold,
            f"dry-run parser QA threshold <= {threshold:.1f} ms",
            "Age/drift values are synthetic and only validate summary bookkeeping.",
        )

    watchdog_rows = [row for row in rows if row["watchdog_trigger"].lower() == "true"]
    explained = all(row["watchdog_reason"] and "synthetic_fault" in row["watchdog_reason"] for row in watchdog_rows)
    safety_states_ok = all("safety_stop" in row["safety_state"] and "reason" in row["safety_state"] for row in watchdog_rows)
    add(
        summary,
        "watchdog_reason_gate",
        "watchdog_triggers_explained",
        f"{len(watchdog_rows)}",
        bool(watchdog_rows) and explained and safety_states_ok,
        "synthetic watchdog triggers must include safety_state and reason",
        "Explained synthetic watchdog triggers do not prove robot safety supervision.",
    )

    cpu_mean = sum(fnum(row["cpu_percent"]) for row in rows) / len(rows)
    gpu_mean = sum(fnum(row["gpu_percent"]) for row in rows) / len(rows)
    gpu_mem_peak = max(fnum(row["gpu_memory_mb"]) for row in rows)
    for check_id, metric, value, unit in (
        ("cpu_load_mean_gate", "cpu_load_mean_percent", cpu_mean, "percent"),
        ("gpu_load_mean_gate", "gpu_load_mean_percent", gpu_mean, "percent"),
        ("gpu_memory_peak_gate", "gpu_memory_peak_mb", gpu_mem_peak, "MB"),
    ):
        threshold = DRYRUN_THRESHOLDS[metric]
        add(
            summary,
            check_id,
            metric,
            f"{value:.3f}",
            value <= threshold,
            f"dry-run parser QA threshold <= {threshold:.1f} {unit}",
            "System-load values are synthetic and do not prove embedded feasibility.",
        )

    sources = {row.get("telemetry_source", "") for row in rows}
    bags = {row.get("rosbag_path", "") for row in rows}
    add(
        summary,
        "source_boundary_gate",
        "synthetic_source_declared",
        f"sources={';'.join(sorted(sources))}; rosbag_paths={';'.join(sorted(bags))}",
        sources == {"synthetic_runtime_telemetry_dryrun"} and all(path.startswith("synthetic://") for path in bags),
        "dry-run rows must be visibly synthetic and non-bag evidence",
        "The declared synthetic source prevents treating these rows as HIL or robot measurements.",
    )
    return summary


def write_summary(rows: list[SummaryRow]) -> None:
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with OUT_SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SummaryRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])


def write_report(rows: list[SummaryRow], trace_rows: int, input_path: Path) -> None:
    failed = [row for row in rows if row.status != "PASS"]
    lines = [
        "# ROS2 Runtime Telemetry Dry-Run Summary, 2026-06-04",
        "",
        "## Decision",
        "",
        f"Trace rows: {trace_rows}",
        f"Summary checks: {len(rows)}",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All runtime telemetry dry-run summary checks passed." if not failed else "One or more runtime telemetry dry-run checks failed.",
        "",
        "## Scope",
        "",
        "This dry-run validates the CSV parser, summary-statistic calculations, frame-drop accounting, watchdog-reason bookkeeping, command-age tracking, clock-drift tracking, and CPU/GPU telemetry summary path.",
        "",
        f"Input trace: `{input_path.name}`.",
        "",
        "It does not prove live ROS2 timing, rosbag extraction correctness, HIL replay timing, actuator bridge behavior, embedded feasibility, deployment safety, or physical robot motion.",
        "",
        "| status | check | value | acceptance |",
        "|---|---|---:|---|",
    ]
    lines.extend(f"| {row.status} | {row.check_id} | {row.value} | {row.acceptance} |" for row in rows)
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=None, help="Optional runtime telemetry CSV to summarize.")
    parser.add_argument("--trace-out", type=Path, default=OUT_TRACE, help="Trace output path when generating synthetic rows.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    SOURCE.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)

    if args.input is None:
        trace = synthetic_trace()
        write_trace(trace, args.trace_out)
        input_path = args.trace_out
    else:
        input_path = args.input
        trace = read_csv(input_path)

    summary = summarize(trace)
    write_summary(summary)
    write_report(summary, len(trace), input_path)
    failed = [row for row in summary if row.status != "PASS"]
    print(args.trace_out if args.input is None else input_path)
    print(OUT_SUMMARY)
    print(OUT_REPORT)
    print(f"trace_rows={len(trace)} passed={len(summary) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
