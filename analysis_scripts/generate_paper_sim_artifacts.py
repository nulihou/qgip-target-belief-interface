#!/usr/bin/env python3
"""Generate paper-ready simulation tables, source data, and compact figures.

This script is intentionally deterministic and uses only CSV files already
present in the workspace. It centralizes the numerical values used in the
manuscript so that tables and figures can be regenerated after new CARLA runs.
"""

from __future__ import annotations

import csv
import math
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "RA_L_optimization_20260528" / "08_paper_ready_outputs"
SRC = OUT / "source_data"
TABLES = OUT / "tables"
FIGS = OUT / "figures"
MANUSCRIPT_FIGS = ROOT / "RA_L_optimization_20260528" / "01_manuscript" / "paper_picture"


INPUTS = {
    "existing_episode_summary": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "paper_candidate_existing_episode_summary.csv",
    "ambiguity300_summary": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_stress_paired_metrics300"
    / "paper_metrics300_summary.csv",
    "ambiguity300_pairwise": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_stress_paired_metrics300"
    / "paper_metrics300_pairwise_stats.csv",
    "raw_glare100_summary": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_stress_raw_glare100"
    / "paper_raw_glare100_summary.csv",
    "timing_fn300_summary": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_stress_timing_fn300"
    / "paper_timing_fn300_summary.csv",
    "timing_fn300_pairwise": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_stress_timing_fn300"
    / "paper_timing_fn300_pairwise_stats.csv",
    "boundary100_summary": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_stress_boundary100"
    / "boundary100_summary.csv",
    "boundary100_pairwise": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_stress_boundary100"
    / "boundary100_pairwise_stats.csv",
    "synthetic_pop_nis300_summary": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "synthetic_pop_nis300"
    / "synthetic_pop_nis_summary.csv",
    "synthetic_pop_nis300_episode_results": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "synthetic_pop_nis300"
    / "synthetic_pop_nis_episode_results.csv",
    "carla_nis_diagnostic_summary": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_nis_diagnostic"
    / "nis_diagnostic_summary.csv",
    "carla_nis_diagnostic_episode_results": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_nis_diagnostic"
    / "pilot"
    / "noise_05"
    / "qgip.csv",
    "carla_nis_noise_sweep_qgip100_summary": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_nis_diagnostic100"
    / "nis_noise_sweep_qgip100_summary.csv",
    "carla_nis_outlier_qgip100_summary": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_nis_outlier100"
    / "nis_outlier_qgip100_summary.csv",
    "final_dataset_split_check": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "final_dataset_split_check.csv",
    "final_dataset_split_overlap": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "final_dataset_split_overlap.csv",
    "final_dataset_split_report": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "final_dataset_split_check.md",
    "main1000_qgip_episode_results": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_main1000_qgip"
    / "paper"
    / "main_default"
    / "qgip.csv",
    "main1000_std_kf_episode_results": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_main1000_std_kf"
    / "paper"
    / "main_default"
    / "std_kf.csv",
    "main1000_rule_episode_results": ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_main1000_rule"
    / "paper"
    / "main_default"
    / "rule.csv",
}


MAIN_METHOD_ORDER = [
    ("E2E/PID baseline", "E2E Baseline (No MPC)", "E2E", "docs\\experiments\\01_main_town05\\baseline_e2e_300.csv"),
    ("Rule + MPC", "Rule-Based + MPC", "Heuristic", "docs\\experiments\\01_main_town05\\baseline_rule_300.csv"),
    ("Modular PID", "Modular PID", "Industrial", "scripts\\experiments\\final_300\\results_modular_pid.csv"),
    ("Std KF + MPC", "Std KF + MPC", "Ablation", "scripts\\experiments\\final_300\\results_std_kf.csv"),
    ("QGIP-Net full", "QGIP-Net (Ours)", "Proposed", "scripts\\experiments\\final_300\\results_ours.csv"),
]

AMBIGUITY_ORDER = [
    ("fp_10", "rule", "Rule + MPC"),
    ("fp_10", "qgip_no_query", "QGIP no-query/no-gating"),
    ("fp_10", "qgip", "QGIP-Net"),
    ("idswitch", "rule", "Rule + MPC"),
    ("idswitch", "std_kf", "Std KF + MPC"),
    ("idswitch", "qgip", "QGIP-Net"),
]

BOUNDARY_ORDER = [
    ("fp_20", "rule", "Rule + MPC"),
    ("fp_20", "qgip_no_query", "QGIP no-query/no-gating"),
    ("fp_20", "qgip", "QGIP-Net"),
    ("idswitch_40", "rule", "Rule + MPC"),
    ("idswitch_40", "std_kf", "Std KF + MPC"),
    ("idswitch_40", "qgip", "QGIP-Net"),
    ("fp20_idswitch20", "rule", "Rule + MPC"),
    ("fp20_idswitch20", "qgip_no_query", "QGIP no-query/no-gating"),
    ("fp20_idswitch20", "qgip", "QGIP-Net"),
]

