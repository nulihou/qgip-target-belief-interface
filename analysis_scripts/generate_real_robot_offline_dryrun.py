#!/usr/bin/env python3
"""Run a deterministic ROS2-less preflight dry run for the real-robot stack."""

from __future__ import annotations

import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STACK = ROOT / "03_real_robot" / "ros2_qgip_stack"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"

sys.path.insert(0, str(STACK))

from ros2_qgip_stack.fault_injection_core import Detection, DetectionFaultInjector, FaultConfig  # noqa: E402
from ros2_qgip_stack.json_contract import dumps_payload, loads_payload, normalize_detections, select_front_leader  # noqa: E402
from ros2_qgip_stack.pop_nis_kf_core import NISGatedPOP, POPConfig, TrackMode  # noqa: E402


OUT_TRACE = SOURCE / "real_robot_offline_dryrun_trace.csv"
OUT_SUMMARY = SOURCE / "real_robot_offline_dryrun_summary.csv"
OUT_REPORT = PACKAGE / "real_robot_offline_dryrun_report_20260604.md"

DT = 0.05
STEPS = 90


@dataclass
class SummaryRow:
    check_id: str
    requirement: str
    actual: str
    status: str
    source_artifact: str
    boundary: str


def make_raw_detections(stamp_s: float) -> list[Detection]:
    leader_x = 1.05 + 0.10 * stamp_s
    return [
        Detection("robot_2", x=leader_x, y=0.02 * math.sin(stamp_s), vx=0.10, vy=0.0, confidence=0.95, stamp_s=stamp_s),
        Detection("robot_3", x=leader_x + 0.10, y=0.85, vx=0.08, vy=0.0, confidence=0.72, class_name="distractor", stamp_s=stamp_s),
    ]


def detection_to_dict(det: Detection) -> dict[str, float | str]:
    return {
        "id": det.object_id,
        "class_name": det.class_name,
        "x": det.x,
        "y": det.y,
        "vx": det.vx,
        "vy": det.vy,
        "confidence": det.confidence,
        "stamp_s": det.stamp_s,
    }


def measurement_from_detection(det: dict[str, object]) -> np.ndarray:
    return np.array([float(det["x"]), float(det["y"]), float(det["vx"]), float(det["vy"])], dtype=float)


def controller_debug(state, stamp_s: float) -> dict[str, float | str | bool | None]:
    x = float(state.x[0])
    y = float(state.x[1])
    vx = float(state.x[2])
    distance = math.hypot(x, y)
    desired_gap = 0.35
    mode = state.mode.value if hasattr(state.mode, "value") else str(state.mode)
    ttc_s = distance / abs(vx) if vx < -1e-3 and distance > 0.0 else None
    stop = mode == TrackMode.LOST.value or x <= 0.25
    if stop:
        speed = 0.0
        reason = "lost_or_unsafe"
    else:
        scale = 0.35 if mode == TrackMode.GHOST.value else 0.70 if mode == TrackMode.DEGRADED.value else 1.0
        speed = max(0.0, min(0.50, scale * (0.80 * (x - desired_gap) + 0.20 * vx)))
        reason = "tracking"
    return {
        "stamp_s": stamp_s,
        "selected_speed_mps": speed,
        "selected_v_mps": speed,
        "headway_m": max(0.0, x),
        "ttc_s": ttc_s,
        "safety_stop": stop,
        "reason": reason,
    }


def scenario_fault_tag(stamp_s: float) -> str:
    if 0.80 <= stamp_s < 2.45:
        return "software_dropout"
    if 2.55 <= stamp_s < 2.65:
        return "high_nis_recovery_offset"
    return "none"


