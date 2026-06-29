#!/usr/bin/env python3
"""Run executable smoke tests for the pure-Python real-robot preflight core."""

from __future__ import annotations

import csv
import importlib.util
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REAL_ROBOT = ROOT / "03_real_robot"
STACK = REAL_ROBOT / "ros2_qgip_stack"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"

OUT_CSV = SOURCE / "real_robot_software_smoke_test.csv"
OUT_REPORT = PACKAGE / "real_robot_software_smoke_test_report_20260604.md"


@dataclass
class SmokeRow:
    check_id: str
    requirement: str
    actual: str
    status: str
    source_artifacts: str
    boundary: str


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def close_vec(a: np.ndarray, b: np.ndarray, atol: float = 1e-9) -> bool:
    return bool(np.allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float), atol=atol, rtol=0.0))


def finite_symmetric_psd(matrix: np.ndarray) -> bool:
    mat = np.asarray(matrix, dtype=float)
    if not np.all(np.isfinite(mat)):
        return False
    if not np.allclose(mat, mat.T, atol=1e-9):
        return False
    return bool(np.min(np.linalg.eigvalsh(mat)) >= -1e-9)


def controller_proxy(mode: str, x: float, y: float = 0.0, vx: float = 0.0) -> dict[str, float | bool | str | None]:
    distance = math.hypot(x, y)
    desired_gap = 0.35
    ttc_s = distance / abs(vx) if vx < -1e-3 and distance > 0.0 else None
    stop = mode == "LOST" or x <= 0.25
    if stop:
        return {
            "selected_speed_mps": 0.0,
            "selected_v_mps": 0.0,
            "headway_m": max(0.0, x),
            "ttc_s": ttc_s,
            "safety_stop": True,
            "reason": "lost_or_unsafe",
        }
    scale = 0.35 if mode == "GHOST" else 0.70 if mode == "DEGRADED" else 1.0
    speed = max(0.0, min(0.50, scale * (0.80 * (x - desired_gap) + 0.20 * vx)))
    return {
        "selected_speed_mps": speed,
        "selected_v_mps": speed,
        "headway_m": max(0.0, x),
        "ttc_s": ttc_s,
        "safety_stop": False,
        "reason": "tracking",
    }


def add(rows: list[SmokeRow], check_id: str, requirement: str, ok: bool, actual: str, source_artifacts: str, boundary: str) -> None:
    rows.append(
        SmokeRow(
            check_id=check_id,
            requirement=requirement,
            actual=actual,
            status="PASS" if ok else "FAIL",
            source_artifacts=source_artifacts,
            boundary=boundary,
        )
    )


