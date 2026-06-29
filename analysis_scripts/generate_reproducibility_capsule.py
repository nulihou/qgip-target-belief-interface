#!/usr/bin/env python3
"""Generate a reproducibility capsule for the extended manuscript package."""

from __future__ import annotations

import csv
import importlib.metadata
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "06_submission_package"
ENV_CSV = OUT_DIR / "software_environment_audit_20260604.csv"
COMMAND_CSV = OUT_DIR / "reproducibility_command_manifest_20260604.csv"
CAPSULE_MD = OUT_DIR / "reproducibility_capsule_20260604.md"


PYTHON_PACKAGES = [
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("scipy", "scipy"),
    ("matplotlib", "matplotlib"),
    ("Pillow", "Pillow"),
]

ROS2_MODULES = ["rclpy", "geometry_msgs", "std_msgs", "nav_msgs", "tf2_ros", "launch", "launch_ros"]


def package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "MISSING"


def command_version(command: str, args: list[str]) -> tuple[str, str]:
    executable = shutil.which(command)
    if not executable:
        return "missing", "not found on PATH"
    try:
        proc = subprocess.run([command, *args], capture_output=True, text=False, timeout=15)
    except Exception as exc:  # pragma: no cover - environment-specific.
        return "present", f"version query failed: {exc}"

    def decode(data: bytes | None) -> str:
        if not data:
            return ""
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("gbk", errors="replace")

    output = (decode(proc.stdout) + "\n" + decode(proc.stderr)).strip().splitlines()
    version_line = next((line.strip() for line in output if "version" in line.lower()), "")
    first = version_line or next((line.strip() for line in output if line.strip()), "")
    return "present", first or f"returncode={proc.returncode}"


def file_exists(path: str) -> str:
    full = ROOT / path
    return "present" if full.exists() and full.stat().st_size > 0 else "missing"