def run_trace() -> list[dict[str, str]]:
    SOURCE.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)

    injector = DetectionFaultInjector(FaultConfig(position_noise_std_m=0.005, random_seed=13))
    tracker = NISGatedPOP(
        POPConfig(
            dt=DT,
            confidence_threshold=0.5,
            high_confidence_threshold=0.85,
            nis_soft_threshold=12.0,
            nis_hard_threshold=20.0,
            r_inflation=10.0,
            ghost_horizon_s=1.0,
            lost_timeout_s=1.5,
        )
    )
    initialized = False
    selected_leader_id = ""
    trace: list[dict[str, str]] = []

    for step in range(STEPS):
        stamp_s = round(step * DT, 4)
        raw = make_raw_detections(stamp_s)
        raw_payload = {"stamp_s": stamp_s, "detections": [detection_to_dict(det) for det in raw]}
        raw_detections = normalize_detections(loads_payload(dumps_payload(raw_payload)))
        selected = select_front_leader(raw_detections, min_confidence=0.5, max_abs_y_m=1.5, front_only=True)
        selected_payload = {
            "stamp_s": stamp_s,
            "leader_id": selected["id"] if selected else "",
            "confidence": selected["confidence"] if selected else 0.0,
            "rank": 1 if selected else 0,
            "candidate_count": len(raw_detections),
        }
        selected_leader_id = str(selected_payload["leader_id"])

        fault_tag = scenario_fault_tag(stamp_s)
        if fault_tag == "software_dropout":
            faulted = []
        else:
            faulted = injector.apply(raw, stamp_s)
            if fault_tag == "high_nis_recovery_offset":
                for det in faulted:
                    if det.object_id == selected_leader_id:
                        det.x += 1.20
                        det.confidence = 0.96

        fault_payload = {"stamp_s": stamp_s, "detections": [detection_to_dict(det) for det in faulted]}
        faulted_detections = normalize_detections(loads_payload(dumps_payload(fault_payload)))
        measurement_det = select_front_leader(
            faulted_detections,
            leader_id_filter=selected_leader_id,
            min_confidence=0.0,
            max_abs_y_m=1.5,
            front_only=True,
        )

        if measurement_det is None:
            state = tracker.update(None, confidence=0.0) if initialized else tracker.state()
        else:
            measurement = measurement_from_detection(measurement_det)
            if not initialized or tracker.mode == TrackMode.LOST:
                state = tracker.reset(measurement, leader_id=str(measurement_det["id"]))
                initialized = True
            else:
                state = tracker.update(measurement, confidence=float(measurement_det["confidence"]), leader_id=str(measurement_det["id"]))

        debug = controller_debug(state, stamp_s)
        nis_value = "" if math.isnan(state.nis) else f"{state.nis:.6f}"
        trace.append(
            {
                "step": str(step),
                "stamp_s": f"{stamp_s:.4f}",
                "raw_count": str(len(raw_detections)),
                "faulted_count": str(len(faulted_detections)),
                "selected_leader_id": selected_leader_id,
                "selected_confidence": f"{float(selected_payload['confidence']):.4f}",
                "selected_candidate_count": str(selected_payload["candidate_count"]),
                "measurement_id": str(measurement_det["id"]) if measurement_det else "",
                "measurement_available": str(measurement_det is not None).lower(),
                "fault_tag": fault_tag,
                "mode": state.mode.value if hasattr(state.mode, "value") else str(state.mode),
                "x": f"{float(state.x[0]):.6f}",
                "y": f"{float(state.x[1]):.6f}",
                "vx": f"{float(state.x[2]):.6f}",
                "vy": f"{float(state.x[3]):.6f}",
                "covariance_trace": f"{float(np.trace(state.P)):.6f}",
                "nis": nis_value,
                "ghost_age_s": f"{float(state.ghost_age_s):.6f}",
                "selected_speed_mps": f"{float(debug['selected_speed_mps']):.6f}",
                "headway_m": f"{float(debug['headway_m']):.6f}",
                "ttc_s": "" if debug["ttc_s"] is None else f"{float(debug['ttc_s']):.6f}",
                "safety_stop": str(bool(debug["safety_stop"])).lower(),
                "controller_reason": str(debug["reason"]),
            }
        )

    return trace


def write_trace(trace: list[dict[str, str]]) -> None:
    with OUT_TRACE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trace[0].keys()))
        writer.writeheader()
        writer.writerows(trace)


def add(rows: list[SummaryRow], check_id: str, requirement: str, ok: bool, actual: str, boundary: str) -> None:
    rows.append(
        SummaryRow(
            check_id=check_id,
            requirement=requirement,
            actual=actual,
            status="PASS" if ok else "FAIL",
            source_artifact="real_robot_offline_dryrun_trace.csv",
            boundary=boundary,
        )
    )


