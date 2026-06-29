#!/usr/bin/env python3
"""Generate a bounded safety-case claim graph for the simulation-first package."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
TABLES = ROOT / "08_paper_ready_outputs" / "tables"
PACKAGE = ROOT / "06_submission_package"
MANUSCRIPT = ROOT / "01_manuscript" / "RA_L_extended_working.tex"

OUT_CSV = SOURCE / "safety_case_claim_graph.csv"
OUT_TABLE = TABLES / "table_safety_case_claim_graph.tex"
OUT_REPORT = PACKAGE / "safety_case_audit_report_20260604.md"


@dataclass
class SafetyCaseRow:
    node_id: str
    claim_layer: str
    claim_or_assumption: str
    evidence_artifacts: str
    evidence_status: str
    boundary: str
    next_required_evidence: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def exists_rel(rel: str) -> bool:
    path = ROOT / rel
    return path.exists() and path.stat().st_size > 0


def all_pass(rel: str, expected_rows: int) -> bool:
    path = ROOT / rel
    if not path.exists():
        return False
    rows = read_csv(path)
    return len(rows) == expected_rows and all(row.get("status") == "PASS" for row in rows)


def contains_terms(path: Path, terms: tuple[str, ...]) -> bool:
    if not path.exists():
        return False
    body = path.read_text(encoding="utf-8", errors="replace").lower()
    return all(term.lower() in body for term in terms)


def status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def build_rows() -> list[SafetyCaseRow]:
    rows = [
        SafetyCaseRow(
            "SC0",
            "top claim",
            "The package supports a bounded simulation-first safety argument for structured-road following under the tested perception-uncertainty protocols.",
            "claim_evidence_matrix.csv; statistical_claim_audit.csv; RA_L_extended_working.tex",
            status(all_pass("08_paper_ready_outputs/source_data/statistical_claim_audit.csv", 36) and exists_rel("08_paper_ready_outputs/source_data/claim_evidence_matrix.csv")),
            "The argument is simulation-first and does not prove zero real-world risk, unrestricted deployment, or completed physical validation.",
            "Independent raw-run reproduction, DOI-backed repository, ROS2/HIL timing, and supervised robot trials.",
        ),
        SafetyCaseRow(
            "SC1",
            "ODD and split control",
            "The evaluation ODD and dataset split are explicit enough to prevent route/map leakage overclaims.",
            "final_dataset_split_check.csv; final_dataset_split_overlap.csv; table_dataset_split_audit.tex",
            status(exists_rel("08_paper_ready_outputs/source_data/final_dataset_split_check.csv") and exists_rel("08_paper_ready_outputs/source_data/final_dataset_split_overlap.csv")),
            "Split checks prove file-level separation only; Town10HD/Leaderboard remains stress evidence, not unrestricted map-level deployment proof.",
            "External held-out maps and raw route manifests deposited with DOI metadata.",
        ),
        SafetyCaseRow(
            "SC2",
            "target-consistency evidence",
            "The main discriminating benefit is improved target consistency under ambiguity, not universal mission-completion superiority.",
            "stress_summary_combined.csv; pairwise_stats_combined.csv; claim_evidence_matrix.csv",
            status(exists_rel("08_paper_ready_outputs/source_data/stress_summary_combined.csv") and exists_rel("08_paper_ready_outputs/source_data/pairwise_stats_combined.csv")),
            "Route-level completion can remain equal under conservative MPC; target-consistency metrics carry the central comparative claim.",
            "Additional ambiguous multi-agent scenarios with raw logs and independent reruns.",
        ),
        SafetyCaseRow(
            "SC3",
            "finite-sample collision interpretation",
            "Zero observed collisions are reported as finite-sample observations with a rule-of-three boundary.",
            "statistical_claim_audit.csv; RA_L_extended_working.tex",
            status(all_pass("08_paper_ready_outputs/source_data/statistical_claim_audit.csv", 36) and contains_terms(MANUSCRIPT, ("rule of three", "not imply zero real-world risk"))),
            "A finite simulation protocol cannot certify true collision probability as zero.",
            "Larger raw reruns, independent scenario sampling, and physical safety-supervisor logs.",
        ),
        SafetyCaseRow(
            "SC4",
            "fail-safe availability trade-off",
            "Fail-safe stops are counted as task failures, making the safety-versus-availability trade-off visible.",
            "claim_evidence_matrix.csv; RA_L_extended_working.tex",
            status(contains_terms(MANUSCRIPT, ("fail-safe stops as task failures", "safety vs."))),
            "Conservatism can reduce availability; the current paper does not solve all stopping or semantic rule-compliance failures.",
            "Risk-aware planner tuning and real-world operator-reviewed availability metrics.",
        ),
        SafetyCaseRow(
            "SC5",
            "uncertainty monitor response",
            "NIS/POP diagnostics expose uncertainty response under noise and outlier perturbations.",
            "carla_nis_noise_sweep_qgip100_summary.csv; carla_nis_outlier_qgip100_summary.csv; fig_extended_nis_response",
            status(exists_rel("08_paper_ready_outputs/source_data/carla_nis_noise_sweep_qgip100_summary.csv") and exists_rel("08_paper_ready_outputs/figures/fig_extended_nis_response.svg")),
            "NIS diagnostics are not real-sensor calibration and do not prove ROS2 runtime behavior.",
            "Sensor-calibrated residual distributions and ROS2 bagged NIS traces.",
        ),
        SafetyCaseRow(
            "SC6",
            "stress coverage",
            "Detector/timing, raw-sensor-like, ambiguity, boundary, and NIS diagnostic layers reduce single-protocol dependence.",
            "simulation_protocol_registry.csv; stress_summary_combined.csv; publication_figure_qa.csv",
            status(all_pass("08_paper_ready_outputs/source_data/simulation_protocol_registry.csv", 21) and all_pass("08_paper_ready_outputs/source_data/publication_figure_qa.csv", 92)),
            "Layered stress coverage remains scripted simulation evidence, not photorealistic raw-sensor validation.",
            "Raw-sensor replay, weather/lighting sweeps, and independent stress-protocol reruns.",
        ),
        SafetyCaseRow(
            "SC7",
            "ROS2 preflight readiness",
            "ROS2 interface, CI, software-smoke, HIL-manifest, and gate audits prepare the system for supervised real-robot validation.",
            "ros2_static_interface_audit.csv; ros2_workspace_ci_audit.csv; real_robot_software_smoke_test.csv; pre_real_robot_gate_audit.csv",
            status(all_pass("08_paper_ready_outputs/source_data/ros2_static_interface_audit.csv", 19) and all_pass("08_paper_ready_outputs/source_data/pre_real_robot_gate_audit.csv", 23)),
            "Static and desktop checks do not prove colcon build/test, live ros2 launch, rosbag timing, or robot motion.",
            "Executed colcon logs, launch logs, bags, HIL replay summaries, and operator-signed run manifests.",
        ),
        SafetyCaseRow(
            "SC8",
            "runtime telemetry readiness",
            "Runtime telemetry schema, manifest, audit, and parser dry-run make future HIL/robot timing evidence immediately auditable.",
            "ros2_runtime_telemetry_audit.csv; ros2_runtime_telemetry_dryrun_summary.csv; runtime_telemetry_manifest_template.yaml",
            status(all_pass("08_paper_ready_outputs/source_data/ros2_runtime_telemetry_audit.csv", 15) and all_pass("08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_summary.csv", 16)),
            "Telemetry readiness and synthetic parser QA do not prove live ROS2 timing, embedded feasibility, or physical robot motion.",
            "Filled runtime telemetry CSVs, rosbag metadata, topic-hz logs, system-load logs, and incident reports.",
        ),
        SafetyCaseRow(
            "SC9",
            "publication and data provenance",
            "Figure/table QA, source-data provenance, reproducibility capsule, and local deposit metadata control package drift.",
            "publication_figure_qa.csv; source_data_provenance_audit.csv; reproducibility_command_manifest_20260604.csv; repository_deposit_manifest_20260603.csv",
            status(all_pass("08_paper_ready_outputs/source_data/source_data_provenance_audit.csv", 96) and exists_rel("06_submission_package/repository_deposit_manifest_20260603.csv")),
            "Local provenance is not a DOI-backed repository and does not replace independent raw-data reproduction.",
            "Public repository DOI/accession, licence, reviewer link, and raw-run reproduction instructions.",
        ),
        SafetyCaseRow(
            "SC10",
            "non-claim boundary",
            "The manuscript and audit reports explicitly block physical-validation, zero-risk, and deployment-safety overclaims.",
            "manuscript_argument_traceability.csv; reviewer_risk_response_matrix_20260603.md; full_goal_completion_audit_20260603.md",
            status(all_pass("08_paper_ready_outputs/source_data/manuscript_argument_traceability.csv", 22) and contains_terms(MANUSCRIPT, ("simulation-only", "not a ROS2 build, launch, rosbag, timing, or physical robot trial result"))),
            "Lexical and artifact-level boundary checks do not replace expert review.",
            "Reviewer-facing response updates after raw reruns, ROS2/HIL logs, DOI deposit, and robot trials.",
        ),
        SafetyCaseRow(
            "SC11",
            "remaining validation gap",
            "The remaining gap is external execution evidence rather than missing local pre-real-robot package structure.",
            "full_goal_completion_audit_20260603.md; pre_real_robot_gate_audit_report_20260604.md; repository_deposit_readiness_report_20260603.md",
            status(contains_terms(PACKAGE / "pre_real_robot_gate_audit_report_20260604.md", ("does not prove ROS2 build success", "does not contain completed physical robot trial data"))),
            "The package is not complete for a physical-validation claim.",
            "Run colcon build/test, ros2 launch, HIL replay, runtime telemetry extraction, physical trials, and DOI deposit.",
        ),
    ]
    return rows


def esc(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}")
        .replace("_", "\\_")
        .replace("%", "\\%")
        .replace("&", "\\&")
        .replace("#", "\\#")
    )


def write_csv(rows: list[SafetyCaseRow]) -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(SafetyCaseRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])


def write_table(rows: list[SafetyCaseRow]) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    selected = [row for row in rows if row.node_id in {"SC0", "SC2", "SC3", "SC7", "SC8", "SC10", "SC11"}]
    lines = [
        "% Auto-generated by generate_safety_case_audit.py",
        "\\renewcommand{\\arraystretch}{0.94}",
        "\\begin{tabular}{@{}p{0.11\\linewidth} p{0.26\\linewidth} p{0.24\\linewidth} p{0.29\\linewidth}@{}}",
        "\\toprule",
        "\\textbf{Node} & \\textbf{Claim} & \\textbf{Evidence} & \\textbf{Boundary / next evidence} \\\\",
        "\\midrule",
    ]
    for row in selected:
        lines.append(
            f"{esc(row.node_id)} & {esc(row.claim_layer)}: {esc(row.claim_or_assumption)} & "
            f"{esc(row.evidence_status)}; {esc(row.evidence_artifacts)} & "
            f"{esc(row.boundary)} Next: {esc(row.next_required_evidence)} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    OUT_TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(rows: list[SafetyCaseRow]) -> None:
    PACKAGE.mkdir(parents=True, exist_ok=True)
    failed = [row for row in rows if row.evidence_status != "PASS"]
    lines = [
        "# Safety-Case Claim Graph Audit Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"Rows: {len(rows)}",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All safety-case claim graph checks passed." if not failed else "One or more safety-case checks failed.",
        "",
        "## Scope",
        "",
        "This safety-case graph maps top-level safety, ODD, target-consistency, finite-sample collision, fail-safe, uncertainty-monitor, ROS2-preflight, runtime-telemetry, provenance, and non-claim boundary nodes to concrete artifacts.",
        "",
        "It does not prove zero real-world risk, raw CARLA rerun reproducibility, ROS2 launch/build success, HIL timing, embedded deployment feasibility, DOI publication, or physical robot validation.",
        "",
        "| status | node | layer | evidence |",
        "|---|---|---|---|",
    ]
    lines.extend(f"| {row.evidence_status} | {row.node_id} | {row.claim_layer} | {row.evidence_artifacts} |" for row in rows)
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = build_rows()
    write_csv(rows)
    write_table(rows)
    write_report(rows)
    failed = [row for row in rows if row.evidence_status != "PASS"]
    print(OUT_CSV)
    print(OUT_TABLE)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
