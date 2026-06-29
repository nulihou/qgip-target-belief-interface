#!/usr/bin/env python3
"""Run a local synthetic POP/NIS fault-stress experiment.

This is a computer-only sanity/stress experiment for the estimator and a simple
velocity safety filter. It is not a CARLA or real-robot result.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
REAL_ROBOT_DIR = ROOT / "RA_L_optimization_20260528" / "03_real_robot"
DEFAULT_OUT = ROOT / "RA_L_optimization_20260528" / "07_computer_experiments"
sys.path.insert(0, str(REAL_ROBOT_DIR))

from fault_injection_core import Detection, DetectionFaultInjector, FaultConfig  # noqa: E402
from pop_nis_kf_core import NISGatedPOP, POPConfig, TrackMode  # noqa: E402


@dataclass(frozen=True)
class StressCondition:
    name: str
    dropout_duration_s: float = 0.0
    dropout_period_s: float = 4.0
    position_noise_std_m: float = 0.0
    velocity_noise_std_mps: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    confidence_scale: float = 1.0
    delay_s: float = 0.0


CONDITIONS: Tuple[StressCondition, ...] = (
    StressCondition("clean"),
    StressCondition("dropout_0p5s", dropout_duration_s=0.5),
    StressCondition("dropout_1p0s", dropout_duration_s=1.0),
    StressCondition("noise_0p15_delay_0p1", position_noise_std_m=0.15, velocity_noise_std_mps=0.20, delay_s=0.10),
    StressCondition("false_negative_50pct", false_negative_rate=0.50),
    StressCondition("false_positive_25pct", false_positive_rate=0.25, confidence_scale=0.65),
    StressCondition(
        "combined_hard",
        dropout_duration_s=0.8,
        position_noise_std_m=0.12,
        velocity_noise_std_mps=0.25,
        false_positive_rate=0.25,
        false_negative_rate=0.25,
        confidence_scale=0.70,
        delay_s=0.10,
    ),
)


class DetectorHoldBaseline:
    """Detector-only baseline that holds the last state through dropouts."""

    def __init__(self, dt: float = 0.05, lost_timeout_s: float = 1.5):
        self.dt = dt
        self.lost_timeout_s = lost_timeout_s
        self.x: Optional[np.ndarray] = None
        self.missed_s = lost_timeout_s
        self.mode = TrackMode.LOST
        self.nis = float("nan")

    def update(self, measurement: Optional[np.ndarray], confidence: float) -> Tuple[Optional[np.ndarray], TrackMode, float]:
        if measurement is not None and confidence >= 0.5:
            self.x = np.asarray(measurement, dtype=float).reshape(4).copy()
            self.missed_s = 0.0
            self.mode = TrackMode.TRACKING
            return self.x.copy(), self.mode, self.nis
        if self.x is not None:
            self.missed_s += self.dt
            self.mode = TrackMode.GHOST if self.missed_s <= self.lost_timeout_s else TrackMode.LOST
            return self.x.copy(), self.mode, self.nis
        self.mode = TrackMode.LOST
        return None, self.mode, self.nis


class POPWrapper:
    def __init__(self, mode: str, dt: float):
        if mode == "std_kf":
            cfg = POPConfig(
                dt=dt,
                nis_soft_threshold=1.0e12,
                nis_hard_threshold=1.0e12,
                r_inflation=1.0,
                ghost_horizon_s=1.0,
                lost_timeout_s=1.5,
            )
        elif mode == "nis_pop":
            cfg = POPConfig(dt=dt, ghost_horizon_s=1.0, lost_timeout_s=1.5)
        else:
            raise ValueError(f"Unsupported POP wrapper mode: {mode}")
        self.tracker = NISGatedPOP(cfg)
        self.initialized = False

    def update(self, measurement: Optional[np.ndarray], confidence: float) -> Tuple[Optional[np.ndarray], TrackMode, float]:
        if not self.initialized:
            if measurement is None or confidence < self.tracker.cfg.confidence_threshold:
                return None, TrackMode.LOST, float("nan")
            state = self.tracker.reset(measurement)
            self.initialized = True
            return state.x, state.mode, state.nis
        state = self.tracker.update(measurement, confidence)
        return state.x, state.mode, state.nis


def select_detection(detections: Iterable[Detection]) -> Optional[Detection]:
    front = [det for det in detections if det.x > 0.05]
    if not front:
        return None
    return max(front, key=lambda d: (d.confidence, -abs(d.y), d.x))


def leader_acceleration(t: float) -> float:
    if 3.5 <= t < 4.4:
        return -0.75
    if 6.2 <= t < 7.1:
        return 0.55
    if 8.5 <= t < 9.2:
        return -0.45
    return 0.0


def controller_step(
    estimate: Optional[np.ndarray],
    mode: TrackMode,
    ego_v: float,
    dt: float,
    max_speed: float,
) -> Tuple[float, bool]:
    if estimate is None or mode == TrackMode.LOST:
        target_v = 0.0
        safety_stop = True
    else:
        est_gap = float(estimate[0])
        est_rel_v = float(estimate[2])
        desired_gap = 0.55 + 0.65 * max(ego_v, 0.0)
        target_v = ego_v + est_rel_v + 0.90 * (est_gap - desired_gap)
        safety_stop = False
        if est_gap < 0.30 or mode == TrackMode.DEGRADED:
            target_v = min(target_v, 0.15)
            safety_stop = True
        if mode == TrackMode.GHOST:
            target_v = min(target_v, ego_v)
    target_v = float(np.clip(target_v, 0.0, max_speed))
    accel = float(np.clip((target_v - ego_v) / dt, -0.85, 0.60))
    return float(np.clip(ego_v + accel * dt, 0.0, max_speed)), safety_stop


def run_episode(condition: StressCondition, method: str, seed: int, dt: float, horizon_s: float) -> Dict[str, object]:
    rng = np.random.default_rng(seed)
    injector = DetectionFaultInjector(
        FaultConfig(
            dropout_period_s=condition.dropout_period_s,
            dropout_duration_s=condition.dropout_duration_s,
            position_noise_std_m=condition.position_noise_std_m,
            velocity_noise_std_mps=condition.velocity_noise_std_mps,
            false_positive_rate=condition.false_positive_rate,
            false_negative_rate=condition.false_negative_rate,
            confidence_scale=condition.confidence_scale,
            delay_s=condition.delay_s,
            random_seed=seed,
        )
    )

    if method == "Detector hold + PID":
        tracker = DetectorHoldBaseline(dt=dt)
    elif method == "Std KF + safety filter":
        tracker = POPWrapper("std_kf", dt)
    elif method == "NIS-POP + safety filter":
        tracker = POPWrapper("nis_pop", dt)
    else:
        raise ValueError(method)

    leader_x = 1.45
    leader_y = 0.0
    leader_v = 0.42 + float(rng.normal(0.0, 0.015))
    ego_x = 0.0
    ego_v = 0.30
    max_speed = 0.80

    errors: List[float] = []
    min_gap = float("inf")
    lost_frames = 0
    ghost_frames = 0
    degraded_frames = 0
    safety_stop_frames = 0
    nis_values: List[float] = []

    steps = int(horizon_s / dt)
    for step in range(steps):
        t = step * dt
        leader_v = float(np.clip(leader_v + leader_acceleration(t) * dt, 0.08, 0.70))
        leader_y = 0.10 * math.sin(0.75 * t)
        leader_x += leader_v * dt
        true_gap = leader_x - ego_x
        true_rel_v = leader_v - ego_v

        raw = [
            Detection(
                object_id="leader",
                x=true_gap,
                y=leader_y,
                vx=true_rel_v,
                vy=0.075 * math.cos(0.75 * t),
                confidence=0.90,
                stamp_s=t,
            )
        ]
        faulty = injector.apply(raw, t)
        selected = select_detection(faulty)
        measurement = None
        confidence = 0.0
        if selected is not None:
            measurement = np.array([selected.x, selected.y, selected.vx, selected.vy], dtype=float)
            confidence = float(selected.confidence)

        estimate, mode, nis = tracker.update(measurement, confidence)
        if estimate is not None:
            errors.append(float(np.linalg.norm(estimate[:2] - np.array([true_gap, leader_y]))))
        if mode == TrackMode.LOST:
            lost_frames += 1
        elif mode == TrackMode.GHOST:
            ghost_frames += 1
        elif mode == TrackMode.DEGRADED:
            degraded_frames += 1
        if not math.isnan(nis):
            nis_values.append(float(nis))

        ego_v, safety_stop = controller_step(estimate, mode, ego_v, dt, max_speed)
        safety_stop_frames += int(safety_stop)
        ego_x += ego_v * dt
        min_gap = min(min_gap, leader_x - ego_x)

    rmse = math.sqrt(mean([err * err for err in errors])) if errors else float("nan")
    p95_error = float(np.percentile(errors, 95)) if errors else float("nan")
    contact = min_gap < 0.05
    near_miss = min_gap < 0.25
    completion = not contact and lost_frames < int(0.40 * steps)
    return {
        "condition": condition.name,
        "method": method,
        "seed": seed,
        "completion": int(completion),
        "contact": int(contact),
        "near_miss": int(near_miss),
        "min_gap_m": min_gap,
        "tracking_rmse_m": rmse,
        "tracking_p95_error_m": p95_error,
        "lost_fraction": lost_frames / steps,
        "ghost_fraction": ghost_frames / steps,
        "degraded_fraction": degraded_frames / steps,
        "safety_stop_fraction": safety_stop_frames / steps,
        "mean_nis": mean(nis_values) if nis_values else "",
    }


def summarize(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["condition"]), str(row["method"])), []).append(row)

    summary: List[Dict[str, object]] = []
    for (condition, method), group in sorted(grouped.items()):
        n = len(group)
        summary.append(
            {
                "condition": condition,
                "method": method,
                "n": n,
                "completion": sum(int(r["completion"]) for r in group),
                "contact": sum(int(r["contact"]) for r in group),
                "near_miss": sum(int(r["near_miss"]) for r in group),
                "completion_rate": mean(float(r["completion"]) for r in group),
                "contact_rate": mean(float(r["contact"]) for r in group),
                "near_miss_rate": mean(float(r["near_miss"]) for r in group),
                "mean_min_gap_m": mean(float(r["min_gap_m"]) for r in group),
                "mean_tracking_rmse_m": mean(float(r["tracking_rmse_m"]) for r in group),
                "mean_tracking_p95_error_m": mean(float(r["tracking_p95_error_m"]) for r in group),
                "mean_lost_fraction": mean(float(r["lost_fraction"]) for r in group),
                "mean_ghost_fraction": mean(float(r["ghost_fraction"]) for r in group),
                "mean_degraded_fraction": mean(float(r["degraded_fraction"]) for r in group),
                "mean_safety_stop_fraction": mean(float(r["safety_stop_fraction"]) for r in group),
            }
        )
    return summary


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: List[Dict[str, object]]) -> None:
    lines = [
        "# Synthetic POP/NIS Stress Summary",
        "",
        "This is a local synthetic estimator/controller stress test. It is useful for code-level sanity checks, but it must not be reported as CARLA or real-robot validation.",
        "",
        "| Condition | Method | n | Completion | Contact | Near-miss | Mean min gap (m) | RMSE (m) | Lost frac | Safety-stop frac |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        n = int(row["n"])
        lines.append(
            f"| {row['condition']} | {row['method']} | {n} | "
            f"{int(row['completion'])}/{n} ({100.0 * float(row['completion_rate']):.1f}%) | "
            f"{int(row['contact'])}/{n} ({100.0 * float(row['contact_rate']):.1f}%) | "
            f"{int(row['near_miss'])}/{n} ({100.0 * float(row['near_miss_rate']):.1f}%) | "
            f"{float(row['mean_min_gap_m']):.3f} | {float(row['mean_tracking_rmse_m']):.3f} | "
            f"{float(row['mean_lost_fraction']):.3f} | {float(row['mean_safety_stop_fraction']):.3f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--dt", type=float, default=0.05)
    parser.add_argument("--horizon-s", type=float, default=12.0)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    methods = ["Detector hold + PID", "Std KF + safety filter", "NIS-POP + safety filter"]
    rows: List[Dict[str, object]] = []
    for condition in CONDITIONS:
        for method in methods:
            for episode in range(args.episodes):
                seed = 1000 * (CONDITIONS.index(condition) + 1) + 37 * episode + methods.index(method)
                rows.append(run_episode(condition, method, seed, args.dt, args.horizon_s))

    episode_path = args.out_dir / "synthetic_pop_nis_episode_results.csv"
    summary_path = args.out_dir / "synthetic_pop_nis_summary.csv"
    md_path = args.out_dir / "synthetic_pop_nis_summary.md"
    summary_rows = summarize(rows)
    write_csv(episode_path, rows)
    write_csv(summary_path, summary_rows)
    write_markdown(md_path, summary_rows)
    print(f"[OK] synthetic episodes: {len(rows)} -> {episode_path}")
    print(f"[OK] synthetic summary: {len(summary_rows)} rows -> {summary_path}")
    print(f"[OK] markdown summary -> {md_path}")


if __name__ == "__main__":
    main()