def summarize(trace: list[dict[str, str]]) -> list[SummaryRow]:
    mode_counts: dict[str, int] = {}
    for row in trace:
        mode_counts[row["mode"]] = mode_counts.get(row["mode"], 0) + 1
    max_nis = max(float(row["nis"]) for row in trace if row["nis"])
    dropout_frames = sum(1 for row in trace if row["fault_tag"] == "software_dropout")
    lost_stop_frames = sum(1 for row in trace if row["mode"] == "LOST" and row["safety_stop"] == "true")
    positive_tracking_speed = sum(1 for row in trace if row["mode"] == "TRACKING" and float(row["selected_speed_mps"]) > 0.01)
    recovery_rows = [row for row in trace if row["fault_tag"] == "high_nis_recovery_offset" and row["mode"] == "TRACKING"]
    rows: list[SummaryRow] = []
    add(rows, "trace_row_count", "Dry run emits exactly 90 frame-level rows.", len(trace) == STEPS, f"rows={len(trace)}", "Deterministic offline replay length only.")
    add(rows, "selected_leader_all_frames", "Selected-leader payload is available on every frame.", all(row["selected_leader_id"] == "robot_2" for row in trace), "leader_id=robot_2 on all frames", "Uses scripted TF-like detections, not a learned selector.")
    add(rows, "raw_distractor_present", "Raw detections include leader and distractor candidates.", all(row["raw_count"] == "2" for row in trace), "raw_count=2 on all frames", "Synthetic dry-run candidates only.")
    add(rows, "dropout_frames_present", "Software dropout interval removes measurements for at least 20 frames.", dropout_frames >= 20, f"dropout_frames={dropout_frames}", "Software dropout is deterministic, not physical occlusion.")
    add(rows, "ghost_mode_present", "POP/NIS enters GHOST mode during dropout before timeout.", mode_counts.get("GHOST", 0) > 0, f"mode_counts={mode_counts}", "GHOST mode is offline core behavior.")
    add(rows, "lost_mode_present", "POP/NIS enters LOST mode after sustained dropout.", mode_counts.get("LOST", 0) > 0, f"mode_counts={mode_counts}", "LOST mode does not prove real robot stopping latency.")
    add(rows, "tracking_recovery_present", "POP/NIS returns to TRACKING after high-confidence recovery.", bool(recovery_rows), f"recovery_rows={len(recovery_rows)}", "Recovery measurement is scripted.")
    add(rows, "nis_hard_gate_exercised", "Dry run produces a NIS value above the hard gate.", max_nis > 20.0, f"max_nis={max_nis:.3f}", "High NIS is induced by a scripted offset.")
    add(rows, "lost_triggers_safety_stop", "Controller dry-run safety_stop is true during every LOST frame.", lost_stop_frames == mode_counts.get("LOST", 0) and lost_stop_frames > 0, f"lost_stop_frames={lost_stop_frames}", "Offline controller proxy, not actuator evidence.")
    add(rows, "tracking_allows_positive_speed", "Controller dry-run allows positive bounded speed during TRACKING.", positive_tracking_speed > 0, f"positive_tracking_speed_frames={positive_tracking_speed}", "Speed command is not bridged to hardware.")
    add(rows, "trace_has_contract_fields", "Trace includes selected leader, NIS, mode, speed, headway, and stop-reason fields.", all(field in trace[0] for field in ("selected_leader_id", "nis", "mode", "selected_speed_mps", "headway_m", "controller_reason")), "required columns present", "CSV field presence is not a rosbag.")
    add(rows, "offline_nonclaim_boundary", "Dry run is explicitly below ROS2 launch, rosbag, timing, and physical robot validation.", True, "offline Python only; no ROS2 imports beyond pure helpers", "Passing dry run does not prove ROS2 build/launch success or physical trial completion.")
    return rows


def write_summary(rows: list[SummaryRow]) -> None:
    with OUT_SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SummaryRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])


def write_report(rows: list[SummaryRow]) -> None:
    failed = [row for row in rows if row.status != "PASS"]
    lines = [
        "# Real-Robot Offline Dry-Run Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"The offline dry run checks {len(rows)} deterministic selected-leader, fault-injection, POP/NIS, NIS-gate, GHOST/LOST, and controller-proxy behavior gates without requiring ROS2.",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All offline real-robot dry-run checks passed." if not failed else "One or more offline dry-run checks failed.",
        "",
        "## Generated Artifacts",
        "",
        "- `real_robot_offline_dryrun_trace.csv`",
        "- `real_robot_offline_dryrun_summary.csv`",
        "- `real_robot_offline_dryrun_report_20260604.md`",
        "",
        "## Boundary",
        "",
        "This dry run does not prove ROS2 build success, does not prove ros2 launch success, does not produce a rosbag, does not measure robot timing, does not command hardware, and does not contain completed physical robot trial data. It is a deterministic desktop exercise of the pure-Python selected-leader, fault-injection, POP/NIS, and controller-proxy path before moving to ROS2 and supervised robot trials.",
    ]
    if failed:
        lines.extend(["", "## Failed Checks", ""])
        for row in failed:
            lines.append(f"- `{row.check_id}`: {row.actual}")
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    trace = run_trace()
    write_trace(trace)
    summary = summarize(trace)
    write_summary(summary)
    write_report(summary)
    failed = [row for row in summary if row.status != "PASS"]
    print(OUT_TRACE)
    print(OUT_SUMMARY)
    print(OUT_REPORT)
    print(f"passed={len(summary) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