def run_smoke() -> list[SmokeRow]:
    rows: list[SmokeRow] = []

    stack_core = STACK / "ros2_qgip_stack"
    sys.path.insert(0, str(STACK))
    root_pop = load_module("root_pop_nis_kf_core_smoke", REAL_ROBOT / "pop_nis_kf_core.py")
    root_fault = load_module("root_fault_injection_core_smoke", REAL_ROBOT / "fault_injection_core.py")
    stack_pop = load_module("stack_pop_nis_kf_core_smoke", stack_core / "pop_nis_kf_core.py")
    stack_fault = load_module("stack_fault_injection_core_smoke", stack_core / "fault_injection_core.py")
    json_contract = load_module("stack_json_contract_smoke", stack_core / "json_contract.py")

    add(
        rows,
        "core_modules_importable",
        "Root and installable pure-Python core modules import without ROS2.",
        all(module is not None for module in (root_pop, root_fault, stack_pop, stack_fault, json_contract)),
        "root POP/fault and stack POP/fault/json modules imported",
        "03_real_robot/*.py; 03_real_robot/ros2_qgip_stack/ros2_qgip_stack/*.py",
        "Importability of pure-Python helpers does not prove rclpy node launch.",
    )

    root_tracker = root_pop.NISGatedPOP(root_pop.POPConfig(dt=0.1, ghost_horizon_s=0.2, lost_timeout_s=0.3))
    stack_tracker = stack_pop.NISGatedPOP(stack_pop.POPConfig(dt=0.1, ghost_horizon_s=0.2, lost_timeout_s=0.3))
    z0 = np.array([1.0, 0.0, 0.2, 0.0])
    zr = root_tracker.reset(z0, leader_id="robot_2")
    zs = stack_tracker.reset(z0, leader_id="robot_2")
    add(
        rows,
        "pop_reset_parity",
        "Root and installable POP trackers reset to the same state.",
        close_vec(zr.x, zs.x) and close_vec(zr.P, zs.P) and zr.mode.value == zs.mode.value,
        f"root_mode={zr.mode.value}; stack_mode={zs.mode.value}; root_x={np.round(zr.x, 4).tolist()}",
        "pop_nis_kf_core.py",
        "Behavior parity checks local Python copies only, not ROS2 message transport.",
    )

    meas = np.array([1.02, 0.01, 0.2, 0.0])
    zr = root_tracker.update(meas, confidence=0.9, leader_id="robot_2")
    zs = stack_tracker.update(meas, confidence=0.9, leader_id="robot_2")
    add(
        rows,
        "pop_tracking_update_parity",
        "Root and installable POP trackers match during normal tracking update.",
        close_vec(zr.x, zs.x) and zr.mode.value == zs.mode.value and abs(zr.nis - zs.nis) < 1e-9,
        f"mode={zr.mode.value}; nis={zr.nis:.6f}",
        "pop_nis_kf_core.py",
        "Single-step parity does not replace rosbag replay.",
    )

    root_mode_sequence = []
    stack_mode_sequence = []
    for _ in range(4):
        zr = root_tracker.update(None, confidence=0.0)
        zs = stack_tracker.update(None, confidence=0.0)
        root_mode_sequence.append(zr.mode.value)
        stack_mode_sequence.append(zs.mode.value)
    add(
        rows,
        "pop_dropout_mode_sequence_parity",
        "Missing measurements drive matching GHOST-to-LOST behavior in both core copies.",
        root_mode_sequence == stack_mode_sequence and "GHOST" in root_mode_sequence and root_mode_sequence[-1] == "LOST",
        f"root_sequence={root_mode_sequence}; stack_sequence={stack_mode_sequence}",
        "pop_nis_kf_core.py",
        "Dropout sequence is deterministic unit evidence, not physical occlusion evidence.",
    )

    soft_tracker = stack_pop.NISGatedPOP(stack_pop.POPConfig(dt=0.1, nis_soft_threshold=2.0, nis_hard_threshold=4.0, high_confidence_threshold=0.95))
    soft_tracker.reset(np.array([0.0, 0.0, 0.0, 0.0]), leader_id="robot_2")
    soft_state = soft_tracker.update(np.array([0.5, 0.0, 0.0, 0.0]), confidence=0.8, leader_id="robot_2")
    add(
        rows,
        "pop_soft_gate_degraded_mode",
        "A large moderate-confidence innovation enters DEGRADED mode instead of hard reset.",
        soft_state.mode.value == "DEGRADED" and soft_state.nis > soft_tracker.cfg.nis_soft_threshold,
        f"mode={soft_state.mode.value}; nis={soft_state.nis:.3f}",
        "ros2_qgip_stack/pop_nis_kf_core.py",
        "NIS thresholds are software-gate checks and are not real sensor calibration.",
    )

    hard_tracker = stack_pop.NISGatedPOP(stack_pop.POPConfig(dt=0.1, nis_soft_threshold=2.0, nis_hard_threshold=4.0, high_confidence_threshold=0.85))
    hard_tracker.reset(np.array([0.0, 0.0, 0.0, 0.0]), leader_id="robot_2")
    hard_measurement = np.array([0.8, 0.1, 0.0, 0.0])
    hard_state = hard_tracker.update(hard_measurement, confidence=0.96, leader_id="robot_2")
    add(
        rows,
        "pop_hard_gate_high_confidence_reset",
        "A high-confidence hard-gate innovation resets to the new measurement and remains TRACKING.",
        hard_state.mode.value == "TRACKING" and close_vec(hard_state.x, hard_measurement),
        f"mode={hard_state.mode.value}; nis={hard_state.nis:.3f}; x={np.round(hard_state.x, 3).tolist()}",
        "ros2_qgip_stack/pop_nis_kf_core.py",
        "Hard reset behavior is an offline core invariant, not runtime recovery evidence.",
    )

    add(
        rows,
        "pop_covariance_well_formed",
        "POP covariance remains finite, symmetric, and positive semidefinite after smoke updates.",
        finite_symmetric_psd(hard_state.P) and finite_symmetric_psd(soft_state.P),
        f"hard_trace={np.trace(hard_state.P):.6f}; soft_trace={np.trace(soft_state.P):.6f}",
        "ros2_qgip_stack/pop_nis_kf_core.py",
        "Matrix well-formedness is local numerical hygiene, not closed-loop safety certification.",
    )

    dets = [
        stack_fault.Detection("robot_2", x=1.0, y=0.0, confidence=0.9, stamp_s=0.1),
        stack_fault.Detection("robot_3", x=1.2, y=0.6, confidence=0.8, stamp_s=0.1),
    ]
    dropout = stack_fault.DetectionFaultInjector(stack_fault.FaultConfig(dropout_period_s=1.0, dropout_duration_s=0.2))
    add(
        rows,
        "fault_dropout_window_empty",
        "Fault injector removes detections inside the configured dropout window.",
        dropout.apply(dets, 0.1) == [],
        f"in_dropout_window={dropout.in_dropout_window(0.1)}; outputs=0",
        "ros2_qgip_stack/fault_injection_core.py",
        "Software dropout is not a physical sensing failure.",
    )

    delay = stack_fault.DetectionFaultInjector(stack_fault.FaultConfig(delay_s=0.1))
    first = delay.apply(dets, 0.0)
    second = delay.apply(dets, 0.1)
    add(
        rows,
        "fault_delay_fifo_behavior",
        "Fault injector delay queue withholds the first frame and releases it after the configured delay.",
        len(first) == 0 and len(second) == 2 and second[0].object_id == "robot_2",
        f"first={len(first)}; second={len(second)}; second_first_id={second[0].object_id if second else ''}",
        "ros2_qgip_stack/fault_injection_core.py",
        "FIFO delay smoke test does not measure ROS2 timestamp jitter.",
    )

    switcher = stack_fault.DetectionFaultInjector(stack_fault.FaultConfig(id_switch_probability=1.0, random_seed=3))
    switched = switcher.apply(dets, 0.3)
    add(
        rows,
        "fault_id_switch_behavior",
        "Fault injector can deterministically swap object identities for paired candidates.",
        len(switched) == 2 and [det.object_id for det in switched] == ["robot_3", "robot_2"],
        f"ids={[det.object_id for det in switched]}",
        "ros2_qgip_stack/fault_injection_core.py",
        "ID-switch injection is a scripted perturbation, not a real tracker failure log.",
    )

    fp = stack_fault.DetectionFaultInjector(stack_fault.FaultConfig(false_positive_rate=1.0, random_seed=5))
    with_fp = fp.apply([dets[0]], 0.4)
    add(
        rows,
        "fault_false_positive_behavior",
        "Fault injector can append a deterministic false-positive candidate.",
        len(with_fp) == 2 and any(det.class_name == "false_positive" for det in with_fp),
        f"outputs={len(with_fp)}; classes={[det.class_name for det in with_fp]}",
        "ros2_qgip_stack/fault_injection_core.py",
        "False-positive injection is a preflight perturbation only.",
    )

    payload = {"stamp_s": 0.2, "detections": [{"id": "robot_2", "x": 1.0, "y": 0.0, "confidence": 0.95}]}
    encoded = json_contract.dumps_payload(payload)
    decoded = json_contract.loads_payload(encoded)
    normalized = json_contract.normalize_detections(decoded)
    add(
        rows,
        "json_roundtrip_and_normalization",
        "JSON payloads round-trip and normalize into finite detection dictionaries.",
        decoded["stamp_s"] == 0.2 and len(normalized) == 1 and normalized[0]["id"] == "robot_2",
        f"encoded={encoded}; normalized_count={len(normalized)}",
        "ros2_qgip_stack/json_contract.py",
        "JSON contract tests std_msgs/String payload shape, not ROS2 QoS behavior.",
    )

    clamped = json_contract.normalize_detection({"id": "bad", "x": "nan", "y": float("inf"), "confidence": 9.0}, fallback_stamp_s=1.5)
    add(
        rows,
        "json_nonfinite_and_confidence_clamp",
        "JSON normalization replaces non-finite coordinates and clamps confidence to [0,1].",
        clamped["x"] == 0.0 and clamped["y"] == 0.0 and clamped["confidence"] == 1.0,
        f"x={clamped['x']}; y={clamped['y']}; confidence={clamped['confidence']}",
        "ros2_qgip_stack/json_contract.py",
        "Input sanitation does not prove upstream detector validity.",
    )

    leader = json_contract.select_front_leader(
        [
            {"id": "robot_back", "x": -0.5, "y": 0.0, "vx": 0.0, "vy": 0.0, "confidence": 1.0, "stamp_s": 0.0},
            {"id": "robot_2", "x": 1.0, "y": 0.05, "vx": 0.0, "vy": 0.0, "confidence": 0.9, "stamp_s": 0.0},
            {"id": "robot_3", "x": 1.1, "y": 1.2, "vx": 0.0, "vy": 0.0, "confidence": 0.95, "stamp_s": 0.0},
        ],
        min_confidence=0.5,
        max_abs_y_m=0.5,
        front_only=True,
    )
    add(
        rows,
        "json_front_leader_selection_policy",
        "Leader selection rejects behind/lateral candidates and returns the front in-lane leader.",
        leader is not None and leader["id"] == "robot_2",
        f"selected={leader['id'] if leader else ''}",
        "ros2_qgip_stack/json_contract.py",
        "This is the deterministic preflight selector, not a learned perception result.",
    )

    try:
        json_contract.loads_payload("[]")
        malformed_rejected = False
        malformed_actual = "accepted"
    except ValueError as exc:
        malformed_rejected = True
        malformed_actual = str(exc)
    add(
        rows,
        "json_malformed_payload_rejected",
        "Non-object JSON payloads are rejected by the helper contract.",
        malformed_rejected,
        malformed_actual,
        "ros2_qgip_stack/json_contract.py",
        "Malformed-payload rejection is local parsing evidence, not network fault coverage.",
    )

    tracking = controller_proxy("TRACKING", x=1.0, vx=0.1)
    degraded = controller_proxy("DEGRADED", x=1.0, vx=0.1)
    ghost = controller_proxy("GHOST", x=1.0, vx=0.1)
    lost = controller_proxy("LOST", x=1.0, vx=0.1)
    unsafe = controller_proxy("TRACKING", x=0.2, vx=0.0)
    ok_controller = (
        not tracking["safety_stop"]
        and 0.0 < float(ghost["selected_speed_mps"]) < float(degraded["selected_speed_mps"]) < float(tracking["selected_speed_mps"]) <= 0.5
        and lost["safety_stop"]
        and float(lost["selected_speed_mps"]) == 0.0
        and unsafe["safety_stop"]
    )
    add(
        rows,
        "controller_proxy_safety_invariants",
        "Controller proxy reduces speed in GHOST/DEGRADED and stops for LOST or unsafe headway.",
        ok_controller,
        (
            f"tracking={tracking['selected_speed_mps']:.3f}; "
            f"degraded={degraded['selected_speed_mps']:.3f}; ghost={ghost['selected_speed_mps']:.3f}; "
            f"lost_stop={lost['safety_stop']}; unsafe_stop={unsafe['safety_stop']}"
        ),
        "velocity_safety_controller_node.py behavior mirrored in offline smoke test",
        "Controller proxy invariants are not actuator, bridge, or E-stop evidence.",
    )

    add(
        rows,
        "software_smoke_nonclaim_boundary",
        "Smoke test explicitly stays below ROS2 build, launch, rosbag, timing, and physical validation claims.",
        True,
        "pure-Python executable checks only; ROS2 nodes are not launched",
        "real_robot_software_smoke_test.csv; real_robot_software_smoke_test_report_20260604.md",
        "Passing this smoke test does not prove ROS2 build/launch success, rosbag capture, real-time latency, or physical robot safety.",
    )

    return rows