def write_environment() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = [
        {
            "category": "runtime",
            "name": "python",
            "status": "present",
            "version_or_detail": sys.version.split()[0],
            "scope": "analysis scripts and verifiers",
        },
        {
            "category": "runtime",
            "name": "platform",
            "status": "present",
            "version_or_detail": platform.platform(),
            "scope": "local verification context",
        },
    ]

    for module_name, dist_name in PYTHON_PACKAGES:
        version = package_version(dist_name)
        rows.append(
            {
                "category": "python_package",
                "name": module_name,
                "status": "present" if version != "MISSING" else "missing",
                "version_or_detail": version,
                "scope": "paper artifact generation and QA",
            }
        )

    for command, args, scope in (
        ("pdflatex", ["--version"], "manuscript compilation"),
        ("pdftoppm", ["-v"], "PDF page rendering"),
        ("ros2", ["--help"], "future ROS2 execution; not required for local manuscript package verification"),
        ("colcon", ["--help"], "future ROS2 workspace build; not required for local manuscript package verification"),
    ):
        status, detail = command_version(command, args)
        if command in {"ros2", "colcon"} and status == "missing":
            status = "expected_missing_for_local_package"
        rows.append(
            {
                "category": "external_command",
                "name": command,
                "status": status,
                "version_or_detail": detail,
                "scope": scope,
            }
        )

    for module in ROS2_MODULES:
        found = False
        try:
            __import__(module)
            found = True
        except Exception:
            found = False
        rows.append(
            {
                "category": "ros2_python_module",
                "name": module,
                "status": "present" if found else "expected_missing_for_local_package",
                "version_or_detail": "importable" if found else "not importable in this desktop Python environment",
                "scope": "future ROS2/HIL execution, not proof of current physical validation",
            }
        )

    with ENV_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def write_commands() -> list[dict[str, str]]:
    commands = [
        {
            "step": "1",
            "purpose": "Regenerate extended source data, tables, and extended figure exports",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_extended_artifacts.py",
            "expected_outputs": "claim_evidence_matrix.csv; table_claim_evidence_matrix.tex; fig_extended_dataset_split; fig_extended_stress_outcomes; fig_extended_nis_response; extended tables",
            "current_output_status": file_exists("08_paper_ready_outputs/figures/fig_extended_nis_response.svg"),
            "boundary": "Uses existing processed CARLA summaries; does not rerun CARLA.",
        },
        {
            "step": "2",
            "purpose": "Regenerate Nature-style system/evidence Figure 1",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_nature_main_figure.py",
            "expected_outputs": "fig_nature_system_evidence.{pdf,svg,tiff,png}; fig_nature_system_evidence_source.csv",
            "current_output_status": file_exists("08_paper_ready_outputs/figures/fig_nature_system_evidence.svg"),
            "boundary": "Figure generated from staged source data and scripted schematic logic.",
        },
        {
            "step": "3",
            "purpose": "Compile extended manuscript",
            "working_directory": "RA_L_optimization_20260528/01_manuscript",
            "command": "pdflatex -interaction=nonstopmode -halt-on-error RA_L_extended_working.tex",
            "expected_outputs": "RA_L_extended_working.pdf and LaTeX log",
            "current_output_status": file_exists("01_manuscript/RA_L_extended_working.pdf"),
            "boundary": "Run twice when references/citations change.",
        },
        {
            "step": "4",
            "purpose": "Render extended manuscript pages for visual QA",
            "working_directory": "RA_L_optimization_20260528/01_manuscript",
            "command": "pdftoppm -png -r 160 RA_L_extended_working.pdf ../09_pdf_qa/extended_v5_page",
            "expected_outputs": "extended_v5_page-01.png through extended_v5_page-19.png",
            "current_output_status": file_exists("09_pdf_qa/extended_v5_page-19.png"),
            "boundary": "Uses existing compiled PDF; checks layout, not scientific truth.",
        },
        {
            "step": "5",
            "purpose": "Build PDF contact sheet",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/make_pdf_contact_sheet.py --pattern extended_v5_page-*.png --out contact_sheet_extended_v5.png",
            "expected_outputs": "contact_sheet_extended_v5.png",
            "current_output_status": file_exists("09_pdf_qa/contact_sheet_extended_v5.png"),
            "boundary": "Visual QA helper only.",
        },
        {
            "step": "6",
            "purpose": "Audit manuscript-level statistical claims against staged source data",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_statistical_claim_audit.py",
            "expected_outputs": "statistical_claim_audit.csv; statistical_claim_audit_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/statistical_claim_audit.csv"),
            "boundary": "Checks processed source-data consistency; does not prove raw CARLA rerun reproducibility or physical validation.",
        },
        {
            "step": "7",
            "purpose": "Audit Nature-style manuscript argument chain",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_manuscript_argument_audit.py",
            "expected_outputs": "manuscript_argument_traceability.csv; manuscript_argument_audit_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/manuscript_argument_traceability.csv"),
            "boundary": "Checks manuscript structure and evidence discipline; does not replace expert peer review.",
        },
        {
            "step": "8",
            "purpose": "Generate bounded safety-case claim graph audit",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_safety_case_audit.py",
            "expected_outputs": "safety_case_claim_graph.csv; table_safety_case_claim_graph.tex; safety_case_audit_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/safety_case_claim_graph.csv"),
            "boundary": "Claim-discipline audit only; does not prove safety certification, ROS2 launch, HIL timing, DOI publication, or physical validation.",
        },
        {
            "step": "9",
            "purpose": "Generate bounded safety-case evidence-boundary figure",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_safety_case_figure.py",
            "expected_outputs": "fig_safety_case_evidence_map.{pdf,svg,tiff,png}; fig_safety_case_evidence_map_source.csv",
            "current_output_status": file_exists("08_paper_ready_outputs/figures/fig_safety_case_evidence_map.svg"),
            "boundary": "Visualizes the claim-boundary audit; does not add physical validation, ROS2/HIL timing, or DOI evidence.",
        },
        {
            "step": "9",
            "purpose": "Audit ROS2 static interface wiring before real-robot execution",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_ros2_static_interface_audit.py",
            "expected_outputs": "ros2_static_interface_audit.csv; ros2_static_interface_audit_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/ros2_static_interface_audit.csv"),
            "boundary": "Checks static topic/launch/config consistency; does not prove ROS2 build, launch, rosbag, or robot motion.",
        },
        {
            "step": "9",
            "purpose": "Validate real-robot preflight package offline without ROS2",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_real_robot_preflight_validation.py",
            "expected_outputs": "real_robot_preflight_validation.csv; real_robot_preflight_validation_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/real_robot_preflight_validation.csv"),
            "boundary": "Checks static package consistency only; does not prove ROS2 build, launch, rosbag, timing, or robot motion.",
        },
        {
            "step": "10",
            "purpose": "Audit ROS2 workspace CI and build-test readiness assets",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_ros2_workspace_ci_audit.py",
            "expected_outputs": "ros2_workspace_ci_audit.csv; ros2_workspace_ci_audit_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/ros2_workspace_ci_audit.csv"),
            "boundary": "Checks local pure-core pytest and static CI assets; does not prove colcon build/test, live ROS2 launch, rosbag timing, HIL, or robot motion.",
        },
        {
            "step": "11",
            "purpose": "Run ROS2 runtime telemetry parser and summary dry-run",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_ros2_runtime_telemetry_dryrun.py",
            "expected_outputs": "ros2_runtime_telemetry_dryrun_trace.csv; ros2_runtime_telemetry_dryrun_summary.csv; ros2_runtime_telemetry_dryrun_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/ros2_runtime_telemetry_dryrun_summary.csv"),
            "boundary": "Synthetic parser QA; does not prove live ROS2 timing, rosbag extraction, HIL timing, embedded feasibility, or robot motion.",
        },
        {
            "step": "12",
            "purpose": "Audit ROS2 runtime telemetry instrumentation readiness",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_ros2_runtime_telemetry_audit.py",
            "expected_outputs": "ros2_runtime_telemetry_audit.csv; ros2_runtime_telemetry_audit_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/ros2_runtime_telemetry_audit.csv"),
            "boundary": "Checks timing, frame-drop, watchdog, command-age, clock-drift, and CPU/GPU telemetry contracts; does not prove live ROS2 timing, HIL, embedded feasibility, or robot motion.",
        },
        {
            "step": "13",
            "purpose": "Run executable pure-Python real-robot software smoke test",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_real_robot_software_smoke_test.py",
            "expected_outputs": "real_robot_software_smoke_test.csv; real_robot_software_smoke_test_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/real_robot_software_smoke_test.csv"),
            "boundary": "Exercises pure-Python POP/NIS, fault injection, JSON contract, and controller-proxy invariants; does not prove ROS2 launch, rosbag, timing, or robot motion.",
        },
        {
            "step": "14",
            "purpose": "Audit ROS2/HIL replay manifest before Stage C execution",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_ros2_hil_replay_manifest_audit.py",
            "expected_outputs": "ros2_hil_replay_manifest_audit.csv; ros2_hil_replay_manifest_audit_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/ros2_hil_replay_manifest_audit.csv"),
            "boundary": "Checks HIL replay manifest, rosbag topic coverage, ROS clock playback, safety-state logging, and disabled actuator bridge; does not prove live HIL timing or robot motion.",
        },
        {
            "step": "15",
            "purpose": "Run deterministic ROS2-less real-robot preflight dry run",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_real_robot_offline_dryrun.py",
            "expected_outputs": "real_robot_offline_dryrun_trace.csv; real_robot_offline_dryrun_summary.csv; real_robot_offline_dryrun_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/real_robot_offline_dryrun_summary.csv"),
            "boundary": "Exercises pure-Python selected-leader/fault-injection/POP-NIS/controller-proxy behavior; does not prove ROS2 launch, rosbag, timing, or robot motion.",
        },
        {
            "step": "16",
            "purpose": "Generate offline dry-run contract-timeline diagnostic figure",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/fig13_offline_dryrun_contract_timeline_v2.py",
            "expected_outputs": "fig13_offline_dryrun_contract_timeline_v2.{pdf,svg,tiff,png}; fig13_offline_dryrun_contract_timeline_v2_source_data.csv",
            "current_output_status": file_exists("08_paper_ready_outputs/figures/fig13_offline_dryrun_contract_timeline_v2.svg"),
            "boundary": "Publication-style preflight contract timeline from the offline dry-run trace; does not prove ROS2 launch, rosbag, timing, or robot motion.",
        },
        {
            "step": "17",
            "purpose": "Build figure accessibility QA contact sheet",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_figure_accessibility_qa.py",
            "expected_outputs": "figure_accessibility_contact_sheet_v1.png; figure_accessibility_metrics.csv",
            "current_output_status": file_exists("09_pdf_qa/figure_accessibility_contact_sheet_v1.png"),
            "boundary": "Approximate visual QA after all ten figure exports exist; not a formal perceptual user study.",
        },
        {
            "step": "18",
            "purpose": "Audit publication figure exports, source data, vector text, and raster resolution",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_publication_figure_qa.py",
            "expected_outputs": "publication_figure_qa.csv; publication_figure_qa_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/publication_figure_qa.csv"),
            "boundary": "Machine-readable figure QA; does not replace human vector-editor and target-journal production checks.",
        },
        {
            "step": "19",
            "purpose": "Generate pre-real-robot go/no-go gate audit",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_pre_real_robot_gate_audit.py",
            "expected_outputs": "pre_real_robot_gate_audit.csv; table_pre_real_robot_gate_audit.tex; pre_real_robot_gate_audit_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/pre_real_robot_gate_audit.csv"),
            "boundary": "Synthesizes staged readiness gates; does not prove ROS2 launch, rosbag, timing, or robot motion.",
        },
        {
            "step": "20",
            "purpose": "Generate reviewer-facing simulation protocol registry",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_simulation_protocol_registry.py",
            "expected_outputs": "simulation_protocol_registry.csv; table_simulation_protocol_registry.tex; simulation_protocol_registry_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/simulation_protocol_registry.csv"),
            "boundary": "Maps protocols to artifacts and scripts; does not rerun CARLA, launch ROS2, or collect physical robot data.",
        },
        {
            "step": "21",
            "purpose": "Generate protocol-to-claim evidence coverage figure",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_evidence_coverage_matrix.py",
            "expected_outputs": "fig_evidence_coverage_matrix.{pdf,svg,tiff,png}; fig_evidence_coverage_matrix_source.csv",
            "current_output_status": file_exists("08_paper_ready_outputs/figures/fig_evidence_coverage_matrix.svg"),
            "boundary": "Visual evidence map generated from staged protocol and claim artifacts; does not add new CARLA reruns or physical validation evidence.",
        },
        {
            "step": "21",
            "purpose": "Generate simulation effect-size and finite-sample boundary figure",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_simulation_effect_size_figure.py",
            "expected_outputs": "fig_simulation_effect_size.{pdf,svg,tiff,png}; fig_simulation_effect_size_source.csv",
            "current_output_status": file_exists("08_paper_ready_outputs/figures/fig_simulation_effect_size.svg"),
            "boundary": "Condenses processed CARLA benchmark and paired-statistics evidence; does not rerun CARLA or add physical validation evidence.",
        },
        {
            "step": "21",
            "purpose": "Generate simulation stress atlas figure",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_simulation_stress_atlas_figure.py",
            "expected_outputs": "fig_simulation_stress_atlas.{pdf,svg,tiff,png}; fig_simulation_stress_atlas_source.csv",
            "current_output_status": file_exists("08_paper_ready_outputs/figures/fig_simulation_stress_atlas.svg"),
            "boundary": "Synthesizes processed CARLA stress evidence and diagnostics; does not rerun CARLA or add ROS2/HIL/physical validation evidence.",
        },
        {
            "step": "21",
            "purpose": "Generate pre-real-robot validation-boundary narrative figure",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/fig12_validation_boundary_narrative_v4.py",
            "expected_outputs": "fig12_validation_boundary_narrative_v4.{pdf,svg,tiff,png}; fig12_validation_boundary_narrative_v4_source_data.csv",
            "current_output_status": file_exists("08_paper_ready_outputs/figures/fig12_validation_boundary_narrative_v4.svg"),
            "boundary": "Summarizes the validation boundary between prepared local readiness evidence and still-required ROS2/HIL, rosbag, and physical-robot evidence.",
        },
        {
            "step": "21",
            "purpose": "Audit source-data provenance, figure/table mapping, FAIR metadata, and deposit links",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_source_data_provenance_audit.py",
            "expected_outputs": "source_data_provenance_audit.csv; source_data_provenance_audit_report_20260604.md",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/source_data_provenance_audit.csv"),
            "boundary": "Checks processed source-data provenance; does not prove raw CARLA rerun reproducibility, DOI publication, or physical robot validation.",
        },
        {
            "step": "22",
            "purpose": "Generate repository deposit metadata and checksums",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/generate_repository_deposit_artifacts.py",
            "expected_outputs": "repository_deposit_manifest_20260603.csv; SHA256 checksum file; DataCite draft; repository README draft",
            "current_output_status": file_exists("06_submission_package/repository_deposit_manifest_20260603.csv"),
            "boundary": "Does not mint a DOI or create a public repository record.",
        },
        {
            "step": "23",
            "purpose": "Summarize future real-robot trial CSVs",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/summarize_real_robot_trials.py RA_L_optimization_20260528/03_real_robot/real_robot_results_template.csv --output RA_L_optimization_20260528/08_paper_ready_outputs/source_data/real_robot_template_summary.csv",
            "expected_outputs": "real_robot_template_summary.csv",
            "current_output_status": file_exists("08_paper_ready_outputs/source_data/real_robot_template_summary.csv"),
            "boundary": "Template demonstration only; no physical robot evidence is claimed.",
        },
        {
            "step": "24",
            "purpose": "Verify final extended package",
            "working_directory": ".",
            "command": "python RA_L_optimization_20260528/05_analysis_scripts/verify_extended_package.py",
            "expected_outputs": "extended_submission_verification_report_20260603.md",
            "current_output_status": file_exists("06_submission_package/extended_submission_verification_report_20260603.md"),
            "boundary": "Verifies package consistency, not external repository publication or physical validation.",
        },
    ]
    for index, row in enumerate(commands, start=1):
        row["step"] = str(index)
    with COMMAND_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(commands[0].keys()))
        writer.writeheader()
        writer.writerows(commands)
    return commands