RAW_ORDER = [
    ("raw_glare", "detector_tracker", "Detector/Tracker + MPC"),
    ("raw_glare", "qgip", "QGIP-Net"),
    ("raw_lidar_dropout", "detector_tracker", "Detector/Tracker + MPC"),
    ("raw_lidar_dropout", "qgip", "QGIP-Net"),
]

TIMING_ORDER = [
    ("fn_50", "std_kf"),
    ("fn_50", "imm_kf"),
    ("fn_50", "qgip"),
    ("delay_200", "std_kf"),
    ("delay_200", "imm_kf"),
    ("delay_200", "qgip"),
]


def main() -> None:
    ensure_dirs()
    check_inputs()

    existing = read_csv(INPUTS["existing_episode_summary"])
    ambiguity = read_csv(INPUTS["ambiguity300_summary"])
    ambiguity_pairwise = read_csv(INPUTS["ambiguity300_pairwise"])
    raw_glare = read_csv(INPUTS["raw_glare100_summary"])
    timing = read_csv(INPUTS["timing_fn300_summary"])
    timing_pairwise = read_csv(INPUTS["timing_fn300_pairwise"])
    boundary = read_csv(INPUTS["boundary100_summary"])
    boundary_pairwise = read_csv(INPUTS["boundary100_pairwise"])
    main1000 = build_main1000_summary()

    raw_combined = raw_glare + [
        row for row in boundary if row["condition_id"] == "raw_lidar_dropout"
    ]
    stress_combined = add_suite(ambiguity, "ambiguity300") + add_suite(
        raw_combined, "raw_sensor_like"
    ) + add_suite(timing, "detector_timing300") + add_suite(boundary, "boundary100")
    pairwise_combined = add_suite(ambiguity_pairwise, "ambiguity300") + add_suite(
        timing_pairwise, "detector_timing300"
    ) + add_suite(boundary_pairwise, "boundary100")

    write_csv(SRC / "stress_summary_combined.csv", stress_combined)
    write_csv(SRC / "pairwise_stats_combined.csv", pairwise_combined)
    copy_synthetic_pop_nis_outputs()
    write_main_source(existing)
    write_csv(SRC / "main1000_nominal_source.csv", main1000)
    scenario_coverage = build_scenario_coverage(main1000, ambiguity, timing, raw_combined, boundary)
    write_csv(SRC / "carla_scenario_coverage_source.csv", scenario_coverage)

    write_text(TABLES / "table_main_benchmark.tex", main_benchmark_tex(existing))
    write_text(TABLES / "table_main1000_nominal.tex", main1000_nominal_tex(main1000))
    write_text(TABLES / "table_scenario_coverage.tex", scenario_coverage_tex(scenario_coverage))
    write_text(TABLES / "table_primary_ambiguity.tex", primary_ambiguity_tex(ambiguity))
    write_text(TABLES / "table_detector_timing.tex", detector_timing_tex(timing))
    write_text(TABLES / "table_raw_sensor_like.tex", raw_sensor_tex(raw_combined))
    write_text(TABLES / "table_boundary_stress.tex", boundary_tex(boundary))
    write_text(
        TABLES / "simulation_tables.md",
        markdown_review(existing, main1000, scenario_coverage, ambiguity, timing, raw_combined, boundary),
    )
    write_text(OUT / "README_sources.md", sources_readme())

    write_figures(ambiguity, boundary)
    print(f"Wrote paper-ready simulation artifacts under {OUT}")


def ensure_dirs() -> None:
    for directory in (OUT, SRC, TABLES, FIGS, MANUSCRIPT_FIGS):
        directory.mkdir(parents=True, exist_ok=True)


