#!/usr/bin/env python3
"""Generate DOI-ready repository deposit metadata from the local package.

The generated files are drafts for a public repository record. They deliberately keep
repository, DOI, creator, licence, and funding fields as TBD where the author or
institution must make the final decision.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "06_submission_package"

MANIFEST = OUT_DIR / "repository_deposit_manifest_20260603.csv"
CHECKSUMS = OUT_DIR / "repository_deposit_checksums_sha256_20260603.txt"
DATACITE = OUT_DIR / "datacite_metadata_draft_20260603.yaml"
README = OUT_DIR / "repository_readme_draft_20260603.md"
REPORT = OUT_DIR / "repository_deposit_readiness_report_20260603.md"

INCLUDE_FILES = [
    "01_manuscript/RA_L_extended_working.pdf",
    "01_manuscript/RA_L_extended_working.tex",
    "01_manuscript/RA_L_main_working.pdf",
    "01_manuscript/RA_L_main_working.tex",
    "01_manuscript/RA_L_supplemental_simulation_results.pdf",
    "01_manuscript/RA_L_supplemental_simulation_results.tex",
]

INCLUDE_DIRS = [
    "03_real_robot",
    "05_analysis_scripts",
    "08_paper_ready_outputs/figures",
    "08_paper_ready_outputs/source_data",
    "08_paper_ready_outputs/tables",
]

INCLUDE_PACKAGE_DOCS = [
    "data_code_availability_statement.md",
    "extended_nature_figure_qa_report_20260603.md",
    "extended_package_manifest_20260603.md",
    "figure_accessibility_qa_report_20260603.md",
    "full_goal_completion_audit_20260603.md",
    "nature_data_availability_plan_20260603.md",
    "pre_real_robot_completion_audit_20260603.md",
    "pre_real_robot_validation_protocol_20260603.md",
    "real_robot_preflight_readiness_report_20260603.md",
    "real_robot_preflight_validation_report_20260604.md",
    "real_robot_software_smoke_test_report_20260604.md",
    "real_robot_offline_dryrun_report_20260604.md",
    "ros2_workspace_ci_audit_report_20260604.md",
    "ros2_runtime_telemetry_audit_report_20260604.md",
    "ros2_runtime_telemetry_dryrun_report_20260604.md",
    "pre_real_robot_gate_audit_report_20260604.md",
    "reproducibility_capsule_20260604.md",
    "reproducibility_command_manifest_20260604.csv",
    "software_environment_audit_20260604.csv",
    "simulation_protocol_registry_report_20260604.md",
    "statistical_claim_audit_report_20260604.md",
    "manuscript_argument_audit_report_20260604.md",
    "safety_case_audit_report_20260604.md",
    "ros2_static_interface_audit_report_20260604.md",
    "ros2_hil_replay_manifest_audit_report_20260604.md",
    "publication_figure_qa_report_20260604.md",
    "source_data_provenance_audit_report_20260604.md",
    "reviewer_risk_response_matrix_20260603.md",
]

INCLUDE_QA = [
    "09_pdf_qa/contact_sheet_extended_v5.png",
    "09_pdf_qa/figure_accessibility_contact_sheet_v1.png",
]

EXCLUDE_PARTS = {"__pycache__"}
EXCLUDE_SUFFIXES = {".pyc", ".aux", ".log", ".out", ".bbl", ".blg", ".synctex", ".fls", ".fdb_latexmk"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def should_include(path: Path) -> bool:
    rel_parts = path.relative_to(ROOT).parts
    if any(part in EXCLUDE_PARTS for part in rel_parts):
        return False
    if path.suffix.lower() in EXCLUDE_SUFFIXES:
        return False
    return path.is_file()


def role_for(rel: str) -> str:
    if rel.startswith("01_manuscript/"):
        return "manuscript"
    if rel.startswith("03_real_robot/"):
        return "real_robot_preflight_protocol"
    if rel.startswith("05_analysis_scripts/"):
        return "analysis_or_verification_code"
    if rel.startswith("08_paper_ready_outputs/source_data/"):
        return "processed_source_data"
    if rel.startswith("08_paper_ready_outputs/figures/"):
        return "publication_figure_export"
    if rel.startswith("08_paper_ready_outputs/tables/"):
        return "generated_table"
    if rel.startswith("09_pdf_qa/"):
        return "visual_qa"
    if rel.startswith("06_submission_package/"):
        return "submission_documentation"
    return "supporting_file"


def supports_for(rel: str) -> str:
    if "source_data" in rel:
        return "simulation claims; figure source data; table source data"
    if "real_robot" in rel or "03_real_robot" in rel or "ros2" in rel.lower():
        return "pre-real-robot validation readiness"
    if "figure" in rel or rel.endswith((".pdf", ".svg", ".tiff", ".png")):
        return "figure reproduction and QA"
    if "verify" in rel or "audit" in rel or "readiness" in rel:
        return "reproducibility and claim-boundary audit"
    if rel.startswith("01_manuscript/"):
        return "manuscript snapshot"
    return "supporting reproducibility"


def access_route_for(rel: str) -> str:
    if rel.startswith("03_real_robot/"):
        return "public repository after DOI deposit; no physical run data included"
    if rel.startswith("08_paper_ready_outputs/source_data/"):
        return "public repository after DOI deposit"
    if rel.startswith("05_analysis_scripts/"):
        return "public repository after DOI deposit, subject to software licence"
    return "public repository after DOI deposit"


def collect_files() -> list[Path]:
    files: list[Path] = []
    for item in INCLUDE_FILES:
        path = ROOT / item
        if path.exists() and should_include(path):
            files.append(path)
    for directory in INCLUDE_DIRS:
        base = ROOT / directory
        if not base.exists():
            continue
        files.extend(path for path in base.rglob("*") if should_include(path))
    for item in INCLUDE_PACKAGE_DOCS:
        path = OUT_DIR / item
        if path.exists() and should_include(path):
            files.append(path)
    for item in INCLUDE_QA:
        path = ROOT / item
        if path.exists() and should_include(path):
            files.append(path)
    return sorted(set(files), key=lambda p: p.relative_to(ROOT).as_posix())


def write_manifest(files: list[Path]) -> list[dict[str, str]]:
    rows = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        rows.append(
            {
                "relative_path": rel,
                "role": role_for(rel),
                "file_format": path.suffix.lower().lstrip(".") or "none",
                "size_bytes": str(path.stat().st_size),
                "sha256": sha256(path),
                "supports": supports_for(rel),
                "access_route": access_route_for(rel),
                "notes": "Generated local file; repository identifier remains TBD.",
            }
        )
    with MANIFEST.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with CHECKSUMS.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(f"{row['sha256']}  {row['relative_path']}\n")
    return rows


def write_datacite(rows: list[dict[str, str]]) -> None:
    DATACITE.write_text(
        f"""# DataCite-style metadata draft for repository deposit
