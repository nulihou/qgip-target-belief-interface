#!/usr/bin/env python3
"""Verify the extended simulation-first manuscript package."""

from __future__ import annotations

import csv
import hashlib
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "06_submission_package"
REPORT = PACKAGE_DIR / "extended_submission_verification_report_20260603.md"


class CheckLog:
    def __init__(self) -> None:
        self.rows: list[tuple[bool, str, str]] = []

    def add(self, ok: bool, name: str, detail: str = "") -> None:
        self.rows.append((ok, name, detail))

    @property
    def failed(self) -> int:
        return sum(1 for ok, _, _ in self.rows if not ok)

    @property
    def passed(self) -> int:
        return sum(1 for ok, _, _ in self.rows if ok)


def latest_extended_zip() -> Path:
    candidates = sorted(PACKAGE_DIR.glob("current_extended_simulation_first_20260603_final_v*_structured.zip"))
    if not candidates:
        raise FileNotFoundError("no extended package zip found")

    def version(path: Path) -> int:
        match = re.search(r"_v(\d+)_structured\.zip$", path.name)
        return int(match.group(1)) if match else -1

    return max(candidates, key=version)


def rel(path: str) -> Path:
    return ROOT / path


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def text_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def python_source_compile_ok(path: Path) -> tuple[bool, str]:
    try:
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except Exception as exc:  # pragma: no cover - verifier reports exact blocker.
        return False, str(exc)
    return True, "syntax ok"


