"""Enhanced Kalman tracker with NEES computation, reset decomposition, and
safety diagnostics.

This module extends the existing KalmanTracker with:
1. NEES (Normalized Estimation Error Squared) — requires ground-truth state
2. Reset counter decomposition — why was each reset accepted/rejected?
3. Safety-availability diagnostics — TTC, headway, stop duration, Lost cause

Usage as a drop-in replacement in run_closed_loop.py:
    from kf_diagnostics import DiagnosticKalmanTracker as KalmanTracker
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np


class DiagnosticKalmanTracker:
    """Extended Kalman tracker with NEES and reset diagnostics.

    API-compatible with the existing KalmanTracker in run_closed_loop.py,
    but adds diagnostic fields accessible after each episode.
    """

    def __init__(self, dt: float = 0.05):
        self.dt = dt
        # State: [x, y, vx, vy]
        self.x = np.zeros(4)
        self.P = np.eye(4) * 100.0

        # Process Model (Constant Velocity)
        self.F = np.eye(4)
        self.F[0, 2] = dt
        self.F[1, 3] = dt

        # Measurement Model
        self.H = np.eye(4)

        # Noise Covariances
        self.R = np.eye(4) * 0.1
        self.Q = np.eye(4) * 0.5

        self.is_initialized = False
        self.lost_steps = 0
        self.last_nis = float("nan")
        self.last_nees = float("nan")
        self.last_update_mode = "uninitialized"
        self.disable_nis_gating = False
        self.disable_hard_recovery = False

        # ── NEES tracking ──
        self.nees_values: list[float] = []
        self.nees_overconfident_count = 0
        self.nees_underconfident_count = 0
        self.nees_in_bounds_count = 0

        # ── Reset counter decomposition ──
        self.reset_stats = {
            "hard_gate_violations": 0,
            "reset_candidates": 0,
            "accepted_resets": 0,
            "rejected_by_confidence": 0,
            "rejected_by_lane": 0,
            "rejected_by_temporal": 0,
            "rejected_by_ttc": 0,
            "rejected_by_headway": 0,
            "total_soft_updates": 0,
            "total_normal_updates": 0,
            "total_hard_rejects": 0,
        }

        # ── Safety diagnostics (episode-level) ──
        self.min_ttc: float = float("inf")
        self.min_headway_s: float = float("inf")
        self.min_distance_m: float = float("inf")
        self.max_decel: float = 0.0
        self.stop_duration_frames: int = 0
        self.near_miss_events: int = 0
        self.lost_cause: str = "none"
        self.lost_detail: str = ""
        self.mode_duration_frames: dict[str, int] = defaultdict(int)

    # ── NEES computation ──
    def compute_nees(self, ground_truth_state: np.ndarray) -> float | None:
        """Compute NEES when CARLA ground truth is available.

        Args:
            ground_truth_state: [x, y, vx, vy] from CARLA actor ground truth

        Returns:
            NEES value or None if not initialized
        """
        if not self.is_initialized:
            return None
        err = ground_truth_state - self.x
        try:
            nees = float(err.T @ np.linalg.inv(self.P) @ err)
        except np.linalg.LinAlgError:
            return None

        self.last_nees = nees
        self.nees_values.append(nees)

        # Chi-squared (df=4): 95% = 9.488, 99% = 13.277
        chi2_4_95 = 9.488
        chi2_4_05 = 0.711

        if nees < chi2_4_05:
            self.nees_overconfident_count += 1
        elif nees > chi2_4_95:
            self.nees_underconfident_count += 1
        else:
            self.nees_in_bounds_count += 1

        return nees

    def get_nees_stats(self) -> dict:
        """Return NEES calibration summary."""
        n = len(self.nees_values)
        if n == 0:
            return {
                "nees_mean": float("nan"),
                "nees_p95": float("nan"),
                "nees_in_bounds_pct": float("nan"),
                "nees_overconfident_pct": float("nan"),
                "nees_underconfident_pct": float("nan"),
                "nees_samples": 0,
            }
        return {
            "nees_mean": float(np.mean(self.nees_values)),
            "nees_p95": float(np.percentile(self.nees_values, 95)),
            "nees_in_bounds_pct": self.nees_in_bounds_count / n * 100,
            "nees_overconfident_pct": self.nees_overconfident_count / n * 100,
            "nees_underconfident_pct": self.nees_underconfident_count / n * 100,
            "nees_samples": n,
        }

    def get_reset_stats(self) -> dict:
        """Return reset decomposition summary."""
        return dict(self.reset_stats)

    def get_safety_diagnostics(self) -> dict:
        """Return safety-availability diagnostics."""
        return {
            "min_ttc_s": self.min_ttc if self.min_ttc != float("inf") else None,
            "min_headway_s": (
                self.min_headway_s
                if self.min_headway_s != float("inf")
                else None
            ),
            "min_distance_m": (
                self.min_distance_m
                if self.min_distance_m != float("inf")
                else None
            ),
            "max_decel_ms2": self.max_decel,
            "stop_duration_s": self.stop_duration_frames * self.dt,
            "near_miss_events": self.near_miss_events,
            "lost_cause": self.lost_cause,
            "lost_detail": self.lost_detail,
            "mode_durations": dict(self.mode_duration_frames),
        }

    # ── Safety diagnostics update (call each frame from BatchEvaluator) ──
    def update_safety_diagnostics(
        self,
        ttc: float | None = None,
        headway_s: float | None = None,
        distance_m: float | None = None,
        decel_ms2: float | None = None,
        ego_speed_ms: float | None = None,
    ) -> None:
        """Record safety-critical values each frame."""
        if ttc is not None and ttc > 0 and ttc < self.min_ttc:
            self.min_ttc = ttc
        if headway_s is not None and headway_s > 0 and headway_s < self.min_headway_s:
            self.min_headway_s = headway_s
        if distance_m is not None and distance_m > 0 and distance_m < self.min_distance_m:
            self.min_distance_m = distance_m
        if decel_ms2 is not None and abs(decel_ms2) > abs(self.max_decel):
            self.max_decel = decel_ms2
        if ego_speed_ms is not None and ego_speed_ms < 0.1:
            self.stop_duration_frames += 1

    def set_lost_cause(
        self,
        cause: str,
        detail: str = "",
    ) -> None:
        """Record why the episode was Lost."""
        self.lost_cause = cause
        self.lost_detail = detail

    # ── Original API (identical to KalmanTracker) ──

    def update(self, measurement, confidence=1.0):
        if not self.is_initialized:
            self.x = measurement
            self.P = np.diag([1.0, 1.0, 100.0, 100.0])
            self.is_initialized = True
            self.lost_steps = 0
            self.last_nis = 0.0
            self.last_update_mode = "init"
            self.reset_stats["total_normal_updates"] += 1
            self.mode_duration_frames["init"] += 1
            return self.x

        current_R = self.R * (1.0 / (confidence + 1e-6))
        current_Q = self.Q * (1.0 + 5.0 * (1.0 - confidence))

        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + current_Q

        y = measurement - self.H @ self.x
        S = self.H @ self.P @ self.H.T + current_R
        nis = float(y.T @ np.linalg.inv(S) @ y)
        self.last_nis = nis

        if self.disable_nis_gating:
            K = self.P @ self.H.T @ np.linalg.inv(S)
            self.x = self.x + K @ y
            self.P = (np.eye(4) - K @ self.H) @ self.P
            self.lost_steps = 0
            self.last_update_mode = "normal"
            self.reset_stats["total_normal_updates"] += 1
            self.mode_duration_frames["normal"] += 1
            return self.x

        T_reset = 20.0
        T_reject = 12.0

        if nis > T_reset:
            self.reset_stats["hard_gate_violations"] += 1
            self.reset_stats["reset_candidates"] += 1

            if self.disable_hard_recovery:
                self.last_update_mode = "hard_reject"
                self.reset_stats["total_hard_rejects"] += 1
                self.mode_duration_frames["hard_reject"] += 1
            elif confidence > 0.8:
                self.x = measurement
                self.P = np.diag([1.0, 1.0, 100.0, 100.0])
                self.last_update_mode = "hard_reset"
                self.reset_stats["accepted_resets"] += 1
                self.mode_duration_frames["hard_reset"] += 1
            else:
                self.last_update_mode = "hard_reject"
                self.reset_stats["rejected_by_confidence"] += 1
                self.reset_stats["total_hard_rejects"] += 1
                self.mode_duration_frames["hard_reject"] += 1

        elif nis > T_reject:
            inflated_R = current_R * 10.0
            S_soft = self.H @ self.P @ self.H.T + inflated_R
            K = self.P @ self.H.T @ np.linalg.inv(S_soft)
            self.x = self.x + K @ y
            self.P = (np.eye(4) - K @ self.H) @ self.P
            self.last_update_mode = "soft"
            self.reset_stats["total_soft_updates"] += 1
            self.mode_duration_frames["soft"] += 1

        else:
            K = self.P @ self.H.T @ np.linalg.inv(S)
            self.x = self.x + K @ y
            self.P = (np.eye(4) - K @ self.H) @ self.P
            self.last_update_mode = "normal"
            self.reset_stats["total_normal_updates"] += 1
            self.mode_duration_frames["normal"] += 1

        self.lost_steps = 0
        return self.x

    def predict(self):
        if not self.is_initialized:
            return None
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        self.lost_steps += 1
        self.last_nis = float("nan")
        self.last_nees = float("nan")
        self.last_update_mode = "predict"
        self.mode_duration_frames["predict"] += 1
        return self.x

    def reset_diagnostics(self) -> None:
        """Reset per-episode diagnostic counters (call after each episode)."""
        self.nees_values.clear()
        self.nees_overconfident_count = 0
        self.nees_underconfident_count = 0
        self.nees_in_bounds_count = 0
        for k in self.reset_stats:
            self.reset_stats[k] = 0
        self.min_ttc = float("inf")
        self.min_headway_s = float("inf")
        self.min_distance_m = float("inf")
        self.max_decel = 0.0
        self.stop_duration_frames = 0
        self.near_miss_events = 0
        self.lost_cause = "none"
        self.lost_detail = ""
        self.mode_duration_frames.clear()


# ==============================================================================
# Safety-Availability Diagnostic Table Generator
# ==============================================================================


def load_episode_results(csv_path: str) -> list[dict]:
    """Load per-episode CSV and compute diagnostics."""
    import csv

    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def compute_safety_availability_table(
    summary_rows: list[dict],
) -> dict:
    """Compute the safety-availability diagnostic table from experiment data.

    Args:
        summary_rows: List of per-condition summary dicts with keys:
            method, condition, n, success_rate, lost_rate, collision_rate,
            near_miss_rate, min_ttc_p5, min_headway_p5, stop_duration_mean,
            max_decel, jerk_p95, lost_cause_distribution

    Returns:
        Dict with table rows and formatted LaTeX table body.
    """
    table_rows = []
    for row in summary_rows:
        table_rows.append(
            {
                "method": row.get("method", ""),
                "condition": row.get("condition", ""),
                "min_ttc_p5": row.get("min_ttc_p5", ""),
                "min_headway_p5": row.get("min_headway_p5", ""),
                "stop_duration_mean_s": row.get("stop_duration_mean_s", ""),
                "max_decel_ms2": row.get("max_decel_ms2", ""),
                "jerk_p95": row.get("jerk_p95", ""),
                "lost_cause_primary": row.get("lost_cause_primary", ""),
                "near_miss_rate": row.get("near_miss_rate", ""),
                "collision_rate": row.get("collision_rate", ""),
                "success_rate": row.get("success_rate", ""),
            }
        )
    return {"rows": table_rows}


def format_latex_safety_table(table_data: dict) -> str:
    """Format the safety-availability table as LaTeX."""
    rows = table_data["rows"]
    if not rows:
        return "% No data"

    header = (
        r"\begin{table}[t]"
        "\n"
        r"\caption{Safety--availability diagnostics.}"
        "\n"
        r"\label{tab:safety_availability}"
        "\n"
        r"\centering"
        "\n"
        r"\scriptsize"
        "\n"
        r"\begin{tabular}{l l c c c c c c c c}"
        "\n"
        r"\toprule"
        "\n"
        r"\textbf{Method} & \textbf{Condition} & \textbf{min TTC p5} & "
        r"\textbf{min headway p5} & \textbf{stop dur.} & "
        r"\textbf{max decel} & \textbf{jerk p95} & "
        r"\textbf{Lost cause} & \textbf{Near-miss} & \textbf{Collision} \\"
        "\n"
        r"\midrule"
        "\n"
    )

    body_lines = []
    for r in rows:
        body_lines.append(
            f"{r['method']} & {r['condition']} & "
            f"{r['min_ttc_p5']} & {r['min_headway_p5']} & "
            f"{r['stop_duration_mean_s']} & {r['max_decel_ms2']} & "
            f"{r['jerk_p95']} & {r['lost_cause_primary']} & "
            f"{r['near_miss_rate']} & {r['collision_rate']} \\\\"
        )

    footer = (
        r"\bottomrule"
        "\n"
        r"\end{tabular}"
        "\n"
        r"\end{table}"
        "\n"
    )

    return header + "\n".join(body_lines) + "\n" + footer


def compute_nees_calibration_table(
    nees_by_condition: list[dict],
) -> str:
    """Generate NIS/NEES calibration LaTeX table.

    Args:
        nees_by_condition: List of dicts with:
            condition, nis_mean, nis_p95, chi2_coverage_p95, chi2_coverage_p99,
            nees_mean, nees_p95, nees_in_bounds_pct, nees_over_pct, nees_under_pct

    Returns:
        LaTeX table body.
    """
    header = (
        r"\begin{table}[t]"
        "\n"
        r"\caption{NIS/NEES calibration diagnostic.}"
        "\n"
        r"\label{tab:nis_nees_calibration}"
        "\n"
        r"\centering"
        "\n"
        r"\scriptsize"
        "\n"
        r"\begin{tabular}{l c c c c c c c c}"
        "\n"
        r"\toprule"
        "\n"
        r"\textbf{Condition} & \textbf{NIS mean} & \textbf{NIS p95} & "
        r"\textbf{$\chi^2_2$ p95 cov.} & \textbf{$\chi^2_2$ p99 cov.} & "
        r"\textbf{NEES mean} & \textbf{NEES p95} & "
        r"\textbf{In-bounds \%} & \textbf{Over-conf. \%} \\"
        "\n"
        r"\midrule"
        "\n"
    )

    body_lines = []
    for r in nees_by_condition:
        body_lines.append(
            f"{r['condition']} & {r['nis_mean']} & {r['nis_p95']} & "
            f"{r['chi2_coverage_p95']} & {r['chi2_coverage_p99']} & "
            f"{r['nees_mean']} & {r['nees_p95']} & "
            f"{r['nees_in_bounds_pct']} & {r['nees_over_pct']} \\\\"
        )

    footer = r"\bottomrule" "\n" r"\end{tabular}" "\n" r"\end{table}" "\n"

    return header + "\n".join(body_lines) + "\n" + footer


def compute_reset_decomposition_table(
    reset_by_condition: list[dict],
) -> str:
    """Generate reset decomposition LaTeX table.

    Args:
        reset_by_condition: List of dicts with:
            condition, hard_gate_violations, reset_candidates, accepted_resets,
            rejected_by_confidence, rejected_by_lane, rejected_by_temporal,
            rejected_by_ttc, recovery_time_mean
    """
    header = (
        r"\begin{table}[t]"
        "\n"
        r"\caption{Reset counter decomposition.}"
        "\n"
        r"\label{tab:reset_decomposition}"
        "\n"
        r"\centering"
        "\n"
        r"\scriptsize"
        "\n"
        r"\begin{tabular}{l c c c c c c c c}"
        "\n"
        r"\toprule"
        "\n"
        r"\textbf{Condition} & \textbf{Violations} & \textbf{Candidates} & "
        r"\textbf{Accepted} & \textbf{Rej. conf.} & \textbf{Rej. lane} & "
        r"\textbf{Rej. temporal} & \textbf{Rej. TTC} & \textbf{Recovery s} \\"
        "\n"
        r"\midrule"
        "\n"
    )

    body_lines = []
    for r in reset_by_condition:
        body_lines.append(
            f"{r['condition']} & {r['hard_gate_violations']} & "
            f"{r['reset_candidates']} & {r['accepted_resets']} & "
            f"{r['rejected_by_confidence']} & {r['rejected_by_lane']} & "
            f"{r['rejected_by_temporal']} & {r['rejected_by_ttc']} & "
            f"{r['recovery_time_mean']} \\\\"
        )

    footer = r"\bottomrule" "\n" r"\end{tabular}" "\n" r"\end{table}" "\n"

    return header + "\n".join(body_lines) + "\n" + footer