# Do not treat this file as a minted DOI record. Replace all TBD fields after deposit.
identifier:
  identifier: "TBD DOI or accession"
  identifierType: "DOI"
creators:
  - name: "TBD author list"
    nameType: "Personal"
titles:
  - title: "QGIP-Net simulation-first source data, figures, analysis scripts, and ROS2 preflight templates"
publisher: "TBD repository"
publicationYear: "{date.today().year}"
resourceType:
  resourceTypeGeneral: "Dataset"
  resourceType: "Processed simulation source data and analysis code"
version: "2026-06-03-extended-v29-draft"
language: "en"
subjects:
  - "autonomous driving"
  - "vehicle following"
  - "CARLA simulation"
  - "NIS-gated Kalman filtering"
  - "model predictive control"
  - "ROS2 preflight validation"
descriptions:
  - descriptionType: "Abstract"
    description: >
      This draft repository package contains processed CARLA source data, figure
      source data, generated manuscript tables, publication figure exports, analysis
      and verification scripts, and ROS2/physical-validation preflight templates for
      the QGIP-Net simulation-first manuscript. The package supports bounded
      simulation claims and does not contain completed physical-robot trial data.
rightsList:
  - rights: "TBD data licence"
    rightsUri: "TBD"
  - rights: "TBD software licence"
    rightsUri: "TBD"
relatedIdentifiers:
  - relatedIdentifier: "TBD manuscript DOI or preprint URL"
    relatedIdentifierType: "DOI"
    relationType: "IsSupplementTo"
  - relatedIdentifier: "TBD code repository URL"
    relatedIdentifierType: "URL"
    relationType: "IsSupplementedBy"
formats:
  - "CSV"
  - "Markdown"
  - "Python"
  - "TeX"
  - "PDF"
  - "SVG"
  - "TIFF"
  - "PNG"
  - "YAML"
