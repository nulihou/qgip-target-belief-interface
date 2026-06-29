#!/usr/bin/env python3
"""Generate a reviewer-facing simulation protocol registry."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
TABLES = ROOT / "08_paper_ready_outputs" / "tables"
PACKAGE = ROOT / "06_submission_package"
SCRIPTS = ROOT / "05_analysis_scripts"
REAL_ROBOT = ROOT / "03_real_robot"

OUT_CSV = SOURCE / "simulation_protocol_registry.csv"
OUT_TABLE = TABLES / "table_simulation_protocol_registry.tex"
OUT_REPORT = PACKAGE / "simulation_protocol_registry_report_20260604.md"


@dataclass
class ProtocolRow:
    protocol_id: str
    evidence_role: str
    sample_scope: str
    perturbation_or_condition: str
    primary_metrics: str
    source_artifacts: str
    generator_or_audit_script: str
    derived_outputs: str
    manuscript_anchor: str
    status: str
    boundary: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_rows(path: Path) -> int:
    return len(read_csv(path))


def exists_rel(rel: str) -> bool:
    path = ROOT / rel
    return path.exists() and path.stat().st_size > 0


def csv_rows_rel(rel: str) -> int:
    path = ROOT / rel
    return csv_rows(path) if path.exists() else -1


def script_exists(name: str) -> bool:
    return (SCRIPTS / name).exists() and (SCRIPTS / name).stat().st_size > 0


def status_for(required_files: tuple[str, ...], required_scripts: tuple[str, ...] = (), row_expectations: tuple[tuple[str, int], ...] = ()) -> str:
    files_ok = all(exists_rel(item) for item in required_files)
    scripts_ok = all(script_exists(item) for item in required_scripts)
    rows_ok = all(csv_rows_rel(item) == expected for item, expected in row_expectations)
    return "PASS" if files_ok and scripts_ok and rows_ok else "FAIL"


def esc(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}")
        .replace("_", "\\_")
        .replace("%", "\\%")
        .replace("&", "\\&")
        .replace("#", "\\#")
    )


TABLE_LABELS = {
    "split_audit": "Split audit",
    "main300_blackout_benchmark": "Main N=300",
    "main1000_nominal_sanity": "Nominal N=1000",
    "primary_fp10_ambiguity": "FP ambiguity",
    "primary_idswitch_ambiguity": "ID-switch ambiguity",
    "detector_timing_stress": "Detector/timing",
    "raw_sensor_like_stress": "Raw-like",
    "boundary_ambiguity_stress": "Boundary",
    "nis_noise_diagnostic": "NIS noise",
    "nis_outlier_diagnostic": "NIS outlier",
    "statistical_traceability": "Statistical trace",
    "figure_table_reproduction": "Figure/table QA",
    "ros2_preflight_protocol": "ROS2 preflight",
    "ros2_workspace_ci_audit": "ROS2 CI",
    "ros2_runtime_telemetry_audit": "Runtime telemetry",
    "ros2_runtime_telemetry_dryrun": "Telemetry dry run",
    "real_robot_software_smoke": "Software smoke",
    "offline_preflight_dryrun": "Offline dry run",
    "ros2_hil_replay_manifest_audit": "HIL replay",
    "safety_case_claim_graph": "Safety case",
    "pre_real_robot_gate_audit": "Pre-real gate",
}


def rows() -> list[ProtocolRow]:
    data = [
        ProtocolRow(
            protocol_id="split_audit",
            evidence_role="dataset and leakage control",
            sample_scope="train=4050, val=450, test=500 route files",
            perturbation_or_condition="fixed split labels; no evaluation failure injection",
            primary_metrics="split counts, missing files, pairwise path overlap",
            source_artifacts="08_paper_ready_outputs/source_data/final_dataset_split_check.csv; 08_paper_ready_outputs/source_data/final_dataset_split_overlap.csv",
            generator_or_audit_script="check_final_dataset_split.py; generate_extended_artifacts.py",
            derived_outputs="table_dataset_split_audit.tex; fig_extended_dataset_split",
            manuscript_anchor="Dataset Split and Audit Trail",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/final_dataset_split_check.csv",
                    "08_paper_ready_outputs/source_data/final_dataset_split_overlap.csv",
                    "08_paper_ready_outputs/tables/table_dataset_split_audit.tex",
                ),
                ("check_final_dataset_split.py", "generate_extended_artifacts.py"),
                (
                    ("08_paper_ready_outputs/source_data/final_dataset_split_check.csv", 3),
                    ("08_paper_ready_outputs/source_data/final_dataset_split_overlap.csv", 3),
                ),
            ),
            boundary="File-level split audit; not unrestricted map-level or deployment generalization.",
        ),
        ProtocolRow(
            protocol_id="main300_blackout_benchmark",
            evidence_role="standard closed-loop benchmark",
            sample_scope="N=300 episodes per reported main benchmark",
            perturbation_or_condition="planner-input object-list blackout, default t_blind=1.0 s",
            primary_metrics="success, collision, lost, jerk",
            source_artifacts="08_paper_ready_outputs/source_data/main_benchmark_source.csv",
            generator_or_audit_script="generate_paper_sim_artifacts.py",
            derived_outputs="table_main_benchmark.tex; RA_L_extended_working.tex Table results",
            manuscript_anchor="Main Simulation Results",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/main_benchmark_source.csv",
                    "08_paper_ready_outputs/tables/table_main_benchmark.tex",
                ),
                ("generate_paper_sim_artifacts.py",),
            ),
            boundary="Maintains continuity with the original benchmark but is not the main discriminator for query guidance.",
        ),
        ProtocolRow(
            protocol_id="main1000_nominal_sanity",
            evidence_role="low-ambiguity stability sanity check",
            sample_scope="N=1000 nominal main-default episodes",
            perturbation_or_condition="clean nominal leader-following with shared safety layer",
            primary_metrics="success, collision, near miss, lost, minimum distance, NIS mean",
            source_artifacts="08_paper_ready_outputs/source_data/main1000_nominal_source.csv",
            generator_or_audit_script="generate_paper_sim_artifacts.py; generate_statistical_claim_audit.py",
            derived_outputs="table_main1000_nominal.tex; statistical_claim_audit.csv",
            manuscript_anchor="Metrics and Main Benchmark",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/main1000_nominal_source.csv",
                    "08_paper_ready_outputs/tables/table_main1000_nominal.tex",
                    "08_paper_ready_outputs/source_data/statistical_claim_audit.csv",
                ),
                ("generate_paper_sim_artifacts.py", "generate_statistical_claim_audit.py"),
                (("08_paper_ready_outputs/source_data/statistical_claim_audit.csv", 36),),
            ),
            boundary="Sanity check for the shared controller; not evidence that query guidance improves completion.",
        ),
        ProtocolRow(
            protocol_id="primary_fp10_ambiguity",
            evidence_role="primary target-consistency test",
            sample_scope="N=300 paired episodes per method",
            perturbation_or_condition="adjacent-lane false positives, fp_10",
            primary_metrics="LeaderAcc, wrong-leader frames, ID switches, paired bootstrap CI",
            source_artifacts="08_paper_ready_outputs/source_data/stress_summary_combined.csv; 08_paper_ready_outputs/source_data/pairwise_stats_combined.csv",
            generator_or_audit_script="summarize_carla_stress_results.py; analyze_carla_pairwise_stats.py; generate_statistical_claim_audit.py",
            derived_outputs="table_primary_ambiguity.tex; statistical_claim_audit.csv",
            manuscript_anchor="Ambiguity Stress: Target Consistency",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/stress_summary_combined.csv",
                    "08_paper_ready_outputs/source_data/pairwise_stats_combined.csv",
                    "08_paper_ready_outputs/tables/table_primary_ambiguity.tex",
                ),
                ("summarize_carla_stress_results.py", "analyze_carla_pairwise_stats.py", "generate_statistical_claim_audit.py"),
            ),
            boundary="Supports target-consistency improvement, not universal route-completion superiority.",
        ),
        ProtocolRow(
            protocol_id="primary_idswitch_ambiguity",
            evidence_role="primary identity-ambiguity test",
            sample_scope="N=300 paired episodes per method",
            perturbation_or_condition="identity-switch perturbation, idswitch",
            primary_metrics="LeaderAcc, ID switches, paired bootstrap CI",
            source_artifacts="08_paper_ready_outputs/source_data/stress_summary_combined.csv; 08_paper_ready_outputs/source_data/pairwise_stats_combined.csv",
            generator_or_audit_script="summarize_carla_stress_results.py; analyze_carla_pairwise_stats.py; generate_statistical_claim_audit.py",
            derived_outputs="table_primary_ambiguity.tex; fig_extended_stress_outcomes",
            manuscript_anchor="Ambiguity Stress: Target Consistency",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/stress_summary_combined.csv",
                    "08_paper_ready_outputs/source_data/pairwise_stats_combined.csv",
                    "08_paper_ready_outputs/figures/fig_extended_stress_outcomes.svg",
                ),
                ("summarize_carla_stress_results.py", "analyze_carla_pairwise_stats.py", "generate_statistical_claim_audit.py"),
            ),
            boundary="Tests identity robustness inside CARLA object/detector interfaces, not open-world semantic reasoning.",
        ),
        ProtocolRow(
            protocol_id="detector_timing_stress",
            evidence_role="coverage stress layer",
            sample_scope="N=300 detector/timing episodes per condition",
            perturbation_or_condition="false-negative detector faults and 200 ms object-message delay",
            primary_metrics="success, collision, lost, LeaderAcc",
            source_artifacts="08_paper_ready_outputs/source_data/stress_summary_combined.csv; 08_paper_ready_outputs/source_data/carla_scenario_coverage_source.csv",
            generator_or_audit_script="summarize_carla_stress_results.py; generate_paper_sim_artifacts.py",
            derived_outputs="table_detector_timing.tex; table_scenario_coverage.tex",
            manuscript_anchor="Expanded Stress-Suite Outcomes",
            status=status_for(
                (
                    "08_paper_ready_outputs/tables/table_detector_timing.tex",
                    "08_paper_ready_outputs/tables/table_scenario_coverage.tex",
                    "08_paper_ready_outputs/source_data/carla_scenario_coverage_source.csv",
                ),
                ("summarize_carla_stress_results.py", "generate_paper_sim_artifacts.py"),
            ),
            boundary="Layered coverage check; not a fully factorial timing/perception sweep.",
        ),
        ProtocolRow(
            protocol_id="raw_sensor_like_stress",
            evidence_role="raw-sensor-like degradation screen",
            sample_scope="N=100 episodes per raw-like condition",
            perturbation_or_condition="glare-like and LiDAR-dropout-like detector degradation profiles",
            primary_metrics="success, collision, lost, LeaderAcc",
            source_artifacts="08_paper_ready_outputs/source_data/stress_summary_combined.csv",
            generator_or_audit_script="summarize_carla_stress_results.py; generate_paper_sim_artifacts.py",
            derived_outputs="table_raw_sensor_like.tex; table_scenario_coverage.tex",
            manuscript_anchor="Expanded Stress-Suite Outcomes",
            status=status_for(
                (
                    "08_paper_ready_outputs/tables/table_raw_sensor_like.tex",
                    "08_paper_ready_outputs/source_data/stress_summary_combined.csv",
                ),
                ("summarize_carla_stress_results.py", "generate_paper_sim_artifacts.py"),
            ),
            boundary="Approximate detector-level degradation; not photorealistic raw-camera/LiDAR simulation.",
        ),
        ProtocolRow(
            protocol_id="boundary_ambiguity_stress",
            evidence_role="supplemental boundary behavior",
            sample_scope="N=100 episodes per boundary condition",
            perturbation_or_condition="fp_20, idswitch_40, fp20_idswitch20",
            primary_metrics="success, collision, lost, LeaderAcc, ID switches",
            source_artifacts="08_paper_ready_outputs/source_data/stress_summary_combined.csv; 08_paper_ready_outputs/source_data/extended_stress_qgip_summary.csv",
            generator_or_audit_script="generate_extended_artifacts.py; generate_statistical_claim_audit.py",
            derived_outputs="table_boundary_stress.tex; table_extended_stress_qgip_summary.tex; fig_extended_stress_outcomes",
            manuscript_anchor="Expanded Stress-Suite Outcomes",
            status=status_for(
                (
                    "08_paper_ready_outputs/tables/table_boundary_stress.tex",
                    "08_paper_ready_outputs/source_data/extended_stress_qgip_summary.csv",
                    "08_paper_ready_outputs/figures/fig_extended_stress_outcomes.svg",
                ),
                ("generate_extended_artifacts.py", "generate_statistical_claim_audit.py"),
                (("08_paper_ready_outputs/source_data/extended_stress_qgip_summary.csv", 7),),
            ),
            boundary="Supplemental boundary evidence; not the primary statistical test.",
        ),
        ProtocolRow(
            protocol_id="nis_noise_diagnostic",
            evidence_role="POP/NIS instrumentation check",
            sample_scope="N=100 QGIP episodes per noise condition",
            perturbation_or_condition="Gaussian observation noise, 0.2/0.5/1.0 m",
            primary_metrics="NIS mean, NIS p95, soft violations, hard violations",
            source_artifacts="08_paper_ready_outputs/source_data/carla_nis_noise_sweep_qgip100_summary.csv; 08_paper_ready_outputs/source_data/carla_nis_noise_sweep_figure_data.csv",
            generator_or_audit_script="generate_nis_diagnostic_artifacts.py; generate_extended_artifacts.py; generate_statistical_claim_audit.py",
            derived_outputs="table_carla_nis_noise_sweep.tex; fig_extended_nis_response",
            manuscript_anchor="NIS Response and Outlier Diagnostics",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/carla_nis_noise_sweep_qgip100_summary.csv",
                    "08_paper_ready_outputs/tables/table_carla_nis_noise_sweep.tex",
                    "08_paper_ready_outputs/figures/fig_extended_nis_response.svg",
                ),
                ("generate_nis_diagnostic_artifacts.py", "generate_extended_artifacts.py", "generate_statistical_claim_audit.py"),
                (("08_paper_ready_outputs/source_data/carla_nis_noise_sweep_qgip100_summary.csv", 3),),
            ),
            boundary="Diagnostic response check; not final covariance calibration or real-sensor validation.",
        ),
        ProtocolRow(
            protocol_id="nis_outlier_diagnostic",
            evidence_role="detector-inconsistency response check",
            sample_scope="N=100 QGIP episodes per outlier condition",
            perturbation_or_condition="false-positive, ID-switch, and combined outlier profiles",
            primary_metrics="NIS mean, NIS p95, hard resets, soft updates",
            source_artifacts="08_paper_ready_outputs/source_data/carla_nis_outlier_qgip100_summary.csv; 08_paper_ready_outputs/source_data/carla_nis_outlier_figure_data.csv",
            generator_or_audit_script="generate_nis_diagnostic_artifacts.py; generate_extended_artifacts.py; generate_statistical_claim_audit.py",
            derived_outputs="table_carla_nis_outlier_sweep.tex; fig_extended_nis_response",
            manuscript_anchor="NIS Response and Outlier Diagnostics",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/carla_nis_outlier_qgip100_summary.csv",
                    "08_paper_ready_outputs/tables/table_carla_nis_outlier_sweep.tex",
                    "08_paper_ready_outputs/figures/fig_extended_nis_response.svg",
                ),
                ("generate_nis_diagnostic_artifacts.py", "generate_extended_artifacts.py", "generate_statistical_claim_audit.py"),
                (("08_paper_ready_outputs/source_data/carla_nis_outlier_qgip100_summary.csv", 3),),
            ),
            boundary="Outlier-response evidence only; not a real detector calibration study.",
        ),
        ProtocolRow(
            protocol_id="statistical_traceability",
            evidence_role="claim/source-data drift control",
            sample_scope="36 numerical checks plus 8 claim-evidence rows",
            perturbation_or_condition="processed source-data consistency audit",
            primary_metrics="split counts, LeaderAcc, paired CIs, NIS values, zero-observation finite-sample checks",
            source_artifacts="08_paper_ready_outputs/source_data/statistical_claim_audit.csv; 08_paper_ready_outputs/source_data/claim_evidence_matrix.csv",
            generator_or_audit_script="generate_statistical_claim_audit.py; generate_extended_artifacts.py",
            derived_outputs="statistical_claim_audit_report_20260604.md; table_claim_evidence_matrix.tex",
            manuscript_anchor="Claim-to-Evidence Traceability",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/statistical_claim_audit.csv",
                    "08_paper_ready_outputs/source_data/claim_evidence_matrix.csv",
                    "06_submission_package/statistical_claim_audit_report_20260604.md",
                ),
                ("generate_statistical_claim_audit.py", "generate_extended_artifacts.py"),
                (
                    ("08_paper_ready_outputs/source_data/statistical_claim_audit.csv", 36),
                    ("08_paper_ready_outputs/source_data/claim_evidence_matrix.csv", 8),
                ),
            ),
            boundary="Prevents manuscript/source-data drift; does not inspect raw CARLA logs.",
        ),
        ProtocolRow(
            protocol_id="figure_table_reproduction",
            evidence_role="publication artifact reproducibility",
            sample_scope="10 main/extended/preflight/safety-case/coverage/effect-size/stress-atlas/readiness figures, 13 table bodies before this registry",
            perturbation_or_condition="scripted figure/table export and source-data mapping",
            primary_metrics="export presence, SVG text/vector screen, TIFF resolution, source-data mapping",
            source_artifacts="08_paper_ready_outputs/source_data/publication_figure_qa.csv; 08_paper_ready_outputs/source_data/source_data_provenance_audit.csv",
            generator_or_audit_script="generate_publication_figure_qa.py; generate_source_data_provenance_audit.py",
            derived_outputs="publication_figure_qa_report_20260604.md; source_data_provenance_audit_report_20260604.md",
            manuscript_anchor="Claim-to-Evidence Traceability",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/publication_figure_qa.csv",
                    "08_paper_ready_outputs/source_data/source_data_provenance_audit.csv",
                    "06_submission_package/publication_figure_qa_report_20260604.md",
                    "06_submission_package/source_data_provenance_audit_report_20260604.md",
                ),
                ("generate_publication_figure_qa.py", "generate_source_data_provenance_audit.py"),
                (("08_paper_ready_outputs/source_data/publication_figure_qa.csv", 92),),
            ),
            boundary="Machine-readable production QA; does not replace human journal-production review.",
        ),
        ProtocolRow(
            protocol_id="ros2_preflight_protocol",
            evidence_role="pre-real-robot validation readiness",
            sample_scope="12 planned real-robot trials plus static ROS2 interface audit",
            perturbation_or_condition="selected-leader route, topic contracts, safety-supervisor gate, metric schema",
            primary_metrics="topic contract rows, offline validation checks, static interface checks, template metric coverage",
            source_artifacts="03_real_robot/ros2_topic_contract.csv; 03_real_robot/real_robot_metric_schema.csv; 08_paper_ready_outputs/source_data/ros2_static_interface_audit.csv; 08_paper_ready_outputs/source_data/real_robot_preflight_validation.csv",
            generator_or_audit_script="generate_ros2_static_interface_audit.py; generate_real_robot_preflight_validation.py; summarize_real_robot_trials.py",
            derived_outputs="ros2_static_interface_audit_report_20260604.md; real_robot_preflight_validation_report_20260604.md; real_robot_template_summary.csv",
            manuscript_anchor="Future validation protocol",
            status=status_for(
                (
                    "03_real_robot/ros2_topic_contract.csv",
                    "03_real_robot/real_robot_metric_schema.csv",
                    "08_paper_ready_outputs/source_data/ros2_static_interface_audit.csv",
                    "08_paper_ready_outputs/source_data/real_robot_preflight_validation.csv",
                    "08_paper_ready_outputs/source_data/real_robot_template_summary.csv",
                ),
                ("generate_ros2_static_interface_audit.py", "generate_real_robot_preflight_validation.py", "summarize_real_robot_trials.py"),
                (
                    ("03_real_robot/ros2_topic_contract.csv", 13),
                    ("03_real_robot/real_robot_metric_schema.csv", 29),
                    ("08_paper_ready_outputs/source_data/ros2_static_interface_audit.csv", 19),
                    ("08_paper_ready_outputs/source_data/real_robot_preflight_validation.csv", 41),
                ),
            ),
            boundary="Preflight protocol only; no ROS2 build, rosbag, physical timing, or robot trial data are claimed.",
        ),
        ProtocolRow(
            protocol_id="ros2_workspace_ci_audit",
            evidence_role="ROS2 workspace build/test readiness audit",
            sample_scope="11 CI asset and pure-core pytest checks before colcon execution",
            perturbation_or_condition="colcon build/test command coverage, launch-argument parsing, pure-core pytest, shadow-command boundary",
            primary_metrics="PASS/FAIL CI asset checks, 7 local pure-core pytest cases, declared ROS2 workspace archive requirements",
            source_artifacts="03_real_robot/ros2_workspace_ci_manifest.yaml; 03_real_robot/run_ros2_workspace_preflight.sh; 03_real_robot/ros2_qgip_stack/test/test_core_contracts.py; 08_paper_ready_outputs/source_data/ros2_workspace_ci_audit.csv",
            generator_or_audit_script="generate_ros2_workspace_ci_audit.py",
            derived_outputs="ros2_workspace_ci_audit.csv; ros2_workspace_ci_audit_report_20260604.md",
            manuscript_anchor="Future validation protocol",
            status=status_for(
                (
                    "03_real_robot/ros2_workspace_ci_manifest.yaml",
                    "03_real_robot/run_ros2_workspace_preflight.sh",
                    "03_real_robot/ros2_qgip_stack/test/test_core_contracts.py",
                    "08_paper_ready_outputs/source_data/ros2_workspace_ci_audit.csv",
                    "06_submission_package/ros2_workspace_ci_audit_report_20260604.md",
                ),
                ("generate_ros2_workspace_ci_audit.py",),
                (("08_paper_ready_outputs/source_data/ros2_workspace_ci_audit.csv", 11),),
            ),
            boundary="CI asset audit only; local pytest does not prove colcon build/test, live ros2 launch, rosbag timing, HIL replay, actuator bridge behavior, or physical robot motion.",
        ),
        ProtocolRow(
            protocol_id="ros2_runtime_telemetry_audit",
            evidence_role="runtime timing and system-load telemetry readiness audit",
            sample_scope="15 telemetry schema, manifest, dry-run, metric-summary, and narrative-boundary checks before HIL timing claims",
            perturbation_or_condition="latency mean/p95/p99, frame drops, watchdog reasons, command age, clock drift, CPU/GPU load, rosbag linkage",
            primary_metrics="PASS/FAIL telemetry instrumentation checks, 24 telemetry fields, 10 required runtime summary fields",
            source_artifacts="03_real_robot/ros2_runtime_telemetry_schema.csv; 03_real_robot/runtime_telemetry_manifest_template.yaml; 08_paper_ready_outputs/source_data/ros2_runtime_telemetry_audit.csv",
            generator_or_audit_script="generate_ros2_runtime_telemetry_audit.py",
            derived_outputs="ros2_runtime_telemetry_audit.csv; ros2_runtime_telemetry_audit_report_20260604.md",
            manuscript_anchor="Runtime and deployment boundary",
            status=status_for(
                (
                    "03_real_robot/ros2_runtime_telemetry_schema.csv",
                    "03_real_robot/runtime_telemetry_manifest_template.yaml",
                    "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_audit.csv",
                    "06_submission_package/ros2_runtime_telemetry_audit_report_20260604.md",
                ),
                ("generate_ros2_runtime_telemetry_audit.py",),
                (("08_paper_ready_outputs/source_data/ros2_runtime_telemetry_audit.csv", 15),),
            ),
            boundary="Telemetry readiness only; no ROS2 launch, HIL timing measurement, embedded feasibility, actuator bridge behavior, or physical robot motion is claimed.",
        ),
        ProtocolRow(
            protocol_id="ros2_runtime_telemetry_dryrun",
            evidence_role="runtime telemetry parser and summary dry-run",
            sample_scope="320 synthetic schema-compatible rows and 16 summary checks before real telemetry CSVs are collected",
            perturbation_or_condition="synthetic latency, frame-drop accounting, watchdog reasons, command-age tracking, clock-drift tracking, CPU/GPU load, and declared synthetic source",
            primary_metrics="latency mean/p95/p99, frame_drop_count, clock_drift_p95_ms, cmd_vel_safe_age_p95_ms, watchdog_triggers_explained, CPU/GPU/gpu-memory summary checks",
            source_artifacts="08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_trace.csv; 08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_summary.csv; 06_submission_package/ros2_runtime_telemetry_dryrun_report_20260604.md",
            generator_or_audit_script="generate_ros2_runtime_telemetry_dryrun.py",
            derived_outputs="ros2_runtime_telemetry_dryrun_trace.csv; ros2_runtime_telemetry_dryrun_summary.csv; ros2_runtime_telemetry_dryrun_report_20260604.md",
            manuscript_anchor="Runtime and deployment boundary",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_trace.csv",
                    "08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_summary.csv",
                    "06_submission_package/ros2_runtime_telemetry_dryrun_report_20260604.md",
                ),
                ("generate_ros2_runtime_telemetry_dryrun.py",),
                (
                    ("08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_trace.csv", 320),
                    ("08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_summary.csv", 16),
                ),
            ),
            boundary="Synthetic parser QA only; no live ROS2 timing, rosbag extraction, HIL timing, embedded feasibility, actuator bridge behavior, or physical robot motion is claimed.",
        ),
        ProtocolRow(
            protocol_id="real_robot_software_smoke",
            evidence_role="pre-ROS2 executable software check",
            sample_scope="17 pure-Python smoke checks before ROS2/HIL execution",
            perturbation_or_condition="POP/NIS core parity, dropout, NIS soft/hard gates, fault injection, JSON payloads, controller proxy",
            primary_metrics="PASS/FAIL behavior checks, mode parity, NIS thresholds, FIFO delay, ID switch, false positive, safety-stop invariants",
            source_artifacts="08_paper_ready_outputs/source_data/real_robot_software_smoke_test.csv; 06_submission_package/real_robot_software_smoke_test_report_20260604.md",
            generator_or_audit_script="generate_real_robot_software_smoke_test.py",
            derived_outputs="real_robot_software_smoke_test.csv; real_robot_software_smoke_test_report_20260604.md",
            manuscript_anchor="Future validation protocol",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/real_robot_software_smoke_test.csv",
                    "06_submission_package/real_robot_software_smoke_test_report_20260604.md",
                ),
                ("generate_real_robot_software_smoke_test.py",),
                (("08_paper_ready_outputs/source_data/real_robot_software_smoke_test.csv", 17),),
            ),
            boundary="Executable desktop software check only; no ROS2 launch, DDS timing, rosbag capture, actuator bridge, or robot motion is claimed.",
        ),
        ProtocolRow(
            protocol_id="offline_preflight_dryrun",
            evidence_role="pre-ROS2 behavior smoke test",
            sample_scope="90 deterministic desktop frames with 33 software-dropout frames",
            perturbation_or_condition="scripted leader/distractor detections, software dropout, high-NIS recovery offset",
            primary_metrics="mode counts, max NIS, selected-leader continuity, safety-stop during LOST, positive tracking speed",
            source_artifacts="08_paper_ready_outputs/source_data/real_robot_offline_dryrun_trace.csv; 08_paper_ready_outputs/source_data/real_robot_offline_dryrun_summary.csv; 08_paper_ready_outputs/source_data/fig13_offline_dryrun_contract_timeline_v2_source_data.csv",
            generator_or_audit_script="generate_real_robot_offline_dryrun.py; fig13_offline_dryrun_contract_timeline_v2.py",
            derived_outputs="real_robot_offline_dryrun_report_20260604.md; fig13_offline_dryrun_contract_timeline_v2",
            manuscript_anchor="Future validation protocol",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/real_robot_offline_dryrun_trace.csv",
                    "08_paper_ready_outputs/source_data/real_robot_offline_dryrun_summary.csv",
                    "08_paper_ready_outputs/source_data/fig13_offline_dryrun_contract_timeline_v2_source_data.csv",
                    "08_paper_ready_outputs/figures/fig13_offline_dryrun_contract_timeline_v2.svg",
                    "06_submission_package/real_robot_offline_dryrun_report_20260604.md",
                ),
                ("generate_real_robot_offline_dryrun.py", "fig13_offline_dryrun_contract_timeline_v2.py"),
                (
                    ("08_paper_ready_outputs/source_data/real_robot_offline_dryrun_trace.csv", 90),
                    ("08_paper_ready_outputs/source_data/real_robot_offline_dryrun_summary.csv", 12),
                    ("08_paper_ready_outputs/source_data/fig13_offline_dryrun_contract_timeline_v2_source_data.csv", 189),
                ),
            ),
            boundary="Desktop dry run only; no ROS2 launch, rosbag, timing, or physical robot motion is claimed.",
        ),
        ProtocolRow(
            protocol_id="ros2_hil_replay_manifest_audit",
            evidence_role="pre-HIL replay manifest audit",
            sample_scope="17 static HIL replay and rosbag manifest checks before Stage C execution",
            perturbation_or_condition="required rosbag topics, ROS clock playback, safety-state logging, actuator-bridge disablement, HIL shadow repeat budget",
            primary_metrics="PASS/FAIL manifest checks, required topic coverage, Stage C/D repeat and speed gates, timing-field readiness",
            source_artifacts="03_real_robot/hil_replay_manifest_template.yaml; 08_paper_ready_outputs/source_data/ros2_hil_replay_manifest_audit.csv; 06_submission_package/ros2_hil_replay_manifest_audit_report_20260604.md",
            generator_or_audit_script="generate_ros2_hil_replay_manifest_audit.py",
            derived_outputs="ros2_hil_replay_manifest_audit.csv; ros2_hil_replay_manifest_audit_report_20260604.md",
            manuscript_anchor="Future validation protocol",
            status=status_for(
                (
                    "03_real_robot/hil_replay_manifest_template.yaml",
                    "08_paper_ready_outputs/source_data/ros2_hil_replay_manifest_audit.csv",
                    "06_submission_package/ros2_hil_replay_manifest_audit_report_20260604.md",
                ),
                ("generate_ros2_hil_replay_manifest_audit.py",),
                (("08_paper_ready_outputs/source_data/ros2_hil_replay_manifest_audit.csv", 17),),
            ),
            boundary="Manifest audit only; no colcon build, ros2 launch, rosbag timing, HIL replay measurement, actuator bridge, or physical robot motion is claimed.",
        ),
        ProtocolRow(
            protocol_id="safety_case_claim_graph",
            evidence_role="bounded safety-case and non-claim argument graph",
            sample_scope="12 top-level, ODD, target-consistency, finite-sample, fail-safe, uncertainty-monitor, ROS2-preflight, telemetry, provenance, and validation-gap nodes",
            perturbation_or_condition="claim-to-evidence discipline across simulation, pre-real-robot readiness, provenance, and remaining external validation gaps",
            primary_metrics="PASS/FAIL evidence status per safety-case node, boundary text, next required evidence",
            source_artifacts="08_paper_ready_outputs/source_data/safety_case_claim_graph.csv; 08_paper_ready_outputs/tables/table_safety_case_claim_graph.tex; 06_submission_package/safety_case_audit_report_20260604.md",
            generator_or_audit_script="generate_safety_case_audit.py",
            derived_outputs="safety_case_claim_graph.csv; table_safety_case_claim_graph.tex; safety_case_audit_report_20260604.md",
            manuscript_anchor="Claim-to-evidence traceability",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/safety_case_claim_graph.csv",
                    "08_paper_ready_outputs/tables/table_safety_case_claim_graph.tex",
                    "06_submission_package/safety_case_audit_report_20260604.md",
                ),
                ("generate_safety_case_audit.py",),
                (("08_paper_ready_outputs/source_data/safety_case_claim_graph.csv", 12),),
            ),
            boundary="Claim-discipline audit only; no safety certification, raw CARLA rerun, ROS2 launch, HIL timing, DOI publication, or physical robot validation is claimed.",
        ),
        ProtocolRow(
            protocol_id="pre_real_robot_gate_audit",
            evidence_role="go/no-go pre-real-robot gate synthesis",
            sample_scope="23 staged network/TF, detection/fault, HIL, runtime-telemetry, closed-loop, evidence-package, and non-claim gates",
            perturbation_or_condition="pre-real-robot readiness gates before ROS2/HIL/physical execution claims",
            primary_metrics="gate pass count, decision labels, next required evidence, non-claim boundaries",
            source_artifacts="08_paper_ready_outputs/source_data/pre_real_robot_gate_audit.csv; 08_paper_ready_outputs/tables/table_pre_real_robot_gate_audit.tex",
            generator_or_audit_script="generate_pre_real_robot_gate_audit.py",
            derived_outputs="pre_real_robot_gate_audit_report_20260604.md; table_pre_real_robot_gate_audit.tex",
            manuscript_anchor="Future validation protocol",
            status=status_for(
                (
                    "08_paper_ready_outputs/source_data/pre_real_robot_gate_audit.csv",
                    "08_paper_ready_outputs/tables/table_pre_real_robot_gate_audit.tex",
                    "06_submission_package/pre_real_robot_gate_audit_report_20260604.md",
                ),
                ("generate_pre_real_robot_gate_audit.py",),
                (("08_paper_ready_outputs/source_data/pre_real_robot_gate_audit.csv", 23),),
            ),
            boundary="Go/no-go readiness synthesis only; it does not prove ROS2 build, ros2 launch, rosbag capture, timing, or physical robot validation.",
        ),
    ]
    return data


def write_csv(rows: list[ProtocolRow]) -> None:
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ProtocolRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])


def write_table(rows: list[ProtocolRow]) -> None:
    lines = [
        "% Auto-generated by generate_simulation_protocol_registry.py",
        "\\setlength{\\tabcolsep}{2pt}",
        "\\renewcommand{\\arraystretch}{0.92}",
        "\\begin{tabular}{@{}>{\\raggedright\\arraybackslash}p{0.14\\linewidth} >{\\raggedright\\arraybackslash}p{0.17\\linewidth} >{\\raggedright\\arraybackslash}p{0.21\\linewidth} >{\\raggedright\\arraybackslash}p{0.18\\linewidth} >{\\raggedright\\arraybackslash}p{0.16\\linewidth}@{}}",
        "\\toprule",
        "\\textbf{Protocol} & \\textbf{Scope} & \\textbf{Inputs / scripts} & \\textbf{Primary metrics} & \\textbf{Boundary} \\\\",
        "\\midrule",
    ]
    for row in rows:
        source_count = len([item for item in row.source_artifacts.split(";") if item.strip()])
        script_count = len([item for item in row.generator_or_audit_script.split(";") if item.strip()])
        inputs = f"{row.evidence_role}; {source_count} source files; {script_count} scripts"
        label = TABLE_LABELS.get(row.protocol_id, row.protocol_id.replace("_", " "))
        lines.append(
            f"{esc(label)} & {esc(row.sample_scope)} & {esc(inputs)} & {esc(row.primary_metrics)} & {esc(row.boundary)} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    OUT_TABLE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_report(rows: list[ProtocolRow]) -> None:
    failed = [row for row in rows if row.status != "PASS"]
    lines = [
        "# Simulation Protocol Registry Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"The simulation protocol registry maps {len(rows)} experiment, diagnostic, audit, figure/table, and real-robot-preflight protocols to their source artifacts, scripts, manuscript anchors, metrics, and evidence boundaries.",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All registered simulation and preflight protocols have source artifacts, generator/audit scripts, and derived outputs present." if not failed else "One or more registered protocols are missing required artifacts.",
        "",
        "## Protocol Families",
        "",
        "- Dataset and leakage control.",
        "- Standard closed-loop benchmark and nominal sanity checks.",
        "- Primary ambiguity stress for target consistency.",
        "- Detector/timing, raw-sensor-like, and supplemental boundary stress layers.",
        "- POP/NIS noise and outlier diagnostics.",
        "- Statistical, manuscript, figure/table, and source-data provenance audits.",
        "- ROS2 preflight protocol, ROS2 workspace CI audit, runtime telemetry audit, runtime telemetry parser dry-run, executable software smoke test, HIL replay manifest audit, safety-case claim graph, and metric-template readiness before physical trials.",
        "",
        "## Boundary",
        "",
        "The registry strengthens methods provenance and manuscript reviewability. It does not prove raw CARLA rerun reproducibility, does not mint a DOI-backed repository, does not prove ROS2 launch/build success, and does not contain completed physical robot trial data.",
    ]
    if failed:
        lines.extend(["", "## Failed Protocols", ""])
        for row in failed:
            lines.append(f"- `{row.protocol_id}`: {row.source_artifacts}; {row.generator_or_audit_script}")
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    PACKAGE.mkdir(parents=True, exist_ok=True)
    registry_rows = rows()
    write_csv(registry_rows)
    write_table(registry_rows)
    write_report(registry_rows)
    failed = [row for row in registry_rows if row.status != "PASS"]
    print(OUT_CSV)
    print(OUT_TABLE)
    print(OUT_REPORT)
    print(f"passed={len(registry_rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