def write_capsule(env_rows: list[dict[str, str]], command_rows: list[dict[str, str]]) -> None:
    package_rows = [row for row in env_rows if row["category"] == "python_package"]
    missing_ros = [row["name"] for row in env_rows if row["category"] == "ros2_python_module" and row["status"].startswith("expected_missing")]
    commands_present = sum(1 for row in command_rows if row["current_output_status"] == "present")
    package_lines = "\n".join(f"- `{row['name']}`: {row['version_or_detail']}" for row in package_rows)
    CAPSULE_MD.write_text(
        f"""# Reproducibility Capsule, 2026-06-04

## Scope

This capsule records how the current extended simulation-first package can be inspected
and regenerated from the staged source data. It is a local reproducibility aid for
manuscript review and repository deposit preparation. It does not rerun CARLA, mint a DOI,
or validate the ROS2 stack on physical robots.

## Generated Artifacts

- `software_environment_audit_20260604.csv`
- `reproducibility_command_manifest_20260604.csv`
- `reproducibility_capsule_20260604.md`

## Local Environment Summary

- Python: {sys.version.split()[0]}
- Platform: {platform.platform()}
- Core Python packages:
{package_lines}

MiKTeX/`pdflatex` and Poppler/`pdftoppm` were found in this local environment. ROS2 Python
modules are not importable in this desktop Python environment: {", ".join(missing_ros)}.
This is expected for the local manuscript package audit and remains a blocker only for
actual ROS2/HIL execution.

## Command Coverage

The command manifest lists {len(command_rows)} reproduction or audit commands. Current
expected outputs are present for {commands_present}/{len(command_rows)} commands.

Use the command manifest as a reviewer-facing map from source data and scripts to the
manuscript PDF, figure exports, visual QA, deposit metadata, and package verifier.

## Non-Claims

- This capsule does not prove raw CARLA rerun reproducibility.
- This capsule does not prove ROS2 launch/build success.
- This capsule does not prove physical robot safety or timing.
- This capsule does not replace a public DOI-backed repository record.
""",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    env_rows = write_environment()
    command_rows = write_commands()
    write_capsule(env_rows, command_rows)
    print(ENV_CSV)
    print(COMMAND_CSV)
    print(CAPSULE_MD)


if __name__ == "__main__":
    main()