sizes:
  - "{len(rows)} files listed in repository_deposit_manifest_20260603.csv"
fundingReferences:
  - funderName: "TBD"
    awardNumber: "TBD"
""",
        encoding="utf-8",
        newline="\n",
    )


def write_readme(rows: list[dict[str, str]]) -> None:
    role_counts: dict[str, int] = {}
    for row in rows:
        role_counts[row["role"]] = role_counts.get(row["role"], 0) + 1
    role_lines = "\n".join(f"- `{role}`: {count} files" for role, count in sorted(role_counts.items()))
    README.write_text(
        f"""# QGIP-Net Simulation-First Repository Deposit Draft

This directory is a DOI-ready draft for depositing the processed source data, analysis
scripts, figure exports, QA artifacts, and ROS2 preflight templates associated with the
QGIP-Net simulation-first manuscript.

## Scope

The deposit supports the bounded claim that QGIP-Net improves target consistency under
tested CARLA ambiguity stress while preserving an inspectable conservative safety layer.
It does not contain completed physical-robot validation data and must not be cited as
evidence of real-world deployment safety.

## Inventory

The full file list, roles, sizes, and SHA256 hashes are in
`repository_deposit_manifest_20260603.csv`. The same hashes are provided in
`repository_deposit_checksums_sha256_20260603.txt`.

Role summary:

{role_lines}

## Main Contents

- `01_manuscript/`: manuscript snapshot used for the deposit.
- `03_real_robot/`: ROS2 preflight templates and package skeleton; no completed robot run data.
- `05_analysis_scripts/`: analysis, figure-generation, verification, and deposit-generation scripts.
- `08_paper_ready_outputs/source_data/`: processed CSV/Markdown source data supporting figures and tables.
- `08_paper_ready_outputs/figures/`: PDF/SVG/TIFF/PNG figure exports.
- `08_paper_ready_outputs/tables/`: generated table bodies.
- `09_pdf_qa/`: page and figure QA contact sheets.
- `06_submission_package/`: availability statements, audits, verification reports, and protocol notes.

## Reuse Notes

Use the processed source-data CSVs and scripts to inspect the manuscript figures and
tables. Raw CARLA logs and simulator assets should be deposited only if the relevant
licences allow redistribution. Physical ROS2/robot data should be added only after
actual runs produce bags, manifests, per-frame CSVs, metric summaries, and incident
reports.

## Required Before Public Release

- Replace `TBD repository`, DOI/accession, author, funding, and licence fields.
- Confirm whether raw CARLA logs may be redistributed.
- Add a repository-generated DOI or accession.
- Add a private reviewer link if submitting before public release.
- Confirm data and software licences with the author or institution.
""",
        encoding="utf-8",
        newline="\n",
    )


def write_report(rows: list[dict[str, str]]) -> None:
    total_size = sum(int(row["size_bytes"]) for row in rows)
    REPORT.write_text(
        f"""# Repository Deposit Readiness Report, 2026-06-03

## Decision

The local package is DOI-ready as a draft deposit bundle, but it is not yet a public
archival record. A repository, persistent identifier, licence, author metadata, and
reviewer link remain TBD.

## Generated Artifacts

- `repository_deposit_manifest_20260603.csv`
- `repository_deposit_checksums_sha256_20260603.txt`
- `datacite_metadata_draft_20260603.yaml`
- `repository_readme_draft_20260603.md`

## Audit Summary

- Manifest rows: {len(rows)}
- Total listed size: {total_size} bytes
- SHA256 hashes: present for every listed file
- Physical robot data: not included and not claimed
- DOI/accession: TBD
- Licence: TBD

## Blocking Items Before Nature-Family Submission

- Choose the repository and mint or reserve the DOI/accession.
- Replace all `TBD repository`, author, funding, licence, DOI, and reviewer-link fields.
- Decide whether raw CARLA logs can be redistributed.
- Add physical ROS2/robot data only after actual trials are completed and audited.
- Ensure the manuscript Data Availability and repository record describe the same files.
""",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = collect_files()
    if not files:
        raise SystemExit("no files collected for repository deposit")
    rows = write_manifest(files)
    write_datacite(rows)
    write_readme(rows)
    write_report(rows)
    print(MANIFEST)
    print(CHECKSUMS)
    print(DATACITE)
    print(README)
    print(REPORT)
    print(f"files={len(rows)}")


if __name__ == "__main__":
    main()