def main() -> None:
    log = CheckLog()
    zip_path = latest_extended_zip()
    log.add(zip_path.exists(), "extended zip exists", str(zip_path))
    log.add(zip_path.stat().st_size > 1_000_000, "extended zip has non-trivial size", "above 1,000,000 bytes")

    workspace_required = [
        "01_manuscript/RA_L_extended_working.pdf",
        "01_manuscript/RA_L_extended_working.tex",
        "05_analysis_scripts/generate_extended_artifacts.py",
        "05_analysis_scripts/generate_nature_main_figure.py",
        "05_analysis_scripts/generate_figure_accessibility_qa.py",
        "05_analysis_scripts/generate_repository_deposit_artifacts.py",
        "05_analysis_scripts/generate_reproducibility_capsule.py",
        "05_analysis_scripts/generate_real_robot_offline_dryrun.py",
        "05_analysis_scripts/fig13_offline_dryrun_contract_timeline_v2.py",
        "05_analysis_scripts/generate_real_robot_preflight_validation.py",
        "05_analysis_scripts/generate_real_robot_software_smoke_test.py",
        "05_analysis_scripts/generate_ros2_workspace_ci_audit.py",
        "05_analysis_scripts/generate_ros2_runtime_telemetry_audit.py",
        "05_analysis_scripts/generate_ros2_runtime_telemetry_dryrun.py",
        "05_analysis_scripts/generate_ros2_hil_replay_manifest_audit.py",
        "05_analysis_scripts/generate_pre_real_robot_gate_audit.py",
        "05_analysis_scripts/generate_simulation_protocol_registry.py",
        "05_analysis_scripts/generate_statistical_claim_audit.py",
        "05_analysis_scripts/generate_manuscript_argument_audit.py",
        "05_analysis_scripts/generate_safety_case_audit.py",
        "05_analysis_scripts/generate_safety_case_figure.py",
        "05_analysis_scripts/generate_evidence_coverage_matrix.py",
        "05_analysis_scripts/generate_simulation_effect_size_figure.py",
        "05_analysis_scripts/generate_simulation_stress_atlas_figure.py",
        "05_analysis_scripts/fig12_validation_boundary_narrative_v4.py",
        "05_analysis_scripts/generate_ros2_static_interface_audit.py",
        "05_analysis_scripts/generate_publication_figure_qa.py",
        "05_analysis_scripts/generate_source_data_provenance_audit.py",
        "05_analysis_scripts/summarize_real_robot_trials.py",
        "05_analysis_scripts/verify_extended_package.py",
        "03_real_robot/pre_real_robot_checklist.md",
        "03_real_robot/ros2_topic_contract.csv",
        "03_real_robot/real_robot_run_manifest_template.yaml",
        "03_real_robot/hil_replay_manifest_template.yaml",
        "03_real_robot/real_robot_metric_schema.csv",
        "03_real_robot/incident_report_template.md",
        "03_real_robot/real_robot_trials_matrix.csv",
        "03_real_robot/preflight_trials_matrix.csv",
        "03_real_robot/real_robot_results_template.csv",
        "03_real_robot/ros2_workspace_ci_manifest.yaml",
        "03_real_robot/run_ros2_workspace_preflight.sh",
        "03_real_robot/ros2_runtime_telemetry_schema.csv",
        "03_real_robot/runtime_telemetry_manifest_template.yaml",
        "03_real_robot/ros2_qgip_stack/README.md",
        "03_real_robot/ros2_qgip_stack/package.xml",
        "03_real_robot/ros2_qgip_stack/setup.py",
        "03_real_robot/ros2_qgip_stack/launch/multi_robot_preflight.launch.py",
        "03_real_robot/ros2_qgip_stack/test/test_core_contracts.py",
        "06_submission_package/extended_package_manifest_20260603.md",
        "06_submission_package/extended_nature_figure_qa_report_20260603.md",
        "06_submission_package/figure_accessibility_qa_report_20260603.md",
        "06_submission_package/real_robot_preflight_readiness_report_20260603.md",
        "06_submission_package/full_goal_completion_audit_20260603.md",
        "06_submission_package/reviewer_risk_response_matrix_20260603.md",
        "06_submission_package/pre_real_robot_validation_protocol_20260603.md",
        "06_submission_package/nature_data_availability_plan_20260603.md",
        "06_submission_package/repository_deposit_manifest_20260603.csv",
        "06_submission_package/repository_deposit_checksums_sha256_20260603.txt",
        "06_submission_package/datacite_metadata_draft_20260603.yaml",
        "06_submission_package/repository_readme_draft_20260603.md",
        "06_submission_package/repository_deposit_readiness_report_20260603.md",
        "06_submission_package/software_environment_audit_20260604.csv",
        "06_submission_package/reproducibility_command_manifest_20260604.csv",
        "06_submission_package/reproducibility_capsule_20260604.md",
        "06_submission_package/real_robot_offline_dryrun_report_20260604.md",
        "06_submission_package/real_robot_software_smoke_test_report_20260604.md",
        "06_submission_package/ros2_workspace_ci_audit_report_20260604.md",
        "06_submission_package/ros2_runtime_telemetry_audit_report_20260604.md",
        "06_submission_package/ros2_runtime_telemetry_dryrun_report_20260604.md",
        "06_submission_package/ros2_hil_replay_manifest_audit_report_20260604.md",
        "06_submission_package/pre_real_robot_gate_audit_report_20260604.md",
        "06_submission_package/real_robot_preflight_validation_report_20260604.md",
        "06_submission_package/simulation_protocol_registry_report_20260604.md",
        "06_submission_package/statistical_claim_audit_report_20260604.md",
        "06_submission_package/manuscript_argument_audit_report_20260604.md",
        "06_submission_package/safety_case_audit_report_20260604.md",
        "06_submission_package/ros2_static_interface_audit_report_20260604.md",
        "06_submission_package/publication_figure_qa_report_20260604.md",
        "06_submission_package/source_data_provenance_audit_report_20260604.md",
        "08_paper_ready_outputs/source_data/figure_accessibility_metrics.csv",
        "08_paper_ready_outputs/source_data/simulation_protocol_registry.csv",
        "08_paper_ready_outputs/source_data/real_robot_preflight_validation.csv",
        "08_paper_ready_outputs/source_data/real_robot_offline_dryrun_trace.csv",
        "08_paper_ready_outputs/source_data/real_robot_offline_dryrun_summary.csv",
        "08_paper_ready_outputs/source_data/real_robot_software_smoke_test.csv",
        "08_paper_ready_outputs/source_data/ros2_workspace_ci_audit.csv",
        "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_audit.csv",
        "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_trace.csv",
        "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_summary.csv",
        "08_paper_ready_outputs/source_data/ros2_hil_replay_manifest_audit.csv",
        "08_paper_ready_outputs/source_data/fig13_offline_dryrun_contract_timeline_v2_source_data.csv",
        "08_paper_ready_outputs/source_data/pre_real_robot_gate_audit.csv",
        "08_paper_ready_outputs/source_data/real_robot_template_summary.csv",
        "08_paper_ready_outputs/source_data/statistical_claim_audit.csv",
        "08_paper_ready_outputs/source_data/manuscript_argument_traceability.csv",
        "08_paper_ready_outputs/source_data/safety_case_claim_graph.csv",
        "08_paper_ready_outputs/source_data/fig_safety_case_evidence_map_source.csv",
        "08_paper_ready_outputs/source_data/fig_query_guided_attention_source.csv",
        "08_paper_ready_outputs/source_data/fig_pop_ghost_tracking_source.csv",
        "08_paper_ready_outputs/source_data/fig_evidence_coverage_matrix_source.csv",
        "08_paper_ready_outputs/source_data/fig_simulation_effect_size_source.csv",
        "08_paper_ready_outputs/source_data/fig_simulation_stress_atlas_source.csv",
        "08_paper_ready_outputs/source_data/fig12_validation_boundary_narrative_v4_source_data.csv",
        "08_paper_ready_outputs/source_data/ros2_static_interface_audit.csv",
        "08_paper_ready_outputs/source_data/publication_figure_qa.csv",
        "08_paper_ready_outputs/source_data/source_data_provenance_audit.csv",
        "08_paper_ready_outputs/source_data/README_fair_metadata.md",
        "08_paper_ready_outputs/tables/table_simulation_protocol_registry.tex",
        "08_paper_ready_outputs/tables/table_safety_case_claim_graph.tex",
        "08_paper_ready_outputs/tables/table_pre_real_robot_gate_audit.tex",
        "09_pdf_qa/contact_sheet_extended_v2.png",
        "09_pdf_qa/contact_sheet_extended_v5.png",
        "09_pdf_qa/figure_accessibility_contact_sheet_v1.png",
    ]
    for item in workspace_required:
        path = rel(item)
        log.add(path.exists() and path.stat().st_size > 0, f"workspace file present: {item}", f"{path.stat().st_size if path.exists() else 0} bytes")

    figure_names = [
        "fig_nature_system_evidence",
        "fig_query_guided_attention",
        "fig_pop_ghost_tracking",
        "fig_extended_dataset_split",
        "fig_extended_stress_outcomes",
        "fig_extended_nis_response",
        "fig13_offline_dryrun_contract_timeline_v2",
        "fig_safety_case_evidence_map",
        "fig_evidence_coverage_matrix",
        "fig_simulation_effect_size",
        "fig_simulation_stress_atlas",
        "fig12_validation_boundary_narrative_v4",
    ]
    for name in figure_names:
        for suffix in (".pdf", ".svg", ".tiff", ".png"):
            fig = rel(f"08_paper_ready_outputs/figures/{name}{suffix}")
            manuscript_fig = rel(f"01_manuscript/paper_picture/{name}{suffix}")
            log.add(fig.exists() and fig.stat().st_size > 0, f"figure export present: {name}{suffix}", f"{fig.stat().st_size if fig.exists() else 0} bytes")
            log.add(
                manuscript_fig.exists() and manuscript_fig.stat().st_size == fig.stat().st_size,
                f"manuscript figure mirror matches: {name}{suffix}",
                f"{manuscript_fig.stat().st_size if manuscript_fig.exists() else 0} bytes",
            )

    expected_csv_rows = {
        "08_paper_ready_outputs/source_data/final_dataset_split_check.csv": 3,
        "08_paper_ready_outputs/source_data/final_dataset_split_overlap.csv": 3,
        "08_paper_ready_outputs/source_data/claim_evidence_matrix.csv": 8,
        "08_paper_ready_outputs/source_data/fig_nature_system_evidence_source.csv": 16,
        "08_paper_ready_outputs/source_data/fig_query_guided_attention_source.csv": 10,
        "08_paper_ready_outputs/source_data/fig_pop_ghost_tracking_source.csv": 4,
        "08_paper_ready_outputs/source_data/extended_stress_qgip_summary.csv": 7,
        "08_paper_ready_outputs/source_data/figure_accessibility_metrics.csv": 39,
        "08_paper_ready_outputs/source_data/simulation_protocol_registry.csv": 21,
        "08_paper_ready_outputs/source_data/real_robot_preflight_validation.csv": 41,
        "08_paper_ready_outputs/source_data/real_robot_offline_dryrun_trace.csv": 90,
        "08_paper_ready_outputs/source_data/real_robot_offline_dryrun_summary.csv": 12,
        "08_paper_ready_outputs/source_data/real_robot_software_smoke_test.csv": 17,
        "08_paper_ready_outputs/source_data/ros2_workspace_ci_audit.csv": 11,
        "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_audit.csv": 15,
        "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_trace.csv": 320,
        "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_summary.csv": 16,
        "08_paper_ready_outputs/source_data/ros2_hil_replay_manifest_audit.csv": 17,
        "08_paper_ready_outputs/source_data/fig13_offline_dryrun_contract_timeline_v2_source_data.csv": 90,
        "08_paper_ready_outputs/source_data/pre_real_robot_gate_audit.csv": 23,
        "08_paper_ready_outputs/source_data/real_robot_template_summary.csv": 1,
        "08_paper_ready_outputs/source_data/statistical_claim_audit.csv": 36,
        "08_paper_ready_outputs/source_data/manuscript_argument_traceability.csv": 22,
        "08_paper_ready_outputs/source_data/safety_case_claim_graph.csv": 12,
        "08_paper_ready_outputs/source_data/fig_safety_case_evidence_map_source.csv": 17,
        "08_paper_ready_outputs/source_data/fig_evidence_coverage_matrix_source.csv": 53,
        "08_paper_ready_outputs/source_data/fig_simulation_effect_size_source.csv": 55,
        "08_paper_ready_outputs/source_data/fig_simulation_stress_atlas_source.csv": 62,
        "08_paper_ready_outputs/source_data/fig12_validation_boundary_narrative_v4_source_data.csv": 4,
        "08_paper_ready_outputs/source_data/ros2_static_interface_audit.csv": 19,
        "08_paper_ready_outputs/source_data/publication_figure_qa.csv": 119,
        "08_paper_ready_outputs/source_data/source_data_provenance_audit.csv": 96,
        "03_real_robot/real_robot_trials_matrix.csv": 12,
        "03_real_robot/preflight_trials_matrix.csv": 12,
        "03_real_robot/real_robot_results_template.csv": 1,
        "03_real_robot/ros2_topic_contract.csv": 13,
        "03_real_robot/real_robot_metric_schema.csv": 29,
        "06_submission_package/repository_deposit_manifest_20260603.csv": 259,
        "06_submission_package/software_environment_audit_20260604.csv": 18,
        "06_submission_package/reproducibility_command_manifest_20260604.csv": 30,
    }
    for item, expected in expected_csv_rows.items():
        path = rel(item)
        actual = csv_rows(path) if path.exists() else -1
        log.add(actual == expected, f"source row count: {item}", f"{actual} rows")

    tex = rel("01_manuscript/RA_L_extended_working.tex").read_text(encoding="utf-8")
    log.add("TODO" not in tex and "placeholder" not in tex.lower() and "TBD" not in tex, "extended TeX has no TODO/placeholder markers")
    log.add("real-world validation boundary" in tex or "not a claim of full real-world autonomy" in tex, "abstract contains explicit real-world risk boundary")
    log.add("claim-to-evidence" in tex.lower(), "extended TeX includes claim-to-evidence traceability")
    log.add("safety-case claim graph" in tex.lower() and "not a safety certification or physical-validation result" in tex.lower(), "extended TeX includes bounded safety-case boundary")
    log.add("fig_safety_case_evidence_map.pdf" in tex and "claim-boundary visualization" in tex, "extended TeX embeds safety-case evidence-boundary figure")
    log.add("fig_query_guided_attention.pdf" in tex and "Query-guided attention mechanism" in tex, "extended TeX embeds query-guided attention mechanism figure")
    log.add("fig_pop_ghost_tracking.pdf" in tex and "Predictive Object Permanence and NIS-gated ghost tracking" in tex, "extended TeX embeds POP ghost-tracking mechanism figure")
    log.add("fig_evidence_coverage_matrix.pdf" in tex and "Simulation-first evidence contract and claim boundary" in tex, "extended TeX embeds protocol-to-claim evidence coverage figure")
    log.add("fig_simulation_effect_size.pdf" in tex and "Query-conditioned target selection improves leader consistency" in tex, "extended TeX embeds simulation effect-size boundary figure")
    log.add("fig_simulation_stress_atlas.pdf" in tex and "Stress-suite design and primary discriminators" in tex, "extended TeX embeds simulation stress atlas figure")
    log.add("fig12_validation_boundary_narrative_v4.pdf" in tex and "Pre-real-robot validation boundary: local readiness is not physical evidence" in tex, "extended TeX embeds pre-real-robot validation-boundary narrative figure")
    log.add("protocol-to-artifact" in tex.lower() and "table_simulation_protocol_registry.tex" in tex, "extended TeX includes simulation protocol registry")
    log.add(("pre_real_robot_gate_audit.csv" in tex or "pre\\_real\\_robot\\_gate\\_audit.csv" in tex) and "table_pre_real_robot_gate_audit.tex" in tex, "extended TeX includes pre-real-robot gate audit table")
    log.add("ROS2-less offline dry-run diagnostic" in tex and "not a ROS2 launch, HIL timing, rosbag, or physical robot result" in tex, "extended TeX includes offline dry-run non-claim boundary")

    latex_log = rel("01_manuscript/RA_L_extended_working.log")
    if latex_log.exists():
        log_text = latex_log.read_text(encoding="utf-8", errors="replace")
        bad_patterns = ["Overfull", "undefined references", "Label(s) may have changed", "Rerun to get"]
        for pattern in bad_patterns:
            log.add(pattern not in log_text, f"LaTeX log clean: no {pattern}")
    else:
        log.add(False, "LaTeX log exists for verification")

    qa_pages = sorted((ROOT / "09_pdf_qa").glob("extended_v5_page-*.png"))
    log.add(len(qa_pages) == 19, "rendered extended PDF page count", f"{len(qa_pages)} pages")
    log.add(rel("09_pdf_qa/contact_sheet_extended_v5.png").exists(), "extended contact sheet exists")

    fair_readme = rel("08_paper_ready_outputs/source_data/README_fair_metadata.md")
    fair_text = fair_readme.read_text(encoding="utf-8") if fair_readme.exists() else ""
    for term in ("FAIR", "File inventory", "Common variable dictionary", "Missing information before public deposit", "DOI-backed repository", "source_data_provenance_audit.csv", "simulation_protocol_registry.csv", "real_robot_preflight_validation.csv", "real_robot_offline_dryrun_trace.csv", "real_robot_offline_dryrun_summary.csv", "real_robot_software_smoke_test.csv", "ros2_workspace_ci_audit.csv", "ros2_runtime_telemetry_audit.csv", "ros2_runtime_telemetry_dryrun_trace.csv", "ros2_runtime_telemetry_dryrun_summary.csv", "ros2_hil_replay_manifest_audit.csv", "fig13_offline_dryrun_contract_timeline_v2_source_data.csv", "fig_safety_case_evidence_map_source.csv", "fig_evidence_coverage_matrix_source.csv", "fig_simulation_effect_size_source.csv", "fig_simulation_stress_atlas_source.csv", "fig12_validation_boundary_narrative_v4_source_data.csv", "pre_real_robot_gate_audit.csv", "safety_case_claim_graph.csv"):
        log.add(term in fair_text, f"FAIR README contains: {term}")

    availability = rel("06_submission_package/data_code_availability_statement.md")
    availability_text = availability.read_text(encoding="utf-8") if availability.exists() else ""
    for term in ("Data Availability", "Code Availability", "Protocol Availability", "TBD repository", "repository_deposit_manifest_20260603.csv"):
        log.add(term in availability_text, f"availability statement contains: {term}")

    nature_plan = rel("06_submission_package/nature_data_availability_plan_20260603.md")
    nature_plan_text = nature_plan.read_text(encoding="utf-8") if nature_plan.exists() else ""
    for term in (
        "Nature-style data and code availability plan",
        "repository_deposit_checksums_sha256_20260603.txt",
        "minted",
        "repository record",
        "投稿前需要确定存储平台",
    ):
        log.add(term in nature_plan_text, f"nature data plan contains: {term}")

    goal_audit = rel("06_submission_package/full_goal_completion_audit_20260603.md")
    goal_text = goal_audit.read_text(encoding="utf-8") if goal_audit.exists() else ""
    for term in (
        "strong simulation-first pre-real-machine checkpoint",
        "Defensible central claim",
        "Claims that must not be made",
        "Remaining Non-Completion Items",
        "DOI-backed data/code record",
    ):
        log.add(term in goal_text, f"full objective audit contains: {term}")

    reviewer_matrix = rel("06_submission_package/reviewer_risk_response_matrix_20260603.md")
    reviewer_text = reviewer_matrix.read_text(encoding="utf-8") if reviewer_matrix.exists() else ""
    for term in (
        "Reviewer Risk and Response Matrix",
        "simulation-only",
        "Zero collisions are overclaimed",
        "Data/code availability is not publication-ready without a DOI",
        "Phrases to Avoid",
    ):
        log.add(term in reviewer_text, f"reviewer risk matrix contains: {term}")

    figure_accessibility = rel("06_submission_package/figure_accessibility_qa_report_20260603.md")
    figure_accessibility_text = figure_accessibility.read_text(encoding="utf-8") if figure_accessibility.exists() else ""
    for term in (
        "Figure Accessibility QA Report",
        "grayscale",
        "deuteranopia",
        "figure_accessibility_contact_sheet_v1.png",
        "not a formal perceptual user study",
    ):
        log.add(term in figure_accessibility_text, f"figure accessibility report contains: {term}")

    real_robot_report = rel("06_submission_package/real_robot_preflight_readiness_report_20260603.md")
    real_robot_report_text = real_robot_report.read_text(encoding="utf-8") if real_robot_report.exists() else ""
    for term in (
        "Real-Robot Preflight Readiness Report",
        "does not claim that physical validation has been completed",
        "ros2_topic_contract.csv",
        "real_robot_run_manifest_template.yaml",
        "Go for closed-loop physical claims in the manuscript: no",
    ):
        log.add(term in real_robot_report_text, f"real-robot preflight report contains: {term}")

    statistical_report = rel("06_submission_package/statistical_claim_audit_report_20260604.md")
    statistical_report_text = statistical_report.read_text(encoding="utf-8") if statistical_report.exists() else ""
    for term in (
        "Statistical Claim Audit Report",
        "All audited claims matched",
        "does not prove raw CARLA rerun reproducibility",
        "physical robot validation",
        "real-world risk certification",
    ):
        log.add(term in statistical_report_text, f"statistical claim audit report contains: {term}")

    argument_report = rel("06_submission_package/manuscript_argument_audit_report_20260604.md")
    argument_report_text = argument_report.read_text(encoding="utf-8") if argument_report.exists() else ""
    for term in (
        "Manuscript Argument Audit Report",
        "reader-question chain",
        "All audited narrative checks passed",
        "does not prove physical robot validation",
        "does not replace expert peer review",
        "simulation-first boundary",
        "dry-run-only",
    ):
        log.add(term in argument_report_text, f"manuscript argument audit report contains: {term}")

    ros2_static_report = rel("06_submission_package/ros2_static_interface_audit_report_20260604.md")
    ros2_static_report_text = ros2_static_report.read_text(encoding="utf-8") if ros2_static_report.exists() else ""
    for term in (
        "ROS2 Static Interface Audit Report",
        "All audited static-interface checks passed",
        "selected-leader route",
        "external safety-supervisor gate",
        "does not prove ROS2 launch/build success",
        "does not prove physical robot validation",
    ):
        log.add(term in ros2_static_report_text, f"ROS2 static interface audit report contains: {term}")

    real_robot_validation_report = rel("06_submission_package/real_robot_preflight_validation_report_20260604.md")
    real_robot_validation_text = real_robot_validation_report.read_text(encoding="utf-8") if real_robot_validation_report.exists() else ""
    for term in (
        "Real-Robot Preflight Offline Validation Report",
        "All offline real-robot preflight validation checks passed",
        "Selected-leader route",
        "Topic contract",
        "run manifest",
        "does not prove ROS2 build success",
        "does not prove ros2 launch success",
        "does not contain completed physical robot trial data",
    ):
        log.add(term in real_robot_validation_text, f"real-robot preflight validation report contains: {term}")

    real_robot_dryrun_report = rel("06_submission_package/real_robot_offline_dryrun_report_20260604.md")
    real_robot_dryrun_text = real_robot_dryrun_report.read_text(encoding="utf-8") if real_robot_dryrun_report.exists() else ""
    for term in (
        "Real-Robot Offline Dry-Run Report",
        "All offline real-robot dry-run checks passed",
        "selected-leader",
        "POP/NIS",
        "GHOST/LOST",
        "does not prove ROS2 build success",
        "does not produce a rosbag",
        "does not contain completed physical robot trial data",
    ):
        log.add(term in real_robot_dryrun_text, f"real-robot offline dry-run report contains: {term}")

    real_robot_smoke_report = rel("06_submission_package/real_robot_software_smoke_test_report_20260604.md")
    real_robot_smoke_text = real_robot_smoke_report.read_text(encoding="utf-8") if real_robot_smoke_report.exists() else ""
    for term in (
        "Real-Robot Software Smoke Test Report",
        "All real-robot software smoke checks passed",
        "POP/NIS",
        "fault injection",
        "JSON payload contracts",
        "controller-proxy safety invariants",
        "does not exercise rclpy",
        "physical robot motion",
    ):
        log.add(term in real_robot_smoke_text, f"real-robot software smoke report contains: {term}")

    ros2_ci_report = rel("06_submission_package/ros2_workspace_ci_audit_report_20260604.md")
    ros2_ci_text = ros2_ci_report.read_text(encoding="utf-8") if ros2_ci_report.exists() else ""
    for term in (
        "ROS2 Workspace CI Audit Report",
        "All ROS2 workspace CI audit checks passed",
        "colcon build/test commands",
        "launch-argument parsing",
        "pure-core pytest",
        "no-actuator-bridge safety boundaries",
        "does not prove colcon build success",
        "physical robot motion",
    ):
        log.add(term in ros2_ci_text, f"ROS2 workspace CI audit report contains: {term}")

    runtime_telemetry_report = rel("06_submission_package/ros2_runtime_telemetry_audit_report_20260604.md")
    runtime_telemetry_text = runtime_telemetry_report.read_text(encoding="utf-8") if runtime_telemetry_report.exists() else ""
    for term in (
        "ROS2 Runtime Telemetry Audit Report",
        "All ROS2 runtime telemetry audit checks passed",
        "runtime timing",
        "frame-drop",
        "watchdog",
        "clock-drift",
        "CPU/GPU telemetry",
        "does not prove ROS2 launch success",
        "physical robot motion",
    ):
        log.add(term in runtime_telemetry_text, f"ROS2 runtime telemetry audit report contains: {term}")

    runtime_dryrun_report = rel("06_submission_package/ros2_runtime_telemetry_dryrun_report_20260604.md")
    runtime_dryrun_text = runtime_dryrun_report.read_text(encoding="utf-8") if runtime_dryrun_report.exists() else ""
    for term in (
        "ROS2 Runtime Telemetry Dry-Run Summary",
        "All runtime telemetry dry-run summary checks passed",
        "frame-drop accounting",
        "watchdog-reason bookkeeping",
        "CPU/GPU telemetry summary path",
        "does not prove live ROS2 timing",
        "physical robot motion",
    ):
        log.add(term in runtime_dryrun_text, f"ROS2 runtime telemetry dry-run report contains: {term}")

    hil_replay_report = rel("06_submission_package/ros2_hil_replay_manifest_audit_report_20260604.md")
    hil_replay_text = hil_replay_report.read_text(encoding="utf-8") if hil_replay_report.exists() else ""
    for term in (
        "ROS2/HIL Replay Manifest Audit Report",
        "All ROS2/HIL replay manifest audit checks passed",
        "rosbag logging",
        "ROS clock playback",
        "safety-state logging",
        "actuator-bridge disablement",
        "does not prove colcon build success",
        "physical robot motion",
    ):
        log.add(term in hil_replay_text, f"ROS2/HIL replay manifest audit report contains: {term}")

    pre_real_gate_report = rel("06_submission_package/pre_real_robot_gate_audit_report_20260604.md")
    pre_real_gate_text = pre_real_gate_report.read_text(encoding="utf-8") if pre_real_gate_report.exists() else ""
    for term in (
        "Pre-Real-Robot Gate Audit Report",
        "All audited pre-real-robot gates are prepared",
        "network/TF",
        "HIL shadow-control",
        "low-speed closed-loop",
        "negative-claim gates",
        "does not prove ROS2 build success",
        "does not contain completed physical robot trial data",
    ):
        log.add(term in pre_real_gate_text, f"pre-real-robot gate audit report contains: {term}")

    publication_figure_report = rel("06_submission_package/publication_figure_qa_report_20260604.md")
    publication_figure_text = publication_figure_report.read_text(encoding="utf-8") if publication_figure_report.exists() else ""
    for term in (
        "Publication Figure QA Report",
        "All audited publication-figure checks passed",
        "89/183 mm figure widths",
        "editable text/vector layers",
        "figure_accessibility_metrics.csv",
        "does not replace human inspection",
        "target-journal production review",
    ):
        log.add(term in publication_figure_text, f"publication figure QA report contains: {term}")

    protocol_registry_report = rel("06_submission_package/simulation_protocol_registry_report_20260604.md")
    protocol_registry_text = protocol_registry_report.read_text(encoding="utf-8") if protocol_registry_report.exists() else ""
    for term in (
        "Simulation Protocol Registry Report",
        "All registered simulation and preflight protocols",
        "Dataset and leakage control",
        "Primary ambiguity stress",
        "ROS2 preflight protocol",
        "ROS2 workspace CI audit",
        "runtime telemetry audit",
        "runtime telemetry parser dry-run",
        "safety-case claim graph",
        "software smoke test",
        "HIL replay",
        "does not prove raw CARLA rerun reproducibility",
        "does not contain completed physical robot trial data",
    ):
        log.add(term in protocol_registry_text, f"simulation protocol registry report contains: {term}")

    source_provenance_report = rel("06_submission_package/source_data_provenance_audit_report_20260604.md")
    source_provenance_text = source_provenance_report.read_text(encoding="utf-8") if source_provenance_report.exists() else ""
    for term in (
        "Source Data Provenance Audit Report",
        "All audited source-data provenance checks passed",
        "figure-to-source-data mapping",
        "table-to-source-data mapping",
        "safety-case claim graph",
        "ROS2 workspace CI",
        "ROS2 runtime telemetry",
        "runtime telemetry parser dry-run",
        "software-smoke",
        "HIL replay",
        "does not prove raw CARLA rerun reproducibility",
        "does not replace DOI-backed repository publication",
        "does not contain completed physical robot trial data",
    ):
        log.add(term in source_provenance_text, f"source-data provenance audit report contains: {term}")

    safety_case_report = rel("06_submission_package/safety_case_audit_report_20260604.md")
    safety_case_text = safety_case_report.read_text(encoding="utf-8") if safety_case_report.exists() else ""
    for term in (
        "Safety-Case Claim Graph Audit Report",
        "All safety-case claim graph checks passed",
        "top-level safety",
        "finite-sample collision",
        "runtime-telemetry",
        "remaining validation gap",
        "does not prove zero real-world risk",
        "physical robot validation",
    ):
        log.add(term in safety_case_text, f"safety-case audit report contains: {term}")

    real_robot_python = [
        *sorted(rel("03_real_robot").glob("*.py")),
        *sorted(rel("03_real_robot/ros2_qgip_stack").glob("*.py")),
        *sorted(rel("03_real_robot/ros2_qgip_stack/launch").glob("*.py")),
        *sorted(rel("03_real_robot/ros2_qgip_stack/ros2_qgip_stack").glob("*.py")),
        *sorted(rel("03_real_robot/ros2_qgip_stack/test").glob("*.py")),
        rel("05_analysis_scripts/summarize_real_robot_trials.py"),
        rel("05_analysis_scripts/generate_reproducibility_capsule.py"),
        rel("05_analysis_scripts/generate_repository_deposit_artifacts.py"),
        rel("05_analysis_scripts/generate_real_robot_offline_dryrun.py"),
        rel("05_analysis_scripts/fig13_offline_dryrun_contract_timeline_v2.py"),
        rel("05_analysis_scripts/generate_real_robot_preflight_validation.py"),
        rel("05_analysis_scripts/generate_real_robot_software_smoke_test.py"),
        rel("05_analysis_scripts/generate_ros2_workspace_ci_audit.py"),
        rel("05_analysis_scripts/generate_ros2_runtime_telemetry_audit.py"),
        rel("05_analysis_scripts/generate_ros2_runtime_telemetry_dryrun.py"),
        rel("05_analysis_scripts/generate_ros2_hil_replay_manifest_audit.py"),
        rel("05_analysis_scripts/generate_pre_real_robot_gate_audit.py"),
        rel("05_analysis_scripts/generate_statistical_claim_audit.py"),
        rel("05_analysis_scripts/generate_simulation_protocol_registry.py"),
        rel("05_analysis_scripts/generate_manuscript_argument_audit.py"),
        rel("05_analysis_scripts/generate_safety_case_audit.py"),
        rel("05_analysis_scripts/generate_safety_case_figure.py"),
        rel("05_analysis_scripts/generate_evidence_coverage_matrix.py"),
        rel("05_analysis_scripts/generate_simulation_effect_size_figure.py"),
        rel("05_analysis_scripts/generate_simulation_stress_atlas_figure.py"),
        rel("05_analysis_scripts/fig12_validation_boundary_narrative_v4.py"),
        rel("05_analysis_scripts/generate_ros2_static_interface_audit.py"),
        rel("05_analysis_scripts/generate_publication_figure_qa.py"),
        rel("05_analysis_scripts/generate_source_data_provenance_audit.py"),
    ]
    for path in real_robot_python:
        ok, detail = python_source_compile_ok(path)
        log.add(ok, f"python syntax ok: {path.relative_to(ROOT).as_posix()}", detail)

    deposit_manifest = rel("06_submission_package/repository_deposit_manifest_20260603.csv")
    if deposit_manifest.exists():
        with deposit_manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            deposit_rows = list(csv.DictReader(handle))
        missing = []
        mismatched = []
        for row in deposit_rows:
            path = rel(row["relative_path"])
            if not path.exists():
                missing.append(row["relative_path"])
                continue
            actual = sha256(path)
            if actual != row["sha256"]:
                mismatched.append(row["relative_path"])
        roles = {row["role"] for row in deposit_rows}
        required_roles = {
            "manuscript",
            "processed_source_data",
            "publication_figure_export",
            "analysis_or_verification_code",
            "real_robot_preflight_protocol",
            "submission_documentation",
            "visual_qa",
        }
        log.add(not missing, "deposit manifest files exist", "; ".join(missing[:5]))
        log.add(not mismatched, "deposit manifest SHA256 matches workspace files", "; ".join(mismatched[:5]))
        log.add(required_roles.issubset(roles), "deposit manifest covers required roles", ", ".join(sorted(roles)))
    else:
        log.add(False, "deposit manifest exists for checksum verification")

    checksum_file = rel("06_submission_package/repository_deposit_checksums_sha256_20260603.txt")
    log.add(checksum_file.exists() and text_lines(checksum_file) == 259, "repository checksum line count", f"{text_lines(checksum_file) if checksum_file.exists() else 0} lines")

    datacite = rel("06_submission_package/datacite_metadata_draft_20260603.yaml")
    datacite_text = datacite.read_text(encoding="utf-8") if datacite.exists() else ""
    for term in (
        "Do not treat this file as a minted DOI record",
        "TBD DOI or accession",
        "Processed simulation source data and analysis code",
        "does not contain completed physical-robot trial data",
    ):
        log.add(term in datacite_text, f"DataCite draft contains: {term}")

    deposit_readme = rel("06_submission_package/repository_readme_draft_20260603.md")
    deposit_readme_text = deposit_readme.read_text(encoding="utf-8") if deposit_readme.exists() else ""
    for term in (
        "DOI-ready draft",
        "does not contain completed physical-robot validation data",
        "repository_deposit_manifest_20260603.csv",
        "Required Before Public Release",
    ):
        log.add(term in deposit_readme_text, f"repository README draft contains: {term}")

    deposit_report = rel("06_submission_package/repository_deposit_readiness_report_20260603.md")
    deposit_report_text = deposit_report.read_text(encoding="utf-8") if deposit_report.exists() else ""
    for term in (
        "Repository Deposit Readiness Report",
        "not yet a public",
        "archival record",
        "Manifest rows: 259",
        "DOI/accession: TBD",
    ):
        log.add(term in deposit_report_text, f"repository deposit report contains: {term}")

    reproducibility_capsule = rel("06_submission_package/reproducibility_capsule_20260604.md")
    reproducibility_text = reproducibility_capsule.read_text(encoding="utf-8") if reproducibility_capsule.exists() else ""
    for term in (
        "Reproducibility Capsule",
        "does not rerun CARLA",
        "30 reproduction or audit commands",
        "does not prove ROS2 launch/build success",
        "does not replace a public DOI-backed repository record",
    ):
        log.add(term in reproducibility_text, f"reproducibility capsule contains: {term}")

    env_audit = rel("06_submission_package/software_environment_audit_20260604.csv")
    env_text = env_audit.read_text(encoding="utf-8") if env_audit.exists() else ""
    for term in ("python", "matplotlib", "pdflatex", "expected_missing_for_local_package"):
        log.add(term in env_text, f"environment audit contains: {term}")

    with zipfile.ZipFile(zip_path) as zf:
        entries = zf.infolist()
        names = [entry.filename.replace("\\", "/") for entry in entries]
        log.add(len(entries) >= 80, "zip entry count", f"{len(entries)} entries")
        forbidden = [
            name
            for name in names
            if re.search(r"\.(aux|log|out|bbl|blg|synctex|fls|fdb_latexmk)$", name)
            or "__pycache__" in name
            or name.endswith("~")
        ]
        log.add(not forbidden, "zip excludes temporary/build files", "; ".join(forbidden[:5]))
        zip_required = [
            "01_manuscript/RA_L_extended_working.pdf",
            "01_manuscript/RA_L_extended_working.tex",
            "05_analysis_scripts/generate_extended_artifacts.py",
            "05_analysis_scripts/generate_nature_main_figure.py",
            "05_analysis_scripts/generate_figure_accessibility_qa.py",
            "05_analysis_scripts/generate_repository_deposit_artifacts.py",
            "05_analysis_scripts/generate_reproducibility_capsule.py",
            "05_analysis_scripts/generate_real_robot_offline_dryrun.py",
            "05_analysis_scripts/fig13_offline_dryrun_contract_timeline_v2.py",
            "05_analysis_scripts/generate_real_robot_preflight_validation.py",
            "05_analysis_scripts/generate_real_robot_software_smoke_test.py",
            "05_analysis_scripts/generate_ros2_workspace_ci_audit.py",
            "05_analysis_scripts/generate_ros2_runtime_telemetry_audit.py",
            "05_analysis_scripts/generate_ros2_runtime_telemetry_dryrun.py",
            "05_analysis_scripts/generate_ros2_hil_replay_manifest_audit.py",
            "05_analysis_scripts/generate_pre_real_robot_gate_audit.py",
            "05_analysis_scripts/generate_simulation_protocol_registry.py",
            "05_analysis_scripts/generate_statistical_claim_audit.py",
            "05_analysis_scripts/generate_manuscript_argument_audit.py",
            "05_analysis_scripts/generate_safety_case_audit.py",
            "05_analysis_scripts/generate_safety_case_figure.py",
            "05_analysis_scripts/generate_evidence_coverage_matrix.py",
            "05_analysis_scripts/generate_simulation_effect_size_figure.py",
            "05_analysis_scripts/generate_simulation_stress_atlas_figure.py",
            "05_analysis_scripts/fig12_validation_boundary_narrative_v4.py",
            "05_analysis_scripts/generate_ros2_static_interface_audit.py",
            "05_analysis_scripts/generate_publication_figure_qa.py",
            "05_analysis_scripts/generate_source_data_provenance_audit.py",
            "05_analysis_scripts/summarize_real_robot_trials.py",
            "05_analysis_scripts/verify_extended_package.py",
            "03_real_robot/pre_real_robot_checklist.md",
            "03_real_robot/ros2_topic_contract.csv",
            "03_real_robot/real_robot_run_manifest_template.yaml",
            "03_real_robot/hil_replay_manifest_template.yaml",
            "03_real_robot/real_robot_metric_schema.csv",
            "03_real_robot/incident_report_template.md",
            "03_real_robot/real_robot_trials_matrix.csv",
            "03_real_robot/preflight_trials_matrix.csv",
            "03_real_robot/real_robot_results_template.csv",
            "03_real_robot/ros2_workspace_ci_manifest.yaml",
            "03_real_robot/run_ros2_workspace_preflight.sh",
            "03_real_robot/ros2_runtime_telemetry_schema.csv",
            "03_real_robot/runtime_telemetry_manifest_template.yaml",
            "03_real_robot/ros2_qgip_stack/README.md",
            "03_real_robot/ros2_qgip_stack/package.xml",
            "03_real_robot/ros2_qgip_stack/setup.py",
            "03_real_robot/ros2_qgip_stack/launch/multi_robot_preflight.launch.py",
            "03_real_robot/ros2_qgip_stack/test/test_core_contracts.py",
            "08_paper_ready_outputs/figures/fig_nature_system_evidence.svg",
            "08_paper_ready_outputs/figures/fig_nature_system_evidence.tiff",
            "08_paper_ready_outputs/source_data/fig_nature_system_evidence_source.csv",
            "08_paper_ready_outputs/source_data/figure_accessibility_metrics.csv",
            "08_paper_ready_outputs/source_data/simulation_protocol_registry.csv",
            "08_paper_ready_outputs/source_data/real_robot_preflight_validation.csv",
            "08_paper_ready_outputs/source_data/real_robot_offline_dryrun_trace.csv",
            "08_paper_ready_outputs/source_data/real_robot_offline_dryrun_summary.csv",
            "08_paper_ready_outputs/source_data/real_robot_software_smoke_test.csv",
            "08_paper_ready_outputs/source_data/ros2_workspace_ci_audit.csv",
            "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_audit.csv",
            "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_trace.csv",
            "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_summary.csv",
            "08_paper_ready_outputs/source_data/ros2_hil_replay_manifest_audit.csv",
            "08_paper_ready_outputs/source_data/fig13_offline_dryrun_contract_timeline_v2_source_data.csv",
            "08_paper_ready_outputs/source_data/pre_real_robot_gate_audit.csv",
            "08_paper_ready_outputs/source_data/real_robot_template_summary.csv",
            "08_paper_ready_outputs/source_data/statistical_claim_audit.csv",
            "08_paper_ready_outputs/source_data/manuscript_argument_traceability.csv",
            "08_paper_ready_outputs/source_data/safety_case_claim_graph.csv",
            "08_paper_ready_outputs/source_data/fig_safety_case_evidence_map_source.csv",
            "08_paper_ready_outputs/source_data/fig_evidence_coverage_matrix_source.csv",
            "08_paper_ready_outputs/source_data/fig_simulation_effect_size_source.csv",
            "08_paper_ready_outputs/source_data/fig_simulation_stress_atlas_source.csv",
            "08_paper_ready_outputs/source_data/fig12_validation_boundary_narrative_v4_source_data.csv",
            "08_paper_ready_outputs/source_data/ros2_static_interface_audit.csv",
            "08_paper_ready_outputs/source_data/publication_figure_qa.csv",
            "08_paper_ready_outputs/source_data/source_data_provenance_audit.csv",
            "08_paper_ready_outputs/tables/table_simulation_protocol_registry.tex",
            "08_paper_ready_outputs/tables/table_safety_case_claim_graph.tex",
            "08_paper_ready_outputs/tables/table_pre_real_robot_gate_audit.tex",
            "08_paper_ready_outputs/figures/fig_extended_nis_response.svg",
            "08_paper_ready_outputs/figures/fig_extended_nis_response.tiff",
            "08_paper_ready_outputs/figures/fig13_offline_dryrun_contract_timeline_v2.svg",
            "08_paper_ready_outputs/figures/fig13_offline_dryrun_contract_timeline_v2.tiff",
            "08_paper_ready_outputs/figures/fig_safety_case_evidence_map.svg",
            "08_paper_ready_outputs/figures/fig_safety_case_evidence_map.tiff",
            "08_paper_ready_outputs/figures/fig_evidence_coverage_matrix.svg",
            "08_paper_ready_outputs/figures/fig_evidence_coverage_matrix.tiff",
            "08_paper_ready_outputs/figures/fig_simulation_effect_size.svg",
            "08_paper_ready_outputs/figures/fig_simulation_effect_size.tiff",
            "08_paper_ready_outputs/figures/fig_simulation_stress_atlas.svg",
            "08_paper_ready_outputs/figures/fig_simulation_stress_atlas.tiff",
            "08_paper_ready_outputs/figures/fig12_validation_boundary_narrative_v4.svg",
            "08_paper_ready_outputs/figures/fig12_validation_boundary_narrative_v4.tiff",
            "08_paper_ready_outputs/source_data/claim_evidence_matrix.csv",
            "09_pdf_qa/contact_sheet_extended_v5.png",
            "09_pdf_qa/figure_accessibility_contact_sheet_v1.png",
            "06_submission_package/full_goal_completion_audit_20260603.md",
            "06_submission_package/reviewer_risk_response_matrix_20260603.md",
            "06_submission_package/figure_accessibility_qa_report_20260603.md",
            "06_submission_package/real_robot_preflight_readiness_report_20260603.md",
            "06_submission_package/extended_nature_figure_qa_report_20260603.md",
            "06_submission_package/pre_real_robot_validation_protocol_20260603.md",
            "06_submission_package/nature_data_availability_plan_20260603.md",
            "06_submission_package/repository_deposit_manifest_20260603.csv",
            "06_submission_package/repository_deposit_checksums_sha256_20260603.txt",
            "06_submission_package/datacite_metadata_draft_20260603.yaml",
            "06_submission_package/repository_readme_draft_20260603.md",
            "06_submission_package/repository_deposit_readiness_report_20260603.md",
            "06_submission_package/software_environment_audit_20260604.csv",
            "06_submission_package/reproducibility_command_manifest_20260604.csv",
            "06_submission_package/reproducibility_capsule_20260604.md",
            "06_submission_package/real_robot_offline_dryrun_report_20260604.md",
            "06_submission_package/real_robot_software_smoke_test_report_20260604.md",
            "06_submission_package/ros2_workspace_ci_audit_report_20260604.md",
            "06_submission_package/ros2_runtime_telemetry_audit_report_20260604.md",
            "06_submission_package/ros2_runtime_telemetry_dryrun_report_20260604.md",
            "06_submission_package/ros2_hil_replay_manifest_audit_report_20260604.md",
            "06_submission_package/pre_real_robot_gate_audit_report_20260604.md",
            "06_submission_package/real_robot_preflight_validation_report_20260604.md",
            "06_submission_package/simulation_protocol_registry_report_20260604.md",
            "06_submission_package/statistical_claim_audit_report_20260604.md",
            "06_submission_package/manuscript_argument_audit_report_20260604.md",
            "06_submission_package/safety_case_audit_report_20260604.md",
            "06_submission_package/ros2_static_interface_audit_report_20260604.md",
            "06_submission_package/publication_figure_qa_report_20260604.md",
            "06_submission_package/source_data_provenance_audit_report_20260604.md",
            "06_submission_package/extended_submission_verification_report_20260603.md",
            "08_paper_ready_outputs/source_data/README_fair_metadata.md",
        ]
        for item in zip_required:
            hit = [entry for entry in entries if entry.filename.replace("\\", "/").endswith(item)]
            log.add(bool(hit) and hit[0].file_size > 0, f"zip contains: {item}", f"{hit[0].file_size if hit else 0} bytes")

    lines = [
        "# Extended package verification report",
        "",
        "Date: 2026-06-03",
        f"Package: `{zip_path.name}`",
        "",
        f"Passed: {log.passed}",
        f"Failed: {log.failed}",
        "",
        "| Status | Check | Detail |",
        "|---|---|---|",
    ]
    for ok, name, detail in log.rows:
        status = "PASS" if ok else "FAIL"
        lines.append(f"| {status} | {name} | {detail} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT}")
    print(f"passed={log.passed} failed={log.failed}")
    if log.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
