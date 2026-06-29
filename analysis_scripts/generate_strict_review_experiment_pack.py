#!/usr/bin/env python3
"""Build the strict-review experiment supplement.

This script does not fabricate experiment results. It consolidates completed
CARLA CSVs, emits paper-ready summary tables, and writes explicit queues for
the remaining CARLA-dependent experiments requested by strict reviewers:

- contribution ablations;
- NIS threshold sensitivity and calibration diagnostics;
- dynamic ambiguity scenarios;
- rendered-sensor-like weather/degradation profiles.

After new CARLA runs finish, rerun this script to refresh the source-data
tables and the audit report.
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "RA_L_optimization_20260528"
EXP = PROJECT / "07_computer_experiments"
OUT = PROJECT / "08_paper_ready_outputs"
SRC = OUT / "source_data"
TABLES = OUT / "tables"
SUB = PROJECT / "06_submission_package"
RUNNER = PROJECT / "04_simulation_stress" / "run_carla_batch.py"


COMPLETED_SOURCES = [
    {
        "condition_id": "fp_10",
        "method": "qgip",
        "label": "QGIP-Net",
        "path": EXP / "carla_stress_paired_metrics300" / "paper" / "fp_10" / "qgip.csv",
    },
    {
        "condition_id": "fp_10",
        "method": "qgip_no_query",
        "label": "QGIP no-query",
        "path": EXP / "carla_stress_paired_metrics300" / "paper" / "fp_10" / "qgip_no_query.csv",
    },
    {
        "condition_id": "fp_10",
        "method": "rule",
        "label": "Rule + MPC",
        "path": EXP / "carla_stress_paired_metrics300" / "paper" / "fp_10" / "rule.csv",
    },
    {
        "condition_id": "fp_10",
        "method": "sort_mpc",
        "label": "SORT + MPC",
        "path": EXP / "critical_experiments_20260606" / "sort_mpc_fp10" / "sort_mpc.csv",
    },
    {
        "condition_id": "fp_10",
        "method": "qgip_gnn_selector",
        "label": "Forced QGIP GNN selector",
        "path": EXP / "critical_experiments_20260606" / "gnn_selector_fp10" / "gnn_selector.csv",
    },
    {
        "condition_id": "idswitch",
        "method": "qgip",
        "label": "QGIP-Net",
        "path": EXP / "carla_stress_paired_metrics300" / "paper" / "idswitch" / "qgip.csv",
    },
    {
        "condition_id": "idswitch",
        "method": "std_kf",
        "label": "Std KF + MPC",
        "path": EXP / "carla_stress_paired_metrics300" / "paper" / "idswitch" / "std_kf.csv",
    },
    {
        "condition_id": "idswitch",
        "method": "rule",
        "label": "Rule + MPC",
        "path": EXP / "carla_stress_paired_metrics300" / "paper" / "idswitch" / "rule.csv",
    },
    {
        "condition_id": "idswitch",
        "method": "sort_mpc",
        "label": "SORT + MPC",
        "path": EXP / "critical_experiments_20260606" / "sort_mpc_idswitch" / "sort_mpc.csv",
    },
]


DYNAMIC_CONDITIONS = [
    {
        "condition_id": "hard_brake",
        "scenario_profile": "hard_brake",
        "fault_args": "--false-negative-rate 0.20 --delay-ms 50",
        "episodes": 300,
        "methods": ["qgip", "std_kf", "imm_kf", "sort_mpc"],
        "primary_metrics": "min_ttc;min_headway;near_miss;recovery_time;lost",
    },
    {
        "condition_id": "cut_in",
        "scenario_profile": "cut_in",
        "fault_args": "--ambiguity-test --false-positive-rate 0.15 --id-switch-probability 0.10",
        "episodes": 300,
        "methods": ["qgip", "qgip_no_query", "qgip_gnn_selector", "sort_mpc", "rule"],
        "primary_metrics": "leaderacc;wrong_leader_frames;id_switches;near_miss",
    },
    {
        "condition_id": "cut_out",
        "scenario_profile": "cut_out",
        "fault_args": "--ambiguity-test --false-negative-rate 0.50",
        "episodes": 300,
        "methods": ["qgip", "qgip_no_ghost", "qgip_last_hold", "std_kf", "imm_kf"],
        "primary_metrics": "recovery_time;lost;nis_violations;wrong_leader_frames",
    },
    {
        "condition_id": "curve_following",
        "scenario_profile": "curve_following",
        "fault_args": "--observation-noise 0.5 --false-negative-rate 0.15",
        "episodes": 300,
        "methods": ["qgip", "std_kf", "imm_kf", "sort_mpc"],
        "primary_metrics": "leaderacc;min_headway;near_miss;lost",
    },
    {
        "condition_id": "merge_like",
        "scenario_profile": "merge",
        "fault_args": "--ambiguity-test --false-positive-rate 0.20 --id-switch-probability 0.15",
        "episodes": 300,
        "methods": ["qgip", "qgip_no_query", "sort_mpc", "rule"],
        "primary_metrics": "leaderacc;id_switches;wrong_leader_frames;near_miss",
    },
    {
        "condition_id": "wrong_query",
        "scenario_profile": "wrong_query",
        "fault_args": "--ambiguity-test --query-profile wrong_right --false-positive-rate 0.10",
        "episodes": 100,
        "methods": ["qgip", "qgip_no_query", "sort_mpc"],
        "primary_metrics": "wrong_query_sensitivity;leaderacc;wrong_leader_frames",
    },
    {
        "condition_id": "delayed_query",
        "scenario_profile": "delayed_query",
        "fault_args": "--ambiguity-test --query-profile change_left --query-delay-frames 80 --false-positive-rate 0.10",
        "episodes": 100,
        "methods": ["qgip", "qgip_no_query", "sort_mpc"],
        "primary_metrics": "delayed_query_recovery;leaderacc;id_switches",
    },
]


THRESHOLD_CONDITIONS = [
    {"condition_id": "nis_gate_06_12_noise05", "soft": 6.0, "hard": 12.0, "noise": 0.5, "episodes": 100},
    {"condition_id": "nis_gate_09_15_noise05", "soft": 9.0, "hard": 15.0, "noise": 0.5, "episodes": 100},
    {"condition_id": "nis_gate_12_20_noise05", "soft": 12.0, "hard": 20.0, "noise": 0.5, "episodes": 100},
    {"condition_id": "nis_gate_20_30_noise05", "soft": 20.0, "hard": 30.0, "noise": 0.5, "episodes": 100},
    {"condition_id": "nis_gate_12_20_noise10", "soft": 12.0, "hard": 20.0, "noise": 1.0, "episodes": 100},
]


SENSOR_CONDITIONS = [
    {
        "condition_id": "weather_glare_detector",
        "weather": "glare",
        "sensor": "camera_glare",
        "episodes": 100,
        "methods": ["qgip", "detector_tracker"],
        "primary_metrics": "leaderacc;lost;recovery_time;nis_violations",
    },
    {
        "condition_id": "weather_low_light_detector",
        "weather": "low_light",
        "sensor": "low_light",
        "episodes": 100,
        "methods": ["qgip", "detector_tracker"],
        "primary_metrics": "leaderacc;lost;false_negative_frames",
    },
    {
        "condition_id": "lidar_dropout_detector",
        "weather": "fog",
        "sensor": "lidar_dropout",
        "episodes": 100,
        "methods": ["qgip", "detector_tracker"],
        "primary_metrics": "lost;leaderacc;recovery_time",
    },
]


def main() -> None:
    SRC.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    SUB.mkdir(parents=True, exist_ok=True)

    completed = build_completed_summary()
    ablation = build_ablation_summary()
    nis = build_nis_summary()
    pairwise = build_pairwise_stats()
    dynamic_queue = build_dynamic_queue()
    threshold_queue = build_threshold_queue()
    sensor_queue = build_sensor_queue()
    dynamic_summary = summarize_queue_results(dynamic_queue)
    threshold_summary = summarize_queue_results(threshold_queue)
    sensor_summary = summarize_queue_results(sensor_queue)

    write_csv(SRC / "strict_completed_baseline_summary_20260608.csv", completed)
    write_csv(SRC / "strict_component_ablation_summary_20260608.csv", ablation)
    write_csv(SRC / "strict_nis_calibration_summary_20260608.csv", nis)
    write_csv(SRC / "strict_pairwise_stats_20260608.csv", pairwise)
    write_csv(SRC / "strict_dynamic_scenario_queue_20260608.csv", dynamic_queue)
    write_csv(SRC / "strict_nis_threshold_sensitivity_queue_20260608.csv", threshold_queue)
    write_csv(SRC / "strict_rendered_sensor_like_queue_20260608.csv", sensor_queue)
    write_csv(SRC / "strict_dynamic_scenario_summary_20260608.csv", dynamic_summary)
    write_csv(SRC / "strict_nis_threshold_sensitivity_summary_20260608.csv", threshold_summary)
    write_csv(SRC / "strict_rendered_sensor_like_summary_20260608.csv", sensor_summary)
    write_csv(PROJECT / "04_simulation_stress" / "strict_dynamic_scenario_queue_20260608.csv", dynamic_queue)
    write_csv(PROJECT / "04_simulation_stress" / "strict_nis_threshold_sensitivity_queue_20260608.csv", threshold_queue)
    write_csv(PROJECT / "04_simulation_stress" / "strict_rendered_sensor_like_queue_20260608.csv", sensor_queue)

    write_completed_table(completed)
    write_ablation_table(ablation)
    write_nis_table(nis)
    write_pairwise_table(pairwise)
    write_dynamic_results_table(dynamic_summary)
    write_threshold_results_table(threshold_summary)
    write_sensor_results_table(sensor_summary)
    write_runner(SUB / "run_strict_review_queues_20260608.ps1", dynamic_queue + threshold_queue + sensor_queue)
    write_report(completed, ablation, nis, pairwise, dynamic_queue, threshold_queue, sensor_queue)
    print("Wrote strict-review experiment pack.")


def build_completed_summary() -> list[dict[str, object]]:
    rows = []
    for spec in COMPLETED_SOURCES:
        summary = summarize_episode_csv(spec["path"])
        row = {
            "condition_id": spec["condition_id"],
            "method": spec["method"],
            "label": spec["label"],
            "source_csv": str(spec["path"]),
            "status": "complete" if spec["path"].exists() else "missing",
        }
        row.update(summary)
        rows.append(row)
    return rows


def build_ablation_summary() -> list[dict[str, object]]:
    path = EXP / "component_ablation_20260605" / "paper_scale_metrics_20260605.csv"
    if not path.exists():
        return []
    rows = []
    for row in read_csv(path):
        rows.append(
            {
                "run_id": row["run_id"],
                "method": row["method"],
                "episodes": row["episodes"],
                "success": row["success"],
                "collision": row["collision"],
                "lost": row["lost"],
                "leader_acc": safe_float(row.get("leaderacc_mean")),
                "wrong_leader_frame_rate": safe_float(row.get("wrong_leader_frame_rate")),
                "wrong_leader_frames_total": safe_float(row.get("wrong_leader_frames_total")),
                "id_switches_total": safe_float(row.get("id_switches_total")),
                "id_switches_per_episode": safe_float(row.get("id_switches_total")) / max(1.0, safe_float(row.get("episodes"))),
                "nis_weighted_mean": safe_float(row.get("nis_weighted_mean")),
                "nis_soft_violations_total": safe_float(row.get("nis_soft_violations_total")),
                "nis_hard_violations_total": safe_float(row.get("nis_hard_violations_total")),
                "kf_hard_resets_total": safe_float(row.get("kf_hard_resets_total")),
                "kf_hard_rejects_total": safe_float(row.get("kf_hard_rejects_total")),
                "status": row.get("status", ""),
            }
        )
    return rows


def build_nis_summary() -> list[dict[str, object]]:
    candidates = [
        EXP / "carla_nis_diagnostic100" / "nis_noise_sweep_qgip100_summary.csv",
        EXP / "carla_nis_outlier100" / "nis_outlier_qgip100_summary.csv",
    ]
    rows = []
    for path in candidates:
        if not path.exists():
            continue
        for row in read_csv(path):
            out = {"source_csv": str(path)}
            out.update(row)
            rows.append(out)
    return rows


def build_pairwise_stats() -> list[dict[str, object]]:
    grouped: dict[str, dict[str, Path]] = {}
    for spec in COMPLETED_SOURCES:
        if not spec["path"].exists():
            continue
        grouped.setdefault(spec["condition_id"], {})[spec["method"]] = spec["path"]

    rows = []
    for condition_id, methods in sorted(grouped.items()):
        ref_path = methods.get("qgip")
        if ref_path is None:
            continue
        ref_rows = episode_map(read_csv(ref_path))
        for method, path in sorted(methods.items()):
            if method == "qgip":
                continue
            cmp_rows = episode_map(read_csv(path))
            episodes = sorted(set(ref_rows) & set(cmp_rows), key=lambda value: int(value))
            pairs_ref = [ref_rows[ep] for ep in episodes]
            pairs_cmp = [cmp_rows[ep] for ep in episodes]
            out = {
                "condition_id": condition_id,
                "reference_method": "qgip",
                "comparison_method": method,
                "paired_n": len(episodes),
            }
            for metric in ["LeaderAcc", "WrongLeaderFrames", "IDSwitches"]:
                diffs = paired_diffs(pairs_ref, pairs_cmp, metric)
                low, high = bootstrap_ci(diffs, seed=20260608 + len(rows))
                out[f"{metric.lower()}_diff_qgip_minus_cmp"] = mean(diffs) if diffs else ""
                out[f"{metric.lower()}_ci95_low"] = low
                out[f"{metric.lower()}_ci95_high"] = high
            out["success_diff_qgip_minus_cmp"] = rate_result(pairs_ref, "Success") - rate_result(pairs_cmp, "Success")
            out["lost_diff_qgip_minus_cmp"] = rate_result(pairs_ref, "Lost") - rate_result(pairs_cmp, "Lost")
            rows.append(out)
    return rows


def build_dynamic_queue() -> list[dict[str, object]]:
    rows = []
    for condition in DYNAMIC_CONDITIONS:
        for method in condition["methods"]:
            out_csv = EXP / "strict_review_20260608" / "dynamic" / condition["condition_id"] / f"{method}.csv"
            command = [
                "python",
                str(RUNNER),
                "--method",
                method,
                "--episodes",
                str(condition["episodes"]),
                "--scenario-profile",
                condition["scenario_profile"],
                "--out",
                str(out_csv),
            ]
            command.extend(condition["fault_args"].split())
            rows.append(queue_row(condition["condition_id"], method, condition["episodes"], out_csv, command, condition["primary_metrics"]))
    return rows


def build_threshold_queue() -> list[dict[str, object]]:
    rows = []
    for condition in THRESHOLD_CONDITIONS:
        out_csv = EXP / "strict_review_20260608" / "nis_threshold" / condition["condition_id"] / "qgip.csv"
        command = [
            "python",
            str(RUNNER),
            "--method",
            "qgip",
            "--episodes",
            str(condition["episodes"]),
            "--observation-noise",
            str(condition["noise"]),
            "--nis-soft-gate",
            str(condition["soft"]),
            "--nis-hard-gate",
            str(condition["hard"]),
            "--out",
            str(out_csv),
        ]
        rows.append(queue_row(condition["condition_id"], "qgip", condition["episodes"], out_csv, command, "nis_violations;lost;near_miss;recovery_time"))
    return rows


def build_sensor_queue() -> list[dict[str, object]]:
    rows = []
    for condition in SENSOR_CONDITIONS:
        for method in condition["methods"]:
            out_csv = EXP / "strict_review_20260608" / "sensor_like" / condition["condition_id"] / f"{method}.csv"
            command = [
                "python",
                str(RUNNER),
                "--method",
                method,
                "--episodes",
                str(condition["episodes"]),
                "--weather-profile",
                condition["weather"],
                "--sensor-profile",
                condition["sensor"],
                "--out",
                str(out_csv),
            ]
            rows.append(queue_row(condition["condition_id"], method, condition["episodes"], out_csv, command, condition["primary_metrics"]))
    return rows


def queue_row(condition_id: str, method: str, episodes: int, out_csv: Path, command: list[str], primary_metrics: str) -> dict[str, object]:
    observed_rows = count_rows(out_csv)
    if not out_csv.exists():
        status = "pending"
    elif observed_rows >= episodes:
        status = "complete"
    else:
        status = "partial"
    return {
        "queue_id": f"{condition_id}__{method}",
        "condition_id": condition_id,
        "method": method,
        "episodes": episodes,
        "output_csv": str(out_csv),
        "command": " ".join(quote_arg(item) for item in command),
        "primary_metrics": primary_metrics,
        "status": status,
        "observed_rows": observed_rows,
    }


def summarize_queue_results(queue_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for queue in queue_rows:
        output_csv = Path(str(queue["output_csv"]))
        summary = summarize_episode_csv(output_csv)
        row = {
            "queue_id": queue["queue_id"],
            "condition_id": queue["condition_id"],
            "method": queue["method"],
            "episodes": queue["episodes"],
            "observed_rows": queue["observed_rows"],
            "status": queue["status"],
            "source_csv": str(output_csv),
            "primary_metrics": queue["primary_metrics"],
        }
        row.update(summary)
        rows.append(row)
    return rows


def summarize_episode_csv(path: Path) -> dict[str, object]:
    if not path.exists():
        return empty_summary()
    rows = read_csv(path)
    n = len(rows)
    success = count_result(rows, "Success")
    collision = count_result(rows, "Collision")
    lost = count_result(rows, "Lost")
    leader_frames = sum_int(rows, "LeaderFrames")
    wrong_frames = sum_int(rows, "WrongLeaderFrames")
    id_switches = sum_int(rows, "IDSwitches")
    nis_frames = sum_int(rows, "NISFrames")
    near_miss = sum(1 for row in rows if str(row.get("NearMiss", "")).strip() in {"1", "true", "True"})
    nis_mean_weighted = weighted_mean(rows, "NISMean", "NISFrames")
    leader_acc = (leader_frames - wrong_frames) / leader_frames if leader_frames > 0 else ""
    return {
        "n": n,
        "success_count": success,
        "success_rate": success / n if n else "",
        "collision_count": collision,
        "collision_rate": collision / n if n else "",
        "zero_collision_rule3_upper": 3.0 / n if n and collision == 0 else "",
        "lost_count": lost,
        "lost_rate": lost / n if n else "",
        "near_miss_count": near_miss,
        "near_miss_rate": near_miss / n if n else "",
        "leader_acc": leader_acc,
        "wrong_leader_frames_mean": wrong_frames / n if n else "",
        "id_switches_mean": id_switches / n if n else "",
        "dropout_frames_mean": sum_int(rows, "DropoutFrames") / n if n else "",
        "recovery_time_mean": mean_float(rows, "RecoveryTime"),
        "false_positive_frames_mean": sum_int(rows, "FalsePositiveFrames") / n if n else "",
        "false_negative_frames_mean": sum_int(rows, "FalseNegativeFrames") / n if n else "",
        "nis_mean_weighted": nis_mean_weighted,
        "nis_p95_episode_mean": mean_float(rows, "NISP95"),
        "nis_soft_violations_mean": sum_int(rows, "NISSoftViolations") / n if n else "",
        "nis_hard_violations_mean": sum_int(rows, "NISHardViolations") / n if n else "",
        "min_distance_p5": percentile([safe_float(row.get("MinDistance")) for row in rows if row.get("MinDistance")], 5),
        "min_ttc_p5": percentile([safe_float(row.get("MinTTC")) for row in rows if row.get("MinTTC")], 5),
        "min_headway_p5": percentile([safe_float(row.get("MinHeadway")) for row in rows if row.get("MinHeadway")], 5),
    }


def empty_summary() -> dict[str, object]:
    keys = [
        "n",
        "success_count",
        "success_rate",
        "collision_count",
        "collision_rate",
        "zero_collision_rule3_upper",
        "lost_count",
        "lost_rate",
        "near_miss_count",
        "near_miss_rate",
        "leader_acc",
        "wrong_leader_frames_mean",
        "id_switches_mean",
        "dropout_frames_mean",
        "recovery_time_mean",
        "false_positive_frames_mean",
        "false_negative_frames_mean",
        "nis_mean_weighted",
        "nis_p95_episode_mean",
        "nis_soft_violations_mean",
        "nis_hard_violations_mean",
        "min_distance_p5",
        "min_ttc_p5",
        "min_headway_p5",
    ]
    return {key: "" for key in keys}


def write_completed_table(rows: list[dict[str, object]]) -> None:
    lines = [
        "\\begin{tabular}{llrrrrr}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{Method} & \\textbf{N} & \\textbf{LeaderAcc} & \\textbf{Wrong-leader} & \\textbf{IDSwitch} & \\textbf{Succ./Lost} \\\\",
        "\\midrule",
    ]
    for row in rows:
        if row["status"] != "complete":
            continue
        lines.append(
            f"{row['condition_id']} & {row['label']} & {row['n']} & "
            f"{fmt_pct(row['leader_acc'])} & {fmt_num(row['wrong_leader_frames_mean'])} & "
            f"{fmt_num(row['id_switches_mean'])} & {fmt_pct(row['success_rate'])}/{fmt_pct(row['lost_rate'])} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLES / "table_strict_completed_baselines_20260608.tex").write_text("\n".join(lines), encoding="utf-8")


def write_ablation_table(rows: list[dict[str, object]]) -> None:
    lines = [
        "\\begin{tabular}{lrrrrr}",
        "\\toprule",
        "\\textbf{Variant} & \\textbf{N} & \\textbf{Wrong-leader rate} & \\textbf{IDSwitch/ep} & \\textbf{NIS mean} & \\textbf{Hard reset} \\\\",
        "\\midrule",
    ]
    selected = [
        "full_stack_lane_gate",
        "no_lane_gate",
        "gnn_selector",
        "gnn_film_off",
        "gnn_edge_off",
        "pop_ghost_off",
        "hard_recovery_off",
        "nis_off",
        "mpc_filter_off",
    ]
    by_id = {row["run_id"]: row for row in rows}
    for run_id in selected:
        row = by_id.get(run_id)
        if not row:
            continue
        lines.append(
            f"{run_id.replace('_', '\\_')} & {row['episodes']} & "
            f"{fmt_pct(row['wrong_leader_frame_rate'])} & {fmt_num(row['id_switches_per_episode'])} & "
            f"{fmt_num(row['nis_weighted_mean'])} & {fmt_num(row['kf_hard_resets_total'])} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLES / "table_strict_component_ablation_20260608.tex").write_text("\n".join(lines), encoding="utf-8")


def write_nis_table(rows: list[dict[str, object]]) -> None:
    lines = [
        "\\begin{tabular}{lrrrrr}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{N} & \\textbf{Success} & \\textbf{NIS mean} & \\textbf{NIS p95} & \\textbf{Soft/Hard} \\\\",
        "\\midrule",
    ]
    for row in rows:
        condition = row.get("condition_id", "")
        if not condition:
            continue
        lines.append(
            f"{str(condition).replace('_', '\\_')} & {row.get('n', '')} & {fmt_pct(row.get('success_rate', ''))} & "
            f"{fmt_num(row.get('nismean_mean', ''))} & {fmt_num(row.get('nisp95_mean', ''))} & "
            f"{fmt_num(row.get('nissoftviolations_mean', ''))}/{fmt_num(row.get('nishardviolations_mean', ''))} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLES / "table_strict_nis_calibration_20260608.tex").write_text("\n".join(lines), encoding="utf-8")


def write_pairwise_table(rows: list[dict[str, object]]) -> None:
    lines = [
        "\\begin{tabular}{llrrr}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{Comparison} & \\textbf{N} & \\textbf{LeaderAcc diff} & \\textbf{IDSwitch diff} \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(
            f"{latex_escape(row['condition_id'])} & {latex_escape(row['comparison_method'])} & {row['paired_n']} & "
            f"{fmt_ci_pct(row.get('leaderacc_diff_qgip_minus_cmp'), row.get('leaderacc_ci95_low'), row.get('leaderacc_ci95_high'))} & "
            f"{fmt_ci_num(row.get('idswitches_diff_qgip_minus_cmp'), row.get('idswitches_ci95_low'), row.get('idswitches_ci95_high'))} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLES / "table_strict_pairwise_stats_20260608.tex").write_text("\n".join(lines), encoding="utf-8")


def write_dynamic_results_table(rows: list[dict[str, object]]) -> None:
    lines = [
        "\\begin{tabular}{llrrrrrr}",
        "\\toprule",
        "\\textbf{Scenario} & \\textbf{Method} & \\textbf{N} & \\textbf{LeaderAcc} & \\textbf{Wrong-leader} & \\textbf{IDSwitch} & \\textbf{Near/Lost} & \\textbf{Dist p5} \\\\",
        "\\midrule",
    ]
    for row in rows:
        if row["status"] != "complete":
            continue
        lines.append(
            f"{latex_escape(row['condition_id'])} & {latex_escape(row['method'])} & {row['n']} & "
            f"{fmt_pct(row['leader_acc'])} & {fmt_num(row['wrong_leader_frames_mean'])} & "
            f"{fmt_num(row['id_switches_mean'])} & {fmt_pct(row['near_miss_rate'])}/{fmt_pct(row['lost_rate'])} & "
            f"{fmt_num(row['min_distance_p5'])} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLES / "table_strict_dynamic_scenario_results_20260608.tex").write_text("\n".join(lines), encoding="utf-8")


def write_threshold_results_table(rows: list[dict[str, object]]) -> None:
    lines = [
        "\\begin{tabular}{lrrrrrr}",
        "\\toprule",
        "\\textbf{Gate/noise} & \\textbf{N} & \\textbf{Success} & \\textbf{Lost} & \\textbf{NIS mean} & \\textbf{NIS p95} & \\textbf{Soft/Hard} \\\\",
        "\\midrule",
    ]
    for row in rows:
        if row["status"] != "complete":
            continue
        lines.append(
            f"{latex_escape(row['condition_id'])} & {row['n']} & {fmt_pct(row['success_rate'])} & "
            f"{fmt_pct(row['lost_rate'])} & {fmt_num(row['nis_mean_weighted'])} & "
            f"{fmt_num(row['nis_p95_episode_mean'])} & {fmt_num(row['nis_soft_violations_mean'])}/{fmt_num(row['nis_hard_violations_mean'])} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLES / "table_strict_nis_threshold_sensitivity_results_20260608.tex").write_text("\n".join(lines), encoding="utf-8")


def write_sensor_results_table(rows: list[dict[str, object]]) -> None:
    lines = [
        "\\begin{tabular}{llrrrrr}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{Method} & \\textbf{N} & \\textbf{LeaderAcc} & \\textbf{Lost} & \\textbf{FN frames} & \\textbf{Recovery} \\\\",
        "\\midrule",
    ]
    for row in rows:
        if row["status"] != "complete":
            continue
        lines.append(
            f"{latex_escape(row['condition_id'])} & {latex_escape(row['method'])} & {row['n']} & "
            f"{fmt_pct(row['leader_acc'])} & {fmt_pct(row['lost_rate'])} & "
            f"{fmt_num(row['false_negative_frames_mean'])} & {fmt_num(row['recovery_time_mean'])} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLES / "table_strict_rendered_sensor_like_results_20260608.tex").write_text("\n".join(lines), encoding="utf-8")


def write_runner(path: Path, rows: list[dict[str, object]]) -> None:
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$env:KMP_DUPLICATE_LIB_OK = 'TRUE'",
        "# Start CARLA separately before running this queue.",
        "",
    ]
    for row in rows:
        lines.append(f"Write-Host '[{row['queue_id']}]'")
        lines.append(str(row["command"]))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_report(
    completed: list[dict[str, object]],
    ablation: list[dict[str, object]],
    nis: list[dict[str, object]],
    pairwise: list[dict[str, object]],
    dynamic_queue: list[dict[str, object]],
    threshold_queue: list[dict[str, object]],
    sensor_queue: list[dict[str, object]],
) -> None:
    done = sum(1 for row in completed if row["status"] == "complete")
    missing = sum(1 for row in completed if row["status"] != "complete")
    dynamic_stats = queue_completion_stats(dynamic_queue)
    threshold_stats = queue_completion_stats(threshold_queue)
    sensor_stats = queue_completion_stats(sensor_queue)
    lines = [
        "# Strict Review Experiment Completion Report",
        "",
        f"Date: {date.today().isoformat()}",
        "",
        "## What is complete",
        "",
        f"- Completed baseline/selector CSV groups consolidated: {done}.",
        f"- Missing baseline/selector CSV groups: {missing}.",
        f"- Component ablation rows available: {len(ablation)}.",
        f"- NIS diagnostic summary rows available: {len(nis)}.",
        f"- Paired comparison rows available: {len(pairwise)}.",
        f"- Dynamic scenario CARLA groups complete: {dynamic_stats['complete']}/{dynamic_stats['total']} ({dynamic_stats['observed_episodes']}/{dynamic_stats['expected_episodes']} episodes).",
        f"- NIS threshold sensitivity CARLA groups complete: {threshold_stats['complete']}/{threshold_stats['total']} ({threshold_stats['observed_episodes']}/{threshold_stats['expected_episodes']} episodes).",
        f"- Rendered-sensor-like/weather CARLA groups complete: {sensor_stats['complete']}/{sensor_stats['total']} ({sensor_stats['observed_episodes']}/{sensor_stats['expected_episodes']} episodes).",
        "",
        "Completed evidence supports target-consistency and diagnostic claims, not physical deployment safety.",
        "",
        "## Paper-ready outputs",
        "",
        "- `08_paper_ready_outputs/source_data/strict_dynamic_scenario_summary_20260608.csv`.",
        "- `08_paper_ready_outputs/source_data/strict_nis_threshold_sensitivity_summary_20260608.csv`.",
        "- `08_paper_ready_outputs/source_data/strict_rendered_sensor_like_summary_20260608.csv`.",
        "- `08_paper_ready_outputs/tables/table_strict_dynamic_scenario_results_20260608.tex`.",
        "- `08_paper_ready_outputs/tables/table_strict_nis_threshold_sensitivity_results_20260608.tex`.",
        "- `08_paper_ready_outputs/tables/table_strict_rendered_sensor_like_results_20260608.tex`.",
        "",
        "## Strict reviewer interpretation",
        "",
        "- The completed ablations show route success is controller-dominated; paper claims should emphasize LeaderAcc, wrong-leader exposure, ID switches, NIS modes, and availability costs.",
        "- The completed dynamic suite expands coverage beyond static adjacent-lane object-list ambiguity, but it does not support a blanket superiority claim over SORT+MPC.",
        "- In cut-in, merge-like, wrong-query, and delayed-query profiles, QGIP underperforms SORT+MPC on LeaderAcc; these rows should be framed as stress-test limitations or as motivation for a stronger selector-path variant.",
        "- QGIP and QGIP no-query are identical in several dynamic profiles, so these rows do not demonstrate a query-language contribution. Use the existing component ablation or add a forced-GNN query/no-query dynamic comparison before making a strong semantic-query claim.",
        "- The completed threshold sweep supports an operating-gate sensitivity claim under the tested observation-noise settings; it is not a formal probabilistic calibration proof.",
        "- The completed sensor-like suite uses CARLA weather plus detector-output degradation; it is not a substitute for raw camera/LiDAR detector experiments.",
        "",
    ]
    (SUB / "strict_review_experiment_completion_report_20260608.md").write_text("\n".join(lines), encoding="utf-8")


def queue_completion_stats(rows: list[dict[str, object]]) -> dict[str, int]:
    return {
        "total": len(rows),
        "complete": sum(1 for row in rows if row.get("status") == "complete"),
        "partial": sum(1 for row in rows if row.get("status") == "partial"),
        "pending": sum(1 for row in rows if row.get("status") == "pending"),
        "expected_episodes": sum(int(row.get("episodes") or 0) for row in rows),
        "observed_episodes": sum(int(row.get("observed_rows") or 0) for row in rows),
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def episode_map(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {str(row.get("Episode", "")).strip(): row for row in rows if str(row.get("Episode", "")).strip()}


def paired_diffs(ref_rows: list[dict[str, str]], cmp_rows: list[dict[str, str]], metric: str) -> list[float]:
    diffs = []
    for ref_row, cmp_row in zip(ref_rows, cmp_rows):
        ref = safe_float(ref_row.get(metric))
        cmp_value = safe_float(cmp_row.get(metric))
        if math.isfinite(ref) and math.isfinite(cmp_value):
            diffs.append(ref - cmp_value)
    return diffs


def bootstrap_ci(values: list[float], seed: int, samples: int = 1000) -> tuple[object, object]:
    if not values:
        return "", ""
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    boot = []
    n = len(values)
    for _ in range(samples):
        boot.append(mean(values[rng.randrange(n)] for _i in range(n)))
    return percentile(boot, 2.5), percentile(boot, 97.5)


def rate_result(rows: list[dict[str, str]], result: str) -> float:
    if not rows:
        return float("nan")
    return count_result(rows, result) / len(rows)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["empty"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def count_result(rows: list[dict[str, str]], result: str) -> int:
    return sum(1 for row in rows if row.get("Result", "").strip() == result)


def sum_int(rows: list[dict[str, str]], field: str) -> int:
    total = 0
    for row in rows:
        text = str(row.get(field, "")).strip()
        if text:
            try:
                total += int(float(text))
            except ValueError:
                pass
    return total


def mean_float(rows: list[dict[str, str]], field: str) -> object:
    values = [safe_float(row.get(field)) for row in rows if str(row.get(field, "")).strip()]
    values = [value for value in values if math.isfinite(value)]
    return mean(values) if values else ""


def weighted_mean(rows: list[dict[str, str]], value_field: str, weight_field: str) -> object:
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        value = safe_float(row.get(value_field))
        weight = safe_float(row.get(weight_field))
        if math.isfinite(value) and math.isfinite(weight) and weight > 0:
            numerator += value * weight
            denominator += weight
    return numerator / denominator if denominator > 0 else ""


def percentile(values: list[float], q: float) -> object:
    values = [value for value in values if math.isfinite(value)]
    if not values:
        return ""
    values.sort()
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def safe_float(value: object) -> float:
    try:
        text = str(value).strip()
        if not text:
            return float("nan")
        return float(text)
    except (TypeError, ValueError):
        return float("nan")


def fmt_num(value: object) -> str:
    number = safe_float(value)
    if not math.isfinite(number):
        return "--"
    return f"{number:.1f}" if abs(number) >= 10 else f"{number:.3f}"


def fmt_pct(value: object) -> str:
    number = safe_float(value)
    if not math.isfinite(number):
        return "--"
    return f"{100.0 * number:.1f}\\%"


def fmt_ci_pct(value: object, low: object, high: object) -> str:
    number = safe_float(value)
    if not math.isfinite(number):
        return "--"
    return f"{100.0 * number:.1f}\\% [{100.0 * safe_float(low):.1f}, {100.0 * safe_float(high):.1f}]"


def fmt_ci_num(value: object, low: object, high: object) -> str:
    number = safe_float(value)
    if not math.isfinite(number):
        return "--"
    return f"{number:.1f} [{safe_float(low):.1f}, {safe_float(high):.1f}]"


def latex_escape(value: object) -> str:
    return str(value).replace("_", "\\_")


def quote_arg(value: object) -> str:
    text = str(value)
    if not text or any(ch.isspace() for ch in text):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


if __name__ == "__main__":
    main()
