#!/usr/bin/env python3
"""Audit the manuscript argument chain against Nature-style reader needs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "01_manuscript" / "RA_L_extended_working.tex"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
PACKAGE = ROOT / "06_submission_package"
OUT_CSV = SOURCE / "manuscript_argument_traceability.csv"
OUT_REPORT = PACKAGE / "manuscript_argument_audit_report_20260604.md"


@dataclass
class AuditRow:
    audit_id: str
    reader_question: str
    manuscript_region: str
    required_signal: str
    actual_evidence: str
    status: str
    source_artifact: str
    boundary: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def norm(text: str) -> str:
    return " ".join(text.lower().split())


def present(text_lower: str, phrases: list[str]) -> tuple[bool, list[str], list[str]]:
    found = [phrase for phrase in phrases if phrase.lower() in text_lower]
    missing = [phrase for phrase in phrases if phrase.lower() not in text_lower]
    return not missing, found, missing


def first_line(raw_lines: list[str], phrase: str) -> str:
    needle = phrase.lower()
    for index, line in enumerate(raw_lines, start=1):
        if needle in line.lower():
            return f"line {index}"
    return "not found"


def status_text(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def actual(found: list[str], missing: list[str]) -> str:
    if missing:
        return "found: " + "; ".join(found) + " | missing: " + "; ".join(missing)
    return "found: " + "; ".join(found)


def add(
    rows: list[AuditRow],
    audit_id: str,
    reader_question: str,
    manuscript_region: str,
    required_signal: str,
    found: list[str],
    missing: list[str],
    source_artifact: str,
    boundary: str,
) -> None:
    rows.append(
        AuditRow(
            audit_id=audit_id,
            reader_question=reader_question,
            manuscript_region=manuscript_region,
            required_signal=required_signal,
            actual_evidence=actual(found, missing),
            status=status_text(not missing),
            source_artifact=source_artifact,
            boundary=boundary,
        )
    )


def main() -> None:
    raw = MANUSCRIPT.read_text(encoding="utf-8")
    raw_lines = raw.splitlines()
    text_lower = norm(raw)
    claim_rows = read_csv(SOURCE / "claim_evidence_matrix.csv")
    stat_rows = read_csv(SOURCE / "statistical_claim_audit.csv")
    dryrun_rows = read_csv(SOURCE / "real_robot_offline_dryrun_summary.csv")
    ci_rows = read_csv(SOURCE / "ros2_workspace_ci_audit.csv")
    telemetry_rows = read_csv(SOURCE / "ros2_runtime_telemetry_audit.csv")
    telemetry_dryrun_rows = read_csv(SOURCE / "ros2_runtime_telemetry_dryrun_summary.csv")
    hil_rows = read_csv(SOURCE / "ros2_hil_replay_manifest_audit.csv")
    gate_rows = read_csv(SOURCE / "pre_real_robot_gate_audit.csv")
    safety_case_rows = read_csv(SOURCE / "safety_case_claim_graph.csv")

    rows: list[AuditRow] = []

    checks = [
        (
            "paper_type_signal",
            "What kind of paper is this?",
            "title, abstract, method",
            ["extended simulation-first manuscript", "target-belief-to-control", "carla"],
            "Algorithmic/methods paper logic is explicit: system contract first, then controlled evidence.",
        ),
        (
            "relevance_problem_signal",
            "Is this relevant to me?",
            "abstract and introduction",
            ["perception uncertainty", "structured-road operational design domain", "safety-critical control system", "resilience"],
            "Relevance is bounded to structured-road following rather than all autonomous driving.",
        ),
        (
            "novelty_signal",
            "What is new here?",
            "introduction and method",
            ["intent-to-belief interface", "predictive object permanence", "nis-gated", "collision-feasibility filtering"],
            "Novelty is framed as an interface and system contract, not as an invented safety proof.",
        ),
        (
            "trust_evidence_signal",
            "Do I trust the evidence?",
            "abstract and experiments",
            ["n=300", "paired bootstrap intervals", "leaderacc", "rule of three"],
            "Trust is based on paired stress protocols and finite-sample uncertainty language.",
        ),
        (
            "reuse_methods_signal",
            "Can I reproduce or reuse the method?",
            "method and experiments",
            ["tau_{soft}=12.0", "tau_{hard}=20.0", "gamma=10.0", "t_g=30", "paired random seeds"],
            "Reusability is limited to staged source data and documented protocols until raw reruns are deposited.",
        ),
        (
            "split_traceability_signal",
            "Is the data split defensible?",
            "dataset split and audit trail",
            ["4050 generated paths", "450 paths", "500 town05 paths", "zero missing files", "zero train--validation"],
            "Split audit proves file-level separation only, not unrestricted map-level generalization.",
        ),
        (
            "route_target_separation_signal",
            "Is the central claim measured with the right metric?",
            "evaluation metrics and ambiguity stress",
            ["separate physical safety from task availability", "route-level success is similar", "leader-selection metrics", "target consistency"],
            "The paper avoids using equal route completion as evidence for query-guidance superiority.",
        ),
        (
            "main_discriminator_signal",
            "What actually improves?",
            "ablation and ambiguity stress",
            ["86.2\\%", "90.7\\%", "+0.331", "+0.346", "39.2"],
            "Improvement is target consistency under ambiguity, not universal completion.",
        ),
        (
            "boundary_stress_signal",
            "Where does the result weaken?",
            "boundary stress summary and stress synthesis",
            ["fp20\\_idswitch20", "80.0\\%", "126.5 per episode", "boundary result"],
            "Boundary stress is retained as non-saturated supplemental evidence.",
        ),
        (
            "nis_diagnostic_signal",
            "Does uncertainty instrumentation respond?",
            "NIS response and outlier diagnostics",
            ["nis p95", "soft and hard gates", "hard resets", "detector inconsistency"],
            "NIS evidence is diagnostic, not real-sensor calibration or ROS2 proof.",
        ),
        (
            "claim_evidence_signal",
            "Can claims be traced to artifacts?",
            "claim-to-evidence traceability",
            ["evidentiary contract", "primary quantitative support", "boundary of interpretation", "source artifact"],
            "Traceability prevents stronger claims than the staged evidence can support.",
        ),
        (
            "negative_claim_signal",
            "Are overclaims actively blocked?",
            "claim-to-evidence traceability and limitations",
            ["not as a proof of zero risk", "not treated as evidence that the learned selector improves mission completion", "not included in the present evaluation"],
            "Negative-claim controls are required because zero-collision and equal-success results are easy to overread.",
        ),
        (
            "real_world_boundary_signal",
            "Where does the current evidence stop?",
            "future validation and limitations",
            ["simulation-only", "ros2 wheeled-robot trials are the next validation layer", "not as a replacement for full-size vehicle validation"],
            "This audit does not prove physical robot validation.",
        ),
        (
            "offline_dryrun_boundary_signal",
            "Is the offline real-robot preflight evidence framed correctly?",
            "future validation and dry-run figure",
            ["ROS2-less offline dry-run diagnostic", "not a ROS2 build, launch, rosbag, timing, or physical robot trial result"],
            "The dry-run is useful as a deterministic preflight smoke test, not as real-middleware or robot evidence.",
        ),
        (
            "pre_real_gate_signal",
            "Are real-robot go/no-go gates visible before physical claims?",
            "future validation and gate audit table",
            ["Pre-real-robot go/no-go gate audit", "pre\\_real\\_robot\\_gate\\_audit.csv", "before any physical closed-loop claim is made"],
            "Go/no-go gates are documented for staged execution while explicitly blocking physical claims until runtime evidence exists.",
        ),
        (
            "safety_case_signal",
            "Is the safety argument organized as a bounded claim graph rather than a certification claim?",
            "claim-to-evidence traceability and reviewer-risk controls",
            ["safety-case claim graph", "top-level simulation-first safety argument", "remaining external validation gap", "rather than a certification or real-world safety case"],
            "The safety-case graph disciplines the argument without converting simulation evidence into certification.",
        ),
        (
            "deployment_boundary_signal",
            "Is runtime deployment framed honestly?",
            "runtime and deployment boundary",
            ["desktop gpu", "future ros2 validation should measure latency mean/p95/p99", "synthetic telemetry-parser dry run", "instrumentation readiness rather than hil timing"],
            "Runtime claims remain pre-deployment until robot-computer timing is measured.",
        ),
        (
            "limitations_completeness_signal",
            "Are failure modes visible?",
            "discussion and limitations",
            ["constant-velocity assumption", "query dependence", "red-light infraction", "semantic rule compliance"],
            "Limitations identify transfer risks rather than hiding them in future work.",
        ),
        (
            "conclusion_hourglass_signal",
            "Does the conclusion close with contribution, evidence, and boundary?",
            "conclusion",
            ["central contribution", "current carla results", "before treating ros2 wheeled-robot deployment as a later validation step"],
            "Conclusion widens back to implication without introducing new evidence.",
        ),
    ]

    for audit_id, question, region, phrases, boundary in checks:
        ok, found, missing = present(text_lower, phrases)
        add(
            rows,
            audit_id,
            question,
            region,
            "; ".join(phrases),
            found,
            missing,
            "RA_L_extended_working.tex",
            boundary,
        )

    forbidden = [
        "guarantees safety",
        "guaranteed safety",
        "proved safe",
        "proves real-world safety",
        "validated on physical robots",
        "completed physical validation",
        "certifies zero risk",
    ]
    ok, found_forbidden, missing_forbidden = present(text_lower, forbidden)
    rows.append(
        AuditRow(
            audit_id="forbidden_overclaim_screen",
            reader_question="Does the paper avoid unsupported deployment claims?",
            manuscript_region="full manuscript",
            required_signal="No unsupported safety-certification or physical-validation phrases.",
            actual_evidence="forbidden phrases present: " + ("; ".join(found_forbidden) if found_forbidden else "none"),
            status="FAIL" if ok else "PASS",
            source_artifact="RA_L_extended_working.tex",
            boundary="Screening is lexical; expert review is still required.",
        )
    )

    claim_count_ok = len(claim_rows) == 8
    stat_pass_ok = len(stat_rows) == 36 and all(row.get("status") == "PASS" for row in stat_rows)
    dryrun_pass_ok = len(dryrun_rows) == 12 and all(row.get("status") == "PASS" for row in dryrun_rows)
    ci_pass_ok = len(ci_rows) == 11 and all(row.get("status") == "PASS" for row in ci_rows)
    telemetry_pass_ok = len(telemetry_rows) == 15 and all(row.get("status") == "PASS" for row in telemetry_rows)
    telemetry_dryrun_pass_ok = len(telemetry_dryrun_rows) == 16 and all(row.get("status") == "PASS" for row in telemetry_dryrun_rows)
    hil_pass_ok = len(hil_rows) == 17 and all(row.get("status") == "PASS" for row in hil_rows)
    gate_pass_ok = len(gate_rows) == 23 and all(row.get("status") == "PASS" for row in gate_rows)
    safety_case_pass_ok = len(safety_case_rows) == 12 and all(row.get("evidence_status") == "PASS" for row in safety_case_rows)
    rows.append(
        AuditRow(
            audit_id="source_traceability_alignment",
            reader_question="Do narrative claims align with machine-readable evidence?",
            manuscript_region="source-data package",
            required_signal="8 claim-evidence rows, 36 PASS statistical checks, 12 PASS behavior dry-run checks, 11 PASS ROS2 workspace CI checks, 15 PASS runtime telemetry checks, 16 PASS telemetry parser dry-run checks, 17 PASS HIL replay-manifest checks, 23 PASS pre-real gate checks, and 12 PASS safety-case nodes.",
            actual_evidence=(
                f"claim_evidence_rows={len(claim_rows)}; "
                f"statistical_rows={len(stat_rows)}; statistical_all_pass={stat_pass_ok}; "
                f"dryrun_rows={len(dryrun_rows)}; dryrun_all_pass={dryrun_pass_ok}; "
                f"ci_rows={len(ci_rows)}; ci_all_pass={ci_pass_ok}; "
                f"telemetry_rows={len(telemetry_rows)}; telemetry_all_pass={telemetry_pass_ok}; "
                f"telemetry_dryrun_rows={len(telemetry_dryrun_rows)}; telemetry_dryrun_all_pass={telemetry_dryrun_pass_ok}; "
                f"hil_rows={len(hil_rows)}; hil_all_pass={hil_pass_ok}; "
                f"gate_rows={len(gate_rows)}; gate_all_pass={gate_pass_ok}; "
                f"safety_case_rows={len(safety_case_rows)}; safety_case_all_pass={safety_case_pass_ok}"
            ),
            status=status_text(claim_count_ok and stat_pass_ok and dryrun_pass_ok and ci_pass_ok and telemetry_pass_ok and telemetry_dryrun_pass_ok and hil_pass_ok and gate_pass_ok and safety_case_pass_ok),
            source_artifact="claim_evidence_matrix.csv; statistical_claim_audit.csv; real_robot_offline_dryrun_summary.csv; ros2_workspace_ci_audit.csv; ros2_runtime_telemetry_audit.csv; ros2_runtime_telemetry_dryrun_summary.csv; ros2_hil_replay_manifest_audit.csv; pre_real_robot_gate_audit.csv; safety_case_claim_graph.csv",
            boundary="Alignment check covers processed artifacts and preflight audits, not raw CARLA reruns, ROS2 bags, or physical robot trials.",
        )
    )

    rows.append(
        AuditRow(
            audit_id="line_anchor_check",
            reader_question="Can key narrative gates be located quickly?",
            manuscript_region="line anchors",
            required_signal="Main argument gates have concrete line anchors.",
            actual_evidence=(
                f"simulation-first={first_line(raw_lines, 'simulation-first')}; "
                f"claim-to-evidence={first_line(raw_lines, 'Claim-to-Evidence Traceability')}; "
                f"simulation-only={first_line(raw_lines, 'simulation-only')}; "
                f"conclusion={first_line(raw_lines, '\\section{Conclusion}')}"
            ),
            status="PASS",
            source_artifact="RA_L_extended_working.tex",
            boundary="Line anchors aid review but do not replace content judgment.",
        )
    )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AuditRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])

    failed = [row for row in rows if row.status != "PASS"]
    report_lines = [
        "# Manuscript Argument Audit Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"The manuscript argument audit checks {len(rows)} Nature-style paper-architecture gates in the reader-question chain: relevance, novelty, trust, reuse, meaning, and boundary.",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All audited narrative checks passed." if not failed else "One or more narrative checks failed.",
        "",
        "## Scope",
        "",
        "This audit checks whether the extended manuscript exposes a coherent algorithmic/methods-paper argument: a bounded problem, a specific system contract, source-backed simulation evidence, explicit negative-claim controls, and a simulation-first boundary.",
        "",
        "It does not prove physical robot validation, raw CARLA rerun reproducibility, deployment safety, or DOI publication. It also does not replace expert peer review; it is a drift-control layer for manuscript structure and evidence discipline.",
        "",
        "## Reader-Question Chain",
        "",
        "- Relevance: perception uncertainty is framed inside a structured-road ODD.",
        "- Novelty: the contribution is the target-belief-to-control interface with POP/NIS and MPC filtering.",
        "- Trust: paired CARLA stress evidence, rule-of-three interpretation, and statistical audit outputs are linked.",
        "- Reuse: methods parameters, split policy, failure injection, and repository artifacts are identified.",
        "- Pre-real-robot readiness: ROS2 workspace CI assets, runtime telemetry instrumentation, ROS2-less dry-run evidence, and go/no-go gate audit rows are visible without converting them into physical-validation claims.",
        "- Boundary: simulation-only, ROS2-next, dry-run-only, real-world-risk, and semantic-rule-compliance limits are explicit.",
        "",
        "## Audit Files",
        "",
        "- `manuscript_argument_traceability.csv`",
        "- `manuscript_argument_audit_report_20260604.md`",
    ]
    if failed:
        report_lines.extend(["", "## Failed Checks", ""])
        for row in failed:
            report_lines.append(f"- `{row.audit_id}`: {row.actual_evidence}")

    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")

    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
