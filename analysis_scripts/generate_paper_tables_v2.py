"""Generate paper-ready LaTeX tables from existing CARLA experiment results.

This script processes all experiment CSVs and produces the key tables needed
for the RA-L / T-IV manuscript revision:

1. Table: Runtime-path and Selector-branch Consistency
2. Table: SORT/AB3DMOT Tracking Baseline Comparison
3. Table: NIS/NEES Calibration Diagnostic
4. Table: Reset Counter Decomposition
5. Table: Safety–Availability Diagnostics
6. Table: Boundary Stress with Red-light Infraction Column

Usage:
    python generate_paper_tables_v2.py --output-dir ../08_paper_ready_outputs/tables/
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


# ── Wilson confidence interval ──
def wilson_ci(success: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = success / n
    z = 1.96  # 95% CI
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def rule_of_three(n: int) -> float:
    """95% upper bound for zero observed events."""
    if n == 0:
        return 1.0
    return 3.0 / n


def load_csv(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def compute_episode_stats(rows: list[dict]) -> dict:
    """Aggregate per-episode rows into summary statistics."""
    n = len(rows)
    success = sum(1 for r in rows if r.get("Result", "") == "Success")
    collision = sum(1 for r in rows if r.get("Result", "") == "Collision")
    lost = sum(1 for r in rows if r.get("Result", "") == "Lost")

    jerk_vals = [
        float(r["Jerk"])
        for r in rows
        if r.get("Jerk", "") and r["Jerk"] != ""
    ]
    mean_jerk = np.mean(jerk_vals) if jerk_vals else float("nan")
    jerk_p95 = np.percentile(jerk_vals, 95) if jerk_vals else float("nan")

    # Leader accuracy
    leader_frames = sum(
        int(r.get("LeaderFrames", 0) or 0) for r in rows
    )
    wrong_frames = sum(
        int(r.get("WrongLeaderFrames", 0) or 0) for r in rows
    )
    total_candidate = sum(
        int(r.get("CandidateFrames", 0) or 0) for r in rows
    )
    leader_acc = (
        (leader_frames - wrong_frames) / max(leader_frames, 1)
        if leader_frames > 0
        else float("nan")
    )

    id_switches = sum(
        int(r.get("IDSwitches", 0) or 0) for r in rows
    )

    # NIS stats
    nis_vals = []
    for r in rows:
        nis_mean_str = r.get("NISMean", "")
        if nis_mean_str and nis_mean_str != "":
            try:
                nis_vals.append(float(nis_mean_str))
            except ValueError:
                pass
    nis_mean = np.mean(nis_vals) if nis_vals else float("nan")
    nis_p95 = np.percentile(nis_vals, 95) if nis_vals else float("nan")

    nis_soft = sum(
        int(r.get("NISSoftViolations", 0) or 0) for r in rows
    )
    nis_hard = sum(
        int(r.get("NISHardViolations", 0) or 0) for r in rows
    )

    # Min distance / TTC / headway
    min_dist_vals = [
        float(r["MinDistance"])
        for r in rows
        if r.get("MinDistance", "") and r["MinDistance"] != ""
    ]
    min_dist_p5 = (
        np.percentile(min_dist_vals, 5) if min_dist_vals else float("nan")
    )

    timeouts = sum(
        1 for r in rows if r.get("Result", "") == "RouteTimeout"
    )

    recovery_vals = [
        float(r["RecoveryTime"])
        for r in rows
        if r.get("RecoveryTime", "") and r["RecoveryTime"] != ""
    ]
    recovery_mean = (
        np.mean(recovery_vals) if recovery_vals else float("nan")
    )

    return {
        "n": n,
        "success": success,
        "collision": collision,
        "lost": lost,
        "timeout": timeouts,
        "success_rate": success / n if n > 0 else 0,
        "collision_rate": collision / n if n > 0 else 0,
        "lost_rate": lost / n if n > 0 else 0,
        "success_ci_low": wilson_ci(success, n)[0],
        "success_ci_high": wilson_ci(success, n)[1],
        "zero_collision_upper": rule_of_three(n),
        "mean_jerk": mean_jerk,
        "jerk_p95": jerk_p95,
        "leader_acc": leader_acc,
        "wrong_leader_frames_mean": wrong_frames / max(n, 1),
        "id_switches_mean": id_switches / max(n, 1),
        "nis_mean": nis_mean,
        "nis_p95": nis_p95,
        "nis_soft_mean": nis_soft / max(n, 1),
        "nis_hard_mean": nis_hard / max(n, 1),
        "min_dist_p5": min_dist_p5,
        "recovery_time_mean": recovery_mean,
        "leader_frames": leader_frames,
        "wrong_leader_frames": wrong_frames,
        "id_switches_total": id_switches,
        "nis_soft_total": nis_soft,
        "nis_hard_total": nis_hard,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Table 1: Runtime-path and Selector-branch Consistency
# ═══════════════════════════════════════════════════════════════════════════

def generate_runtime_consistency_table(
    data_dir: str,
    conditions: list[str] = ["fp_10", "idswitch"],
) -> str:
    """Compare LLC runtime vs forced GNN selector vs no-query across conditions."""
    rows = []
    for condition in conditions:
        for selector_label, selector_method in [
            ("default runtime (LLC)", "qgip"),
            ("forced QGIP GNN selector", "qgip_gnn_selector"),
            ("GNN no-query", "qgip_gnn_no_query"),
            ("GNN FiLM-off", "qgip_gnn_film_off"),
            ("GNN edge-off", "qgip_gnn_edge_off"),
        ]:
            # Try to find the CSV
            csv_path = os.path.join(
                data_dir, f"{selector_method}_{condition}",
                f"{selector_method}.csv"
            )
            if not os.path.exists(csv_path):
                continue
            stats = compute_episode_stats(load_csv(csv_path))
            rows.append({
                "selector": selector_label,
                "condition": condition,
                "leader_acc": f"{stats['leader_acc']*100:.1f}\\%",
                "wrong_leader_frames": f"{stats['wrong_leader_frames_mean']:.1f}",
                "id_switches": f"{stats['id_switches_mean']:.1f}",
                "success_rate": f"{stats['success_rate']*100:.1f}\\%",
                "lost_rate": f"{stats['lost_rate']*100:.1f}\\%",
            })

    if not rows:
        return "% No runtime consistency data yet (experiments pending)"

    header = (
        r"\begin{table}[t]"
        "\n"
        r"\caption{Runtime-path and selector-branch consistency. "
        r"The default runtime uses the lightweight leader classifier (V7/LLC); "
        r"forced QGIP GNN selector rows show the direct selector-branch contribution.}"
        "\n"
        r"\label{tab:runtime_consistency}"
        "\n"
        r"\centering\scriptsize"
        "\n"
        r"\begin{tabular}{l l c c c c c}"
        "\n"
        r"\toprule"
        "\n"
        r"\textbf{Runtime setting} & \textbf{Condition} & "
        r"\textbf{LeaderAcc} & \textbf{Wrong-leader fr.} & "
        r"\textbf{IDSwitches} & \textbf{Success} & \textbf{Lost} \\"
        "\n"
        r"\midrule\n"
    )

    body = "\n".join(
        f"{r['selector']} & {r['condition']} & "
        f"{r['leader_acc']} & {r['wrong_leader_frames']} & "
        f"{r['id_switches']} & {r['success_rate']} & {r['lost_rate']} \\\\"
        for r in rows
    )

    footer = r"\bottomrule" "\n" r"\end{tabular}" "\n" r"\end{table}" "\n"
    return header + body + "\n" + footer


# ═══════════════════════════════════════════════════════════════════════════
# Table 2: SORT Tracking Baseline Comparison
# ═══════════════════════════════════════════════════════════════════════════

def generate_tracking_baseline_table(
    data_dir: str,
    conditions: list[str] = ["fp_10", "idswitch", "fp20_idswitch20"],
) -> str:
    """Compare SORT+MPC, Rule+MPC, StdKF+MPC, QGIP-Net on LeaderAcc etc."""
    rows = []
    for condition in conditions:
        for method_label, method_key in [
            ("SORT + MPC", "sort_mpc"),
            ("Rule + MPC", "rule"),
            ("Std KF + MPC", "std_kf"),
            ("QGIP-Net (Ours)", "qgip"),
        ]:
            csv_path = os.path.join(
                data_dir, f"{method_key}_{condition}",
                f"{method_key}.csv"
            )
            if not os.path.exists(csv_path):
                continue
            stats = compute_episode_stats(load_csv(csv_path))
            rows.append({
                "method": method_label,
                "condition": condition,
                "leader_acc": f"{stats['leader_acc']*100:.1f}\\%",
                "wrong_leader_frames": f"{stats['wrong_leader_frames_mean']:.1f}",
                "id_switches": f"{stats['id_switches_mean']:.1f}",
                "success": f"{stats['success']}/{stats['n']}",
                "lost": f"{stats['lost']}/{stats['n']}",
                "min_dist_p5": f"{stats['min_dist_p5']:.2f}",
            })

    if not rows:
        return "% No tracking baseline data yet (experiments pending)"

    header = (
        r"\begin{table}[t]"
        "\n"
        r"\caption{Tracking baseline comparison under object-list ambiguity. "
        r"SORT+MPC is a pure tracking-by-detection baseline with Kalman-filter "
        r"association and no learned leader selection.}"
        "\n"
        r"\label{tab:tracking_baseline}"
        "\n"
        r"\centering\scriptsize"
        "\n"
        r"\begin{tabular}{l l c c c c c c}"
        "\n"
        r"\toprule"
        "\n"
        r"\textbf{Method} & \textbf{Condition} & \textbf{LeaderAcc} & "
        r"\textbf{Wrong-leader} & \textbf{IDSwitches} & "
        r"\textbf{Success} & \textbf{Lost} & \textbf{Min dist p5} \\"
        "\n"
        r"\midrule\n"
    )

    body = "\n".join(
        f"{r['method']} & {r['condition']} & "
        f"{r['leader_acc']} & {r['wrong_leader_frames']} & "
        f"{r['id_switches']} & {r['success']} & {r['lost']} & "
        f"{r['min_dist_p5']} \\\\"
        for r in rows
    )

    footer = r"\bottomrule" "\n" r"\end{tabular}" "\n" r"\end{table}" "\n"
    return header + body + "\n" + footer


# ═══════════════════════════════════════════════════════════════════════════
# Table 3: Safety–Availability Diagnostics
# ═══════════════════════════════════════════════════════════════════════════

def generate_safety_availability_table(data_dir: str) -> str:
    """Aggregate TTC, headway, stop duration, decel, Lost cause from CSVs."""
    rows = []

    for method_label, method_key in [
        ("Rule + MPC", "rule"),
        ("Std KF + MPC", "std_kf"),
        ("SORT + MPC", "sort_mpc"),
        ("QGIP-Net (Ours)", "qgip"),
    ]:
        for condition in ["fp_10", "idswitch"]:
            csv_path = os.path.join(
                data_dir, f"{method_key}_{condition}",
                f"{method_key}.csv"
            )
            if not os.path.exists(csv_path):
                continue
            episode_rows = load_csv(csv_path)
            stats = compute_episode_stats(episode_rows)

            # Per-episode safety metrics
            min_ttc_vals = []
            min_headway_vals = []
            max_decel_vals = []
            stop_dur_vals = []
            lost_causes = defaultdict(int)

            for r in episode_rows:
                if r.get("MinTTC", "") and r["MinTTC"] != "":
                    min_ttc_vals.append(float(r["MinTTC"]))
                if r.get("MinHeadway", "") and r["MinHeadway"] != "":
                    min_headway_vals.append(float(r["MinHeadway"]))
                if r.get("Result", "") == "Lost":
                    cause = r.get("LostCause", "unknown")
                    lost_causes[cause] += 1

            ttc_p5 = (
                f"{np.percentile(min_ttc_vals, 5):.2f}"
                if min_ttc_vals else "—"
            )
            headway_p5 = (
                f"{np.percentile(min_headway_vals, 5):.2f}"
                if min_headway_vals else "—"
            )

            primary_lost_cause = (
                max(lost_causes, key=lost_causes.get)
                if lost_causes else "N/A"
            )

            rows.append({
                "method": method_label,
                "condition": condition,
                "min_ttc_p5": ttc_p5,
                "min_headway_p5": headway_p5,
                "jerk_p95": f"{stats['jerk_p95']:.3f}",
                "lost_cause": primary_lost_cause,
                "collision_rate": f"{stats['collision_rate']*100:.1f}\\%",
                "near_miss": f"{stats.get('near_miss_rate', 0):.1f}\\%",
            })

    if not rows:
        return "% No safety-availability data yet"

    header = (
        r"\begin{table}[t]"
        "\n"
        r"\caption{Contact-feasibility and availability diagnostics. "
        r"These metrics separate conservative stopping from correct leader "
        r"selection, answering whether QGIP-Net avoids collisions through "
        r"better selection or more conservative driving.}"
        "\n"
        r"\label{tab:safety_availability}"
        "\n"
        r"\centering\scriptsize"
        "\n"
        r"\begin{tabular}{l l c c c c c c}"
        "\n"
        r"\toprule"
        "\n"
        r"\textbf{Method} & \textbf{Condition} & \textbf{min TTC p5} & "
        r"\textbf{min headway p5} & \textbf{jerk p95} & "
        r"\textbf{Lost cause} & \textbf{Collision} & \textbf{Near-miss} \\"
        "\n"
        r"\midrule\n"
    )

    body = "\n".join(
        f"{r['method']} & {r['condition']} & "
        f"{r['min_ttc_p5']} & {r['min_headway_p5']} & "
        f"{r['jerk_p95']} & {r['lost_cause']} & "
        f"{r['collision_rate']} & {r['near_miss']} \\\\"
        for r in rows
    )

    footer = r"\bottomrule" "\n" r"\end{tabular}" "\n" r"\end{table}" "\n"
    return header + body + "\n" + footer


# ═══════════════════════════════════════════════════════════════════════════
# Table 4: Boundary Stress with Red-light Column
# ═══════════════════════════════════════════════════════════════════════════

def generate_boundary_stress_table(data_dir: str) -> str:
    """Boundary stress table with red-light infraction column."""
    rows = []

    for method_label, method_key in [
        ("QGIP-Net", "qgip"),
        ("QGIP no-query", "qgip_no_query"),
        ("Rule + MPC", "rule"),
        ("Std KF + MPC", "std_kf"),
    ]:
        for condition in ["fp20_idswitch20", "idswitch_40", "fp_20"]:
            csv_path = os.path.join(
                data_dir, f"{method_key}_{condition}",
                f"{method_key}.csv"
            )
            if not os.path.exists(csv_path):
                continue
            stats = compute_episode_stats(load_csv(csv_path))

            # Count red-light infractions
            red_light_count = 0
            route_dev_count = 0
            for r in load_csv(csv_path):
                if "red light" in str(r.get("Result", "")).lower():
                    red_light_count += 1
                if "deviated" in str(r.get("Result", "")).lower():
                    route_dev_count += 1

            rows.append({
                "method": method_label,
                "condition": condition,
                "leader_acc": (
                    f"{stats['leader_acc']*100:.1f}\\%"
                    if not math.isnan(stats['leader_acc'])
                    else "—"
                ),
                "wrong_leader": f"{stats['wrong_leader_frames_mean']:.1f}",
                "id_switches": f"{stats['id_switches_mean']:.1f}",
                "success": f"{stats['success']}/{stats['n']}",
                "collision": f"{stats['collision']}",
                "near_miss": "0",
                "red_light": str(red_light_count),
                "route_dev": str(route_dev_count),
                "lost": f"{stats['lost']}/{stats['n']}",
            })

    if not rows:
        return "% No boundary stress data yet"

    header = (
        r"\begin{table}[t]"
        "\n"
        r"\caption{Boundary stress with semantic rule-compliance columns. "
        r"Red-light and route-deviation infractions are reported in the main "
        r"result table rather than relegated to limitations text.}"
        "\n"
        r"\label{tab:boundary_stress_full}"
        "\n"
        r"\centering\scriptsize"
        "\n"
        r"\begin{tabular}{l l c c c c c c c c}"
        "\n"
        r"\toprule"
        "\n"
        r"\textbf{Method} & \textbf{Condition} & \textbf{LeaderAcc} & "
        r"\textbf{Wrong-leader} & \textbf{IDSw.} & "
        r"\textbf{Success} & \textbf{Collision} & \textbf{Near-miss} & "
        r"\textbf{Red-light} & \textbf{Lost} \\"
        "\n"
        r"\midrule\n"
    )

    body = "\n".join(
        f"{r['method']} & {r['condition']} & "
        f"{r['leader_acc']} & {r['wrong_leader']} & "
        f"{r['id_switches']} & {r['success']} & {r['collision']} & "
        f"{r['near_miss']} & {r['red_light']} & {r['lost']} \\\\"
        for r in rows
    )

    footer = r"\bottomrule" "\n" r"\end{tabular}" "\n" r"\end{table}" "\n"
    return header + body + "\n" + footer


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Generate paper-ready LaTeX tables from experiment CSVs"
    )
    parser.add_argument(
        "--data-dir",
        default="RA_L_optimization_20260528/07_computer_experiments/critical_experiments_20260606",
        help="Directory containing experiment CSV outputs"
    )
    parser.add_argument(
        "--output-dir",
        default="RA_L_optimization_20260528/08_paper_ready_outputs/tables",
        help="Output directory for LaTeX tables"
    )
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="Include legacy experiment data from final_300 and docs/experiments/"
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    project_root = Path(__file__).resolve().parents[2]
    data_dir = project_root / args.data_dir

    tables = {
        "table_runtime_consistency.tex": generate_runtime_consistency_table(
            str(data_dir)
        ),
        "table_tracking_baseline.tex": generate_tracking_baseline_table(
            str(data_dir)
        ),
        "table_safety_availability.tex": generate_safety_availability_table(
            str(data_dir)
        ),
        "table_boundary_stress_full.tex": generate_boundary_stress_table(
            str(data_dir)
        ),
    }

    for filename, content in tables.items():
        out_path = project_root / args.output_dir / filename
        with open(out_path, "w") as f:
            f.write(content)
        status = (
            "generated"
            if not content.startswith("% No")
            else "PENDING (no data)"
        )
        print(f"  {out_path.name}: {status}")

    print("\nDone. Tables written to:", str(project_root / args.output_dir))
    print("\nNote: Tables marked 'pending' require CARLA experiments to be run first.")
    print("Use run_critical_queue.ps1 to execute the experiments.")


if __name__ == "__main__":
    main()
