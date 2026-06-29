#!/usr/bin/env python3
"""Verify the current simulation-first manuscript and submission package.

The checks intentionally cover only claims that can be proven from local files:
source CSVs, LaTeX logs, compiled PDFs, and the structured ZIP archive. This is
not a scientific proof of external validity; it is a reproducibility and
claim-consistency gate for the current CARLA-first submission package.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "RA_L_optimization_20260528"
MANUSCRIPT = WORK / "01_manuscript"
SOURCE = WORK / "08_paper_ready_outputs" / "source_data"
TABLES = WORK / "08_paper_ready_outputs" / "tables"
PACKAGE = WORK / "06_submission_package"
REPORT = PACKAGE / "submission_verification_report_20260603.md"


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


checks: list[Check] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    checks.append(Check(name, passed, detail))


def require(condition: bool, name: str, detail: str = "") -> None:
    record(name, condition, detail)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def row_by(rows: list[dict[str, str]], **keys: str) -> dict[str, str]:
    for row in rows:
        if all(row.get(key) == value for key, value in keys.items()):
            return row
    raise AssertionError(f"missing row {keys}")


def close(value: str | float, expected: float, tol: float = 1e-6) -> bool:
    return abs(float(value) - expected) <= tol


def pct_text(value: str | float) -> str:
    return f"{100.0 * float(value):.1f}\\%"


def num_text(value: str | float, digits: int = 1) -> str:
    return f"{float(value):.{digits}f}"


def expect_text(text: str, needle: str, name: str) -> None:
    require(needle in text, name, f"needle={needle!r}")


def latest_versioned_path(pattern: str, kind: str) -> Path:
    candidates: list[tuple[int, Path]] = []
    for path in PACKAGE.glob(pattern):
        match = re.search(r"_v(\d+)_structured", path.name)
        if match:
            candidates.append((int(match.group(1)), path))
    if not candidates:
        raise AssertionError(f"no versioned {kind} matching {pattern}")
    return max(candidates, key=lambda item: item[0])[1]


def package_version(path: Path) -> int:
    match = re.search(r"_v(\d+)_structured", path.name)
    if not match:
        raise AssertionError(f"could not parse package version from {path.name}")
    return int(match.group(1))


def pdf_pages(path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or f"pdfinfo failed for {path}")
    match = re.search(r"^Pages:\s+(\d+)$", result.stdout, flags=re.MULTILINE)
    if not match:
        raise AssertionError(f"could not parse page count for {path}")
    return int(match.group(1))


def check_required_files() -> None:
    required = [
        MANUSCRIPT / "RA_L_main_working.tex",
        MANUSCRIPT / "RA_L_main_working.pdf",
        MANUSCRIPT / "RA_L_supplemental_simulation_results.tex",
        MANUSCRIPT / "RA_L_supplemental_simulation_results.pdf",
        SOURCE / "main_benchmark_source.csv",
        SOURCE / "main1000_nominal_source.csv",
        SOURCE / "stress_summary_combined.csv",
        SOURCE / "pairwise_stats_combined.csv",
        SOURCE / "carla_scenario_coverage_source.csv",
        SOURCE / "carla_nis_noise_sweep_qgip100_summary.csv",
        SOURCE / "carla_nis_outlier_qgip100_summary.csv",
        SOURCE / "final_dataset_split_check.csv",
        SOURCE / "final_dataset_split_overlap.csv",
        SOURCE / "final_dataset_split_check.md",
        TABLES / "table_carla_nis_noise_sweep.tex",
        TABLES / "table_carla_nis_outlier_sweep.tex",
    ]
    for path in required:
        require(path.exists(), f"required file exists: {path.relative_to(WORK)}")


def check_latex_and_pdf() -> None:
    main_log = read_text(MANUSCRIPT / "RA_L_main_working.log")
    supp_log = read_text(MANUSCRIPT / "RA_L_supplemental_simulation_results.log")
    bad = re.compile(
        r"(LaTeX Error|Package .* Error|Fatal error|Emergency stop|Undefined control sequence|"
        r"There were undefined references|Citation .* undefined|Reference .* undefined|"
        r"Overfull \\hbox|Overfull \\vbox)",
        re.IGNORECASE,
    )
    require(not bad.search(main_log), "main LaTeX log has no fatal/undefined/overfull errors")
    require(not bad.search(supp_log), "supplement LaTeX log has no fatal/undefined/overfull errors")
    require(pdf_pages(MANUSCRIPT / "RA_L_main_working.pdf") == 8, "main PDF is 8 pages")
    require(pdf_pages(MANUSCRIPT / "RA_L_supplemental_simulation_results.pdf") == 2, "supplement PDF is 2 pages")


def check_manuscript_claims() -> None:
    main_tex = read_text(MANUSCRIPT / "RA_L_main_working.tex")
    supp_tex = read_text(MANUSCRIPT / "RA_L_supplemental_simulation_results.tex")
    main_benchmark = read_csv(SOURCE / "main_benchmark_source.csv")
    main1000 = read_csv(SOURCE / "main1000_nominal_source.csv")
    stress = read_csv(SOURCE / "stress_summary_combined.csv")
    pairwise = read_csv(SOURCE / "pairwise_stats_combined.csv")
    boundary = row_by(stress, condition_id="fp20_idswitch20", method="qgip")
    boundary_no_query = row_by(stress, condition_id="fp20_idswitch20", method="qgip_no_query")
    boundary_rule = row_by(stress, condition_id="fp20_idswitch20", method="rule")

    qgip_main = row_by(main_benchmark, method="QGIP-Net (Ours)")
    std_main = row_by(main_benchmark, method="Std KF + MPC")
    require(qgip_main["success"] == "230" and close(qgip_main["success_rate"], 0.7666666667, 1e-4), "main benchmark QGIP source is 230/300 success")
    require(std_main["success"] == "220" and close(std_main["success_rate"], 0.7333333333, 1e-4), "main benchmark Std-KF source is 220/300 success")
    expect_text(main_tex, "76.7\\%", "main text contains QGIP 76.7% benchmark")
    expect_text(main_tex, "73.3\\%", "main text contains Std-KF 73.3% benchmark")

    for row in main1000:
        require(
            row["n"] == "1000"
            and row["success"] == "735"
            and row["lost"] == "265"
            and row["collision"] == "0"
            and row["near_miss"] == "0",
            f"N=1000 nominal source counts for {row['method']}",
        )
    for needle in ("735/1000", "73.5\\%", "265/1000", "26.5\\%", "zero observed collisions", "zero near-misses"):
        expect_text(main_tex, needle, f"main text contains N=1000 claim token {needle}")

    fp_qgip = row_by(stress, condition_id="fp_10", method="qgip")
    fp_no_query = row_by(stress, condition_id="fp_10", method="qgip_no_query")
    fp_rule = row_by(stress, condition_id="fp_10", method="rule")
    ids_qgip = row_by(stress, condition_id="idswitch", method="qgip")
    ids_std = row_by(stress, condition_id="idswitch", method="std_kf")
    ids_rule = row_by(stress, condition_id="idswitch", method="rule")
    claim_rows = [
        (fp_qgip, 0.8624215919, "fp_10 QGIP LeaderAcc"),
        (fp_no_query, 0.5316686851, "fp_10 no-query LeaderAcc"),
        (fp_rule, 0.4378830958, "fp_10 rule LeaderAcc"),
        (ids_qgip, 0.9067758293, "idswitch QGIP LeaderAcc"),
        (ids_std, 0.5604415650, "idswitch Std-KF LeaderAcc"),
        (ids_rule, 0.4765061332, "idswitch rule LeaderAcc"),
        (boundary, 0.800, "boundary QGIP LeaderAcc"),
        (boundary_no_query, 0.478, "boundary no-query LeaderAcc"),
        (boundary_rule, 0.362, "boundary rule LeaderAcc"),
    ]
    for row, expected, name in claim_rows:
        require(close(row["leaderacc_mean"], expected, 0.0006), name)
        expect_text(main_tex, pct_text(row["leaderacc_mean"]), f"main text contains {name} formatted value")
    for row, expected, name in [
        (ids_qgip, 39.1966667, "idswitch QGIP ID-switches"),
        (ids_std, 180.6066667, "idswitch Std-KF ID-switches"),
        (ids_rule, 155.1666667, "idswitch rule ID-switches"),
    ]:
        require(close(row["idswitches_mean"], expected, 0.0006), name)
        expect_text(main_tex, num_text(row["idswitches_mean"], 1), f"main text contains {name} formatted value")

    pair_claims = [
        ("fp_10", "qgip_no_query", "+0.331", "[0.304, 0.358]"),
        ("fp_10", "rule", "+0.425", "[0.378, 0.471]"),
        ("idswitch", "std_kf", "+0.346", "[0.314, 0.378]"),
        ("idswitch", "rule", "+0.430", "[0.379, 0.478]"),
    ]
    for condition, comparison, diff_text, ci_text in pair_claims:
        row = row_by(pairwise, condition_id=condition, reference_method="qgip", comparison_method=comparison)
        require(float(row["leaderacc_diff_ref_minus_cmp"]) > 0.3, f"paired LeaderAcc gain positive for {condition} vs {comparison}")
        expect_text(main_tex, diff_text, f"main text contains paired diff {condition} vs {comparison}")
        expect_text(main_tex, ci_text, f"main text contains paired CI {condition} vs {comparison}")

    expect_text(supp_tex, "CARLA NIS diagnostic sweep", "supplement contains NIS noise diagnostic")
    expect_text(supp_tex, "CARLA NIS outlier and ambiguity diagnostic", "supplement contains NIS outlier diagnostic")


def check_nis_sources_and_tables() -> None:
    noise = read_csv(SOURCE / "carla_nis_noise_sweep_qgip100_summary.csv")
    outlier = read_csv(SOURCE / "carla_nis_outlier_qgip100_summary.csv")
    noise_table = read_text(TABLES / "table_carla_nis_noise_sweep.tex")
    outlier_table = read_text(TABLES / "table_carla_nis_outlier_sweep.tex")
    ordered_noise = [row_by(noise, condition_id=item) for item in ("noise_02", "noise_05", "noise_10")]
    nis_means = [float(row["nismean_mean"]) for row in ordered_noise]
    nisp95 = [float(row["nisp95_mean"]) for row in ordered_noise]
    require(nis_means == sorted(nis_means), "NIS noise-sweep means increase monotonically")
    require(nisp95 == sorted(nisp95), "NIS noise-sweep p95 values increase monotonically")
    for row in ordered_noise:
        require(row["n"] == "100" and row["success_count"] == "76" and row["collision_count"] == "0", f"NIS noise source counts for {row['condition_id']}")
    for needle in ("0.405", "1.345", "4.413", "13.118", "33.9/2.9"):
        expect_text(noise_table, needle, f"NIS noise table contains {needle}")

    for condition in ("fp_10", "idswitch_20", "fp10_idswitch20_noise05"):
        row = row_by(outlier, condition_id=condition)
        require(row["n"] == "100" and row["success_count"] == "75" and row["lost_count"] == "25" and row["collision_count"] == "0", f"NIS outlier source counts for {condition}")
        require(float(row["nisp95_mean"]) > 900.0, f"NIS outlier p95 is large for {condition}")
        require(float(row["kfhardresets_mean"]) > 20.0, f"NIS outlier hard resets are nontrivial for {condition}")
    for needle in ("1621.8", "971.8", "1506.3", "80.4", "25.9", "72.2"):
        expect_text(outlier_table, needle, f"NIS outlier table contains {needle}")


def check_scenario_coverage() -> None:
    rows = read_csv(SOURCE / "carla_scenario_coverage_source.csv")
    expected = {
        "straight/curve following",
        "curve following",
        "following with dropout",
        "lead braking",
        "adjacent-lane distractor",
        "cut-in/cut-out identity",
        "combined boundary ambiguity",
    }
    observed = {row["scenario_class"] for row in rows}
    require(expected <= observed, "scenario coverage source includes all named scenario classes", f"observed={sorted(observed)}")
    require(len(rows) >= 7, "scenario coverage has at least seven rows")


def check_dataset_split() -> None:
    rows = read_csv(SOURCE / "final_dataset_split_check.csv")
    overlap = read_csv(SOURCE / "final_dataset_split_overlap.csv")
    expected = {
        "train": ("4050", "4050", "0"),
        "val": ("450", "450", "0"),
        "test_unseen": ("500", "500", "0"),
    }
    for split, (n, existing, missing) in expected.items():
        row = row_by(rows, split=split)
        require(
            row["n"] == n and row["existing_files"] == existing and row["missing_files"] == missing,
            f"dataset split counts verified for {split}",
        )
    for row in overlap:
        require(row["overlap_paths"] == "0", f"dataset split overlap is zero for {row['pair']}")
    report_text = read_text(SOURCE / "final_dataset_split_check.md")
    expect_text(report_text, "train vs test_unseen | 0", "dataset split report states train/test overlap is zero")


def check_package() -> None:
    staging = latest_versioned_path("current_ra_l_simulation_first_20260603_v*_structured", "staging folder")
    archive_path = latest_versioned_path("current_ra_l_simulation_first_20260603_final_v*_structured.zip", "zip")
    version = package_version(archive_path)
    staging_files = [path for path in staging.rglob("*") if path.is_file()]
    with zipfile.ZipFile(archive_path, "r") as archive:
        entries = archive.namelist()
    entry_set = {entry.replace("/", "\\") for entry in entries}
    require(len(entries) == len(staging_files), "ZIP entry count matches staging file count", f"zip={len(entries)} staging={len(staging_files)}")

    required_entries = [
        "01_manuscript\\RA_L_main_working.tex",
        "01_manuscript\\RA_L_main_working.pdf",
        "01_manuscript\\RA_L_supplemental_simulation_results.tex",
        "01_manuscript\\RA_L_supplemental_simulation_results.pdf",
        "08_paper_ready_outputs\\source_data\\carla_nis_outlier_qgip100_summary.csv",
        "08_paper_ready_outputs\\source_data\\final_dataset_split_check.csv",
        "08_paper_ready_outputs\\source_data\\final_dataset_split_overlap.csv",
        "08_paper_ready_outputs\\tables\\table_carla_nis_outlier_sweep.tex",
        f"09_pdf_qa\\contact_sheet_v{version}.png",
        f"09_pdf_qa\\main_v{version}_page-6.png",
        f"09_pdf_qa\\supp_v{version}_page-2.png",
        "04_simulation_stress\\build_carla_stress_queue.py",
        "04_simulation_stress\\run_stress_queue_managed.ps1",
        "05_analysis_scripts\\generate_paper_sim_artifacts.py",
        "05_analysis_scripts\\generate_nis_diagnostic_artifacts.py",
        "05_analysis_scripts\\summarize_carla_stress_results.py",
        "05_analysis_scripts\\verify_submission_package.py",
    ]
    for entry in required_entries:
        require(entry in entry_set, f"ZIP contains required entry {entry}")

    stale_versions = "|".join(f"_v{item}_" for item in range(1, version))
    forbidden = re.compile(rf"(\.(aux|log|out|toc)$|synctex\.gz$|qgip_net_architecture\.pdf$|qgip30|{stale_versions})", re.IGNORECASE)
    bad_entries = [entry for entry in entry_set if forbidden.search(entry)]
    require(not bad_entries, "ZIP has no LaTeX temps, stale version names, or obsolete large architecture PDF", ", ".join(sorted(bad_entries[:10])))

    compare_sources = {
        "01_manuscript\\RA_L_main_working.tex": MANUSCRIPT / "RA_L_main_working.tex",
        "01_manuscript\\RA_L_main_working.pdf": MANUSCRIPT / "RA_L_main_working.pdf",
        "01_manuscript\\RA_L_supplemental_simulation_results.tex": MANUSCRIPT / "RA_L_supplemental_simulation_results.tex",
        "01_manuscript\\RA_L_supplemental_simulation_results.pdf": MANUSCRIPT / "RA_L_supplemental_simulation_results.pdf",
        "08_paper_ready_outputs\\source_data\\main_benchmark_source.csv": SOURCE / "main_benchmark_source.csv",
        "08_paper_ready_outputs\\source_data\\main1000_nominal_source.csv": SOURCE / "main1000_nominal_source.csv",
        "08_paper_ready_outputs\\source_data\\stress_summary_combined.csv": SOURCE / "stress_summary_combined.csv",
        "08_paper_ready_outputs\\source_data\\pairwise_stats_combined.csv": SOURCE / "pairwise_stats_combined.csv",
        "08_paper_ready_outputs\\source_data\\carla_nis_outlier_qgip100_summary.csv": SOURCE / "carla_nis_outlier_qgip100_summary.csv",
        "08_paper_ready_outputs\\source_data\\final_dataset_split_check.csv": SOURCE / "final_dataset_split_check.csv",
        "08_paper_ready_outputs\\source_data\\final_dataset_split_overlap.csv": SOURCE / "final_dataset_split_overlap.csv",
        "08_paper_ready_outputs\\source_data\\final_dataset_split_check.md": SOURCE / "final_dataset_split_check.md",
        "08_paper_ready_outputs\\tables\\table_carla_nis_outlier_sweep.tex": TABLES / "table_carla_nis_outlier_sweep.tex",
        "04_simulation_stress\\build_carla_stress_queue.py": WORK / "04_simulation_stress" / "build_carla_stress_queue.py",
        "04_simulation_stress\\run_stress_queue_managed.ps1": WORK / "04_simulation_stress" / "run_stress_queue_managed.ps1",
        "05_analysis_scripts\\generate_paper_sim_artifacts.py": WORK / "05_analysis_scripts" / "generate_paper_sim_artifacts.py",
        "05_analysis_scripts\\generate_nis_diagnostic_artifacts.py": WORK / "05_analysis_scripts" / "generate_nis_diagnostic_artifacts.py",
        "05_analysis_scripts\\verify_submission_package.py": WORK / "05_analysis_scripts" / "verify_submission_package.py",
    }
    with zipfile.ZipFile(archive_path, "r") as archive:
        entry_lookup = {entry.replace("/", "\\"): entry for entry in archive.namelist()}
        for entry, source in compare_sources.items():
            if entry not in entry_lookup:
                continue
            require(
                archive.read(entry_lookup[entry]) == source.read_bytes(),
                f"ZIP entry matches current workspace file {entry}",
            )


def write_report() -> None:
    passed = sum(1 for item in checks if item.passed)
    failed = len(checks) - passed
    lines = [
        "# Submission Verification Report",
        "",
        f"- Checks passed: {passed}",
        f"- Checks failed: {failed}",
        "",
        "| Status | Check | Detail |",
        "| --- | --- | --- |",
    ]
    for item in checks:
        status = "PASS" if item.passed else "FAIL"
        detail = item.detail.replace("|", "\\|") if item.detail else ""
        lines.append(f"| {status} | {item.name} | {detail} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    try:
        check_required_files()
        check_latex_and_pdf()
        check_manuscript_claims()
        check_nis_sources_and_tables()
        check_scenario_coverage()
        check_dataset_split()
        check_package()
    except Exception as exc:  # Keep report generation even for unexpected failures.
        record("verifier internal exception", False, repr(exc))
    write_report()
    failed = [item for item in checks if not item.passed]
    print(f"Wrote {REPORT}")
    print(f"checks_passed={len(checks) - len(failed)} checks_failed={len(failed)}")
    if failed:
        for item in failed:
            print(f"FAIL: {item.name}: {item.detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
