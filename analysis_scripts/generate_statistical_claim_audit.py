#!/usr/bin/env python3
"""Audit key numerical manuscript claims against staged source-data CSVs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"
OUT_CSV = SOURCE / "statistical_claim_audit.csv"
OUT_REPORT = PACKAGE / "statistical_claim_audit_report_20260604.md"

TOL = 5e-4


@dataclass
class AuditRow:
    claim_id: str
    claim: str
    expected: str
    actual: str
    status: str
    source: str
    boundary: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str) -> float:
    return float(str(value).strip())


def as_int(value: str) -> int:
    return int(float(str(value).strip()))


def status_close(actual: float, expected: float, tol: float = TOL) -> str:
    return "PASS" if abs(actual - expected) <= tol else "FAIL"


def status_equal(actual: int | str, expected: int | str) -> str:
    return "PASS" if actual == expected else "FAIL"


def fmt(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def row_by(rows: list[dict[str, str]], **criteria: str) -> dict[str, str]:
    matches = [
        row
        for row in rows
        if all(str(row.get(key, "")) == str(value) for key, value in criteria.items())
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one row for {criteria}, found {len(matches)}")
    return matches[0]


def pair_by(rows: list[dict[str, str]], condition_id: str, comparison_method: str) -> dict[str, str]:
    return row_by(rows, condition_id=condition_id, reference_method="qgip", comparison_method=comparison_method)


def add(rows: list[AuditRow], claim_id: str, claim: str, expected: str, actual: str, status: str, source: str, boundary: str) -> None:
    rows.append(AuditRow(claim_id, claim, expected, actual, status, source, boundary))


def main() -> None:
    stress = read_csv(SOURCE / "stress_summary_combined.csv")
    pairwise = read_csv(SOURCE / "pairwise_stats_combined.csv")
    split_check = read_csv(SOURCE / "final_dataset_split_check.csv")
    split_overlap = read_csv(SOURCE / "final_dataset_split_overlap.csv")
    main1000 = read_csv(SOURCE / "main1000_nominal_source.csv")
    nis_noise = read_csv(SOURCE / "carla_nis_noise_sweep_qgip100_summary.csv")
    nis_outlier = read_csv(SOURCE / "carla_nis_outlier_qgip100_summary.csv")
    deposit_manifest = read_csv(PACKAGE / "repository_deposit_manifest_20260603.csv")

    audit: list[AuditRow] = []

    expected_split = {"train": 4050, "val": 450, "test_unseen": 500}
    for split, expected in expected_split.items():
        item = row_by(split_check, split=split)
        actual = as_int(item["n"])
        add(
            audit,
            f"split_{split}_count",
            f"Dataset split `{split}` has expected path count.",
            str(expected),
            str(actual),
            status_equal(actual, expected),
            "final_dataset_split_check.csv",
            "Supports split traceability, not unrestricted real-world generalization.",
        )
        missing = as_int(item["missing_files"])
        add(
            audit,
            f"split_{split}_missing",
            f"Dataset split `{split}` has zero missing files.",
            "0",
            str(missing),
            status_equal(missing, 0),
            "final_dataset_split_check.csv",
            "File existence audit only; it does not inspect simulator realism.",
        )

    for item in split_overlap:
        actual = as_int(item["overlap_paths"])
        add(
            audit,
            f"split_overlap_{item['pair'].replace(' ', '_')}",
            f"Split pair `{item['pair']}` has zero path overlap.",
            "0",
            str(actual),
            status_equal(actual, 0),
            "final_dataset_split_overlap.csv",
            "Guards against path overlap; map-level generalization remains bounded by the text.",
        )

    qgip_fp10 = row_by(stress, condition_id="fp_10", method="qgip", suite="ambiguity300")
    noquery_fp10 = row_by(stress, condition_id="fp_10", method="qgip_no_query", suite="ambiguity300")
    rule_fp10 = row_by(stress, condition_id="fp_10", method="rule", suite="ambiguity300")
    for method, item, expected in (
        ("qgip", qgip_fp10, 0.8624),
        ("qgip_no_query", noquery_fp10, 0.5317),
        ("rule", rule_fp10, 0.4379),
    ):
        actual = as_float(item["leaderacc_mean"])
        add(
            audit,
            f"fp10_leaderacc_{method}",
            f"`fp_10` LeaderAcc for {method}.",
            fmt(expected),
            fmt(actual),
            status_close(actual, expected),
            "stress_summary_combined.csv",
            "Primary target-consistency evidence under adjacent-lane false positives.",
        )

    fp10_noquery = pair_by(pairwise, "fp_10", "qgip_no_query")
    fp10_rule = pair_by(pairwise, "fp_10", "rule")
    for label, item, expected, ci_low, ci_high in (
        ("no_query", fp10_noquery, 0.3308, 0.3037, 0.3585),
        ("rule", fp10_rule, 0.4245, 0.3782, 0.4709),
    ):
        actual = as_float(item["leaderacc_diff_ref_minus_cmp"])
        actual_low = as_float(item["leaderacc_diff_ci95_low"])
        actual_high = as_float(item["leaderacc_diff_ci95_high"])
        status = "PASS" if all(
            [
                status_close(actual, expected) == "PASS",
                status_close(actual_low, ci_low) == "PASS",
                status_close(actual_high, ci_high) == "PASS",
            ]
        ) else "FAIL"
        add(
            audit,
            f"fp10_leaderacc_gain_vs_{label}",
            f"`fp_10` paired LeaderAcc gain versus {label}.",
            f"{fmt(expected)} [{fmt(ci_low)}, {fmt(ci_high)}]",
            f"{fmt(actual)} [{fmt(actual_low)}, {fmt(actual_high)}]",
            status,
            "pairwise_stats_combined.csv",
            "Paired bootstrap interval for target-consistency gain; route completion remains equal.",
        )

    qgip_ids = row_by(stress, condition_id="idswitch", method="qgip", suite="ambiguity300")
    rule_ids = row_by(stress, condition_id="idswitch", method="rule", suite="ambiguity300")
    std_ids = row_by(stress, condition_id="idswitch", method="std_kf", suite="ambiguity300")
    for method, item, expected in (
        ("qgip", qgip_ids, 0.9068),
        ("std_kf", std_ids, 0.5604),
        ("rule", rule_ids, 0.4765),
    ):
        actual = as_float(item["leaderacc_mean"])
        add(
            audit,
            f"idswitch_leaderacc_{method}",
            f"`idswitch` LeaderAcc for {method}.",
            fmt(expected),
            fmt(actual),
            status_close(actual, expected),
            "stress_summary_combined.csv",
            "Primary target-consistency evidence under identity perturbation.",
        )
    for method, item, expected in (
        ("qgip", qgip_ids, 39.1967),
        ("std_kf", std_ids, 180.6067),
        ("rule", rule_ids, 155.1667),
    ):
        actual = as_float(item["idswitches_mean"])
        add(
            audit,
            f"idswitch_count_{method}",
            f"`idswitch` mean ID switches for {method}.",
            fmt(expected),
            fmt(actual),
            status_close(actual, expected, tol=1e-3),
            "stress_summary_combined.csv",
            "ID-switch count supports target-consistency interpretation; not a standalone safety proof.",
        )

    ids_std = pair_by(pairwise, "idswitch", "std_kf")
    actual = as_float(ids_std["leaderacc_diff_ref_minus_cmp"])
    add(
        audit,
        "idswitch_leaderacc_gain_vs_std_kf",
        "`idswitch` paired LeaderAcc gain versus Std-KF.",
        "0.3463 [0.3144, 0.3784]",
        f"{fmt(actual)} [{fmt(as_float(ids_std['leaderacc_diff_ci95_low']))}, {fmt(as_float(ids_std['leaderacc_diff_ci95_high']))}]",
        "PASS" if abs(actual - 0.3463) <= TOL else "FAIL",
        "pairwise_stats_combined.csv",
        "Paired bootstrap interval for target-consistency gain.",
    )

    boundary_q = row_by(stress, condition_id="fp20_idswitch20", method="qgip", suite="boundary100")
    for field, expected, label in (
        ("leaderacc_mean", 0.8002, "combined boundary LeaderAcc"),
        ("success_rate", 0.77, "combined boundary success rate"),
        ("collision_rate", 0.0, "combined boundary collision rate"),
    ):
        actual = as_float(boundary_q[field])
        add(
            audit,
            f"boundary_fp20_idswitch20_{field}",
            label,
            fmt(expected),
            fmt(actual),
            status_close(actual, expected),
            "stress_summary_combined.csv",
            "Boundary stress is supplemental and not the primary statistical test.",
        )

    qgip_rows = [row for row in stress if row["method"] == "qgip"]
    nonzero_collision = sum(1 for row in qgip_rows if as_int(row["collision_count"]) != 0)
    nonzero_near = sum(1 for row in qgip_rows if as_int(row["near_miss_count"]) != 0)
    add(
        audit,
        "qgip_stress_zero_observed_collision_nearmiss",
        "All QGIP rows in the completed stress summary have zero observed collisions and near-misses.",
        "nonzero collision rows=0; nonzero near-miss rows=0",
        f"nonzero collision rows={nonzero_collision}; nonzero near-miss rows={nonzero_near}; qgip rows={len(qgip_rows)}",
        "PASS" if nonzero_collision == 0 and nonzero_near == 0 else "FAIL",
        "stress_summary_combined.csv",
        "Finite-sample observation only; does not imply zero real-world risk.",
    )

    for method in ("qgip", "std_kf", "rule"):
        item = row_by(main1000, method=method)
        actual = f"{as_int(item['success'])}/1000 success; {as_int(item['collision'])}/1000 collision; {as_int(item['near_miss'])}/1000 near_miss"
        add(
            audit,
            f"main1000_{method}_outcome",
            f"N=1000 nominal main-default outcome for {method}.",
            "735/1000 success; 0/1000 collision; 0/1000 near_miss",
            actual,
            "PASS" if actual == "735/1000 success; 0/1000 collision; 0/1000 near_miss" else "FAIL",
            "main1000_nominal_source.csv",
            "Low-ambiguity stability check; not method-discrimination evidence.",
        )

    noise_expected = [
        ("noise_02", 0.4045, 1.4323, 0.0, 0.0),
        ("noise_05", 1.3452, 3.7574, 0.0, 0.0),
        ("noise_10", 4.4127, 13.1183, 33.93, 2.91),
    ]
    previous_mean = -1.0
    previous_p95 = -1.0
    monotonic = True
    for condition, mean_expected, p95_expected, soft_expected, hard_expected in noise_expected:
        item = row_by(nis_noise, condition_id=condition)
        mean_actual = as_float(item["nismean_mean"])
        p95_actual = as_float(item["nisp95_mean"])
        soft_actual = as_float(item["nissoftviolations_mean"])
        hard_actual = as_float(item["nishardviolations_mean"])
        monotonic = monotonic and mean_actual > previous_mean and p95_actual > previous_p95
        previous_mean = mean_actual
        previous_p95 = p95_actual
        status = "PASS" if all(
            status_close(a, e, tol=1e-3) == "PASS"
            for a, e in ((mean_actual, mean_expected), (p95_actual, p95_expected), (soft_actual, soft_expected), (hard_actual, hard_expected))
        ) else "FAIL"
        add(
            audit,
            f"nis_noise_{condition}",
            f"NIS noise diagnostic values for {condition}.",
            f"mean={fmt(mean_expected)}; p95={fmt(p95_expected)}; soft={fmt(soft_expected, 2)}; hard={fmt(hard_expected, 2)}",
            f"mean={fmt(mean_actual)}; p95={fmt(p95_actual)}; soft={fmt(soft_actual, 2)}; hard={fmt(hard_actual, 2)}",
            status,
            "carla_nis_noise_sweep_qgip100_summary.csv",
            "Diagnostic sensitivity evidence; not a final covariance calibration proof.",
        )
    add(
        audit,
        "nis_noise_monotonicity",
        "NIS mean and episode p95 increase monotonically across 0.2/0.5/1.0 m noise.",
        "strictly increasing",
        "strictly increasing" if monotonic else "not monotonic",
        "PASS" if monotonic else "FAIL",
        "carla_nis_noise_sweep_qgip100_summary.csv",
        "Monotonic response check only.",
    )

    outlier_expected = [
        ("fp_10", 256.7829, 1621.7783, 80.42),
        ("idswitch_20", 155.3784, 971.7909, 25.93),
        ("fp10_idswitch20_noise05", 240.6521, 1506.2723, 72.23),
    ]
    for condition, mean_expected, p95_expected, resets_expected in outlier_expected:
        item = row_by(nis_outlier, condition_id=condition)
        mean_actual = as_float(item["nismean_mean"])
        p95_actual = as_float(item["nisp95_mean"])
        resets_actual = as_float(item["kfhardresets_mean"])
        status = "PASS" if all(
            status_close(a, e, tol=1e-3) == "PASS"
            for a, e in ((mean_actual, mean_expected), (p95_actual, p95_expected), (resets_actual, resets_expected))
        ) else "FAIL"
        add(
            audit,
            f"nis_outlier_{condition}",
            f"NIS outlier diagnostic values for {condition}.",
            f"mean={fmt(mean_expected)}; p95={fmt(p95_expected)}; hard_resets={fmt(resets_expected, 2)}",
            f"mean={fmt(mean_actual)}; p95={fmt(p95_actual)}; hard_resets={fmt(resets_actual, 2)}",
            status,
            "carla_nis_outlier_qgip100_summary.csv",
            "Outlier-response evidence; not real-sensor calibration.",
        )

    add(
        audit,
        "repository_deposit_manifest_rows",
        "Repository deposit manifest covers the current stable deposit files.",
        "at least 131 rows; 134 rows after statistical-audit artifacts are included",
        f"{len(deposit_manifest)} rows",
        "PASS" if len(deposit_manifest) >= 131 else "FAIL",
        "repository_deposit_manifest_20260603.csv",
        "Local DOI-ready manifest only; no public DOI has been minted.",
    )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AuditRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in audit])

    failed = [row for row in audit if row.status != "PASS"]
    lines = [
        "# Statistical Claim Audit Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"The statistical claim audit checks {len(audit)} key numerical claims against staged source data.",
        f"Passed: {len(audit) - len(failed)}",
        f"Failed: {len(failed)}",
        "All audited claims matched their current processed source-data records." if not failed else "One or more audited claims did not match the staged source data.",
        "",
        "The audit supports the current simulation-first evidence narrative, but it does not prove raw CARLA rerun reproducibility, validate ROS2, complete physical robot validation, mint a DOI, or prove real-world safety.",
        "",
        "## Checked Claim Families",
        "",
        "- Dataset split counts, missing-file counts, and train/validation/test overlap.",
        "- Primary ambiguity stress LeaderAcc and paired bootstrap intervals.",
        "- ID-switch stress LeaderAcc and ID-switch counts.",
        "- Supplemental boundary stress outcomes.",
        "- Finite-sample zero observed collision/near-miss observations in completed QGIP stress rows.",
        "- N=1000 nominal low-ambiguity outcomes.",
        "- CARLA NIS noise and outlier diagnostic values.",
        "- Repository deposit manifest row count.",
        "",
        "## Boundary",
        "",
        "Every zero-collision check is a finite-sample simulation observation. The audit is",
        "designed to prevent manuscript/source-data drift; it must not be interpreted as",
        "real-world risk certification.",
    ]
    if failed:
        lines.extend(["", "## Failed Checks", ""])
        for row in failed:
            lines.append(f"- `{row.claim_id}`: expected {row.expected}; actual {row.actual}")
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(audit) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