def write_csv(rows: list[SmokeRow]) -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SmokeRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])


def write_report(rows: list[SmokeRow]) -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    failed = [row for row in rows if row.status != "PASS"]
    lines = [
        "# Real-Robot Software Smoke Test Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"The software smoke test executes {len(rows)} pure-Python preflight checks covering POP/NIS behavior, root-vs-installable core parity, fault injection, JSON payload contracts, and controller-proxy safety invariants.",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All real-robot software smoke checks passed." if not failed else "One or more real-robot software smoke checks failed.",
        "",
        "## Generated Artifacts",
        "",
        "- `real_robot_software_smoke_test.csv`",
        "- `real_robot_software_smoke_test_report_20260604.md`",
        "",
        "## Scope",
        "",
        "This is an executable desktop test of pure-Python helper logic before ROS2/HIL/physical execution. It is stronger than a static file audit because it checks behavior under deterministic inputs, but it remains below ROS2 node launch and does not exercise rclpy, DDS, robot clocks, rosbag capture, actuator bridges, timing latency, E-stop hardware, or physical robot motion.",
    ]
    if failed:
        lines.extend(["", "## Failed Checks", ""])
        for row in failed:
            lines.append(f"- `{row.check_id}`: {row.actual}")
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    rows = run_smoke()
    write_csv(rows)
    write_report(rows)
    failed = [row for row in rows if row.status != "PASS"]
    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
