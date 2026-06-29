#!/usr/bin/env python3
"""Publication-grade figure QA for the extended manuscript figure bundle."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageStat


ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "08_paper_ready_outputs" / "figures"
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
MANUSCRIPT = ROOT / "01_manuscript"
MANUSCRIPT_FIGS = MANUSCRIPT / "paper_picture"
PACKAGE = ROOT / "06_submission_package"
OUT_CSV = SOURCE / "publication_figure_qa.csv"
OUT_REPORT = PACKAGE / "publication_figure_qa_report_current.md"


@dataclass
class FigureSpec:
    figure_id: str
    role: str
    width_class: str
    min_width_px: int
    max_height_mm: float
    source_files: tuple[str, ...]
    generator: str
    manuscript_token: str
    contract: str


@dataclass
class AuditRow:
    figure_id: str
    check_id: str
    requirement: str
    actual: str
    status: str
    source_artifact: str
    boundary: str


FIGURE_SPECS = [
    FigureSpec(
        figure_id="fig_nature_system_evidence",
        role="schematic-led composite",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=(
            "fig_nature_system_evidence_source.csv",
            "stress_summary_combined.csv",
            "carla_nis_noise_sweep_qgip100_summary.csv",
            "carla_nis_outlier_qgip100_summary.csv",
        ),
        generator="generate_nature_main_figure.py",
        manuscript_token="fig_nature_system_evidence.pdf",
        contract="System contract plus target-consistency and NIS diagnostic evidence.",
    ),
    FigureSpec(
        figure_id="fig_query_guided_attention",
        role="query-guided attention mechanism schematic",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("fig_query_guided_attention_source.csv",),
        generator="generate_nature_style_main_figures.py",
        manuscript_token="fig_query_guided_attention.pdf",
        contract="The initial-draft query-guided attention concept is redrawn as a source-data-backed mechanism figure showing how the same scene yields different target attention under different intent queries.",
    ),
    FigureSpec(
        figure_id="fig_pop_ghost_tracking",
        role="POP/NIS-KF ghost-tracking mechanism schematic",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("fig_pop_ghost_tracking_source.csv",),
        generator="generate_nature_style_main_figures.py",
        manuscript_token="fig_pop_ghost_tracking.pdf",
        contract="The initial-draft POP ghost-tracking concept is redrawn as a mechanism figure linking active update, ghost prediction, re-association, NIS thresholds, and conservative recovery.",
    ),
    FigureSpec(
        figure_id="fig6_split_audit_matrix_only_v2",
        role="dataset split audit matrix",
        width_class="double-column",
        min_width_px=3000,
        max_height_mm=130.0,
        source_files=("final_dataset_split_check.csv", "final_dataset_split_overlap.csv"),
        generator="fig6_split_audit_matrix_only_v2.py",
        manuscript_token="fig6_split_audit_matrix_only_v2.pdf",
        contract="Dataset split composition and held-out-map isolation are summarized as a compact audit matrix.",
    ),
    FigureSpec(
        figure_id="fig9_extended_stress_operating_envelope_refined_v3",
        role="extended stress operating envelope",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("fig9_extended_stress_operating_envelope_refined_v3_source_data.csv", "fig9_extended_stress_operating_envelope_refined_v3_aggregated_points.csv"),
        generator="fig9_extended_stress_operating_envelope_refined_v3.py",
        manuscript_token="fig9_extended_stress_operating_envelope_refined_v3.pdf",
        contract="Extended stress conditions are summarized as a fail-safe Lost versus LeaderAcc operating envelope with finite-sample collision-bound interpretation.",
    ),
    FigureSpec(
        figure_id="fig10_nis_regime_bubble_map_refined_v5",
        role="NIS diagnostic regime map",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("carla_nis_noise_sweep_qgip100_summary.csv", "carla_nis_outlier_qgip100_summary.csv", "fig10_nis_regime_bubble_map_refined_v5_source_data.csv"),
        generator="fig10_nis_regime_bubble_map_refined_v5.py",
        manuscript_token="fig10_nis_regime_bubble_map_refined_v5.pdf",
        contract="NIS noise and outlier responses are summarized as a regime map rather than repeated paired-segment diagnostics.",
    ),
    FigureSpec(
        figure_id="fig13_offline_dryrun_contract_timeline_v2",
        role="offline dry-run contract timeline and telemetry-gate diagnostic",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("fig13_offline_dryrun_contract_timeline_v2_source_data.csv", "real_robot_offline_dryrun_trace.csv", "ros2_runtime_telemetry_dryrun_summary.csv"),
        generator="fig13_offline_dryrun_contract_timeline_v2.py",
        manuscript_token="fig13_offline_dryrun_contract_timeline_v2.pdf",
        contract="The selected-leader, POP/NIS, controller-proxy, and telemetry-gate contracts are logged coherently in a desktop preflight dry run before ROS2/HIL execution.",
    ),
    FigureSpec(
        figure_id="fig11_claim_boundary_bowtie_v4",
        role="safety-case claim-boundary bow-tie schematic",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("fig11_claim_boundary_bowtie_v4_source_data.csv", "fig11_claim_boundary_bowtie_v4_edges.csv", "safety_case_claim_graph.csv"),
        generator="fig11_claim_boundary_bowtie_v4.py",
        manuscript_token="fig11_claim_boundary_bowtie_v4.pdf",
        contract="Completed CARLA simulation and audit evidence are separated from remaining ROS2/HIL and physical-validation requirements through a bow-tie claim-boundary schematic.",
    ),
    FigureSpec(
        figure_id="fig_evidence_coverage_matrix",
        role="protocol-to-claim evidence coverage matrix",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("fig_evidence_coverage_matrix_source.csv", "simulation_protocol_registry.csv", "claim_evidence_matrix.csv"),
        generator="generate_evidence_coverage_matrix.py",
        manuscript_token="fig_evidence_coverage_matrix.pdf",
        contract="Layered simulation, audit, and pre-real-robot protocols are mapped to the claim axes they support and the boundaries they do not cross.",
    ),
    FigureSpec(
        figure_id="fig7_main_result_final_v7",
        role="main route outcome and target-selection evidence",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("fig_simulation_effect_size_source.csv", "main_benchmark_source.csv", "pairwise_stats_combined.csv", "extended_stress_qgip_summary.csv"),
        generator="fig7_main_result_final_v7.py",
        manuscript_token="fig7_main_result_final_v7.pdf",
        contract="Route-level safety and availability are separated from target-selection evidence and finite-sample zero-collision boundaries.",
    ),
    FigureSpec(
        figure_id="fig8_wrong_leader_exposure_diagnostic_v5",
        role="wrong-leader exposure diagnostic",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("figure_stress_leader_metrics.csv",),
        generator="fig8_wrong_leader_exposure_diagnostic_v5.py",
        manuscript_token="fig8_wrong_leader_exposure_diagnostic_v5.pdf",
        contract="Wrong-leader exposure and the LeaderAcc--exposure diagnostic plane expose stable-but-wrong target failures under primary and boundary ambiguity conditions.",
    ),
    FigureSpec(
        figure_id="fig5_stress_suite_discriminators_v3",
        role="stress-suite discriminator synthesis",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("fig_simulation_stress_atlas_source.csv", "main_benchmark_source.csv", "main1000_nominal_source.csv", "stress_summary_combined.csv", "pairwise_stats_combined.csv", "carla_nis_noise_sweep_qgip100_summary.csv", "carla_nis_outlier_qgip100_summary.csv"),
        generator="fig5_stress_suite_discriminators_v3.py",
        manuscript_token="fig5_stress_suite_discriminators_v3.pdf",
        contract="Stress-suite scale, paired ambiguity effects, and NIS diagnostic response are synthesized as method-discriminating evidence.",
    ),
    FigureSpec(
        figure_id="fig12_validation_boundary_narrative_v4",
        role="pre-real-robot validation-boundary narrative",
        width_class="double-column",
        min_width_px=4000,
        max_height_mm=170.0,
        source_files=("fig12_validation_boundary_narrative_v4_source_data.csv", "pre_real_robot_gate_audit.csv"),
        generator="fig12_validation_boundary_narrative_v4.py",
        manuscript_token="fig12_validation_boundary_narrative_v4.pdf",
        contract="Prepared local gate and desktop-preflight evidence are separated from required live ROS2/HIL timing, rosbag, and physical-robot evidence before any live-validation claim is made.",
    ),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def add(rows: list[AuditRow], spec: FigureSpec, check_id: str, requirement: str, ok: bool, actual: str, source: str, boundary: str) -> None:
    rows.append(
        AuditRow(
            figure_id=spec.figure_id,
            check_id=check_id,
            requirement=requirement,
            actual=actual,
            status="PASS" if ok else "FAIL",
            source_artifact=source,
            boundary=boundary,
        )
    )


def image_metrics(path: Path) -> dict[str, float | int | tuple[float, float] | tuple[int, int]]:
    image = Image.open(path)
    rgb = image.convert("RGB")
    stat = ImageStat.Stat(rgb)
    extrema = rgb.getextrema()
    width, height = image.size
    dpi = image.info.get("dpi", (0.0, 0.0))
    grayscale = rgb.convert("L")
    hist = grayscale.histogram()
    total = width * height
    nonwhite = sum(count for value, count in enumerate(hist) if value < 250)
    luma_min, luma_max = grayscale.getextrema()
    return {
        "width": width,
        "height": height,
        "dpi": dpi,
        "mean_luma": sum(stat.mean) / 3.0,
        "luma_range": luma_max - luma_min,
        "nonwhite_fraction": nonwhite / total,
    }


def main() -> None:
    rows: list[AuditRow] = []
    tex = (MANUSCRIPT / "manuscript_current.tex").read_text(encoding="utf-8")
    accessibility = SOURCE / "figure_accessibility_metrics.csv"
    accessibility_rows = csv_rows(accessibility) if accessibility.exists() else -1

    for spec in FIGURE_SPECS:
        paths = {suffix: FIGS / f"{spec.figure_id}.{suffix}" for suffix in ("pdf", "svg", "tiff", "png")}
        export_ok = all(path.exists() and path.stat().st_size > 0 for path in paths.values())
        add(
            rows,
            spec,
            "export_bundle",
            "PDF, SVG, TIFF, and PNG exports exist and are non-empty.",
            export_ok,
            "; ".join(f"{suffix}={paths[suffix].stat().st_size if paths[suffix].exists() else 0} bytes" for suffix in paths),
            "08_paper_ready_outputs/figures",
            "File presence does not prove visual quality by itself.",
        )

        mirror_details = []
        mirror_ok = True
        for suffix, path in paths.items():
            mirror = MANUSCRIPT_FIGS / path.name
            if not mirror.exists() or sha256(path) != sha256(mirror):
                mirror_ok = False
            mirror_details.append(f"{suffix}={'match' if mirror.exists() and path.exists() and sha256(path) == sha256(mirror) else 'mismatch'}")
        add(
            rows,
            spec,
            "manuscript_mirror",
            "Figure exports are mirrored byte-for-byte in the manuscript figure directory.",
            mirror_ok,
            "; ".join(mirror_details),
            "01_manuscript/paper_picture",
            "Mirror consistency does not assess final page layout.",
        )

        tiff_metrics = image_metrics(paths["tiff"])
        dpi_x, dpi_y = tiff_metrics["dpi"]  # type: ignore[misc]
        width = int(tiff_metrics["width"])
        height = int(tiff_metrics["height"])
        width_mm = width / float(dpi_x) * 25.4 if dpi_x else 0.0
        height_mm = height / float(dpi_y) * 25.4 if dpi_y else 0.0
        resolution_ok = width >= spec.min_width_px and float(dpi_x) >= 590.0 and float(dpi_y) >= 590.0 and height_mm <= spec.max_height_mm
        add(
            rows,
            spec,
            "tiff_final_size_resolution",
            "TIFF export is at publication-scale width, 600-dpi class resolution, and within Nature-style height bounds.",
            resolution_ok,
            f"{width}x{height}px; dpi=({float(dpi_x):.1f},{float(dpi_y):.1f}); size={width_mm:.1f}x{height_mm:.1f}mm; width_class={spec.width_class}",
            paths["tiff"].relative_to(ROOT).as_posix(),
            "Size is inferred from TIFF metadata and does not replace final journal production checks.",
        )

        png_metrics = image_metrics(paths["png"])
        nonblank_ok = float(png_metrics["nonwhite_fraction"]) > 0.02 and float(png_metrics["luma_range"]) > 40.0
        add(
            rows,
            spec,
            "png_nonblank_contrast",
            "PNG preview is non-blank and has measurable luminance range.",
            nonblank_ok,
            f"nonwhite_fraction={float(png_metrics['nonwhite_fraction']):.3f}; luma_range={float(png_metrics['luma_range']):.1f}; mean_luma={float(png_metrics['mean_luma']):.1f}",
            paths["png"].relative_to(ROOT).as_posix(),
            "Pixel statistics are a screen for blank/clipped exports, not a substitute for visual inspection.",
        )

        svg_text = paths["svg"].read_text(encoding="utf-8", errors="replace")
        text_count = svg_text.count("<text")
        vector_ok = text_count > 0 and "<image" not in svg_text
        add(
            rows,
            spec,
            "svg_editable_vector_text",
            "SVG keeps text/vector elements editable and avoids embedded raster images for these quantitative/schematic figures.",
            vector_ok,
            f"text_elements={text_count}; embedded_image_tags={svg_text.count('<image')}",
            paths["svg"].relative_to(ROOT).as_posix(),
            "SVG text-count screening cannot prove every glyph is editable in all vector editors.",
        )

        source_details = []
        source_ok = True
        for item in spec.source_files:
            path = SOURCE / item
            if not path.exists() or path.stat().st_size <= 0:
                source_ok = False
                source_details.append(f"{item}=missing")
            else:
                source_details.append(f"{item}={csv_rows(path)} rows")
        add(
            rows,
            spec,
            "source_data_trace",
            "Each quantitative figure has source-data CSVs in the paper-ready source-data directory.",
            source_ok,
            "; ".join(source_details),
            "08_paper_ready_outputs/source_data",
            "Source-data traceability covers processed data, not raw CARLA reruns.",
        )

        generator = ROOT / "05_analysis_scripts" / spec.generator
        generator_text = generator.read_text(encoding="utf-8")
        generator_ok = "svg.fonttype" in generator_text and "pdf.fonttype" in generator_text and "savefig" in generator_text
        add(
            rows,
            spec,
            "python_generator_export_policy",
            "Python generator declares SVG/PDF font editability settings and scripted export calls.",
            generator_ok,
            f"generator={spec.generator}; svg.fonttype={'svg.fonttype' in generator_text}; pdf.fonttype={'pdf.fonttype' in generator_text}",
            f"05_analysis_scripts/{spec.generator}",
            "Script inspection does not replace opening the vector file in Illustrator/Inkscape.",
        )

        manuscript_ok = spec.manuscript_token in tex
        add(
            rows,
            spec,
            "manuscript_embedding",
            "Figure is embedded in the current manuscript source.",
            manuscript_ok,
            f"token={spec.manuscript_token}; present={manuscript_ok}",
            "01_manuscript/manuscript_current.tex",
            "Embedding check does not inspect exact page placement or typography.",
        )

        add(
            rows,
            spec,
            "figure_contract",
            "Figure has a declared claim/evidence role in the QA audit.",
            bool(spec.contract and spec.role),
            f"role={spec.role}; contract={spec.contract}",
            OUT_CSV.name,
            "Contract is a reviewer-facing map, not independent scientific evidence.",
        )

    expected_accessibility_rows = len(FIGURE_SPECS) * 3
    accessory_ok = accessibility_rows == expected_accessibility_rows and (ROOT / "09_pdf_qa" / "figure_accessibility_contact_sheet_v1.png").exists()
    rows.append(
        AuditRow(
            figure_id="figure_bundle",
            check_id="accessibility_qa_link",
            requirement="Figure bundle links to grayscale/deuteranopia accessibility QA outputs.",
            actual=f"figure_accessibility_metrics.csv rows={accessibility_rows}/{expected_accessibility_rows}; contact_sheet_exists={(ROOT / '09_pdf_qa' / 'figure_accessibility_contact_sheet_v1.png').exists()}",
            status="PASS" if accessory_ok else "FAIL",
            source_artifact="figure_accessibility_metrics.csv; figure_accessibility_contact_sheet_v1.png",
            boundary="Existing accessibility QA is approximate and not a formal perceptual user study.",
        )
    )

    rendered_pages = sorted((ROOT / "09_pdf_qa").glob("manuscript_current_page-*.png"))
    expected_rendered_pages = 18
    rows.append(
        AuditRow(
            figure_id="figure_bundle",
            check_id="manuscript_page_render_link",
            requirement="Current manuscript pages have been rendered for page-level figure inspection.",
            actual=f"rendered_pages={len(rendered_pages)}/{expected_rendered_pages}; contact_sheet_exists={(ROOT / '09_pdf_qa' / 'contact_sheet_manuscript_current.png').exists()}",
            status="PASS" if len(rendered_pages) == expected_rendered_pages and (ROOT / "09_pdf_qa" / "contact_sheet_manuscript_current.png").exists() else "FAIL",
            source_artifact="09_pdf_qa/manuscript_current_page-*.png; contact_sheet_manuscript_current.png",
            boundary="Rendered-page QA supports layout review but does not replace human zoom inspection at submission.",
        )
    )

    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(AuditRow.__annotations__.keys()))
        writer.writeheader()
        writer.writerows([row.__dict__ for row in rows])

    failed = [row for row in rows if row.status != "PASS"]
    report_lines = [
        "# Publication Figure QA Report, 2026-06-04",
        "",
        "## Decision",
        "",
        f"The publication figure QA checks {len(rows)} figure-export, source-data, vector, raster-resolution, accessibility, and manuscript-embedding gates for the extended manuscript figure bundle.",
        f"Passed: {len(rows) - len(failed)}",
        f"Failed: {len(failed)}",
        "All audited publication-figure checks passed." if not failed else "One or more publication-figure checks failed.",
        "",
        "## Figure Contracts",
        "",
    ]
    for spec in FIGURE_SPECS:
        report_lines.append(f"- `{spec.figure_id}` ({spec.role}, {spec.width_class}): {spec.contract}")
    report_lines.extend(
        [
            "",
            "## Nature-Style QA Basis",
            "",
            "The audit follows the local Nature-style figure standard and the current Nature research figure guide defaults checked on 2026-06-04: 89/183 mm figure widths, maximum 170 mm main-figure height, 5-7 pt ordinary text, approximately 8 pt bold lowercase panel labels, editable text/vector layers, accessible colours, and 300 dpi or higher raster exports.",
            "",
            "The figure bundle is cross-linked to `figure_accessibility_metrics.csv`, `figure_accessibility_contact_sheet_v1.png`, and the rendered manuscript page contact sheet for page-level inspection.",
            "",
            "## Boundary",
            "",
            "This audit is a machine-readable pre-submission screen. It does not replace human inspection in Illustrator/Inkscape/PDF viewers, target-journal production review, raw-data image-integrity review, or final DOI-backed source-data publication.",
        ]
    )
    if failed:
        report_lines.extend(["", "## Failed Checks", ""])
        for row in failed:
            report_lines.append(f"- `{row.figure_id}/{row.check_id}`: {row.actual}")

    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8", newline="\n")
    print(OUT_CSV)
    print(OUT_REPORT)
    print(f"passed={len(rows) - len(failed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
