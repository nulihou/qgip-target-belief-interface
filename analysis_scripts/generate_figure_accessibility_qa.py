#!/usr/bin/env python3
"""Generate standalone accessibility QA previews for manuscript figures.

The script does not redraw scientific content. It uses the exported PNG previews of the
publication figures and creates a contact sheet with original, grayscale, and approximate
deuteranopia views, plus a small metric CSV for audit traceability.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "08_paper_ready_outputs" / "figures"
QA_DIR = ROOT / "09_pdf_qa"
SOURCE_DIR = ROOT / "08_paper_ready_outputs" / "source_data"
OUT_SHEET = QA_DIR / "figure_accessibility_contact_sheet_v1.png"
OUT_METRICS = SOURCE_DIR / "figure_accessibility_metrics.csv"

FIGURES = [
    ("fig_nature_system_evidence", "System/evidence composite"),
    ("fig_query_guided_attention", "Query-guided attention mechanism"),
    ("fig_pop_ghost_tracking", "POP ghost-tracking mechanism"),
    ("fig6_split_audit_matrix_only_v2", "Dataset split audit"),
    ("fig9_extended_stress_operating_envelope_refined_v3", "Extended stress operating envelope"),
    ("fig10_nis_regime_bubble_map_refined_v5", "NIS diagnostic regime map"),
    ("fig13_offline_dryrun_contract_timeline_v2", "Offline dry-run contract timeline"),
    ("fig11_claim_boundary_bowtie_v4", "Safety-case claim boundary"),
    ("fig_evidence_coverage_matrix", "Evidence coverage matrix"),
    ("fig5_stress_suite_discriminators_v3", "Stress-suite discriminators"),
    ("fig7_main_result_final_v7", "Main result and target-selection evidence"),
    ("fig8_wrong_leader_exposure_diagnostic_v5", "Wrong-leader exposure diagnostic"),
    ("fig12_validation_boundary_narrative_v4", "Pre-real-robot validation boundary"),
]

# Simple RGB-space approximation used for visual QA, not a clinical colour-vision model.
DEUTERANOPIA_MATRIX = np.array(
    [
        [0.625, 0.375, 0.000],
        [0.700, 0.300, 0.000],
        [0.000, 0.300, 0.700],
    ],
    dtype=np.float32,
)


def luma_array(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def to_deuteranopia(image: Image.Image) -> Image.Image:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    transformed = rgb @ DEUTERANOPIA_MATRIX.T
    transformed = np.clip(transformed, 0, 255).astype(np.uint8)
    return Image.fromarray(transformed, mode="RGB")


def fit_to_box(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return fitted


def draw_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str) -> None:
    font = ImageFont.load_default()
    draw.text(xy, text, fill=(20, 20, 20), font=font)


def tile(image: Image.Image, title: str, subtitle: str) -> Image.Image:
    canvas = Image.new("RGB", (430, 310), (255, 255, 255))
    fitted = fit_to_box(image, 390, 235)
    canvas.paste(fitted, ((430 - fitted.width) // 2, 48))
    draw = ImageDraw.Draw(canvas)
    draw_label(draw, (16, 12), title)
    draw_label(draw, (16, 292), subtitle)
    return canvas


def metric_row(name: str, label: str, image: Image.Image) -> dict[str, str]:
    luma = luma_array(image)
    non_white = luma < 0.985
    if np.any(non_white):
        data_luma = luma[non_white]
    else:
        data_luma = luma.reshape(-1)
    p5 = float(np.percentile(data_luma, 5))
    p95 = float(np.percentile(data_luma, 95))
    return {
        "figure": name,
        "label": label,
        "width_px": str(image.width),
        "height_px": str(image.height),
        "non_white_fraction": f"{float(non_white.mean()):.4f}",
        "luma_p05": f"{p5:.4f}",
        "luma_p95": f"{p95:.4f}",
        "luma_p95_minus_p05": f"{p95 - p5:.4f}",
    }


def main() -> None:
    QA_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    sheet_tiles: list[Image.Image] = []
    for name, label in FIGURES:
        path = FIG_DIR / f"{name}.png"
        if not path.exists():
            raise FileNotFoundError(path)
        original = Image.open(path).convert("RGB")
        grayscale = original.convert("L").convert("RGB")
        deut = to_deuteranopia(original)

        rows.append(metric_row(name, label, original))
        rows.append(metric_row(f"{name}__grayscale", label, grayscale))
        rows.append(metric_row(f"{name}__deuteranopia_approx", label, deut))

        sheet_tiles.extend(
            [
                tile(original, label, "original"),
                tile(grayscale, label, "grayscale check"),
                tile(deut, label, "deuteranopia approximation"),
            ]
        )

    cols = 3
    rows_count = len(FIGURES)
    gutter = 12
    margin = 18
    tile_w, tile_h = 430, 310
    sheet = Image.new(
        "RGB",
        (
            margin * 2 + cols * tile_w + (cols - 1) * gutter,
            margin * 2 + rows_count * tile_h + (rows_count - 1) * gutter,
        ),
        (238, 238, 238),
    )
    for idx, item in enumerate(sheet_tiles):
        x = margin + (idx % cols) * (tile_w + gutter)
        y = margin + (idx // cols) * (tile_h + gutter)
        sheet.paste(item, (x, y))
    sheet.save(OUT_SHEET)

    with OUT_METRICS.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(OUT_SHEET)
    print(OUT_METRICS)


if __name__ == "__main__":
    main()
