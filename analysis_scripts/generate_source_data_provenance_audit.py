#!/usr/bin/env python3
"""Audit figure/table source-data provenance for the extended package."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
FIGURES = ROOT / "08_paper_ready_outputs" / "figures"
TABLES = ROOT / "08_paper_ready_outputs" / "tables"
PACKAGE = ROOT / "06_submission_package"
SCRIPTS = ROOT / "05_analysis_scripts"
REAL_ROBOT = ROOT / "03_real_robot"

OUT_CSV = SOURCE / "source_data_provenance_audit.csv"
OUT_REPORT = PACKAGE / "source_data_provenance_audit_report_20260604.md"


@dataclass
class AuditRow:
    audit_id: str
    asset_family: str
    requirement: str
    evidence: str
    status: str
    source_artifacts: str
    derived_outputs: str
    boundary: str


@dataclass
class SourceSpec:
    path: str
    role: str
    min_rows: int | None
    supports: str


@dataclass
class FigureSpec:
    figure_id: str
    source_files: tuple[str, ...]
    generator: str
    claim_role: str


@dataclass
class TableSpec:
    table_file: str
    source_files: tuple[str, ...]
    claim_role: str


SOURCE_SPECS = [
    SourceSpec("main_benchmark_source.csv", "core source data", 1, "main benchmark table"),
    SourceSpec("main1000_nominal_source.csv", "core source data", 1, "nominal N=1000 sanity check"),
    SourceSpec("carla_scenario_coverage_source.csv", "core source data", 1, "scenario coverage table"),
    SourceSpec("stress_summary_combined.csv", "core source data", 1, "stress-suite outcome tables and figures"),
    SourceSpec("pairwise_stats_combined.csv", "core source data", 1, "paired statistics and intervals"),
    SourceSpec("figure_stress_leader_metrics.csv", "core source data", 1, "target-consistency plotting source"),
    SourceSpec("extended_stress_qgip_summary.csv", "core source data", 7, "extended stress synthesis"),
    SourceSpec("claim_evidence_matrix.csv", "core source data", 8, "claim-to-evidence table"),
    SourceSpec("fig_nature_system_evidence_source.csv", "core source data", 12, "Nature-style Figure 1 panels"),
    SourceSpec("final_dataset_split_check.csv", "core source data", 3, "dataset split audit"),
    SourceSpec("final_dataset_split_overlap.csv", "core source data", 3, "dataset overlap audit"),
    SourceSpec("final_dataset_split_check.md", "core source data", None, "human-readable split audit"),
    SourceSpec("carla_nis_diagnostic_summary.csv", "core source data", 1, "initial CARLA NIS diagnostic"),
    SourceSpec("carla_nis_diagnostic_episode_results.csv", "core source data", 1, "per-episode NIS diagnostic"),
    SourceSpec("carla_nis_noise_sweep_qgip100_summary.csv", "core source data", 3, "NIS noise sweep table"),
    SourceSpec("carla_nis_noise_sweep_figure_data.csv", "core source data", 3, "NIS noise figure source"),
    SourceSpec("carla_nis_outlier_qgip100_summary.csv", "core source data", 3, "NIS outlier sweep table"),
    SourceSpec("carla_nis_outlier_figure_data.csv", "core source data", 3, "NIS outlier figure source"),
    SourceSpec("synthetic_pop_nis300_summary.csv", "core source data", 1, "local POP/NIS mechanism check"),
    SourceSpec("synthetic_pop_nis300_episode_results.csv", "core source data", 1, "per-episode mechanism check"),
    SourceSpec("simulation_protocol_registry.csv", "protocol source data", 21, "simulation and preflight protocol registry"),
    SourceSpec("figure_accessibility_metrics.csv", "audit source data", 30, "figure accessibility QA"),
    SourceSpec("real_robot_preflight_validation.csv", "audit source data", 41, "offline real-robot preflight validation"),
    SourceSpec("real_robot_offline_dryrun_trace.csv", "audit source data", 90, "offline real-robot behavior dry-run trace"),
    SourceSpec("real_robot_offline_dryrun_summary.csv", "audit source data", 12, "offline real-robot behavior dry-run summary"),
    SourceSpec("real_robot_software_smoke_test.csv", "audit source data", 17, "executable real-robot software smoke test"),
    SourceSpec("ros2_workspace_ci_audit.csv", "audit source data", 11, "ROS2 workspace CI readiness audit"),
    SourceSpec("ros2_runtime_telemetry_audit.csv", "audit source data", 15, "ROS2 runtime telemetry readiness audit"),
    SourceSpec("ros2_runtime_telemetry_dryrun_trace.csv", "audit source data", 320, "ROS2 runtime telemetry parser dry-run trace"),
    SourceSpec("ros2_runtime_telemetry_dryrun_summary.csv", "audit source data", 16, "ROS2 runtime telemetry parser dry-run summary"),
    SourceSpec("ros2_hil_replay_manifest_audit.csv", "audit source data", 17, "ROS2/HIL replay manifest audit"),
    SourceSpec("fig13_offline_dryrun_contract_timeline_v2_source_data.csv", "core source data", 90, "offline dry-run contract-timeline figure"),
    SourceSpec("pre_real_robot_gate_audit.csv", "audit source data", 23, "pre-real-robot go/no-go gate audit"),
    SourceSpec("real_robot_template_summary.csv", "audit source data", 1, "future real-robot summary template"),
    SourceSpec("statistical_claim_audit.csv", "audit source data", 36, "statistical claim drift control"),
    SourceSpec("manuscript_argument_traceability.csv", "audit source data", 22, "manuscript argument traceability"),
    SourceSpec("safety_case_claim_graph.csv", "audit source data", 12, "bounded safety-case claim graph"),
    SourceSpec("fig_safety_case_evidence_map_source.csv", "core source data", 17, "safety-case evidence-boundary figure"),
    SourceSpec("fig_evidence_coverage_matrix_source.csv", "core source data", 53, "protocol-to-claim evidence coverage figure"),
    SourceSpec("fig_simulation_effect_size_source.csv", "core source data", 55, "simulation effect-size and finite-sample boundary figure"),
    SourceSpec("fig_simulation_stress_atlas_source.csv", "core source data", 62, "simulation stress atlas figure"),
    SourceSpec("fig12_validation_boundary_narrative_v4_source_data.csv", "core source data", 4, "pre-real-robot validation-boundary narrative figure"),
    SourceSpec("ros2_static_interface_audit.csv", "audit source data", 19, "ROS2 static interface traceability"),
    SourceSpec("publication_figure_qa.csv", "audit source data", 92, "publication figure QA traceability"),
]


FIGURE_SPECS = [
    FigureSpec(
        "fig_nature_system_evidence",
        (
            "fig_nature_system_evidence_source.csv",
            "stress_summary_combined.csv",
            "carla_nis_noise_sweep_qgip100_summary.csv",
            "carla_nis_outlier_qgip100_summary.csv",
        ),
        "generate_nature_main_figure.py",
        "system contract, target consistency, and NIS diagnostic evidence",
    ),
    FigureSpec(
        "fig_extended_dataset_split",
        ("final_dataset_split_check.csv", "final_dataset_split_overlap.csv"),
        "generate_extended_artifacts.py",
        "dataset split composition and leakage audit",
    ),
    FigureSpec(
        "fig_extended_stress_outcomes",
        ("extended_stress_qgip_summary.csv", "stress_summary_combined.csv"),
        "generate_extended_artifacts.py",
        "route outcome and target-consistency stress synthesis",
    ),
    FigureSpec(
        "fig_extended_nis_response",
        ("carla_nis_noise_sweep_qgip100_summary.csv", "carla_nis_outlier_qgip100_summary.csv"),
        "generate_extended_artifacts.py",
        "NIS noise and outlier diagnostic response",
    ),
    FigureSpec(
        "fig13_offline_dryrun_contract_timeline_v2",
        ("fig13_offline_dryrun_contract_timeline_v2_source_data.csv", "real_robot_offline_dryrun_trace.csv", "ros2_runtime_telemetry_dryrun_summary.csv"),
        "fig13_offline_dryrun_contract_timeline_v2.py",
        "offline selected-leader, POP/NIS, controller-proxy, and telemetry-gate contract timeline",
    ),
    FigureSpec(
        "fig_safety_case_evidence_map",
        ("fig_safety_case_evidence_map_source.csv", "safety_case_claim_graph.csv"),
        "generate_safety_case_figure.py",
        "bounded safety-case evidence map and external-validation boundary",
    ),
    FigureSpec(
        "fig_evidence_coverage_matrix",
        ("fig_evidence_coverage_matrix_source.csv", "simulation_protocol_registry.csv", "claim_evidence_matrix.csv"),
        "generate_evidence_coverage_matrix.py",
        "protocol-to-claim evidence coverage matrix linking simulation, audit, and pre-real-robot readiness layers",
    ),
    FigureSpec(
        "fig_simulation_effect_size",
        ("fig_simulation_effect_size_source.csv", "main_benchmark_source.csv", "pairwise_stats_combined.csv", "extended_stress_qgip_summary.csv"),
        "generate_simulation_effect_size_figure.py",
        "simulation effect-size synthesis linking route outcomes, target-consistency gains, wrong-leader exposure reduction, and finite-sample collision boundaries",
    ),
    FigureSpec(
        "fig_simulation_stress_atlas",
        ("fig_simulation_stress_atlas_source.csv", "main_benchmark_source.csv", "main1000_nominal_source.csv", "stress_summary_combined.csv", "pairwise_stats_combined.csv", "carla_nis_noise_sweep_qgip100_summary.csv", "carla_nis_outlier_qgip100_summary.csv"),
        "generate_simulation_stress_atlas_figure.py",
        "reader-facing simulation stress atlas linking evidence scale, stress outcomes, ambiguity effect sizes, and NIS diagnostic response",
    ),
    FigureSpec(
        "fig12_validation_boundary_narrative_v4",
        ("fig12_validation_boundary_narrative_v4_source_data.csv", "pre_real_robot_gate_audit.csv"),
        "fig12_validation_boundary_narrative_v4.py",
        "pre-real-robot validation boundary separating prepared local evidence from required live ROS2/HIL and physical-robot evidence",
    ),
]


TABLE_SPECS = [
    TableSpec("simulation_tables.md", ("main_benchmark_source.csv", "stress_summary_combined.csv"), "human-readable table bundle"),
    TableSpec("table_boundary_stress.tex", ("stress_summary_combined.csv",), "boundary stress table"),
    TableSpec("table_carla_nis_noise_sweep.tex", ("carla_nis_noise_sweep_qgip100_summary.csv",), "NIS noise sweep table"),
    TableSpec("table_carla_nis_outlier_sweep.tex", ("carla_nis_outlier_qgip100_summary.csv",), "NIS outlier sweep table"),
    TableSpec("table_claim_evidence_matrix.tex", ("claim_evidence_matrix.csv",), "claim-to-evidence matrix"),
    TableSpec("table_dataset_split_audit.tex", ("final_dataset_split_check.csv", "final_dataset_split_overlap.csv"), "dataset split audit"),
    TableSpec("table_detector_timing.tex", ("stress_summary_combined.csv",), "detector and timing stress table"),
    TableSpec("table_extended_stress_qgip_summary.tex", ("extended_stress_qgip_summary.csv",), "QGIP extended stress summary"),
    TableSpec("table_main1000_nominal.tex", ("main1000_nominal_source.csv",), "nominal non-discrimination boundary"),
    TableSpec("table_main_benchmark.tex", ("main_benchmark_source.csv",), "main benchmark table"),
    TableSpec("table_primary_ambiguity.tex", ("stress_summary_combined.csv", "pairwise_stats_combined.csv"), "primary ambiguity stress table"),
    TableSpec("table_raw_sensor_like.tex", ("stress_summary_combined.csv",), "raw-sensor-like stress table"),
    TableSpec("table_scenario_coverage.tex", ("carla_scenario_coverage_source.csv",), "scenario coverage table"),
    TableSpec("table_simulation_protocol_registry.tex", ("simulation_protocol_registry.csv",), "simulation protocol registry"),
    TableSpec("table_safety_case_claim_graph.tex", ("safety_case_claim_graph.csv",), "bounded safety-case claim graph"),
    TableSpec("table_pre_real_robot_gate_audit.tex", ("pre_real_robot_gate_audit.csv",), "pre-real-robot go/no-go gate audit"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def csv_row_count(path: Path) -> int:
    return len(read_csv(path))


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def add(
    rows: list[AuditRow],
    audit_id: str,
    asset_family: str,
    requirement: str,
    ok: bool,
    evidence: str,
    source_artifacts: str,
    derived_outputs: str,
    boundary: str,
) -> None:
    rows.append(
        AuditRow(
            audit_id=audit_id,
            asset_family=asset_family,
            requirement=requirement,
            evidence=evidence,
            status="PASS" if ok else "FAIL",
            source_artifacts=source_artifacts,
            derived_outputs=derived_outputs,
            boundary=boundary,
        )
    )


def source_ok(filename: str, min_rows: int | None = 1) -> tuple[bool, str]:
    path = SOURCE / filename
    if not path.exists() or path.stat().st_size <= 0:
        return False, f"{filename}=missing_or_empty"
    if min_rows is None:
        return True, f"{filename}={path.stat().st_size} bytes"
    rows = csv_row_count(path)
    return rows >= min_rows, f"{filename}={rows} rows"


def table_ok(spec: TableSpec) -> tuple[bool, str]:
    table = TABLES / spec.table_file
    sources = [source_ok(item, 1) for item in spec.source_files]
    ok = table.exists() and table.stat().st_size > 0 and all(item[0] for item in sources)
    detail = [f"{spec.table_file}={table.stat().st_size if table.exists() else 0} bytes"]
    detail.extend(item[1] for item in sources)
    return ok, "; ".join(detail)


def figure_ok(spec: FigureSpec) -> tuple[bool, str]:
    exports = [FIGURES / f"{spec.figure_id}.{suffix}" for suffix in ("pdf", "svg", "tiff", "png")]
    source_checks = [source_ok(item, 1) for item in spec.source_files]
    generator = SCRIPTS / spec.generator
    ok = all(path.exists() and path.stat().st_size > 0 for path in exports)
    ok = ok and generator.exists() and generator.stat().st_size > 0 and all(item[0] for item in source_checks)
    detail = [f"{path.name}={path.stat().st_size if path.exists() else 0} bytes" for path in exports]
    detail.append(f"{spec.generator}={generator.stat().st_size if generator.exists() else 0} bytes")
    detail.extend(item[1] for item in source_checks)
    return ok, "; ".join(detail)


def all_pass(path: Path, expected_rows: int) -> tuple[bool, str]:
    rows = read_csv(path) if path.exists() else []
    statuses = {row.get("status") or row.get("evidence_status", "") for row in rows}
    ok = len(rows) == expected_rows and statuses == {"PASS"}
    return ok, f"{path.name}={len(rows)} rows; statuses={','.join(sorted(statuses)) or 'none'}"


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())


def main() -> None:
    rows: list[AuditRow] = []

    for spec in SOURCE_SPECS:
        ok, evidence = source_ok(spec.path, spec.min_rows)
        add(
            rows,
            f"source_inventory_{spec.path.replace('.', '_').replace('/', '_')}",
            spec.role,
            f"`{spec.path}` exists, is non-empty, and has the expected minimum row count for {spec.supports}.",
            ok,
            evidence,
            f"08_paper_ready_outputs/source_data/{spec.path}",
            spec.supports,
            "Processed source-data inventory; this does not prove raw CARLA rerun reproducibility.",
        )

    add(
        rows,
        "source_inventory_provenance_audit_declared",
        "audit source data",
        "The provenance audit declares both machine-readable CSV and human-readable report outputs.",
        True,
        f"target_csv={OUT_CSV.relative_to(ROOT).as_posix()}; target_report={OUT_REPORT.relative_to(ROOT).as_posix()}",
        "05_analysis_scripts/generate_source_data_provenance_audit.py",
        "source_data_provenance_audit.csv; source_data_provenance_audit_report_20260604.md",
        "The first run creates these outputs; subsequent verifier runs check packaged copies.",
    )

    for spec in FIGURE_SPECS:
        ok, evidence = figure_ok(spec)
        add(
            rows,
            f"figure_to_source_{spec.figure_id}",
            "figure-to-source-data mapping",
            f"`{spec.figure_id}` has four publication exports, a generator, and source-data files for {spec.claim_role}.",
            ok,
            evidence,
            "; ".join(spec.source_files),
            f"{spec.figure_id}.{{pdf,svg,tiff,png}} via {spec.generator}",
            "Figure source-data traceability covers processed data, not complete raw simulator logs.",
        )

    for spec in TABLE_SPECS:
        ok, evidence = table_ok(spec)
        add(
            rows,
            f"table_to_source_{spec.table_file.replace('.', '_')}",
            "table-to-source-data mapping",
            f"`{spec.table_file}` has a generated table body and source-data files for {spec.claim_role}.",
            ok,
            evidence,
            "; ".join(spec.source_files),
            spec.table_file,
            "Table source-data traceability checks generated artifacts, not independent statistical review.",
        )

    trace_checks = [
        ("claim_evidence_matrix_rows", SOURCE / "claim_evidence_matrix.csv", 8, "claim-to-evidence matrix"),
        ("statistical_claim_audit_all_pass", SOURCE / "statistical_claim_audit.csv", 36, "statistical claim audit"),
        ("manuscript_argument_audit_all_pass", SOURCE / "manuscript_argument_traceability.csv", 22, "manuscript argument audit"),
        ("safety_case_claim_graph_all_pass", SOURCE / "safety_case_claim_graph.csv", 12, "bounded safety-case claim graph"),
        ("ros2_static_interface_audit_all_pass", SOURCE / "ros2_static_interface_audit.csv", 19, "ROS2 static interface audit"),
        ("real_robot_preflight_validation_all_pass", SOURCE / "real_robot_preflight_validation.csv", 41, "offline real-robot preflight validation"),
        ("real_robot_offline_dryrun_summary_all_pass", SOURCE / "real_robot_offline_dryrun_summary.csv", 12, "offline real-robot behavior dry run"),
        ("real_robot_software_smoke_test_all_pass", SOURCE / "real_robot_software_smoke_test.csv", 17, "executable real-robot software smoke test"),
        ("ros2_workspace_ci_audit_all_pass", SOURCE / "ros2_workspace_ci_audit.csv", 11, "ROS2 workspace CI readiness audit"),
        ("ros2_runtime_telemetry_audit_all_pass", SOURCE / "ros2_runtime_telemetry_audit.csv", 15, "ROS2 runtime telemetry readiness audit"),
        ("ros2_runtime_telemetry_dryrun_summary_all_pass", SOURCE / "ros2_runtime_telemetry_dryrun_summary.csv", 16, "ROS2 runtime telemetry parser dry-run summary"),
        ("ros2_hil_replay_manifest_audit_all_pass", SOURCE / "ros2_hil_replay_manifest_audit.csv", 17, "ROS2/HIL replay manifest audit"),
        ("pre_real_robot_gate_audit_all_pass", SOURCE / "pre_real_robot_gate_audit.csv", 23, "pre-real-robot go/no-go gate audit"),
        ("publication_figure_qa_all_pass", SOURCE / "publication_figure_qa.csv", 92, "publication figure QA"),
        ("figure_accessibility_metrics_rows", SOURCE / "figure_accessibility_metrics.csv", 30, "figure accessibility QA"),
    ]
    for audit_id, path, expected, role in trace_checks:
        ok, evidence = all_pass(path, expected) if audit_id.endswith("_all_pass") or "audit" in audit_id or "qa" in audit_id else (csv_row_count(path) == expected, f"{path.name}={csv_row_count(path) if path.exists() else -1} rows")
        add(
            rows,
            audit_id,
            "claim and QA traceability",
            f"`{path.name}` supplies the expected {expected} rows for {role}.",
            ok,
            evidence,
            path.relative_to(ROOT).as_posix(),
            role,
            "Traceability prevents package drift; it is not a substitute for raw data release or expert review.",
        )

    for audit_id, path, expected_rows, role in (
        ("real_robot_topic_contract_rows", REAL_ROBOT / "ros2_topic_contract.csv", 13, "ROS2 topic contract"),
        ("real_robot_metric_schema_rows", REAL_ROBOT / "real_robot_metric_schema.csv", 29, "real-robot metric schema"),
        ("real_robot_manifest_template_present", REAL_ROBOT / "real_robot_run_manifest_template.yaml", None, "future run manifest template"),
    ):
        if expected_rows is None:
            ok = path.exists() and path.stat().st_size > 0
            evidence = f"{path.name}={path.stat().st_size if path.exists() else 0} bytes"
        else:
            ok = path.exists() and csv_row_count(path) == expected_rows
            evidence = f"{path.name}={csv_row_count(path) if path.exists() else -1} rows"
        add(
            rows,
            audit_id,
            "real-robot preflight provenance",
            f"`{path.name}` is present for {role}.",
            ok,
            evidence,
            path.relative_to(ROOT).as_posix(),
            role,
            "Preflight provenance does not contain completed physical robot trial data.",
        )

    fair = SOURCE / "README_fair_metadata.md"
    fair_terms = [
        "FAIR",
        "File inventory",
        "Common variable dictionary",
        "Provenance",
        "Missing information before public deposit",
        "DOI-backed repository",
        "source_data_provenance_audit.csv",
        "simulation_protocol_registry.csv",
        "real_robot_preflight_validation.csv",
        "real_robot_offline_dryrun_trace.csv",
        "real_robot_offline_dryrun_summary.csv",
        "real_robot_software_smoke_test.csv",
        "ros2_workspace_ci_audit.csv",
        "ros2_runtime_telemetry_audit.csv",
        "ros2_runtime_telemetry_dryrun_trace.csv",
        "ros2_runtime_telemetry_dryrun_summary.csv",
        "ros2_hil_replay_manifest_audit.csv",
        "fig13_offline_dryrun_contract_timeline_v2_source_data.csv",
        "fig_safety_case_evidence_map_source.csv",
        "fig_evidence_coverage_matrix_source.csv",
        "pre_real_robot_gate_audit.csv",
        "safety_case_claim_graph.csv",
    ]
    fair_text = text(fair) if fair.exists() else ""
    missing_fair = [term for term in fair_terms if term not in fair_text]
    add(
        rows,
        "fair_readme_required_sections",
        "FAIR metadata",
        "Source-data README contains FAIR sections, file inventory, provenance, DOI boundary, and the provenance-audit output.",
        not missing_fair,
        "missing=" + ("; ".join(missing_fair) if missing_fair else "none"),
        fair.relative_to(ROOT).as_posix(),
        "source-data dictionary and FAIR checklist",
        "FAIR metadata is local until a DOI-backed repository record is created.",
    )

    manifest = PACKAGE / "repository_deposit_manifest_20260603.csv"
    checksums = PACKAGE / "repository_deposit_checksums_sha256_20260603.txt"
    manifest_rows = read_csv(manifest) if manifest.exists() else []
    checksum_lines = count_lines(checksums)
    add(
        rows,
        "deposit_manifest_row_floor",
        "repository deposit provenance",
        "Deposit manifest contains the stable package files and any newer provenance artifacts.",
        len(manifest_rows) >= 223,
        f"manifest_rows={len(manifest_rows)}",
        manifest.relative_to(ROOT).as_posix(),
        "repository deposit manifest",
        "Local manifest does not replace DOI-backed repository publication.",
    )
    add(
        rows,
        "deposit_checksum_alignment",
        "repository deposit provenance",
        "Checksum file has one non-empty line per deposit manifest row.",
        checksum_lines == len(manifest_rows) and checksum_lines >= 223,
        f"manifest_rows={len(manifest_rows)}; checksum_lines={checksum_lines}",
        checksums.relative_to(ROOT).as_posix(),
        "repository deposit checksum file",
        "Checksum alignment is local and does not mint or reserve a DOI.",
    )
    deposit_texts = {
        "datacite": text(PACKAGE / "datacite_metadata_draft_20260603.yaml"),
        "readme": text(PACKAGE / "repository_readme_draft_20260603.md"),
        "report": text(PACKAGE / "repository_deposit_readiness_report_20260603.md"),
    }
    deposit_terms = ["TBD DOI or accession", "DOI-ready draft", "not yet a public", "completed physical-robot validation data"]
    joined_deposit = "\n".join(deposit_texts.values())
    missing_deposit = [term for term in deposit_terms if term not in joined_deposit]
    add(
        rows,
        "deposit_boundary_terms",
        "repository deposit provenance",
        "Deposit metadata exposes DOI, licence, public-record, and physical-data boundaries.",
        not missing_deposit,
        "missing=" + ("; ".join(missing_deposit) if missing_deposit else "none"),
        "06_submission_package/datacite_metadata_draft_20260603.yaml; repository_readme_draft_20260603.md; repository_deposit_readiness_report_20260603.md",
        "repository deposit metadata drafts",
        "Repository deposit metadata remains a draft until a public DOI/accession is minted.",
    )

    commands = PACKAGE / "reproducibility_command_manifest_20260604.csv"
    command_rows = read_csv(commands) if commands.exists() else []
    add(
        rows,
        "reproducibility_command_manifest_rows",
        "reproducibility provenance",
        "Command manifest includes the current regeneration, audit, deposit, and verification commands.",
        len(command_rows) >= 30,
        f"command_rows={len(command_rows)}",
        commands.relative_to(ROOT).as_posix(),
        "reproducibility command manifest",
        "Command manifest is a local replay guide; it does not rerun CARLA or physical robots.",
    )
    capsule = PACKAGE / "reproducibility_capsule_20260604.md"
    capsule_terms = ["does not rerun CARLA", "does not prove ROS2 launch/build success", "does not replace a public DOI-backed repository record"]
    capsule_text = text(capsule) if capsule.exists() else ""
    missing_capsule = [term for term in capsule_terms if term not in capsule_text]
    add(
        rows,
        "reproducibility_capsule_boundaries",
        "reproducibility provenance",
        "Reproducibility capsule states raw-CARLA, ROS2, and DOI boundaries.",
        not missing_capsule,
        "missing=" + ("; ".join(missing_capsule) if missing_capsule else "none"),
        capsule.relative_to(ROOT).as_posix(),
        "reproducibility capsule",
        "Capsule boundaries prevent using local audit artifacts as physical validation.",
    )

    package_manifest = PACKAGE / "extended_package_manifest_20260603.md"
    manifest_terms = [
        "source_data_provenance_audit.csv",
        "source_data_provenance_audit_report_20260604.md",
        "Source-data provenance audit",
        "simulation_protocol_registry.csv",
        "simulation_protocol_registry_report_20260604.md",
        "Simulation protocol registry",
        "real_robot_preflight_validation.csv",
        "real_robot_preflight_validation_report_20260604.md",
        "real_robot_offline_dryrun_trace.csv",
        "real_robot_offline_dryrun_summary.csv",
        "real_robot_offline_dryrun_report_20260604.md",
        "real_robot_software_smoke_test.csv",
        "real_robot_software_smoke_test_report_20260604.md",
        "ros2_workspace_ci_manifest.yaml",
        "run_ros2_workspace_preflight.sh",
        "test_core_contracts.py",
        "generate_ros2_workspace_ci_audit.py",
        "ros2_workspace_ci_audit.csv",
        "ros2_workspace_ci_audit_report_20260604.md",
        "ros2_runtime_telemetry_schema.csv",
        "runtime_telemetry_manifest_template.yaml",
        "generate_ros2_runtime_telemetry_audit.py",
        "ros2_runtime_telemetry_audit.csv",
        "ros2_runtime_telemetry_audit_report_20260604.md",
        "generate_ros2_runtime_telemetry_dryrun.py",
        "ros2_runtime_telemetry_dryrun_trace.csv",
        "ros2_runtime_telemetry_dryrun_summary.csv",
        "ros2_runtime_telemetry_dryrun_report_20260604.md",
        "safety_case_claim_graph.csv",
        "table_safety_case_claim_graph.tex",
        "generate_safety_case_audit.py",
        "safety_case_audit_report_20260604.md",
        "generate_safety_case_figure.py",
        "fig_safety_case_evidence_map_source.csv",
        "fig_safety_case_evidence_map",
        "generate_evidence_coverage_matrix.py",
        "fig_evidence_coverage_matrix_source.csv",
        "fig_evidence_coverage_matrix",
        "hil_replay_manifest_template.yaml",
        "ros2_hil_replay_manifest_audit.csv",
        "ros2_hil_replay_manifest_audit_report_20260604.md",
        "fig13_offline_dryrun_contract_timeline_v2_source_data.csv",
        "fig13_offline_dryrun_contract_timeline_v2",
        "pre_real_robot_gate_audit.csv",
        "table_pre_real_robot_gate_audit.tex",
        "pre_real_robot_gate_audit_report_20260604.md",
    ]
    package_manifest_text = text(package_manifest) if package_manifest.exists() else ""
    missing_package_terms = [term for term in manifest_terms if term not in package_manifest_text]
    add(
        rows,
        "extended_package_manifest_mentions_provenance",
        "package manifest provenance",
        "Extended package manifest lists the source-data provenance audit artifacts.",
        not missing_package_terms,
        "missing=" + ("; ".join(missing_package_terms) if missing_package_terms else "none"),
        package_manifest.relative_to(ROOT).as_posix(),
        "extended package manifest",
        "Package manifest listing is an inventory control, not a scientific result.",
    )

    failed = [row for row in rows if row.status != "PASS"]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AuditRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])

    report_lines = [
        "# Source Data Provenance Audit Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"The source-data provenance audit checks {len(rows)} source inventory, figure-to-source-data mapping, table-to-source-data mapping, FAIR metadata, deposit, and reproducibility gates.",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All audited source-data provenance checks passed." if not failed else "One or more source-data provenance checks failed.",
        "",
        "## Mapping Coverage",
        "",
        "- figure-to-source-data mapping: ten publication figures are linked to their CSV source files and generator scripts.",
        "- table-to-source-data mapping: all generated manuscript table bodies are linked to their processed source-data CSVs.",
        "- audit-to-source mapping: statistical, manuscript-argument, safety-case claim graph, ROS2 static-interface, ROS2 workspace CI, ROS2 runtime telemetry, runtime telemetry parser dry-run, software-smoke, HIL replay, offline dry-run, pre-real-robot gate, publication-figure, and accessibility QA outputs are included in source data.",
        "- deposit mapping: repository manifest, checksums, DataCite draft, README draft, and readiness report remain tied to local artifacts.",
        "",
        "## Boundary",
        "",
        "This audit is a local provenance and drift-control layer. It does not prove raw CARLA rerun reproducibility, does not replace DOI-backed repository publication, and does not contain completed physical robot trial data.",
    ]
    if failed:
        report_lines.extend(["", "## Failed Checks", ""])
        for row in failed:
            report_lines.append(f"- `{row.audit_id}`: {row.evidence}")

    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")
    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