def check_inputs() -> None:
    missing = [str(path) for path in INPUTS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing input CSVs:\n" + "\n".join(missing))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def copy_synthetic_pop_nis_outputs() -> None:
    """Stage local POP/NIS mechanism-check data without mixing it into CARLA tables."""
    for source_key, output_name in (
        ("synthetic_pop_nis300_summary", "synthetic_pop_nis300_summary.csv"),
        ("synthetic_pop_nis300_episode_results", "synthetic_pop_nis300_episode_results.csv"),
        ("carla_nis_diagnostic_summary", "carla_nis_diagnostic_summary.csv"),
        ("carla_nis_diagnostic_episode_results", "carla_nis_diagnostic_episode_results.csv"),
        ("carla_nis_noise_sweep_qgip100_summary", "carla_nis_noise_sweep_qgip100_summary.csv"),
        ("carla_nis_outlier_qgip100_summary", "carla_nis_outlier_qgip100_summary.csv"),
        ("final_dataset_split_check", "final_dataset_split_check.csv"),
        ("final_dataset_split_overlap", "final_dataset_split_overlap.csv"),
        ("final_dataset_split_report", "final_dataset_split_check.md"),
    ):
        source = INPUTS[source_key]
        if source.exists():
            shutil.copyfile(source, SRC / output_name)


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def add_suite(rows: list[dict[str, str]], suite: str) -> list[dict[str, str]]:
    return [dict(row, suite=suite) for row in rows]


def row_by(rows: list[dict[str, str]], condition: str, method: str) -> dict[str, str]:
    for row in rows:
        if row.get("condition_id") == condition and row.get("method") == method:
            return row
    raise KeyError(f"Missing row condition={condition} method={method}")


def main_row_by_method(rows: list[dict[str, str]], method: str, source_suffix: str | None = None) -> dict[str, str]:
    candidates = [
        row
        for row in rows
        if row.get("paper_candidate") == "1" and row.get("method") == method
    ]
    if source_suffix is not None:
        candidates = [
            row for row in candidates if row.get("source", "").replace("/", "\\").endswith(source_suffix)
        ]
    if not candidates:
        raise KeyError(f"Missing main benchmark method={method} source_suffix={source_suffix}")
    return candidates[0]


def pct(value: str | float) -> str:
    return f"{100.0 * float(value):.1f}\\%"


def pct_plain(value: str | float) -> str:
    return f"{100.0 * float(value):.1f}%"


def pct_ci(row: dict[str, str], key: str) -> str:
    rate = float(row[f"{key}_rate"])
    low = float(row[f"{key}_ci_low"])
    high = float(row[f"{key}_ci_high"])
    return f"{100.0 * rate:.1f}\\% [{100.0 * low:.1f}, {100.0 * high:.1f}]"


def num(value: str | float, digits: int = 1) -> str:
    if value in ("", None):
        return "--"
    return f"{float(value):.{digits}f}"


def latex_escape(text: str) -> str:
    return (
        text.replace("\\", "\\textbackslash{}")
        .replace("_", "\\_")
        .replace("%", "\\%")
        .replace("&", "\\&")
    )


def write_main_source(existing: list[dict[str, str]]) -> None:
    rows = []
    for source_method, display, category, source_suffix in MAIN_METHOD_ORDER:
        row = main_row_by_method(existing, source_method, source_suffix)
        rows.append(
            {
                "method": display,
                "category": category,
                "source_method": source_method,
                "source": row["source"],
                "n": row["n"],
                "success": row["success"],
                "success_rate": row["success_rate"],
                "success_ci_low": row["success_ci_low"],
                "success_ci_high": row["success_ci_high"],
                "collision": row["collision"],
                "collision_rate": row["collision_rate"],
                "lost": row["lost"],
                "lost_rate": row["lost_rate"],
                "mean_jerk": row.get("mean_jerk", ""),
            }
        )
    write_csv(SRC / "main_benchmark_source.csv", rows)


def build_main1000_summary() -> list[dict[str, str]]:
    runs = [
        ("QGIP-Net full", "QGIP-Net (Ours)", "qgip", INPUTS["main1000_qgip_episode_results"]),
        ("Std KF + MPC", "Std KF + MPC", "std_kf", INPUTS["main1000_std_kf_episode_results"]),
        ("Rule + MPC", "Rule + MPC", "rule", INPUTS["main1000_rule_episode_results"]),
    ]
    return [
        summarize_episode_rows(source_method, display, method, path)
        for source_method, display, method, path in runs
    ]


def build_scenario_coverage(
    main1000: list[dict[str, str]],
    ambiguity: list[dict[str, str]],
    timing: list[dict[str, str]],
    raw: list[dict[str, str]],
    boundary: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Summarize completed CARLA runs by maneuver/scenario class.

    This is a coverage table, not a new statistical test: detailed per-method
    metrics remain in the source summary CSVs and detailed supplement tables.
    """

    qgip_main = row_by(main1000, "main_default", "qgip")
    raw_glare = row_by(raw, "raw_glare", "qgip")
    raw_lidar = row_by(raw, "raw_lidar_dropout", "qgip")
    fn = row_by(timing, "fn_50", "qgip")
    delay = row_by(timing, "delay_200", "qgip")
    fp = row_by(ambiguity, "fp_10", "qgip")
    fp_baseline = row_by(ambiguity, "fp_10", "qgip_no_query")
    ids = row_by(ambiguity, "idswitch", "qgip")
    ids_baseline = row_by(ambiguity, "idswitch", "std_kf")
    boundary_combo = row_by(boundary, "fp20_idswitch20", "qgip")
    boundary_baseline = row_by(boundary, "fp20_idswitch20", "qgip_no_query")

    return [
        scenario_row(
            "straight/curve following",
            "main_default",
            "planner_input",
            "QGIP / Std KF / Rule",
            qgip_main,
            "scale sanity",
            f"LeaderAcc {pct_plain(qgip_main['leaderacc_mean'])}",
        ),
        scenario_row(
            "curve following",
            "raw_glare",
            "raw_sensor_like",
            "Detector/Tracker / QGIP",
            raw_glare,
            "detector-level glare approximation",
            f"LeaderAcc {pct_plain(raw_glare['leaderacc_mean'])}",
        ),
        scenario_row(
            "following with dropout",
            "raw_lidar_dropout",
            "raw_sensor_like",
            "Detector/Tracker / QGIP",
            raw_lidar,
            "detector-level LiDAR-dropout approximation",
            f"LeaderAcc {pct_plain(raw_lidar['leaderacc_mean'])}",
        ),
        scenario_row(
            "lead braking",
            "fn_50; delay_200",
            "detector/timing",
            "Std KF / IMM-KF / QGIP",
            fn,
            "false negatives and 200 ms delay",
            f"LeaderAcc {pct_plain(fn['leaderacc_mean'])}; delay matched",
            companion_row=delay,
        ),
        scenario_row(
            "adjacent-lane distractor",
            "fp_10",
            "ambiguity",
            "Rule / no-query / QGIP",
            fp,
            "false-positive ambiguity",
            f"QGIP LeaderAcc {pct_plain(fp['leaderacc_mean'])} vs no-query {pct_plain(fp_baseline['leaderacc_mean'])}",
        ),
        scenario_row(
            "cut-in/cut-out identity",
            "idswitch",
            "ambiguity",
            "Rule / Std KF / QGIP",
            ids,
            "ID-switch ambiguity",
            f"QGIP LeaderAcc {pct_plain(ids['leaderacc_mean'])} vs Std KF {pct_plain(ids_baseline['leaderacc_mean'])}",
        ),
        scenario_row(
            "combined boundary ambiguity",
            "fp20_idswitch20",
            "boundary",
            "Rule / no-query / QGIP",
            boundary_combo,
            "stronger false positives plus ID switches",
            f"QGIP LeaderAcc {pct_plain(boundary_combo['leaderacc_mean'])} vs no-query {pct_plain(boundary_baseline['leaderacc_mean'])}",
        ),
    ]


def scenario_row(
    scenario_class: str,
    conditions: str,
    layer: str,
    methods: str,
    row: dict[str, str],
    interpretation: str,
    target_metric: str,
    companion_row: dict[str, str] | None = None,
) -> dict[str, str]:
    if companion_row is not None and (
        row["n"] != companion_row["n"]
        or row["success_rate"] != companion_row["success_rate"]
        or row["collision_rate"] != companion_row["collision_rate"]
        or row["lost_rate"] != companion_row["lost_rate"]
    ):
        target_metric += "; see source rows"
    return {
        "scenario_class": scenario_class,
        "conditions": conditions,
        "layer": layer,
        "methods": methods,
        "n_per_method": row["n"],
        "success_rate": row["success_rate"],
        "collision_rate": row["collision_rate"],
        "lost_rate": row["lost_rate"],
        "near_miss_rate": row.get("near_miss_rate", ""),
        "target_metric": target_metric,
        "interpretation": interpretation,
    }


def summarize_episode_rows(source_method: str, display: str, method: str, path: Path) -> dict[str, str]:
    rows = read_csv(path)
    n = len(rows)
    success = count_result(rows, "Success")
    collision = count_result(rows, "Collision")
    lost = count_result(rows, "Lost")
    near_miss = sum(1 for row in rows if str(row.get("NearMiss", "")).strip() in {"1", "true", "True"})
    success_lo, success_hi = wilson_ci(success, n)
    collision_lo, collision_hi = wilson_ci(collision, n)
    lost_lo, lost_hi = wilson_ci(lost, n)
    return {
        "condition_id": "main_default",
        "source_method": source_method,
        "display_method": display,
        "method": method,
        "source": str(path.relative_to(ROOT)),
        "n": str(n),
        "success": str(success),
        "success_rate": rate(success, n),
        "success_ci_low": f"{success_lo:.6f}",
        "success_ci_high": f"{success_hi:.6f}",
        "collision": str(collision),
        "collision_rate": rate(collision, n),
        "collision_ci_low": f"{collision_lo:.6f}",
        "collision_ci_high": f"{collision_hi:.6f}",
        "zero_collision_rule3_upper": f"{3.0 / n:.6f}" if n else "",
        "lost": str(lost),
        "lost_rate": rate(lost, n),
        "lost_ci_low": f"{lost_lo:.6f}",
        "lost_ci_high": f"{lost_hi:.6f}",
        "near_miss": str(near_miss),
        "near_miss_rate": rate(near_miss, n),
        "mean_jerk": mean_field(rows, "Jerk"),
        "mean_min_distance_m": mean_field(rows, "MinDistance"),
        "leaderacc_mean": mean_field(rows, "LeaderAcc"),
        "nis_mean": qgip_only_mean(method, rows, "NISMean"),
        "nis_p95_episode_mean": qgip_only_mean(method, rows, "NISP95"),
        "nis_soft_violations_mean": qgip_only_mean(method, rows, "NISSoftViolations"),
        "nis_hard_violations_mean": qgip_only_mean(method, rows, "NISHardViolations"),
    }


def count_result(rows: list[dict[str, str]], result: str) -> int:
    return sum(1 for row in rows if row.get("Result", "").strip() == result)


def rate(count: int, n: int) -> str:
    return f"{count / n:.6f}" if n else ""


def mean_field(rows: list[dict[str, str]], key: str) -> str:
    values = []
    for row in rows:
        value = parse_float(row.get(key, ""))
        if value is not None:
            values.append(value)
    return f"{sum(values) / len(values):.6f}" if values else ""


def qgip_only_mean(method: str, rows: list[dict[str, str]], key: str) -> str:
    if method != "qgip":
        return ""
    return mean_field(rows, key)


def parse_float(value: str) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    spread = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return max(0.0, center - spread), min(1.0, center + spread)


def main_benchmark_tex(existing: list[dict[str, str]]) -> str:
    lines = [
        "% Auto-generated by generate_paper_sim_artifacts.py",
        "\\begin{tabular}{l c c c c c}",
        "\\toprule",
        "\\textbf{Method} & \\textbf{Type} & \\textbf{Success} & \\textbf{Collision} & \\textbf{Lost} & \\textbf{Mean Jerk} \\\\",
        "\\midrule",
    ]
    for source_method, display, category, source_suffix in MAIN_METHOD_ORDER:
        row = main_row_by_method(existing, source_method, source_suffix)
        jerk = num(row.get("mean_jerk", ""), 3)
        if display == "QGIP-Net (Ours)":
            display = "\\textbf{QGIP-Net (Ours)}"
            category = "\\textbf{Proposed}"
            success = "\\textbf{" + pct(row["success_rate"]) + "}"
            collision = "\\textbf{" + pct(row["collision_rate"]) + "}"
            lost = "\\textbf{" + pct(row["lost_rate"]) + "}"
        else:
            success = pct(row["success_rate"])
            collision = pct(row["collision_rate"])
            lost = pct(row["lost_rate"])
        lines.append(
            f"{display} & {category} & {success} & {collision} & {lost} & {jerk} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def main1000_nominal_tex(rows: list[dict[str, str]]) -> str:
    lines = [
        "% Auto-generated by generate_paper_sim_artifacts.py",
        "\\begin{tabular}{l c c c c c c c}",
        "\\toprule",
        "\\textbf{Method} & \\textbf{N} & \\textbf{Success} & \\textbf{Collision} & \\textbf{Lost} & \\textbf{Near-miss} & \\textbf{MinDist} & \\textbf{NIS mean} \\\\",
        "\\midrule",
    ]
    for row in rows:
        display = latex_escape(row["display_method"])
        if row["method"] == "qgip":
            display = "\\textbf{QGIP-Net (Ours)}"
            success = "\\textbf{" + count_pct(row["success"], row["success_rate"]) + "}"
        else:
            success = count_pct(row["success"], row["success_rate"])
        collision = count_pct(row["collision"], row["collision_rate"])
        lost = count_pct(row["lost"], row["lost_rate"])
        near_miss = count_pct(row["near_miss"], row["near_miss_rate"])
        min_dist = num(row["mean_min_distance_m"], 2)
        nis = num(row["nis_mean"], 3)
        lines.append(
            f"{display} & {row['n']} & {success} & {collision} & {lost} & {near_miss} & {min_dist} m & {nis} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def scenario_coverage_tex(rows: list[dict[str, str]]) -> str:
    lines = [
        "% Auto-generated by generate_paper_sim_artifacts.py",
        "\\begin{tabular}{l l c c l}",
        "\\toprule",
        "\\textbf{Scenario} & \\textbf{Cond.} & \\textbf{N} & \\textbf{Succ./Lost} & \\textbf{Evidence} \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(
            f"{latex_escape(short_scenario(row['scenario_class']))} & "
            f"\\texttt{{{latex_escape(short_conditions(row['conditions']))}}} & "
            f"{row['n_per_method']} & "
            f"{pct(row['success_rate'])}/{pct(row['lost_rate'])} & "
            f"{latex_escape(short_evidence(row['target_metric']))} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def short_scenario(scenario: str) -> str:
    return {
        "straight/curve following": "straight/curve",
        "following with dropout": "dropout follow",
        "adjacent-lane distractor": "adjacent distractor",
        "cut-in/cut-out identity": "cut-in/out ID",
        "combined boundary ambiguity": "boundary ambiguity",
    }.get(scenario, scenario)


def short_conditions(conditions: str) -> str:
    return {
        "main_default": "main",
        "raw_glare": "glare",
        "raw_lidar_dropout": "lidar",
        "fn_50; delay_200": "fn/delay",
        "fp_10": "fp10",
        "idswitch": "idsw",
        "fp20_idswitch20": "fp20+idsw",
    }.get(conditions, conditions)


def short_evidence(evidence: str) -> str:
    return (
        evidence.replace("LeaderAcc ", "LA ")
        .replace("QGIP LeaderAcc ", "QGIP LA ")
        .replace(" vs no-query ", " vs nq ")
        .replace(" vs Std KF ", " vs KF ")
        .replace("; delay matched", "")
    )


def count_pct(count: str, rate_value: str) -> str:
    return f"{count} ({100.0 * float(rate_value):.1f}\\%)"


def primary_ambiguity_tex(rows: list[dict[str, str]]) -> str:
    lines = [
        "% Auto-generated by generate_paper_sim_artifacts.py",
        "\\begin{tabular}{l l c c c c c}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{Method} & \\textbf{N} & \\textbf{Success} & \\textbf{Lost} & \\textbf{LeaderAcc} & \\textbf{IDSwitches} \\\\",
        "\\midrule",
    ]
    for idx, (condition, method, display) in enumerate(AMBIGUITY_ORDER):
        if idx == 3:
            lines.append("\\midrule")
        row = row_by(rows, condition, method)
        leader = pct(row["leaderacc_mean"])
        ids = num(row["idswitches_mean"], 1)
        if method == "qgip":
            leader = "\\textbf{" + leader + "}"
            if condition == "idswitch":
                ids = "\\textbf{" + ids + "}"
        lines.append(
            f"\\texttt{{{latex_escape(condition)}}} & {latex_escape(display)} & {row['n']} & {pct(row['success_rate'])} & {pct(row['lost_rate'])} & {leader} & {ids} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def detector_timing_tex(rows: list[dict[str, str]]) -> str:
    by_condition = {condition: [] for condition, _ in TIMING_ORDER}
    for condition, method in TIMING_ORDER:
        by_condition[condition].append(row_by(rows, condition, method))
    lines = [
        "% Auto-generated by generate_paper_sim_artifacts.py",
        "\\begin{tabular}{l c c c c c c}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{Methods} & \\textbf{N/method} & \\textbf{Success} & \\textbf{Collision} & \\textbf{Lost} & \\textbf{LeaderAcc} \\\\",
        "\\midrule",
    ]
    for condition in ("fn_50", "delay_200"):
        row = by_condition[condition][0]
        lines.append(
            f"\\texttt{{{latex_escape(condition)}}} & Std KF / IMM-KF / QGIP & {row['n']} & {pct(row['success_rate'])} & {pct(row['collision_rate'])} & {pct(row['lost_rate'])} & {pct(row['leaderacc_mean'])} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def raw_sensor_tex(rows: list[dict[str, str]]) -> str:
    lines = [
        "% Auto-generated by generate_paper_sim_artifacts.py",
        "\\begin{tabular}{l l c c c c c}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{Method} & \\textbf{Success} & \\textbf{Collision} & \\textbf{Lost} & \\textbf{LeaderAcc} & \\textbf{IDSwitches} \\\\",
        "\\midrule",
    ]
    for condition, method, display in RAW_ORDER:
        row = row_by(rows, condition, method)
        lines.append(
            f"\\texttt{{{latex_escape(condition)}}} & {latex_escape(display)} & {pct(row['success_rate'])} & {pct(row['collision_rate'])} & {pct(row['lost_rate'])} & {pct(row['leaderacc_mean'])} & {num(row['idswitches_mean'], 1)} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def boundary_tex(rows: list[dict[str, str]]) -> str:
    lines = [
        "% Auto-generated by generate_paper_sim_artifacts.py",
        "\\begin{tabular}{l l c c c}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{Method} & \\textbf{LeaderAcc} & \\textbf{WrongFrames} & \\textbf{IDSwitches} \\\\",
        "\\midrule",
    ]
    for idx, (condition, method, display) in enumerate(BOUNDARY_ORDER):
        if idx in (3, 6):
            lines.append("\\midrule")
        row = row_by(rows, condition, method)
        leader = pct(row["leaderacc_mean"])
        wrong = num(row["wrongleaderframes_mean"], 1)
        ids = num(row["idswitches_mean"], 1)
        if method == "qgip":
            leader = "\\textbf{" + leader + "}"
            wrong = "\\textbf{" + wrong + "}"
            if condition != "fp_20":
                ids = "\\textbf{" + ids + "}"
        lines.append(
            f"\\texttt{{{latex_escape(condition)}}} & {latex_escape(display)} & {leader} & {wrong} & {ids} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def markdown_review(
    existing: list[dict[str, str]],
    main1000: list[dict[str, str]],
    scenario_coverage: list[dict[str, str]],
    ambiguity: list[dict[str, str]],
    timing: list[dict[str, str]],
    raw: list[dict[str, str]],
    boundary: list[dict[str, str]],
) -> str:
    parts = ["# Paper-Ready Simulation Tables\n"]
    parts.append("## Main Benchmark\n")
    parts.append("| Method | N | Success | Collision | Lost | Mean jerk |\n| --- | ---: | ---: | ---: | ---: | ---: |")
    for source_method, display, _, source_suffix in MAIN_METHOD_ORDER:
        row = main_row_by_method(existing, source_method, source_suffix)
        parts.append(
            f"| {display} | {row['n']} | {pct(row['success_rate'])} | {pct(row['collision_rate'])} | {pct(row['lost_rate'])} | {num(row.get('mean_jerk', ''), 3)} |"
        )
    parts.append("\n## Nominal Main-Default N=1000 Sanity Check\n")
    parts.append("| Method | N | Success | Collision | Lost | Near-miss | Mean min distance | NIS mean |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in main1000:
        parts.append(
            f"| {row['display_method']} | {row['n']} | {count_pct(row['success'], row['success_rate'])} | {count_pct(row['collision'], row['collision_rate'])} | {count_pct(row['lost'], row['lost_rate'])} | {count_pct(row['near_miss'], row['near_miss_rate'])} | {num(row['mean_min_distance_m'], 2)} m | {num(row['nis_mean'], 3)} |"
        )
    parts.append("\n## Scenario-Class Coverage\n")
    parts.append(markdown_scenario_coverage(scenario_coverage))
    parts.append("\n## Primary Ambiguity Stress\n")
    parts.append(markdown_metric_table(ambiguity, AMBIGUITY_ORDER))
    parts.append("\n## Detector/Timing Stress\n")
    parts.append(markdown_metric_table(timing, [(c, m, m) for c, m in TIMING_ORDER]))
    parts.append("\n## Raw-Sensor-Like Stress\n")
    parts.append(markdown_metric_table(raw, RAW_ORDER))
    parts.append("\n## Supplemental Boundary Stress\n")
    parts.append(markdown_metric_table(boundary, BOUNDARY_ORDER))
    return "\n".join(parts)


def markdown_scenario_coverage(rows: list[dict[str, str]]) -> str:
    lines = [
        "| Scenario | Conditions | Layer | N/method | Success | Collision | Lost | Evidence role |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['scenario_class']} | `{row['conditions']}` | {row['layer']} | "
            f"{row['n_per_method']} | {pct(row['success_rate'])} | {pct(row['collision_rate'])} | "
            f"{pct(row['lost_rate'])} | {row['target_metric']} ({row['interpretation']}) |"
        )
    return "\n".join(lines)


def markdown_metric_table(rows: list[dict[str, str]], order: list[tuple[str, str, str]]) -> str:
    lines = [
        "| Condition | Method | N | Success | Collision | Lost | LeaderAcc | WrongFrames | IDSwitches |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for condition, method, display in order:
        row = row_by(rows, condition, method)
        lines.append(
            f"| `{condition}` | {display} | {row['n']} | {pct(row['success_rate'])} | {pct(row['collision_rate'])} | {pct(row['lost_rate'])} | {pct(row.get('leaderacc_mean', 0.0))} | {num(row.get('wrongleaderframes_mean', ''), 1)} | {num(row.get('idswitches_mean', ''), 1)} |"
        )
    return "\n".join(lines)


def sources_readme() -> str:
    lines = [
        "# Paper Simulation Artifact Sources",
        "",
        "Generated by `RA_L_optimization_20260528/05_analysis_scripts/generate_paper_sim_artifacts.py`.",
        "",
        "## Inputs",
    ]
    for name, path in INPUTS.items():
        rel = path.relative_to(ROOT)
        lines.append(f"- `{name}`: `{rel}`")
    lines.extend(
        [
            "",
            "## Outputs",
            "- `source_data/main_benchmark_source.csv`: main benchmark rows used by Table~II.",
            "- `source_data/main1000_nominal_source.csv`: nominal main-default CARLA N=1000 sanity-check rows for QGIP-Net, Std-KF+MPC, and Rule+MPC.",
            "- `source_data/carla_scenario_coverage_source.csv`: compact maneuver/scenario-class coverage map derived from completed CARLA summaries.",
            "- `source_data/stress_summary_combined.csv`: all current stress summary rows.",
            "- `source_data/pairwise_stats_combined.csv`: paired McNemar/bootstrap statistics.",
            "- `source_data/synthetic_pop_nis300_summary.csv`: local POP/NIS mechanism-check summary (not CARLA or real-robot validation).",
            "- `source_data/synthetic_pop_nis300_episode_results.csv`: per-episode data for the local POP/NIS mechanism check.",
            "- `source_data/carla_nis_diagnostic_summary.csv`: small CARLA NIS logging diagnostic summary.",
            "- `source_data/carla_nis_diagnostic_episode_results.csv`: per-episode CARLA NIS diagnostic rows.",
            "- `source_data/carla_nis_noise_sweep_qgip100_summary.csv`: CARLA QGIP-Net detector-noise/NIS sweep summary.",
            "- `source_data/carla_nis_noise_sweep_figure_data.csv`: source data for the CARLA NIS sweep figure.",
            "- `source_data/carla_nis_outlier_qgip100_summary.csv`: CARLA QGIP-Net NIS outlier/ambiguity diagnostic summary.",
            "- `source_data/carla_nis_outlier_figure_data.csv`: compact source data for the CARLA NIS outlier/ambiguity diagnostic.",
            "- `source_data/final_dataset_split_check.csv`: train/validation/test split counts, town composition, and missing-file counts.",
            "- `source_data/final_dataset_split_overlap.csv`: pairwise split-overlap counts.",
            "- `source_data/final_dataset_split_check.md`: human-readable dataset split audit.",
            "- `tables/*.tex`: table bodies that can be pasted into the manuscript table environments.",
            "- `figures/fig_leaderacc_stress.(pdf|png)`: LeaderAcc comparison figure.",
            "- `figures/fig_idswitch_stress.(pdf|png)`: ID-switch comparison figure.",
        ]
    )
    return "\n".join(lines)


def write_figures(ambiguity: list[dict[str, str]], boundary: list[dict[str, str]]) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - optional dependency fallback
        write_text(FIGS / "FIGURE_GENERATION_SKIPPED.txt", f"matplotlib unavailable: {exc}")
        return

    groups = [
        ("fp_10", ambiguity, [("rule", "Rule"), ("qgip_no_query", "No query"), ("qgip", "QGIP")]),
        ("idswitch", ambiguity, [("rule", "Rule"), ("std_kf", "Std KF"), ("qgip", "QGIP")]),
        ("fp_20", boundary, [("rule", "Rule"), ("qgip_no_query", "No query"), ("qgip", "QGIP")]),
        ("idswitch_40", boundary, [("rule", "Rule"), ("std_kf", "Std KF"), ("qgip", "QGIP")]),
        ("fp20_idswitch20", boundary, [("rule", "Rule"), ("qgip_no_query", "No query"), ("qgip", "QGIP")]),
    ]
    write_figure_source(groups, ambiguity, boundary)
    plot_metric(
        groups,
        "leaderacc_mean",
        "Leader selection accuracy",
        "LeaderAcc",
        FIGS / "fig_leaderacc_stress",
        percent=True,
    )
    plot_metric(
        groups,
        "idswitches_mean",
        "Average ID switches per episode",
        "ID switches",
        FIGS / "fig_idswitch_stress",
        percent=False,
    )
    copy_figure_to_manuscript(FIGS / "fig_leaderacc_stress", MANUSCRIPT_FIGS / "figure_stress_leaderacc")
    copy_figure_to_manuscript(FIGS / "fig_idswitch_stress", MANUSCRIPT_FIGS / "figure_stress_idswitch")


def copy_figure_to_manuscript(src_base: Path, dst_base: Path) -> None:
    import shutil

    for suffix in (".pdf", ".png"):
        src = src_base.with_suffix(suffix)
        if src.exists():
            shutil.copyfile(src, dst_base.with_suffix(suffix))


def write_figure_source(groups, ambiguity, boundary) -> None:
    rows = []
    for condition, source_rows, method_specs in groups:
        for method, display in method_specs:
            row = row_by(source_rows, condition, method)
            rows.append(
                {
                    "condition_id": condition,
                    "method": method,
                    "display": display,
                    "leaderacc_mean": row["leaderacc_mean"],
                    "idswitches_mean": row["idswitches_mean"],
                    "wrongleaderframes_mean": row["wrongleaderframes_mean"],
                }
            )
    write_csv(SRC / "figure_stress_leader_metrics.csv", rows)


def plot_metric(groups, metric: str, title: str, ylabel: str, out_base: Path, percent: bool) -> None:
    import matplotlib.pyplot as plt

    colors = {"Rule": "#7a7a7a", "No query": "#d68a00", "Std KF": "#4f78a8", "QGIP": "#20815a"}
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    width = 0.22
    x_positions = list(range(len(groups)))
    for j, label in enumerate(["Rule", "No query", "Std KF", "QGIP"]):
        xs = []
        ys = []
        for i, (condition, source_rows, method_specs) in enumerate(groups):
            found = None
            for method, display in method_specs:
                if display == label:
                    found = row_by(source_rows, condition, method)
                    break
            if found is None:
                continue
            xs.append(i + (j - 1.5) * width)
            value = float(found[metric])
            ys.append(100.0 * value if percent else value)
        if xs:
            ax.bar(xs, ys, width=width, label=label, color=colors[label], edgecolor="black", linewidth=0.4)
    ax.set_xticks(x_positions)
    ax.set_xticklabels([condition.replace("_", "\n") for condition, _, _ in groups], fontsize=8)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(axis="y", alpha=0.25, linewidth=0.6)
    ax.legend(ncol=4, fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.10))
    if percent:
        ax.set_ylim(0, 105)
    fig.tight_layout()
    fig.savefig(out_base.with_suffix(".pdf"))
    fig.savefig(out_base.with_suffix(".png"), dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()
