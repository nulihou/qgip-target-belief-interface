#!/usr/bin/env python3
"""Regenerate manuscript figures with a unified Nature-style Python workflow.

The script redraws the figures referenced by the long-form manuscript from
machine-readable source CSV files. It keeps the existing figure filenames so the
LaTeX source does not need to change, while exporting editable PDF/SVG and
high-resolution PNG/TIFF copies to both the manuscript figure folder and the
paper-ready output folder.
"""

from __future__ import annotations

import csv
import math
import shutil
import textwrap
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Patch, Polygon, Rectangle

from qgip_figure_style import TOP_CONF_COLORS as TOP, apply_top_conference_style


WORK = Path(__file__).resolve().parents[1]
SOURCE = WORK / "08_paper_ready_outputs" / "source_data"
FIGS = WORK / "08_paper_ready_outputs" / "figures"
MANUSCRIPT_FIGS = WORK / "01_manuscript" / "paper_picture"

EXPORTS = (".pdf", ".svg", ".png", ".tiff")
FIGURE_NAMES = [
    "fig_nature_system_evidence",
    "fig_query_guided_attention",
    "fig_pop_ghost_tracking",
    "fig_main_target_selection_nature",
    "fig_main_safety_availability_nature",
    "fig_main_nis_diagnostic_nature",
    "fig_evidence_coverage_matrix",
    "fig5_stress_suite_discriminators_v3",
    "fig6_split_audit_matrix_only_v2",
    "fig7_main_result_final_v7",
    "fig8_wrong_leader_exposure_diagnostic_v5",
    "figure_stress_leaderacc",
    "figure_stress_idswitch",
    "fig9_extended_stress_operating_envelope_refined_v3",
    "fig10_nis_regime_bubble_map_refined_v5",
    "fig11_claim_boundary_bowtie_v4",
    "fig12_validation_boundary_narrative_v4",
    "fig13_offline_dryrun_contract_timeline_v2",
]


COLORS = {
    "qgip": TOP["blue"],
    "qgip_light": TOP["blue_light"],
    "rule": TOP["gray"],
    "stdkf": TOP["blue_mid"],
    "noquery": TOP["copper"],
    "success": TOP["teal"],
    "lost": TOP["gray_light"],
    "collision": TOP["brick"],
    "near": TOP["copper_light"],
    "boundary": TOP["violet"],
    "monitor": TOP["blue_mid"],
    "text": TOP["ink"],
    "muted": TOP["gray"],
    "grid": TOP["grid"],
    "empty": TOP["panel"],
    "soft": TOP["copper"],
    "hard": TOP["brick"],
}

COND_LABELS = {
    "fp_10": "FP10",
    "idswitch": "ID switch",
    "fn_50": "FN50",
    "delay_200": "Delay200",
    "raw_glare": "Raw glare",
    "raw_lidar_dropout": "LiDAR drop",
    "fp20_idswitch20": "Boundary",
    "fp_20": "FP20",
    "idswitch_40": "ID switch 40",
    "noise_02": "0.2 m",
    "noise_05": "0.5 m",
    "noise_10": "1.0 m",
    "idswitch_20": "ID20",
    "fp10_idswitch20_noise05": "Combo",
}

METHOD_LABELS = {
    "E2E Baseline (No MPC)": "E2E\n(no MPC)",
    "Modular PID": "Modular\nPID",
    "Rule-Based + MPC": "Rule\n+ MPC",
    "Std KF + MPC": "Std KF\n+ MPC",
    "QGIP-Net (Ours)": "QGIP-Net",
    "rule": "Rule",
    "qgip_no_query": "No query",
    "std_kf": "Std KF",
    "qgip": "QGIP-Net",
}

METHOD_ORDER = [
    "E2E Baseline (No MPC)",
    "Modular PID",
    "Rule-Based + MPC",
    "Std KF + MPC",
    "QGIP-Net (Ours)",
]

AUDIT_ROWS: list[dict[str, str]] = []


apply_top_conference_style()
mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "sans-serif"],
        "font.size": 6.2,
        "axes.titlesize": 7.0,
        "axes.labelsize": 6.2,
        "xtick.labelsize": 5.5,
        "ytick.labelsize": 5.5,
        "legend.fontsize": 5.4,
        "axes.linewidth": 0.55,
        "xtick.major.width": 0.45,
        "ytick.major.width": 0.45,
        "xtick.major.size": 2.2,
        "ytick.major.size": 2.2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    }
)


def mm(value: float) -> float:
    return value / 25.4


def read_source(name: str) -> pd.DataFrame:
    path = SOURCE / name
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def write_schematic_source(name: str, rows: list[dict[str, object]]) -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(SOURCE / name, index=False, encoding="utf-8-sig")


def safe_float(value: object, default: float = math.nan) -> float:
    if pd.isna(value) or value == "":
        return default
    return float(value)


def wrap_label(value: object, width: int = 16) -> str:
    text = str(value)
    return "\n".join(textwrap.wrap(text, width=width, break_long_words=False))


def pct(value: object) -> float:
    return 100.0 * safe_float(value, 0.0)


def clean_axis(ax: plt.Axes, grid: bool = False, axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if grid:
        ax.grid(True, axis=axis, color=COLORS["grid"], linewidth=0.35, alpha=0.7)
        ax.set_axisbelow(True)


def panel_label(ax: plt.Axes, label: str, title: str | None = None, x: float = -0.09) -> None:
    ax.text(x, 1.05, label, transform=ax.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    if title:
        ax.text(0.0, 1.05, title, transform=ax.transAxes, fontsize=7, fontweight="bold", ha="left", va="bottom")


def axis_note(ax: plt.Axes, text: str, loc: str = "lower right") -> None:
    anchors = {
        "lower right": (0.99, 0.02, "right", "bottom"),
        "upper right": (0.99, 0.98, "right", "top"),
        "lower left": (0.01, 0.02, "left", "bottom"),
        "upper left": (0.01, 0.98, "left", "top"),
    }
    x, y, ha, va = anchors[loc]
    ax.text(x, y, text, transform=ax.transAxes, ha=ha, va=va, fontsize=5.1, color=COLORS["muted"])


def backup_existing_outputs() -> None:
    for base in (MANUSCRIPT_FIGS, FIGS):
        backup = base.parent / f"{base.name}_legacy_pre_nature_20260604"
        backup.mkdir(parents=True, exist_ok=True)
        for name in FIGURE_NAMES:
            for suffix in EXPORTS:
                src = base / f"{name}{suffix}"
                if src.exists():
                    dst = backup / src.name
                    if not dst.exists():
                        shutil.copy2(src, dst)


def save_figure(fig: plt.Figure, name: str, width_mm: float, height_mm: float, source_files: list[str]) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_FIGS.mkdir(parents=True, exist_ok=True)
    fig.set_size_inches(mm(width_mm), mm(height_mm), forward=True)
    for suffix in EXPORTS:
        path = FIGS / f"{name}{suffix}"
        if suffix in (".png", ".tiff"):
            fig.savefig(path, dpi=600)
        else:
            fig.savefig(path)
        shutil.copy2(path, MANUSCRIPT_FIGS / path.name)
    AUDIT_ROWS.append(
        {
            "figure": name,
            "width_mm": f"{width_mm:.1f}",
            "height_mm": f"{height_mm:.1f}",
            "source_files": "; ".join(source_files),
            "outputs": "; ".join([f"{name}{suffix}" for suffix in EXPORTS]),
            "font_contract": "pdf.fonttype=42; svg.fonttype=none; text editable",
        }
    )
    plt.close(fig)


def bar_value(rows: pd.DataFrame, condition: str, metric: str, default: float = 0.0) -> float:
    hit = rows[(rows["condition_id"] == condition) & (rows["metric"] == metric)]
    if hit.empty:
        return default
    return safe_float(hit.iloc[0]["value"], default)


def ci_values(row: pd.Series, scale: float = 1.0) -> tuple[float, float]:
    value = safe_float(row["value"]) * scale
    low = safe_float(row.get("ci_low", math.nan)) * scale
    high = safe_float(row.get("ci_high", math.nan)) * scale
    if math.isnan(low) or math.isnan(high):
        return 0.0, 0.0
    return max(value - low, 0.0), max(high - value, 0.0)


def draw_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subtitle: str = "",
    face: str = "#F7F8FA",
    edge: str = "#67717C",
) -> None:
    ax.add_patch(Rectangle((x, y), w, h, facecolor=face, edgecolor=edge, linewidth=0.55))
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=5.8, fontweight="bold", color=COLORS["text"])
    if subtitle:
        ax.text(x + w / 2, y + h * 0.30, subtitle, ha="center", va="center", fontsize=4.9, color=COLORS["muted"])


def draw_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], color: str = "#59616D") -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=7,
            linewidth=0.55,
            color=color,
            shrinkA=2,
            shrinkB=2,
        )
    )


def plot_query_guided_attention() -> None:
    rows = [
        {"mode": "follow leader", "object": "ego", "lateral_m": 0.0, "longitudinal_m": 1.4, "attention": 0.0, "selected": 0, "role": "ego", "score_type": "relative target score"},
        {"mode": "follow leader", "object": "same lane", "lateral_m": 0.0, "longitudinal_m": 8.0, "attention": 0.95, "selected": 1, "role": "same-lane leader", "score_type": "relative target score"},
        {"mode": "follow leader", "object": "far leader", "lateral_m": 0.0, "longitudinal_m": 17.6, "attention": 0.10, "selected": 0, "role": "far leader", "score_type": "relative target score"},
        {"mode": "follow leader", "object": "left lane", "lateral_m": -2.35, "longitudinal_m": 10.0, "attention": 0.05, "selected": 0, "role": "left-lane vehicle", "score_type": "relative target score"},
        {"mode": "follow leader", "object": "right lane", "lateral_m": 2.35, "longitudinal_m": 7.3, "attention": 0.02, "selected": 0, "role": "right-lane vehicle", "score_type": "relative target score"},
        {"mode": "lane change left", "object": "ego", "lateral_m": 0.0, "longitudinal_m": 1.4, "attention": 0.0, "selected": 0, "role": "ego", "score_type": "relative target score"},
        {"mode": "lane change left", "object": "same lane", "lateral_m": 0.0, "longitudinal_m": 8.0, "attention": 0.30, "selected": 0, "role": "same-lane leader", "score_type": "relative target score"},
        {"mode": "lane change left", "object": "far leader", "lateral_m": 0.0, "longitudinal_m": 17.6, "attention": 0.05, "selected": 0, "role": "far leader", "score_type": "relative target score"},
        {"mode": "lane change left", "object": "left lane", "lateral_m": -2.35, "longitudinal_m": 10.0, "attention": 0.85, "selected": 1, "role": "target-lane vehicle", "score_type": "relative target score"},
        {"mode": "lane change left", "object": "right lane", "lateral_m": 2.35, "longitudinal_m": 7.3, "attention": 0.01, "selected": 0, "role": "right-lane vehicle", "score_type": "relative target score"},
    ]
    source_name = "fig_query_guided_attention_source.csv"
    write_schematic_source(source_name, rows)

    import runpy

    build_fig2_v2 = runpy.run_path(str(Path(__file__).with_name("fig2_final_submission_ready_v2.py")))["build_figure"]
    FIGS.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_FIGS.mkdir(parents=True, exist_ok=True)
    fig = build_fig2_v2(str(FIGS / "fig_query_guided_attention"))
    plt.close(fig)
    for suffix in EXPORTS:
        path = FIGS / f"fig_query_guided_attention{suffix}"
        shutil.copy2(path, MANUSCRIPT_FIGS / path.name)
    AUDIT_ROWS.append(
        {
            "figure": "fig_query_guided_attention",
            "width_mm": "183.0",
            "height_mm": "70.9",
            "source_files": source_name,
            "outputs": "; ".join([f"fig_query_guided_attention{suffix}" for suffix in EXPORTS]),
            "font_contract": "pdf.fonttype=42; svg.fonttype=none; text editable",
        }
    )
    return

    rows = [
        {"mode": "follow leader", "object": "ego", "lateral_m": 0.0, "longitudinal_m": 0.0, "attention": 0.0, "selected": 0, "role": "ego"},
        {"mode": "follow leader", "object": "same-lane leader", "lateral_m": 0.0, "longitudinal_m": 10.8, "attention": 0.85, "selected": 1, "role": "leader"},
        {"mode": "follow leader", "object": "far leader", "lateral_m": 0.0, "longitudinal_m": 17.4, "attention": 0.09, "selected": 0, "role": "distractor"},
        {"mode": "follow leader", "object": "left-lane vehicle", "lateral_m": -3.0, "longitudinal_m": 6.2, "attention": 0.04, "selected": 0, "role": "distractor"},
        {"mode": "follow leader", "object": "right-lane vehicle", "lateral_m": 3.0, "longitudinal_m": 3.7, "attention": 0.02, "selected": 0, "role": "distractor"},
        {"mode": "change lane left", "object": "ego", "lateral_m": 0.0, "longitudinal_m": 0.0, "attention": 0.0, "selected": 0, "role": "ego"},
        {"mode": "change lane left", "object": "same-lane leader", "lateral_m": 0.0, "longitudinal_m": 10.8, "attention": 0.25, "selected": 0, "role": "distractor"},
        {"mode": "change lane left", "object": "far leader", "lateral_m": 0.0, "longitudinal_m": 17.4, "attention": 0.04, "selected": 0, "role": "distractor"},
        {"mode": "change lane left", "object": "left-lane vehicle", "lateral_m": -3.0, "longitudinal_m": 6.2, "attention": 0.70, "selected": 1, "role": "target lane"},
        {"mode": "change lane left", "object": "right-lane vehicle", "lateral_m": 3.0, "longitudinal_m": 3.7, "attention": 0.01, "selected": 0, "role": "distractor"},
    ]
    source_name = "fig_query_guided_attention_source.csv"
    write_schematic_source(source_name, rows)
    df = pd.DataFrame(rows)

    with mpl.rc_context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7.0,
            "axes.titlesize": 7.6,
            "axes.labelsize": 7.2,
            "xtick.labelsize": 6.8,
            "ytick.labelsize": 7.0,
            "legend.fontsize": 6.8,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    ):
        follow = {"same lane": 0.85, "left lane": 0.04, "far leader": 0.09, "right lane": 0.02}
        lane_left = {"same lane": 0.25, "left lane": 0.70, "far leader": 0.04, "right lane": 0.01}

        blue = "#0065BD"
        light_blue = "#A9CBE8"
        road = "#F1F3F5"
        road_edge = "#9DA8B2"
        lane = "#FFFFFF"
        dash = "#B7BEC7"
        text = "#111111"
        muted = "#6E7781"
        distractor = "#DADDE1"
        ego_color = "#2F3640"
        connector = "#B4B4B4"

        def panel_heading(ax: plt.Axes, letter: str, title: str) -> None:
            ax.text(0.00, 1.018, letter, transform=ax.transAxes, ha="left", va="bottom", fontsize=9.4, fontweight="bold", color="black")
            ax.text(0.085, 1.018, title, transform=ax.transAxes, ha="left", va="bottom", fontsize=7.9, fontweight="bold", color="black")

        def draw_car(ax: plt.Axes, cx: float, cy: float, color: str, edge: str, scale: float = 1.0, z: float = 4) -> None:
            w, h = 0.070 * scale, 0.135 * scale
            car = FancyBboxPatch(
                (cx - w / 2, cy - h / 2),
                w,
                h,
                boxstyle="round,pad=0.005,rounding_size=0.020",
                facecolor=color,
                edgecolor=edge,
                linewidth=0.75,
                transform=ax.transAxes,
                zorder=z,
                clip_on=False,
            )
            ax.add_patch(car)
            cabin_color = "#F7F7F7" if color != ego_color else "#5B6472"
            cabin = FancyBboxPatch(
                (cx - 0.23 * w, cy - 0.23 * h),
                0.46 * w,
                0.46 * h,
                boxstyle="round,pad=0.002,rounding_size=0.010",
                facecolor=cabin_color,
                edgecolor=edge,
                linewidth=0.45,
                transform=ax.transAxes,
                zorder=z + 0.1,
                clip_on=False,
            )
            ax.add_patch(cabin)
            ax.plot([cx - 0.18 * w, cx + 0.18 * w], [cy + 0.28 * h, cy + 0.28 * h], color=edge, linewidth=0.45, transform=ax.transAxes, zorder=z + 0.2)

        def draw_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], selected: bool = False) -> None:
            ax.add_patch(
                FancyArrowPatch(
                    start,
                    end,
                    transform=ax.transAxes,
                    arrowstyle="-|>",
                    mutation_scale=9.5 if selected else 7.0,
                    linewidth=1.55 if selected else 0.72,
                    linestyle="solid" if selected else (0, (3.2, 2.4)),
                    color=blue if selected else dash,
                    alpha=1.0 if selected else 0.78,
                    zorder=2,
                    clip_on=False,
                )
            )

        def label_two_lines(ax: plt.Axes, x: float, y0: float, label: str, value: float, selected: bool = False, ha: str = "left") -> None:
            value_color = blue if selected else text
            ax.text(x, y0 + 0.015, label, transform=ax.transAxes, ha=ha, va="bottom", fontsize=6.8, color=text, clip_on=False)
            ax.text(
                x,
                y0 - 0.010,
                f"{value:.2f}",
                transform=ax.transAxes,
                ha=ha,
                va="top",
                fontsize=7.1,
                color=value_color,
                fontweight="bold" if selected else "normal",
                clip_on=False,
            )

        node_pos = {
            "ego": (0.500, 0.150),
            "same lane": (0.500, 0.550),
            "far leader": (0.500, 0.835),
            "left lane": (0.315, 0.425),
            "right lane": (0.685, 0.355),
        }
        label_pos = {
            "far leader": (0.610, 0.830, "left", "far leader"),
            "same lane": (0.610, 0.550, "left", "same lane"),
            "left lane": (0.190, 0.423, "right", "left lane"),
            "right lane": (0.795, 0.355, "left", "right lane"),
        }

        def draw_road_scene(ax: plt.Axes, title: str, scores: dict[str, float], selected: str, letter: str) -> None:
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            panel_heading(ax, letter, title)
            ax.add_patch(Rectangle((0.245, 0.055), 0.510, 0.855, transform=ax.transAxes, facecolor=road, edgecolor=road_edge, linewidth=0.85, zorder=0))
            for lx in (0.415, 0.585):
                ax.plot([lx, lx], [0.065, 0.900], transform=ax.transAxes, color=lane, linewidth=1.05, linestyle=(0, (6, 4)), zorder=1)
            ax.plot([0.245, 0.245], [0.055, 0.910], transform=ax.transAxes, color=road_edge, linewidth=0.90, zorder=1)
            ax.plot([0.755, 0.755], [0.055, 0.910], transform=ax.transAxes, color=road_edge, linewidth=0.90, zorder=1)

            ego_xy = node_pos["ego"]
            for name in ["far leader", "same lane", "left lane", "right lane"]:
                sx, sy = ego_xy
                tx, ty = node_pos[name]
                draw_arrow(ax, (sx, sy + 0.065), (tx, ty - 0.070), selected=(name == selected))

            for name in ["far leader", "same lane", "left lane", "right lane"]:
                x, y0 = node_pos[name]
                if name == selected:
                    draw_car(ax, x, y0, blue, "#063F78", z=5)
                else:
                    draw_car(ax, x, y0, distractor, "#777777", z=4)

            ex, ey = ego_xy
            draw_car(ax, ex, ey, ego_color, "#171A1F", z=6)
            ax.text(ex, 0.041, "ego", transform=ax.transAxes, ha="center", va="top", fontsize=6.9, color=text)

            for name in ["far leader", "same lane", "left lane", "right lane"]:
                lx, ly, ha, lab = label_pos[name]
                label_two_lines(ax, lx, ly, lab, scores[name], selected=(name == selected), ha=ha)

        def draw_dumbbell(ax: plt.Axes) -> None:
            labels = ["same lane", "left lane", "far leader", "right lane"]
            y = np.arange(len(labels))[::-1]

            ax.text(-0.155, 1.018, "c", transform=ax.transAxes, ha="left", va="bottom", fontsize=9.4, fontweight="bold", color="black")
            ax.text(-0.040, 1.018, "Target-probability shift", transform=ax.transAxes, ha="left", va="bottom", fontsize=7.9, fontweight="bold", color="black")

            ax.set_xlim(-0.015, 1.005)
            ax.set_ylim(-0.55, 3.55)
            ax.set_yticks(y)
            ax.set_yticklabels(labels)
            ax.set_xticks([0, 0.25, 0.50, 0.75, 1.00])
            ax.set_xticklabels(["0", "0.25", "0.50", "0.75", "1.00"])
            ax.set_xlabel("target probability", labelpad=5)
            ax.grid(axis="x", color="#D8DDE3", linestyle=(0, (2, 2.2)), linewidth=0.55)
            ax.set_axisbelow(True)
            for side in ["top", "right"]:
                ax.spines[side].set_visible(False)
            ax.spines["left"].set_color("#555555")
            ax.spines["bottom"].set_color("#555555")
            ax.spines["left"].set_linewidth(0.70)
            ax.spines["bottom"].set_linewidth(0.70)
            ax.tick_params(axis="both", length=2.8, width=0.65, color="#555555")

            for i, lab in enumerate(labels):
                yy = y[i]
                xf = follow[lab]
                xl = lane_left[lab]
                ax.plot([min(xf, xl), max(xf, xl)], [yy, yy], color=connector, linewidth=1.55, zorder=1)
                ax.scatter(xf, yy, s=38, marker="o", facecolor=blue, edgecolor="#063F78", linewidth=0.6, zorder=3, label="follow leader" if i == 0 else None)
                ax.scatter(xl, yy, s=38, marker="D", facecolor=light_blue, edgecolor="#567FA4", linewidth=0.6, zorder=3, label="lane change left" if i == 0 else None)

            row_map = {lab: y[i] for i, lab in enumerate(labels)}
            for row, x, txt in [
                ("same lane", follow["same lane"], "0.85"),
                ("same lane", lane_left["same lane"], "0.25"),
                ("left lane", follow["left lane"], "0.04"),
                ("left lane", lane_left["left lane"], "0.70"),
            ]:
                ax.text(x, row_map[row] + 0.16, txt, ha="center", va="bottom", fontsize=6.8, color=text)
            ax.text(0.035, row_map["far leader"] + 0.16, "0.04-0.09", ha="left", va="bottom", fontsize=6.4, color=muted)
            ax.text(0.035, row_map["right lane"] + 0.16, "0.01-0.02", ha="left", va="bottom", fontsize=6.4, color=muted)

            handles = [
                Line2D([0], [0], marker="o", linestyle="none", markersize=5.0, markerfacecolor=blue, markeredgecolor="#063F78", label="follow leader"),
                Line2D([0], [0], marker="D", linestyle="none", markersize=4.8, markerfacecolor=light_blue, markeredgecolor="#567FA4", label="lane change left"),
            ]
            ax.legend(handles=handles, frameon=False, loc="lower right", handletextpad=0.45, borderpad=0.2, labelspacing=0.35)

        fig = plt.figure(figsize=(7.16, 2.55), dpi=300)
        gs = fig.add_gridspec(1, 3, width_ratios=[1.00, 1.00, 1.42], wspace=0.44)
        ax_a = fig.add_subplot(gs[0, 0])
        ax_b = fig.add_subplot(gs[0, 1])
        ax_c = fig.add_subplot(gs[0, 2])

        draw_road_scene(ax_a, "q: follow leader", follow, "same lane", "a")
        draw_road_scene(ax_b, "q: lane change left", lane_left, "left lane", "b")
        draw_dumbbell(ax_c)

        fig.subplots_adjust(left=0.038, right=0.990, top=0.905, bottom=0.165)
        save_figure(fig, "fig_query_guided_attention", 183, 65, [source_name])


def plot_pop_ghost_tracking() -> None:
    rows = [
        {"stage": "active update", "time_s": 0.00, "mode": "TRACK", "measurement": 1, "belief_x_m": 0.00, "belief_y_m": 4.0, "truth_x_m": 0.00, "truth_y_m": 4.1, "nis": 3.2, "sigma_m": 0.35, "controller": "track"},
        {"stage": "ghost prediction", "time_s": 0.55, "mode": "GHOST", "measurement": 0, "belief_x_m": 0.25, "belief_y_m": 8.7, "truth_x_m": 0.45, "truth_y_m": 9.1, "nis": 12.4, "sigma_m": 1.10, "controller": "slow"},
        {"stage": "re-association", "time_s": 1.10, "mode": "RESET", "measurement": 1, "belief_x_m": 0.85, "belief_y_m": 13.0, "truth_x_m": 0.95, "truth_y_m": 13.2, "nis": 21.5, "sigma_m": 0.55, "controller": "recover"},
        {"stage": "prolonged loss boundary", "time_s": 1.55, "mode": "SAFE STOP", "measurement": 0, "belief_x_m": 1.10, "belief_y_m": 15.2, "truth_x_m": 1.35, "truth_y_m": 15.7, "nis": 24.2, "sigma_m": 1.45, "controller": "stop"},
    ]
    source_name = "fig_pop_ghost_tracking_source.csv"
    write_schematic_source(source_name, rows)

    import runpy

    build_fig3_v9 = runpy.run_path(str(Path(__file__).with_name("fig3_final_submission_ready_v9.py")))["build_and_save"]

    FIGS.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_FIGS.mkdir(parents=True, exist_ok=True)
    fig = build_fig3_v9(str(FIGS / "fig_pop_ghost_tracking"))
    plt.close(fig)
    for suffix in EXPORTS:
        path = FIGS / f"fig_pop_ghost_tracking{suffix}"
        shutil.copy2(path, MANUSCRIPT_FIGS / path.name)
    AUDIT_ROWS.append(
        {
            "figure": "fig_pop_ghost_tracking",
            "width_mm": "183.0",
            "height_mm": "195.5",
            "source_files": source_name,
            "outputs": "; ".join([f"fig_pop_ghost_tracking{suffix}" for suffix in EXPORTS]),
            "font_contract": "pdf.fonttype=42; svg.fonttype=none; text editable",
        }
    )
    return

    rows = [
        {"stage": "active update", "time_s": 0.00, "mode": "TRACK", "measurement": 1, "belief_x_m": 0.00, "belief_y_m": 4.0, "truth_x_m": 0.00, "truth_y_m": 4.1, "nis": 3.2, "sigma_m": 0.35, "controller": "track"},
        {"stage": "ghost prediction", "time_s": 0.55, "mode": "GHOST", "measurement": 0, "belief_x_m": 0.25, "belief_y_m": 8.7, "truth_x_m": 0.45, "truth_y_m": 9.1, "nis": 12.0, "sigma_m": 1.10, "controller": "slow"},
        {"stage": "re-association", "time_s": 1.10, "mode": "RESET", "measurement": 1, "belief_x_m": 0.85, "belief_y_m": 13.0, "truth_x_m": 0.95, "truth_y_m": 13.2, "nis": 21.5, "sigma_m": 0.55, "controller": "recover"},
        {"stage": "prolonged loss boundary", "time_s": 1.55, "mode": "SAFE STOP", "measurement": 0, "belief_x_m": 1.10, "belief_y_m": 15.2, "truth_x_m": 1.35, "truth_y_m": 15.7, "nis": 24.0, "sigma_m": 1.45, "controller": "stop"},
    ]
    source_name = "fig_pop_ghost_tracking_source.csv"
    write_schematic_source(source_name, rows)
    df = pd.DataFrame(rows)

    fig = plt.figure(figsize=(mm(183), mm(118)))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.10, 0.82], width_ratios=[1.0, 1.0, 1.0, 1.18])
    snapshot_axes = [fig.add_subplot(gs[0, i]) for i in range(3)]
    ax_state = fig.add_subplot(gs[0, 3])
    ax_timeline = fig.add_subplot(gs[1, :])

    def draw_car(ax: plt.Axes, x: float, y: float, face: str, edge: str, label: str = "") -> None:
        ax.add_patch(Rectangle((x - 0.42, y - 0.95), 0.84, 1.90, facecolor=face, edgecolor=edge, linewidth=0.55))
        ax.add_patch(FancyArrowPatch((x, y + 0.15), (x, y + 1.25), arrowstyle="-|>", mutation_scale=8, linewidth=0.55, color=edge))
        if label:
            ax.text(x, y - 1.25, label, ha="center", va="top", fontsize=4.6, color=COLORS["text"])

    def draw_rotated_vehicle(
        ax: plt.Axes,
        x: float,
        y: float,
        heading_deg: float,
        face: str,
        edge: str,
        label: str = "",
        alpha: float = 1.0,
        linestyle: str = "-",
        linewidth: float = 0.82,
        zorder: int = 5,
        label_xy: tuple[float, float] | None = None,
        label_color: str | None = None,
    ) -> None:
        width, length = 1.55, 3.35
        theta = math.radians(heading_deg)
        c, s = math.cos(theta), math.sin(theta)
        rot = np.array([[c, -s], [s, c]])
        body = np.array(
            [
                [-width / 2, -length / 2],
                [width / 2, -length / 2],
                [width / 2, length / 2],
                [-width / 2, length / 2],
            ]
        )
        corners = body @ rot.T + np.array([x, y])
        ax.add_patch(
            Polygon(
                corners,
                closed=True,
                facecolor=face,
                edgecolor=edge,
                linewidth=linewidth,
                linestyle=linestyle,
                alpha=alpha,
                zorder=zorder,
            )
        )
        ax.add_patch(
            FancyArrowPatch(
                (x, y + 0.05),
                (x + 0.22 * s, y + 2.15 * c),
                arrowstyle="-|>",
                mutation_scale=9,
                linewidth=linewidth,
                color=edge,
                alpha=alpha,
                zorder=zorder + 1,
            )
        )
        ax.plot(x, y, "o", color=edge, markersize=2.3, alpha=alpha, zorder=zorder + 2)
        if label:
            lx, ly = label_xy if label_xy is not None else (x, y - length / 2 - 0.70)
            ax.text(
                lx,
                ly,
                label,
                ha="center",
                va="top",
                fontsize=5.0,
                color=label_color or COLORS["text"],
                bbox=dict(facecolor="white", alpha=0.78, edgecolor="none", pad=0.2),
                zorder=zorder + 3,
            )

    def setup_reference_tracking_axis(ax: plt.Axes, show_ylabel: bool = False) -> None:
        ax.set_xlim(-4.0, 4.0)
        ax.set_ylim(-2.0, 22.0)
        ax.set_aspect("equal")
        ax.set_xticks(np.arange(-4, 5, 2))
        ax.set_yticks(np.arange(0, 23, 5))
        ax.tick_params(labelsize=4.8, length=1.8, pad=1.2)
        ax.set_xlabel("lateral position (m)", fontsize=5.0, labelpad=1.2)
        if show_ylabel:
            ax.set_ylabel("longitudinal position (m)", fontsize=5.0, labelpad=1.4)
        else:
            ax.set_yticklabels([])
        ax.grid(True, which="major", color="#E1E4E8", linewidth=0.35)
        ax.set_axisbelow(True)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(0.65)
            spine.set_color("#1C1F23")
        ax.axvline(-3.5, color="#1C1F23", linewidth=0.85)
        ax.axvline(3.5, color="#1C1F23", linewidth=0.85)
        ax.plot([0, 0], [-2.0, 22.0], color="#8B929A", linestyle=(0, (5, 5)), linewidth=0.55)

    def draw_active_tracking_reference(ax: plt.Axes, letter: str, title: str) -> None:
        setup_reference_tracking_axis(ax, show_ylabel=True)
        ax.plot([0.0, 0.0], [0.0, 4.0], color=COLORS["qgip"], linewidth=0.72, alpha=0.78)
        ax.plot(0.0, 0.0, marker="x", color=COLORS["qgip"], markersize=3.0, markeredgewidth=0.70)
        draw_rotated_vehicle(
            ax,
            0.0,
            4.0,
            heading_deg=5.0,
            face="#A9CBE8",
            edge=COLORS["qgip"],
            label=r"$\mathbf{z}_k$ (obs)",
        )
        ax.text(
            -2.55,
            17.05,
            "Sensor: ON",
            color=COLORS["qgip"],
            fontweight="bold",
            fontsize=5.2,
            ha="left",
            va="center",
            bbox=dict(facecolor="white", edgecolor=COLORS["qgip"], linewidth=0.55, boxstyle="round,pad=0.20", alpha=0.95),
            zorder=10,
        )
        panel_label(ax, letter, title, x=-0.18)

    def draw_ghost_prediction_reference(ax: plt.Axes, letter: str, title: str) -> None:
        setup_reference_tracking_axis(ax, show_ylabel=False)
        ax.add_patch(
            Rectangle(
                (-4.0, 6.0),
                8.0,
                14.0,
                facecolor="#F2F3F4",
                edgecolor="#111111",
                hatch="\\\\",
                linewidth=0.35,
                alpha=0.35,
                zorder=0,
            )
        )
        ax.text(
            0.0,
            16.6,
            "OCCLUSION ZONE",
            ha="center",
            va="center",
            fontsize=4.55,
            color="#555B61",
            fontweight="bold",
            bbox=dict(facecolor="white", edgecolor="#D4D8DD", linewidth=0.35, boxstyle="round,pad=0.15", alpha=0.92),
            zorder=12,
        )
        draw_rotated_vehicle(
            ax,
            0.50,
            9.00,
            heading_deg=5.0,
            face="none",
            edge="#333333",
            alpha=0.46,
            linestyle=":",
            linewidth=0.62,
            zorder=4,
        )
        ax.annotate(
            "Ground truth",
            xy=(0.78, 12.0),
            xytext=(1.75, 14.0),
            arrowprops=dict(arrowstyle="->", color="#333333", linewidth=0.45, shrinkA=1, shrinkB=1),
            ha="left",
            va="center",
            fontsize=4.8,
            color="#333333",
            bbox=dict(facecolor="white", alpha=0.82, edgecolor="none", pad=0.15),
            zorder=13,
        )
        ax.add_patch(
            Ellipse(
                (0.20, 8.80),
                width=2.45,
                height=4.25,
                angle=5.0,
                facecolor=COLORS["noquery"],
                edgecolor=COLORS["noquery"],
                linestyle=":",
                linewidth=0.55,
                alpha=0.14,
                zorder=2,
            )
        )
        draw_rotated_vehicle(
            ax,
            0.20,
            8.80,
            heading_deg=5.0,
            face="none",
            edge=COLORS["noquery"],
            alpha=0.95,
            linestyle="--",
            linewidth=0.75,
            zorder=5,
        )
        ax.text(
            0.80,
            5.0,
            r"$\hat{\mathbf{x}}_{k+1|k}$ (ghost)",
            ha="left",
            va="top",
            fontsize=4.8,
            color=COLORS["noquery"],
            bbox=dict(facecolor="white", alpha=0.80, edgecolor="none", pad=0.12),
            zorder=13,
        )
        ax.text(2.60, 6.85, r"$3\sigma$", color=COLORS["noquery"], fontsize=4.6, fontweight="bold", zorder=13)
        ax.text(
            1.75,
            2.05,
            "Kalman\npropagate",
            fontsize=4.7,
            color=COLORS["noquery"],
            ha="center",
            va="center",
            linespacing=0.95,
            bbox=dict(facecolor="white", alpha=0.78, edgecolor="none", pad=0.15),
            zorder=13,
        )
        panel_label(ax, letter, title, x=-0.18)

    def draw_reassociation_reference(ax: plt.Axes, letter: str, title: str) -> None:
        setup_reference_tracking_axis(ax, show_ylabel=False)
        ax.plot([0.0, 0.20, 1.20], [4.0, 8.8, 14.0], color=COLORS["qgip"], linestyle="-", linewidth=0.75, alpha=0.50, zorder=2)
        draw_rotated_vehicle(
            ax,
            0.60,
            13.80,
            heading_deg=5.0,
            face="none",
            edge=COLORS["noquery"],
            alpha=0.68,
            linestyle="--",
            linewidth=0.72,
            zorder=4,
        )
        draw_rotated_vehicle(
            ax,
            1.20,
            14.00,
            heading_deg=2.0,
            face="#A9CBE8",
            edge=COLORS["qgip"],
            linewidth=0.82,
            zorder=6,
        )
        ax.add_patch(
            FancyArrowPatch(
                (0.60, 13.80),
                (1.20, 14.00),
                arrowstyle="<->",
                mutation_scale=7,
                linewidth=0.55,
                color="#111111",
                zorder=9,
            )
        )
        ax.text(
            1.45,
            11.55,
            r"$\mathbf{z}_{k+2}$ (obs)",
            ha="center",
            va="top",
            fontsize=4.9,
            color=COLORS["text"],
            bbox=dict(facecolor="white", alpha=0.80, edgecolor="none", pad=0.10),
            zorder=12,
        )
        ax.text(
            3.05,
            13.20,
            "IoU match\n" + r"$> \tau$",
            fontsize=4.7,
            ha="center",
            va="center",
            color=COLORS["text"],
            linespacing=0.90,
            bbox=dict(facecolor="white", alpha=0.78, edgecolor="none", pad=0.10),
            zorder=12,
        )
        panel_label(ax, letter, title, x=-0.18)

    def draw_snapshot(ax: plt.Axes, idx: int, letter: str, title: str) -> None:
        if idx == 0:
            draw_active_tracking_reference(ax, letter, title)
            return
        if idx == 1:
            draw_ghost_prediction_reference(ax, letter, title)
            return
        if idx == 2:
            draw_reassociation_reference(ax, letter, title)
            return
        row = df.iloc[idx]
        ax.set_xlim(-4.2, 4.2)
        ax.set_ylim(-0.8, 18.5)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.add_patch(Rectangle((-3.6, -0.6), 7.2, 19.0, facecolor="#F7F8FA", edgecolor="#ADB7C2", linewidth=0.60))
        ax.plot([0, 0], [-0.6, 18.4], color="#9CA7B2", linewidth=0.55, linestyle=(0, (5, 4)))
        ax.plot([-3.6, -3.6], [-0.6, 18.4], color="#8F99A3", linewidth=0.80)
        ax.plot([3.6, 3.6], [-0.6, 18.4], color="#8F99A3", linewidth=0.80)
        draw_car(ax, 0.0, 0.8, "#334E68", "#26323D", "ego")
        bx = float(row["belief_x_m"])
        by = float(row["belief_y_m"])
        tx = float(row["truth_x_m"])
        ty = float(row["truth_y_m"])
        sigma = float(row["sigma_m"])
        if idx == 1:
            ax.add_patch(Rectangle((-2.9, 6.0), 5.8, 10.7, facecolor="#FFFFFF", edgecolor="#B7BFC8", linewidth=0.45, hatch="///", alpha=0.75))
            ax.text(0, 15.4, "occlusion zone", ha="center", va="center", fontsize=5.0, color=COLORS["muted"])
        ax.add_patch(Ellipse((bx, by), width=1.25 + sigma, height=2.0 + 1.35 * sigma, facecolor="#EAF7F2", edgecolor=COLORS["success"], linewidth=0.65, alpha=0.90))
        draw_car(ax, bx, by, "#DDEEE3" if idx != 1 else "#F6E6C8", COLORS["success"] if idx != 1 else COLORS["noquery"], "belief")
        ax.plot(tx, ty, marker="o", markersize=2.6, color="#111111")
        ax.text(tx + 0.35, ty + 0.35, "truth", fontsize=4.5, color=COLORS["muted"], ha="left")
        if int(row["measurement"]):
            ax.add_patch(Rectangle((tx - 0.58, ty - 1.10), 1.16, 2.20, fill=False, edgecolor=COLORS["qgip"], linewidth=0.75))
            ax.text(tx - 0.65, ty - 1.40, "z(obs)", fontsize=4.5, color=COLORS["qgip"], ha="right")
        else:
            ax.add_patch(Rectangle((bx - 0.62, by - 1.15), 1.24, 2.30, fill=False, edgecolor=COLORS["noquery"], linewidth=0.70, linestyle="--"))
            ax.text(bx + 0.75, by - 1.40, "ghost", fontsize=4.5, color=COLORS["noquery"], ha="left")
        panel_label(ax, letter, title, x=-0.13)
        ax.text(-3.35, 0.25, str(row["controller"]), fontsize=4.7, color=COLORS["muted"], ha="left")

    draw_snapshot(snapshot_axes[0], 0, "a", "Active tracking")
    draw_snapshot(snapshot_axes[1], 1, "b", "Ghost prediction")
    draw_snapshot(snapshot_axes[2], 2, "c", "Re-association")

    ax_state.set_axis_off()
    ax_state.set_xlim(0, 1)
    ax_state.set_ylim(0, 1)
    panel_label(ax_state, "d", "Hybrid POP state", x=-0.08)
    state_boxes = [
        (0.10, 0.72, 0.78, 0.13, "Reliable update", r"$NIS_t \leq \tau_{soft}$", "#EAF7F2", COLORS["success"]),
        (0.10, 0.50, 0.78, 0.13, "Conservative update", r"$\tau_{soft}<NIS_t\leq\tau_{hard}$", "#FFF4DC", COLORS["noquery"]),
        (0.10, 0.28, 0.78, 0.13, "Ghost prediction", "measurement missing or rejected", "#F8EFEF", COLORS["hard"]),
        (0.10, 0.06, 0.78, 0.13, "Reset / safe stop", "recovery or prolonged loss", "#F5F7FA", "#65717F"),
    ]
    for x, y, w, h, title, body, face, edge in state_boxes:
        ax_state.add_patch(Rectangle((x, y), w, h, facecolor=face, edgecolor=edge, linewidth=0.62))
        ax_state.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=5.6, fontweight="bold", color=COLORS["text"])
        ax_state.text(x + w / 2, y + h * 0.28, body, ha="center", va="center", fontsize=4.7, color=COLORS["muted"])
    for y0, y1 in [(0.72, 0.63), (0.50, 0.41), (0.28, 0.19)]:
        draw_arrow(ax_state, (0.49, y0), (0.49, y1), color="#59616D")

    times = df["time_s"].astype(float).to_numpy()
    nis = df["nis"].astype(float).to_numpy()
    ax_timeline.axhspan(12.0, 20.0, color="#FFF4DC", linewidth=0)
    ax_timeline.axhspan(20.0, max(nis) + 3.0, color="#F8EFEF", linewidth=0)
    ax_timeline.plot(times, nis, color=COLORS["monitor"], linewidth=0.95, marker="o", markersize=3.0)
    ax_timeline.axhline(12.0, color=COLORS["noquery"], linestyle="--", linewidth=0.70)
    ax_timeline.axhline(20.0, color=COLORS["hard"], linestyle=":", linewidth=0.85)
    for _, row in df.iterrows():
        x = float(row["time_s"])
        y = float(row["nis"])
        ax_timeline.text(x, y + 1.15, str(row["mode"]), ha="center", va="bottom", fontsize=5.0, color=COLORS["text"])
    for x0, x1 in [(0.35, 0.88), (1.35, 1.60)]:
        ax_timeline.axvspan(x0, x1, color="#E9EDF2", linewidth=0, zorder=0)
    ax_timeline.set_xlabel("time in a perception-failure episode (s)")
    ax_timeline.set_ylabel("NIS")
    ax_timeline.set_ylim(0, max(nis) + 5.0)
    ax_timeline.set_xlim(-0.08, 1.68)
    clean_axis(ax_timeline, grid=True)
    panel_label(ax_timeline, "e", "Mode-labelled belief reaches control", x=-0.04)
    ax_timeline.legend(
        handles=[
            Line2D([0], [0], color=COLORS["monitor"], marker="o", linewidth=0.9, label="NIS trace"),
            Line2D([0], [0], color=COLORS["noquery"], linestyle="--", linewidth=0.7, label=r"$\tau_{soft}$"),
            Line2D([0], [0], color=COLORS["hard"], linestyle=":", linewidth=0.85, label=r"$\tau_{hard}$"),
        ],
        loc="upper left",
        ncol=3,
        handlelength=1.4,
        columnspacing=1.0,
    )

    fig.subplots_adjust(left=0.045, right=0.985, top=0.90, bottom=0.12, wspace=0.34, hspace=0.52)
    save_figure(fig, "fig_pop_ghost_tracking", 183, 118, [source_name])


def plot_main_target_selection_nature() -> None:
    attention = read_source("fig_query_guided_attention_source.csv")
    pairwise = read_source("pairwise_stats_combined.csv")
    metrics = read_source("figure_stress_leader_metrics.csv")
    source_name = "fig_main_target_selection_nature_source.csv"
    rows: list[dict[str, object]] = []
    rows.extend(attention.to_dict("records"))
    rows.extend(pairwise[pairwise["suite"] == "ambiguity300"].to_dict("records"))
    rows.extend(metrics[metrics["condition_id"].isin(["fp_10", "idswitch"])].to_dict("records"))
    write_schematic_source(source_name, rows)

    fig = plt.figure(figsize=(mm(183), mm(106)))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.05, 1.22, 1.05])
    ax_scene = fig.add_subplot(gs[0, 0])
    ax_gain = fig.add_subplot(gs[0, 1])
    ax_wrong = fig.add_subplot(gs[0, 2])

    ax_scene.set_xlim(-4.8, 4.8)
    ax_scene.set_ylim(-2.4, 20.5)
    ax_scene.set_aspect("equal")
    ax_scene.set_xticks([])
    ax_scene.set_yticks([])
    for spine in ax_scene.spines.values():
        spine.set_visible(False)
    ax_scene.add_patch(Rectangle((-4.2, -2.0), 8.4, 22.0, facecolor="#EEF1F4", edgecolor="#BFC8D2", linewidth=0.55))
    for xline in [-1.4, 1.4]:
        ax_scene.plot([xline, xline], [-2.0, 20.0], color="white", linewidth=0.85, linestyle=(0, (5.0, 5.0)))
    ax_scene.plot([-4.2, -4.2], [-2.0, 20.0], color="#9EA9B3", linewidth=0.75)
    ax_scene.plot([4.2, 4.2], [-2.0, 20.0], color="#9EA9B3", linewidth=0.75)
    sub = attention[attention["mode"] == "follow leader"].copy()
    ego = sub[sub["object"] == "ego"].iloc[0]
    candidates = sub[sub["object"] != "ego"].sort_values("attention")
    for _, row in candidates.iterrows():
        attn = float(row["attention"])
        selected = bool(int(row["selected"]))
        ax_scene.add_patch(
            FancyArrowPatch(
                (float(ego["lateral_m"]), float(ego["longitudinal_m"]) + 0.95),
                (float(row["lateral_m"]), float(row["longitudinal_m"]) - 0.95),
                arrowstyle="-|>",
                mutation_scale=6 + 6 * attn,
                linewidth=0.35 + 2.25 * attn,
                alpha=0.22 + 0.72 * attn,
                color=COLORS["qgip"] if selected else "#9AA3AD",
                shrinkA=3,
                shrinkB=3,
            )
        )
    for _, row in sub.iterrows():
        x = float(row["lateral_m"])
        y = float(row["longitudinal_m"])
        if row["object"] == "ego":
            face = "#334E68"
            label = "ego"
            edge = "#26323D"
        else:
            selected = bool(int(row["selected"]))
            face = COLORS["qgip"] if selected else "#F5D7A9"
            edge = COLORS["qgip"] if selected else "#E1A650"
            label = f"{float(row['attention']):.2f}"
        ax_scene.add_patch(Rectangle((x - 0.45, y - 0.85), 0.90, 1.70, facecolor=face, edgecolor=edge, linewidth=0.45))
        ax_scene.add_patch(FancyArrowPatch((x, y + 0.25), (x, y + 1.15), arrowstyle="-|>", mutation_scale=7, linewidth=0.45, color=edge))
        ax_scene.text(x, y, label, ha="center", va="center", fontsize=4.3, color="white" if face in (COLORS["qgip"], "#334E68") else COLORS["text"], fontweight="bold")
    panel_label(ax_scene, "a", "Ambiguous object-list scene", x=-0.10)

    rows_gain = pairwise[pairwise["suite"] == "ambiguity300"].copy()
    rows_gain["label"] = rows_gain.apply(
        lambda r: f"{COND_LABELS.get(str(r['condition_id']), r['condition_id'])} vs {METHOD_LABELS.get(str(r['comparison_method']), r['comparison_method']).replace(chr(10), ' ')}",
        axis=1,
    )
    rows_gain = rows_gain.sort_values(["condition_id", "comparison_method"])
    y = np.arange(len(rows_gain))
    val = rows_gain["leaderacc_diff_ref_minus_cmp"].astype(float).to_numpy() * 100.0
    low = rows_gain["leaderacc_diff_ci95_low"].astype(float).to_numpy() * 100.0
    high = rows_gain["leaderacc_diff_ci95_high"].astype(float).to_numpy() * 100.0
    ax_gain.axvline(0, color="#747C85", linewidth=0.55)
    ax_gain.hlines(y, low, high, color="#85909A", linewidth=0.85)
    ax_gain.plot(val, y, "o", color=COLORS["qgip"], markersize=4.0)
    for yi, value in zip(y, val):
        ax_gain.text(value + 1.2, yi, f"+{value:.1f}", fontsize=5.1, va="center", color=COLORS["text"])
    ax_gain.set_yticks(y)
    ax_gain.set_yticklabels(rows_gain["label"])
    ax_gain.invert_yaxis()
    ax_gain.set_xlabel("LeaderAcc gain (percentage points)")
    ax_gain.set_xlim(20, 50)
    clean_axis(ax_gain, grid=True, axis="x")
    panel_label(ax_gain, "b", "Paired target-selection gain", x=-0.12)
    axis_note(ax_gain, "N=300 paired episodes; whiskers, 95% bootstrap CI", loc="lower right")

    subset = metrics[metrics["condition_id"].isin(["fp_10", "idswitch"])].copy()
    method_colors = {"rule": COLORS["rule"], "qgip_no_query": COLORS["noquery"], "std_kf": COLORS["stdkf"], "qgip": COLORS["qgip"]}
    method_labels = {"rule": "Rule", "qgip_no_query": "No query", "std_kf": "Std KF", "qgip": "QGIP-Net"}
    cond_order = ["fp_10", "idswitch"]
    for yi, condition in enumerate(cond_order):
        group = subset[subset["condition_id"] == condition].copy()
        xs = group["wrongleaderframes_mean"].astype(float).to_numpy()
        ax_wrong.hlines(yi, xs.min(), xs.max(), color="#B8C0C8", linewidth=0.85, zorder=1)
        for _, row in group.iterrows():
            method = str(row["method"])
            xval = float(row["wrongleaderframes_mean"])
            ax_wrong.plot(xval, yi, "o", color=method_colors.get(method, "#777777"), markersize=4.2, zorder=3)
    ax_wrong.set_yticks(np.arange(len(cond_order)))
    ax_wrong.set_yticklabels(["FP10", "ID switch"])
    ax_wrong.set_xlabel("wrong-leader frames / episode")
    ax_wrong.set_xlim(0, 330)
    clean_axis(ax_wrong, grid=True, axis="x")
    panel_label(ax_wrong, "c", "Wrong-target exposure", x=-0.16)
    ax_wrong.set_ylim(-0.55, 1.55)
    ax_wrong.legend(
        handles=[
            Line2D([0], [0], marker="o", linestyle="none", color=method_colors["qgip"], label="QGIP-Net", markersize=3.6),
            Line2D([0], [0], marker="o", linestyle="none", color=method_colors["qgip_no_query"], label="No query", markersize=3.6),
            Line2D([0], [0], marker="o", linestyle="none", color=method_colors["std_kf"], label="Std KF", markersize=3.6),
            Line2D([0], [0], marker="o", linestyle="none", color=method_colors["rule"], label="Rule", markersize=3.6),
        ],
        loc="upper right",
        handlelength=0.8,
        borderpad=0.1,
    )

    fig.subplots_adjust(left=0.06, right=0.985, top=0.84, bottom=0.20, wspace=0.55)
    save_figure(
        fig,
        "fig_main_target_selection_nature",
        183,
        106,
        ["fig_query_guided_attention_source.csv", "pairwise_stats_combined.csv", "figure_stress_leader_metrics.csv", source_name],
    )


def plot_main_safety_availability_nature() -> None:
    df = read_source("main_benchmark_source.csv")
    source_name = "fig_main_safety_availability_nature_source.csv"
    write_schematic_source(source_name, df.to_dict("records"))
    fig = plt.figure(figsize=(mm(183), mm(95)))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.40, 0.70, 1.05])
    ax_stack = fig.add_subplot(gs[0, 0])
    ax_bound = fig.add_subplot(gs[0, 1])
    ax_scatter = fig.add_subplot(gs[0, 2])

    df = df.copy()
    df["display"] = df["method"].map(lambda v: METHOD_LABELS.get(v, str(v)).replace("\n", " "))
    df = df.set_index("method").loc[METHOD_ORDER].reset_index()
    y = np.arange(len(df))
    success = df["success_rate"].astype(float).to_numpy() * 100
    lost = df["lost_rate"].astype(float).to_numpy() * 100
    collision = df["collision_rate"].astype(float).to_numpy() * 100
    ax_stack.barh(y, success, color=COLORS["success"], edgecolor="white", linewidth=0.35, label="success")
    ax_stack.barh(y, lost, left=success, color="#D8DADD", edgecolor="white", linewidth=0.35, label="fail-safe Lost")
    ax_stack.barh(y, collision, left=success + lost, color=COLORS["collision"], edgecolor="white", linewidth=0.35, label="collision")
    ax_stack.set_yticks(y)
    ax_stack.set_yticklabels(df["display"])
    ax_stack.invert_yaxis()
    ax_stack.set_xlim(0, 100)
    ax_stack.set_xlabel("episodes (%)")
    clean_axis(ax_stack, grid=True, axis="x")
    panel_label(ax_stack, "a", "Route outcome decomposes safety and availability", x=-0.12)
    ax_stack.legend(loc="lower right", ncol=3, handlelength=1.0, columnspacing=0.8)

    Ns = np.array([300, 100])
    bounds = 3.0 / Ns * 100
    ax_bound.plot(bounds, [1, 0], "o", color=COLORS["qgip"], markersize=4.2)
    ax_bound.hlines([1, 0], 0, bounds, color=COLORS["qgip"], linewidth=0.9)
    ax_bound.set_yticks([1, 0])
    ax_bound.set_yticklabels(["N=300", "N=100"])
    ax_bound.set_xlim(0, 3.4)
    ax_bound.set_xlabel("rule-of-three upper bound (%)")
    clean_axis(ax_bound, grid=True, axis="x")
    panel_label(ax_bound, "b", "Zero observed is finite-sample", x=-0.18)
    for yy, b in zip([1, 0], bounds):
        ax_bound.text(b + 0.08, yy, f"{b:.1f}%", va="center", fontsize=5.3)

    x = lost
    yval = np.where(df["collision"].astype(float).to_numpy() == 0, 3.0 / df["n"].astype(float).to_numpy() * 100, collision)
    colors = [COLORS["qgip"] if "QGIP" in m else COLORS["collision"] if c > 0 else "#A9B0B7" for m, c in zip(df["method"], collision)]
    ax_scatter.scatter(x, yval, s=34, color=colors, edgecolor="black", linewidth=0.3, zorder=3)
    for xi, yi, label in zip(x, yval, df["display"]):
        ax_scatter.text(xi + 1.2, yi + 0.12, label, fontsize=4.9, ha="left", va="bottom")
    ax_scatter.set_xlabel("fail-safe Lost (%)")
    ax_scatter.set_ylabel("collision rate or upper bound (%)")
    ax_scatter.set_xlim(0, max(x) + 7)
    ax_scatter.set_ylim(0, max(yval) * 1.18)
    clean_axis(ax_scatter, grid=True)
    for text in list(ax_scatter.texts):
        text.remove()
    panel_label(ax_scatter, "c", "Availability cost vs collision bound", x=-0.14)
    for xi, yi, label in zip(x, yval, df["display"]):
        if label in ("QGIP-Net", "E2E (no MPC)", "Modular PID"):
            ax_scatter.text(xi + 1.0, yi + (0.8 if yi < 5 else 1.5), label, fontsize=4.9, ha="left", va="bottom")

    fig.subplots_adjust(left=0.10, right=0.985, top=0.84, bottom=0.20, wspace=0.58)
    save_figure(fig, "fig_main_safety_availability_nature", 183, 95, ["main_benchmark_source.csv", source_name])


def plot_main_nis_diagnostic_nature() -> None:
    noise = read_source("carla_nis_noise_sweep_qgip100_summary.csv")
    outlier = read_source("carla_nis_outlier_qgip100_summary.csv")
    trace = read_source("fig_pop_ghost_tracking_source.csv")
    source_name = "fig_main_nis_diagnostic_nature_source.csv"
    rows: list[dict[str, object]] = []
    rows.extend(trace.to_dict("records"))
    rows.extend(noise.to_dict("records"))
    rows.extend(outlier.to_dict("records"))
    write_schematic_source(source_name, rows)

    fig = plt.figure(figsize=(mm(183), mm(108)))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.18, 1.0, 1.18])
    ax_trace = fig.add_subplot(gs[0, 0])
    ax_noise = fig.add_subplot(gs[0, 1])
    ax_out = fig.add_subplot(gs[0, 2])

    t = trace["time_s"].astype(float).to_numpy()
    nis = trace["nis"].astype(float).to_numpy()
    ax_trace.axhspan(12, 20, color="#FFF4DC", linewidth=0)
    ax_trace.axhspan(20, max(nis) + 4, color="#F8EFEF", linewidth=0)
    ax_trace.plot(t, nis, color=COLORS["monitor"], marker="o", linewidth=0.9, markersize=3.4)
    ax_trace.axhline(12, color=COLORS["noquery"], linestyle="--", linewidth=0.65)
    ax_trace.axhline(20, color=COLORS["hard"], linestyle=":", linewidth=0.8)
    for _, row in trace.iterrows():
        ax_trace.text(float(row["time_s"]), float(row["nis"]) + 1.0, str(row["mode"]), ha="center", va="bottom", fontsize=5.0)
    ax_trace.set_xlabel("episode time (s)")
    ax_trace.set_ylabel("NIS")
    ax_trace.set_ylim(0, max(nis) + 5)
    clean_axis(ax_trace, grid=True)
    panel_label(ax_trace, "a", "Mode-labelled NIS trace", x=-0.14)

    noise = noise.copy()
    noise["noise_m"] = noise["condition_id"].str.extract(r"noise_(\d+)").astype(float) / 10.0
    noise = noise.sort_values("noise_m")
    ax_noise.plot(noise["noise_m"], noise["nisp95_mean"], color=COLORS["qgip"], marker="o", linewidth=0.9, markersize=3.8)
    ax_noise.fill_between(noise["noise_m"], noise["nisp95_mean"], noise["nisp95_p95"], color=COLORS["qgip_light"], linewidth=0)
    ax_noise.axhline(12, color=COLORS["noquery"], linestyle="--", linewidth=0.65)
    ax_noise.axhline(20, color=COLORS["hard"], linestyle=":", linewidth=0.8)
    ax_noise.set_xlabel("Gaussian position noise (m)")
    ax_noise.set_ylabel("episode NIS p95")
    clean_axis(ax_noise, grid=True)
    panel_label(ax_noise, "b", "Residuals grow with continuous noise", x=-0.16)

    out = outlier.copy()
    out_order = ["fp_10", "idswitch_20", "fp10_idswitch20_noise05"]
    out = out.set_index("condition_id").loc[out_order].reset_index()
    yy = np.arange(len(out))
    ax_out.set_xscale("log")
    ax_out.hlines(yy, out["nisp95_mean"], out["nisp95_p95"], color="#9BA5AF", linewidth=0.85)
    ax_out.plot(out["nisp95_mean"], yy, "o", color=COLORS["qgip"], markersize=4.0, label="mean")
    ax_out.plot(out["nisp95_p95"], yy, "D", color=COLORS["hard"], markersize=3.5, label="episode p95")
    ax_out.axvline(12, color=COLORS["noquery"], linestyle="--", linewidth=0.65)
    ax_out.axvline(20, color=COLORS["hard"], linestyle=":", linewidth=0.8)
    ax_out.set_yticks(yy)
    ax_out.set_yticklabels(["FP10", "ID20", "Combo"])
    ax_out.invert_yaxis()
    ax_out.set_xlabel("NIS p95 (log scale)")
    clean_axis(ax_out, grid=True, axis="x")
    panel_label(ax_out, "c", "Outlier perturbations expose inconsistency", x=-0.14)
    for yi, resets, p95 in zip(yy, out["kfhardresets_mean"].astype(float), out["nisp95_p95"].astype(float)):
        ax_out.text(p95 * 1.10, yi, f"{resets:.0f} resets", fontsize=4.8, color=COLORS["hard"], va="center")
    ax_out.text(
        0.04,
        0.035,
        "circle, mean\n diamond, episode p95",
        transform=ax_out.transAxes,
        fontsize=4.7,
        color=COLORS["muted"],
        ha="left",
        va="bottom",
    )

    fig.subplots_adjust(left=0.07, right=0.96, top=0.82, bottom=0.20, wspace=0.48)
    save_figure(
        fig,
        "fig_main_nis_diagnostic_nature",
        183,
        108,
        ["fig_pop_ghost_tracking_source.csv", "carla_nis_noise_sweep_qgip100_summary.csv", "carla_nis_outlier_qgip100_summary.csv", source_name],
    )


def plot_nature_system_evidence() -> None:
    read_source("fig_nature_system_evidence_source.csv")
    fig, ax = plt.subplots(figsize=(mm(183), mm(126)), constrained_layout=False)
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    blue = COLORS["qgip"]
    green = COLORS["success"]
    orange = COLORS["noquery"]
    neutral = TOP["gray"]
    soft_blue = TOP["blue_bg"]
    soft_green = TOP["teal_light"]
    soft_orange = TOP["copper_light"]
    soft_neutral = TOP["panel"]

    def arrow(
        start: tuple[float, float],
        end: tuple[float, float],
        dashed: bool = False,
        color: str = TOP["charcoal"],
        lw: float = 0.70,
        rad: float = 0.0,
    ) -> None:
        ax.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=7.5,
                linewidth=lw,
                linestyle=(0, (3, 2)) if dashed else "solid",
                color=color,
                shrinkA=2,
                shrinkB=2,
                connectionstyle=f"arc3,rad={rad}",
            )
        )

    def module_box(
        x: float,
        y: float,
        w: float,
        h: float,
        title: str,
        body: str,
        face: str,
        edge: str,
        tag: str | None = None,
    ) -> None:
        ax.add_patch(Rectangle((x, y), w, h, facecolor=face, edgecolor=edge, linewidth=0.70))
        ax.add_patch(Rectangle((x, y + h - 0.026), w, 0.026, facecolor=edge, edgecolor=edge, linewidth=0.0, alpha=0.90))
        ax.text(x + w * 0.50, y + h * 0.62, title, ha="center", va="center", fontsize=5.7, fontweight="bold", color=COLORS["text"], linespacing=0.90)
        ax.text(x + w * 0.50, y + h * 0.30, body, ha="center", va="center", fontsize=4.6, color=COLORS["muted"], linespacing=0.92)
        if tag:
            ax.text(x + w - 0.006, y + h - 0.013, tag, ha="right", va="center", fontsize=4.0, color="white", fontweight="bold")

    def panel_frame(x: float, y: float, w: float, h: float, letter: str, title: str) -> None:
        ax.add_patch(Rectangle((x, y), w, h, facecolor=TOP["paper"], edgecolor=TOP["gray_light"], linewidth=0.55))
        ax.text(x - 0.002, y + h + 0.020, letter, fontsize=8, fontweight="bold", ha="left", va="bottom")
        ax.text(x + 0.033, y + h + 0.021, title, fontsize=6.2, fontweight="bold", ha="left", va="bottom", color=COLORS["text"])

    ax.text(0.018, 0.965, "a", fontsize=8, fontweight="bold", ha="left", va="top")
    ax.text(0.055, 0.966, "QGIP-Net target-belief-to-control architecture", fontsize=7.2, fontweight="bold", ha="left", va="top")

    ax.add_patch(Rectangle((0.018, 0.510), 0.964, 0.350, facecolor=TOP["paper"], edgecolor=TOP["gray_light"], linewidth=0.58))
    ax.add_patch(Rectangle((0.018, 0.807), 0.964, 0.053, facecolor=TOP["blue_bg"], edgecolor="none"))
    ax.add_patch(Rectangle((0.018, 0.510), 0.964, 0.050, facecolor=TOP["teal_light"], edgecolor="none"))
    ax.text(0.032, 0.835, "learned target selection", fontsize=5.6, fontweight="bold", color=COLORS["muted"], ha="left", va="center")
    ax.text(0.032, 0.535, "auditable belief and control interface", fontsize=5.6, fontweight="bold", color=COLORS["muted"], ha="left", va="center")

    boxes = [
        (0.035, 0.650, 0.135, 0.120, "Object-list /\nego-state interface", "IDs, boxes,\nrelative state", soft_neutral, neutral, None),
        (0.195, 0.650, 0.145, 0.120, "Intent-conditioned\nscene graph", "query + lane\nrelations", soft_blue, blue, "learned"),
        (0.365, 0.650, 0.145, 0.120, "Query-guided\nGNN", "attention + leader\ndistribution", soft_blue, blue, "learned"),
        (0.535, 0.650, 0.155, 0.120, "POP / NIS-KF\nbelief", "track / ghost /\ndegraded / reset", soft_green, green, "belief"),
        (0.715, 0.650, 0.145, 0.120, "Lattice MPC", "collision filtering\n+ cost selection", soft_orange, orange, "control"),
        (0.885, 0.650, 0.095, 0.120, "ACC action", "track / slow\n/ stop", soft_neutral, neutral, None),
    ]
    for item in boxes:
        module_box(*item)
    for left, right in zip(boxes[:-1], boxes[1:]):
        arrow((left[0] + left[2], 0.710), (right[0], 0.710))

    ax.plot([0.932, 0.932, 0.055, 0.055], [0.650, 0.575, 0.575, 0.650], color=TOP["gray"], linewidth=0.62, linestyle=(0, (3, 2)))
    arrow((0.055, 0.575), (0.055, 0.650), dashed=True, color=TOP["gray"], lw=0.62)
    ax.text(0.330, 0.592, "closed-loop feedback", fontsize=4.7, color=COLORS["muted"], ha="left", va="center")
    arrow((0.612, 0.650), (0.475, 0.488), dashed=True, color=green, lw=0.62, rad=0.06)
    arrow((0.786, 0.650), (0.845, 0.488), dashed=True, color=orange, lw=0.62, rad=-0.05)
    ax.text(0.575, 0.602, "NIS gating", fontsize=4.7, color=green, ha="center")
    ax.text(0.817, 0.618, "candidate filter", fontsize=4.7, color=orange, ha="center")

    panel_frame(0.035, 0.150, 0.285, 0.255, "b", "Leader attention")
    road_x0, road_y0, road_w, road_h = 0.057, 0.182, 0.117, 0.180
    ax.add_patch(Rectangle((road_x0, road_y0), road_w, road_h, facecolor=TOP["panel"], edgecolor=TOP["gray_light"], linewidth=0.45))
    for frac in (0.33, 0.66):
        ax.plot([road_x0 + road_w * frac, road_x0 + road_w * frac], [road_y0, road_y0 + road_h], color="white", linewidth=0.70, linestyle=(0, (5, 4)))
    vehicle_specs = [
        (0.50, 0.15, "ego", TOP["charcoal"]),
        (0.50, 0.70, "0.95", blue),
        (0.17, 0.58, "0.10", TOP["copper_light"]),
        (0.82, 0.84, "0.05", TOP["copper_light"]),
    ]
    for vx, vy, label, color in vehicle_specs:
        x = road_x0 + road_w * vx - 0.010
        y = road_y0 + road_h * vy - 0.012
        ax.add_patch(Rectangle((x, y), 0.020, 0.024, facecolor=color, edgecolor=TOP["ink"], linewidth=0.35))
        ax.text(x + 0.010, y + 0.012, label, ha="center", va="center", fontsize=3.6, color="white" if color in (blue, TOP["charcoal"]) else COLORS["text"], fontweight="bold")
    arrow((road_x0 + road_w * 0.50, road_y0 + road_h * 0.23), (road_x0 + road_w * 0.50, road_y0 + road_h * 0.62), color=blue, lw=0.75)
    ax.text(0.190, 0.340, "query: follow leader", fontsize=4.6, color=COLORS["muted"], ha="left")
    ax.text(0.190, 0.300, "lane-consistent leader\ngets highest probability", fontsize=4.8, color=COLORS["text"], ha="left", linespacing=1.0)
    ax.text(0.190, 0.218, "learning selects target;\ncontrol does not consume\nraw detections directly", fontsize=4.4, color=COLORS["muted"], ha="left", linespacing=1.0)

    panel_frame(0.360, 0.150, 0.285, 0.255, "c", "POP / NIS-KF modes")
    mode_titles = [("reliable", "update"), ("ghost", "predict"), ("degraded", "hold / slow"), ("reset", "recover")]
    mode_x = [0.382, 0.446, 0.510, 0.574]
    mode_faces = [soft_green, TOP["copper_light"], TOP["brick_light"], soft_green]
    mode_edges = [green, orange, TOP["brick"], green]
    for i, ((title, body), x, face, edge) in enumerate(zip(mode_titles, mode_x, mode_faces, mode_edges)):
        ax.add_patch(Rectangle((x, 0.245), 0.052, 0.080, facecolor=face, edgecolor=edge, linewidth=0.55, linestyle="--" if title == "ghost" else "solid"))
        ax.text(x + 0.026, 0.297, title, ha="center", va="center", fontsize=4.6, fontweight="bold", color=COLORS["text"])
        ax.text(x + 0.026, 0.266, body, ha="center", va="center", fontsize=4.1, color=COLORS["muted"])
        if i < len(mode_x) - 1:
            arrow((x + 0.052, 0.285), (mode_x[i + 1], 0.285), dashed=(title == "ghost"), color=green if i == 0 else neutral, lw=0.55)
    ax.add_patch(Rectangle((0.390, 0.180), 0.034, 0.035, facecolor=TOP["charcoal"], edgecolor=TOP["ink"], linewidth=0.35))
    ax.add_patch(Rectangle((0.586, 0.180), 0.034, 0.035, facecolor=TOP["charcoal"], edgecolor=TOP["ink"], linewidth=0.35))
    ax.plot([0.407, 0.407], [0.215, 0.245], color=green, linewidth=0.65)
    ax.plot([0.603, 0.603], [0.215, 0.245], color=green, linewidth=0.65)
    ax.text(0.384, 0.350, "NIS residuals choose update,\nprediction, degradation, or recovery.", fontsize=4.7, color=COLORS["muted"], ha="left", linespacing=1.0)

    panel_frame(0.685, 0.150, 0.295, 0.255, "d", "MPC feasibility filtering")

    def map_d(px: float, py: float) -> tuple[float, float]:
        return 0.715 + 0.205 * px, 0.202 + 0.130 * py

    for py in (0.12, 0.50, 0.88):
        x0, y0 = map_d(0.0, py)
        x1, y1 = map_d(1.0, py)
        ax.plot([x0, x1], [y0, y1], color=TOP["gray_mid"], linewidth=0.45, linestyle="--" if py == 0.50 else "solid")
    xs = np.linspace(0, 1, 70)
    selected = 0.50 + 0.12 * np.sin(xs * 1.55 * np.pi)
    candidate = 0.50 - 0.36 * (1 - np.cos(xs * np.pi)) / 2
    rejected = 0.50 + 0.40 * (1 - np.cos(xs * np.pi)) / 2
    for ys, color, style, lw in [
        (selected, blue, "solid", 0.90),
        (candidate, TOP["gray_mid"], (0, (4, 2)), 0.62),
        (rejected, COLORS["collision"], (0, (1.2, 2.0)), 0.75),
    ]:
        pts = [map_d(float(x), float(y)) for x, y in zip(xs, ys)]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, linewidth=lw, linestyle=style)
    ox, oy = map_d(0.73, 0.64)
    ax.add_patch(Rectangle((ox - 0.010, oy - 0.026), 0.020, 0.052, facecolor=TOP["brick_light"], edgecolor=COLORS["collision"], linewidth=0.45))
    ex0, ey0 = map_d(0.62, 0.43)
    ex1, ey1 = map_d(0.90, 0.88)
    ax.add_patch(Rectangle((ex0, ey0), ex1 - ex0, ey1 - ey0, fill=False, edgecolor=COLORS["collision"], linewidth=0.55, linestyle="--"))
    ax.text(0.717, 0.354, "selected", fontsize=4.2, color=blue, ha="left")
    ax.text(0.778, 0.354, "candidate", fontsize=4.2, color=COLORS["muted"], ha="left")
    ax.text(0.850, 0.354, "rejected", fontsize=4.2, color=COLORS["collision"], ha="left")
    ax.text(0.710, 0.178, "collision-infeasible rollouts are rejected\nbefore ACC track / slow / stop output", fontsize=4.6, color=COLORS["muted"], ha="left", linespacing=1.0)

    legend_y = 0.055
    legend_items = [
        (0.175, blue, soft_blue, "learned target selection"),
        (0.385, green, soft_green, "probabilistic belief / POP"),
        (0.615, orange, soft_orange, "symbolic planning / control"),
    ]
    for x, edge, face, label in legend_items:
        ax.add_patch(Rectangle((x, legend_y - 0.012), 0.018, 0.018, facecolor=face, edgecolor=edge, linewidth=0.65))
        ax.text(x + 0.024, legend_y - 0.003, label, fontsize=4.8, color=COLORS["muted"], ha="left", va="center")
    ax.plot([0.820, 0.850], [legend_y - 0.003, legend_y - 0.003], color=TOP["gray"], linewidth=0.75, linestyle=(0, (3, 2)))
    ax.text(0.857, legend_y - 0.003, "gating / ghost prediction / feedback", fontsize=4.8, color=COLORS["muted"], ha="left", va="center")

    fig.subplots_adjust(left=0.018, right=0.988, top=0.965, bottom=0.040)
    save_figure(fig, "fig_nature_system_evidence", 183, 126, ["fig_nature_system_evidence_source.csv"])


def plot_evidence_coverage_matrix() -> None:
    import runpy

    builder = runpy.run_path(str(Path(__file__).with_name("fig4_claim_support_matrix_only_v3.py")))["build_matrix_only"]
    for out_dir in (FIGS, MANUSCRIPT_FIGS):
        fig = builder(str(out_dir / "fig_evidence_coverage_matrix"))
        plt.close(fig)
    return

    df = read_source("fig_evidence_coverage_matrix_source.csv")
    support_df = df[df["panel"] == "a_protocol_to_claim_matrix"].copy()
    trace_df = df[df["panel"] == "b_evidence_inventory"].copy()
    support_df["strength"] = pd.to_numeric(support_df["strength_code"], errors="coerce").fillna(0).astype(int)
    group_rows = [
        ("Simulation protocols", "Nominal and blackout benchmarks"),
        ("Simulation protocols", "Primary ambiguity tests"),
        ("Simulation protocols", "Layered detector/timing/raw-like stress"),
        ("Simulation protocols", "NIS noise and outlier diagnostics"),
        ("Audit / provenance", "ODD and split control"),
        ("Audit / provenance", "Statistical and claim traceability"),
        ("Audit / provenance", "Figure/table/source-data QA"),
        ("Readiness boundary", "ROS2 and pre-real-robot readiness"),
    ]
    present = set(support_df["evidence_family"].astype(str))
    families = [family for _, family in group_rows if family in present]
    families += [name for name in dict.fromkeys(support_df["evidence_family"].astype(str)) if name not in families]
    axes = [
        "ODD / split",
        "target consistency",
        "finite-sample safety",
        "uncertainty response",
        "reproducibility / provenance",
        "pre-real-robot readiness",
    ]
    axes = [axis for axis in axes if axis in set(support_df["claim_axis_label"].astype(str))]
    matrix = (
        support_df.pivot_table(index="evidence_family", columns="claim_axis_label", values="strength", aggfunc="max")
        .reindex(index=families, columns=axes)
        .fillna(0)
    )
    codes = (
        support_df.pivot_table(index="evidence_family", columns="claim_axis_label", values="cell_code", aggfunc="first")
        .reindex(index=families, columns=axes)
        .fillna("")
    )

    fig = plt.figure(figsize=(mm(183), mm(126)), constrained_layout=False)
    gs = fig.add_gridspec(2, 1, height_ratios=[4.45, 1.20], hspace=0.42)
    ax = fig.add_subplot(gs[0, 0])

    group_lookup = {family: group for group, family in group_rows}
    group_spans: list[tuple[str, int, int]] = []
    start = 0
    current = group_lookup.get(families[0], "Evidence") if families else "Evidence"
    for idx, family in enumerate(families + ["__sentinel__"]):
        group = group_lookup.get(family, "__sentinel__")
        if group != current:
            group_spans.append((current, start, idx - 1))
            start = idx
            current = group

    for group_idx, (group_name, y0, y1) in enumerate(group_spans):
        if group_idx % 2 == 0:
            ax.add_patch(
                Rectangle(
                    (-0.72, y0 - 0.46),
                    len(axes) + 0.44,
                    y1 - y0 + 0.92,
                    facecolor="#F7F9FB",
                    edgecolor="none",
                    zorder=0,
                )
            )
        ax.axhline(y1 + 0.50, color="#D4DAE1", linewidth=0.45, zorder=1)
        ax.text(
            -1.62,
            (y0 + y1) / 2,
            group_name,
            ha="right",
            va="center",
            fontsize=5.3,
            fontweight="bold",
            color=COLORS["muted"],
        )

    marker_style = {
        3: dict(s=116, facecolors=COLORS["qgip"], edgecolors="#0B3556", linewidths=0.55),
        2: dict(s=92, facecolors="#AFCDE3", edgecolors="#316B96", linewidths=0.50),
        1: dict(s=78, facecolors="white", edgecolors="#7B8794", linewidths=0.75),
    }
    ax.set_xlim(-0.5, matrix.shape[1] - 0.5)
    ax.set_ylim(matrix.shape[0] - 0.5, -0.5)
    for yi, family in enumerate(families):
        for xi, axis_name in enumerate(axes):
            strength = int(matrix.loc[family, axis_name])
            if strength == 0:
                continue
            ax.scatter([xi], [yi], marker="o", zorder=3, **marker_style[strength])
            code = str(codes.loc[family, axis_name])
            label_color = "white" if strength == 3 else COLORS["text"]
            ax.text(xi, yi, code, ha="center", va="center", fontsize=5.1, color=label_color, fontweight="bold", zorder=4)

    ax.set_xticks(np.arange(len(axes)))
    ax.set_xticklabels([wrap_label(v, 15) for v in axes], rotation=30, ha="right", rotation_mode="anchor")
    ax.xaxis.tick_top()
    ax.tick_params(axis="x", top=True, bottom=False, labeltop=True, labelbottom=False, length=0, pad=4)
    ax.set_yticks(np.arange(len(families)))
    ax.set_yticklabels([wrap_label(v, 28) for v in families], fontsize=5.0)
    ax.tick_params(axis="y", length=0, pad=3)
    for xi in range(matrix.shape[1]):
        ax.axvline(xi, color="#EEF1F4", linewidth=0.42, zorder=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    panel_label(ax, "a", "Claim-support contract", x=-0.20)

    handles = [
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=COLORS["qgip"], markeredgecolor="#0B3556", markersize=5.8, label="D  direct evidence"),
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="#AFCDE3", markeredgecolor="#316B96", markersize=5.2, label="S  supporting evidence"),
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="white", markeredgecolor="#7B8794", markersize=4.9, label="C  contextual / boundary"),
    ]
    ax.legend(handles=handles, ncol=3, loc="lower center", bbox_to_anchor=(0.54, -0.19), frameon=False, handlelength=1.0, columnspacing=1.2)

    ax_c = fig.add_subplot(gs[1, 0])
    ax_c.set_axis_off()
    ax_c.set_xlim(0, 1)
    ax_c.set_ylim(0, 1)
    trace_df["trace_count"] = pd.to_numeric(trace_df["strength_code"], errors="coerce").fillna(0)
    trace_order = ["statistical checks", "pre-real-robot gates", "registered protocols", "safety-case nodes", "claim-evidence rows"]
    trace_df["_order"] = trace_df["evidence_family"].map({name: idx for idx, name in enumerate(trace_order)})
    trace_df = trace_df.sort_values(["_order", "evidence_family"])
    ax_c.text(0.010, 0.92, "b", fontsize=8, fontweight="bold", ha="left", va="top")
    ax_c.text(0.055, 0.92, "Traceability records", fontsize=7, fontweight="bold", ha="left", va="top")
    ax_c.plot([0.055, 0.965], [0.70, 0.70], color=COLORS["grid"], linewidth=0.55)
    ax_c.plot([0.055, 0.965], [0.22, 0.22], color=COLORS["grid"], linewidth=0.55)
    xs = np.linspace(0.115, 0.905, len(trace_df))
    for idx, (x, row) in enumerate(zip(xs, trace_df.itertuples(index=False))):
        ax_c.text(x, 0.515, f"{int(row.trace_count)}", ha="center", va="center", fontsize=10.5, fontweight="bold", color=COLORS["qgip"])
        ax_c.text(x, 0.335, wrap_label(row.evidence_family, 16), ha="center", va="center", fontsize=5.25, color=COLORS["muted"], linespacing=0.95)
        if idx < len(xs) - 1:
            mid = (xs[idx] + xs[idx + 1]) / 2
            ax_c.plot([mid, mid], [0.285, 0.635], color=COLORS["grid"], linewidth=0.50)
    fig.subplots_adjust(left=0.315, right=0.985, top=0.83, bottom=0.10)
    save_figure(fig, "fig_evidence_coverage_matrix", 183, 126, ["fig_evidence_coverage_matrix_source.csv"])


def plot_simulation_stress_atlas() -> None:
    import runpy

    builder = runpy.run_path(str(Path(__file__).with_name("fig5_stress_suite_discriminators_v3.py")))["build_figure"]
    for out_dir in (FIGS, MANUSCRIPT_FIGS):
        fig = builder(str(out_dir / "fig5_stress_suite_discriminators_v3"))
        plt.close(fig)
    return

    df = read_source("fig_simulation_stress_atlas_source.csv")
    fig = plt.figure(figsize=(mm(183), mm(126)), constrained_layout=False)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.06, 1.38], height_ratios=[1.0, 1.0], hspace=0.46, wspace=0.36)

    ax_a = fig.add_subplot(gs[:, 0])
    ax_a.set_axis_off()
    ax_a.set_xlim(0, 1)
    ax_a.set_ylim(0, 1)
    a = df[df["panel"] == "a_evidence_scale"].copy()
    a["value"] = pd.to_numeric(a["value"])
    design_order = ["nominal", "main_blackout", "ambiguity", "detector_timing", "raw_like", "boundary", "nis_diagnostic"]
    a["order"] = a["evidence_id"].map({name: idx for idx, name in enumerate(design_order)})
    a = a.sort_values("order")
    panel_label(ax_a, "a", "Stress-suite design", x=-0.08)
    ax_a.text(0.02, 0.900, "family", fontsize=5.5, fontweight="bold", color=COLORS["muted"], ha="left")
    ax_a.text(0.39, 0.900, "scale", fontsize=5.5, fontweight="bold", color=COLORS["muted"], ha="left")
    ax_a.text(0.58, 0.900, "claim target", fontsize=5.5, fontweight="bold", color=COLORS["muted"], ha="left")
    target_map = {
        "nominal": "shared-controller\nsanity check",
        "main_blackout": "blackout safety /\navailability",
        "ambiguity": "target-consistency\nprimary test",
        "detector_timing": "fault-layer\ncoverage",
        "raw_like": "detector-level\ndegradation",
        "boundary": "combined-stress\nboundary",
        "nis_diagnostic": "uncertainty\nmonitor response",
    }
    face_map = {
        "ambiguity": "#EFF6FB",
        "nis_diagnostic": "#F8EEEE",
        "boundary": "#FBF4E8",
    }
    accent_map = {
        "ambiguity": COLORS["qgip"],
        "nis_diagnostic": COLORS["hard"],
        "boundary": COLORS["soft"],
    }
    max_rows = float(a["value"].max()) if not a.empty else 1.0
    y_positions = np.linspace(0.78, 0.16, len(a))
    for y, row in zip(y_positions, a.itertuples(index=False)):
        accent = accent_map.get(row.evidence_id)
        face = face_map.get(row.evidence_id, "white")
        ax_a.add_patch(Rectangle((0.015, y - 0.047), 0.950, 0.078, facecolor=face, edgecolor="none", zorder=0))
        ax_a.plot([0.015, 0.965], [y - 0.047, y - 0.047], color=COLORS["grid"], linewidth=0.45, zorder=1)
        if accent:
            ax_a.add_patch(Rectangle((0.015, y - 0.047), 0.008, 0.078, facecolor=accent, edgecolor="none", zorder=2))
        ax_a.text(
            0.035,
            y - 0.008,
            wrap_label(row.condition_label, 18),
            ha="left",
            va="center",
            fontsize=5.3,
            fontweight="bold" if accent else "normal",
            color=COLORS["text"],
            linespacing=0.90,
        )
        ax_a.text(0.405, y + 0.002, f"{int(row.value):,} rows", ha="left", va="center", fontsize=5.25, color=COLORS["text"])
        ax_a.add_patch(Rectangle((0.405, y - 0.034), 0.135, 0.008, facecolor=COLORS["grid"], edgecolor="none", zorder=1))
        ax_a.add_patch(
            Rectangle(
                (0.405, y - 0.034),
                0.135 * float(row.value) / max_rows,
                0.008,
                facecolor=accent if accent else "#B8C0C9",
                edgecolor="none",
                zorder=2,
            )
        )
        ax_a.text(0.595, y - 0.008, target_map.get(row.evidence_id, str(row.interpretation)), ha="left", va="center", fontsize=5.0, color=COLORS["muted"], linespacing=0.88)
    ax_a.plot([0.015, 0.965], [0.105, 0.105], color=COLORS["grid"], linewidth=0.45)
    ax_a.text(0.020, 0.052, "processed episode-method records", ha="left", va="bottom", fontsize=4.9, color=COLORS["muted"])

    ax_c = fig.add_subplot(gs[0, 1])
    c = df[(df["panel"] == "c_primary_ambiguity_effects") & (df["metric"] == "leaderacc_gain_pp")].copy()
    c = c.iloc[::-1]
    y = np.arange(len(c))
    values = c["value"].astype(float).to_numpy()
    err_low = values - c["ci_low"].astype(float).to_numpy()
    err_high = c["ci_high"].astype(float).to_numpy() - values
    ax_c.errorbar(values, y, xerr=[err_low, err_high], fmt="o", color=COLORS["qgip"], ecolor=COLORS["text"], elinewidth=0.75, capsize=2.3, markersize=3.8)
    ax_c.axvline(0, color="#7B8490", linestyle="--", linewidth=0.65)
    ax_c.set_yticks(y)
    ax_c.set_yticklabels([wrap_label(v.replace(" Std KF", ": Std KF").replace(" rule", ": rule").replace(" no query", ": no query"), 24) for v in c["condition_label"]])
    ax_c.set_xlabel("LeaderAcc gain vs comparator (percentage points)")
    ax_c.set_xlim(-2, max(c["ci_high"].astype(float)) + 6)
    for yi, row in enumerate(c.itertuples(index=False)):
        ax_c.text(float(row.ci_high) + 0.8, yi, f"{float(row.value):.1f}", va="center", ha="left", fontsize=5.0, color=COLORS["text"])
    clean_axis(ax_c, grid=True, axis="x")
    panel_label(ax_c, "b", "Primary ambiguity discriminator", x=-0.11)

    ax_d = fig.add_subplot(gs[1, 1])
    d = df[(df["panel"] == "d_nis_diagnostic_response") & (df["metric"] == "nisp95_mean")].copy()
    order = ["noise_02", "noise_05", "noise_10", "fp_10", "idswitch_20", "fp10_idswitch20_noise05"]
    d["order"] = d["condition_id"].map({k: i for i, k in enumerate(order)})
    d = d.sort_values("order")
    xs = np.arange(len(d))
    nis_values = d["value"].astype(float).to_numpy()
    point_colors = [COLORS["monitor"] if value < 20 else COLORS["hard"] for value in nis_values]
    for xi, value, color in zip(xs, nis_values, point_colors):
        ax_d.vlines(xi, 1.0, value, color=color, linewidth=1.35, alpha=0.9)
    ax_d.scatter(xs, nis_values, s=24, color=point_colors, edgecolor="black", linewidth=0.35, zorder=3)
    ax_d.set_yscale("log")
    ax_d.set_ylim(0.8, 3000)
    ax_d.axhline(12, color=COLORS["soft"], linestyle="--", linewidth=0.65)
    ax_d.axhline(20, color=COLORS["hard"], linestyle=":", linewidth=0.8)
    ax_d.text(0.985, 12 * 1.12, "soft gate", transform=ax_d.get_yaxis_transform(), ha="right", va="bottom", fontsize=5.0, color=COLORS["soft"])
    ax_d.text(0.985, 20 * 1.12, "hard gate", transform=ax_d.get_yaxis_transform(), ha="right", va="bottom", fontsize=5.0, color=COLORS["hard"])
    ax_d.set_ylabel("NIS p95, log scale")
    hard = df[(df["panel"] == "d_nis_diagnostic_response") & (df["metric"] == "nishardviolations_mean")]
    hard_values = [bar_value(hard, c, "nishardviolations_mean", 0.0) for c in d["condition_id"]]
    xtick_labels = [COND_LABELS.get(c, c) for c in d["condition_id"]]
    ax_d.set_xticks(xs)
    ax_d.set_xticklabels(xtick_labels, rotation=30, ha="right")
    ax_d.set_xlabel("perturbation condition")
    clean_axis(ax_d, grid=True, axis="y")
    for xi, hv in zip(xs, hard_values):
        ax_d.text(xi, 1.02, f"HV {hv:.1f}", ha="center", va="bottom", fontsize=4.7, color=COLORS["muted"], rotation=90)
    handles_d = [
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=COLORS["monitor"], markeredgecolor="black", markersize=4.2, label="below hard gate"),
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=COLORS["hard"], markeredgecolor="black", markersize=4.2, label="beyond hard gate"),
    ]
    ax_d.legend(handles=handles_d, loc="upper left", frameon=False, handlelength=1.0)
    panel_label(ax_d, "c", "Diagnostic boundary response", x=-0.11)
    fig.subplots_adjust(left=0.060, right=0.985, top=0.92, bottom=0.16)
    save_figure(fig, "fig_simulation_stress_atlas", 183, 126, ["fig_simulation_stress_atlas_source.csv"])


def parse_town_counts(value: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for chunk in str(value).split(";"):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        town, count = chunk.split(":", 1)
        counts[town.strip()] = int(float(count.strip()))
    return counts


def plot_extended_dataset_split() -> None:
    import runpy

    builder = runpy.run_path(str(Path(__file__).with_name("fig6_split_audit_matrix_only_v2.py")))["build_figure"]
    for out_dir in (FIGS, MANUSCRIPT_FIGS):
        fig = builder(str(out_dir / "fig6_split_audit_matrix_only_v2"))
        plt.close(fig)
    return

    df = read_source("final_dataset_split_check.csv")
    overlap = read_source("final_dataset_split_overlap.csv")
    split_order = ["train", "val", "test_unseen"]
    split_display = {"train": "train", "val": "validation", "test_unseen": "unseen test"}
    training_domain_towns = ["Town03", "Town04", "Town10HD"]
    heldout_town = "Town05"
    town_order = training_domain_towns + [heldout_town]
    available_towns = sorted({town for item in df["town_counts"] for town in parse_town_counts(item)})
    town_order += [town for town in available_towns if town not in town_order]

    rows = df.set_index("split").reindex(split_order)
    counts = pd.DataFrame(
        [
            {town: parse_town_counts(row["town_counts"]).get(town, 0) for town in town_order}
            for _, row in rows.iterrows()
        ],
        index=split_order,
    ).astype(int)
    totals = rows["n"].astype(int)
    missing = rows["missing_files"].astype(int)
    map_assignment_violations = int(counts.loc[["train", "val"], heldout_town].sum() + counts.loc["test_unseen", training_domain_towns].sum())
    pairwise_path_overlaps = int(overlap["overlap_paths"].astype(int).sum())

    fig = plt.figure(figsize=(mm(183), mm(70)))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.42, 1.0], wspace=0.10)
    ax_matrix = fig.add_subplot(gs[0, 0])
    ax_cards = fig.add_subplot(gs[0, 1])

    for i, split in enumerate(split_order):
        for j, town in enumerate(town_order):
            value = int(counts.loc[split, town])
            if value == 0:
                face = "white"
                edge = "#D7DCE2"
                label_color = "#9AA2AA"
                weight = "normal"
            elif town == heldout_town:
                face = COLORS["qgip"]
                edge = "#1E5C84"
                label_color = "white"
                weight = "bold"
            else:
                face = COLORS["qgip_light"]
                edge = "#B9C9D5"
                label_color = COLORS["text"]
                weight = "bold"
            rect = Rectangle(
                (j - 0.5, i - 0.5),
                1.0,
                1.0,
                facecolor=face,
                edgecolor=edge,
                linewidth=0.45,
            )
            ax_matrix.add_patch(rect)
            label = f"{value:,}" if value > 0 else "0"
            ax_matrix.text(j, i, label, ha="center", va="center", fontsize=5.4, color=label_color, fontweight=weight)

    ax_matrix.axvline(len(training_domain_towns) - 0.5, color="#4B5563", linestyle="--", linewidth=0.55)
    ax_matrix.set_xlim(-0.5, len(town_order) - 0.5)
    ax_matrix.set_ylim(len(split_order) - 0.5, -0.95)
    ax_matrix.set_xticks(np.arange(len(town_order)))
    ax_matrix.set_xticklabels(town_order)
    ax_matrix.xaxis.tick_top()
    ax_matrix.tick_params(axis="x", top=True, bottom=False, labeltop=True, labelbottom=False, length=0, pad=2)
    ax_matrix.set_yticks(np.arange(len(split_order)))
    ax_matrix.set_yticklabels([split_display[s] for s in split_order])
    ax_matrix.tick_params(axis="y", length=0)
    for spine in ax_matrix.spines.values():
        spine.set_visible(False)
    ax_matrix.text(-0.05, 1.28, "a", transform=ax_matrix.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax_matrix.text(0.0, 1.28, "Split-by-map audit matrix", transform=ax_matrix.transAxes, fontsize=7, fontweight="bold", ha="left", va="bottom")
    ax_matrix.text(0.37, 1.17, "training-domain maps", transform=ax_matrix.transAxes, ha="center", va="bottom", fontsize=5.2, color=COLORS["muted"])
    ax_matrix.text(0.88, 1.17, "held-out map", transform=ax_matrix.transAxes, ha="center", va="bottom", fontsize=5.2, color=COLORS["muted"])
    ax_matrix.text(
        -0.5,
        2.82,
        "cell values: split-manifest records",
        ha="left",
        va="center",
        fontsize=5.0,
        color=COLORS["muted"],
    )

    ax_cards.set_axis_off()
    ax_cards.text(-0.04, 1.28, "b", transform=ax_cards.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax_cards.text(0.12, 1.28, "Leakage and file QC", transform=ax_cards.transAxes, fontsize=7, fontweight="bold", ha="left", va="bottom")
    card_data = [
        (f"{int(totals.sum()):,}", "total records", "train 4,050; validation 450; unseen 500"),
        (str(int(missing.sum())), "missing files", "existing files equal N in all splits"),
        (
            " / ".join(str(int(v)) for v in overlap["overlap_paths"].astype(int)),
            "pairwise split overlaps",
            "train-val; train-test; val-test",
        ),
        (str(map_assignment_violations), "map-assignment violations", "Town05 only appears in unseen test"),
    ]
    y0 = 0.76
    dy = 0.225
    for idx, (value, label, detail) in enumerate(card_data):
        y_card = y0 - idx * dy
        ax_cards.add_patch(
            FancyBboxPatch(
                (0.02, y_card),
                0.96,
                0.17,
                transform=ax_cards.transAxes,
                boxstyle="round,pad=0.010,rounding_size=0.014",
                facecolor=COLORS["empty"],
                edgecolor=COLORS["grid"],
                linewidth=0.55,
            )
        )
        ax_cards.text(
            0.08,
            y_card + 0.096,
            value,
            transform=ax_cards.transAxes,
            ha="left",
            va="center",
            fontsize=8.7 if idx != 2 else 7.3,
            fontweight="bold",
            color=COLORS["qgip"] if idx == 0 else COLORS["text"],
        )
        ax_cards.text(
            0.39,
            y_card + 0.108,
            label,
            transform=ax_cards.transAxes,
            ha="left",
            va="center",
            fontsize=5.6,
            fontweight="bold",
            color=COLORS["text"],
        )
        ax_cards.text(
            0.39,
            y_card + 0.050,
            detail,
            transform=ax_cards.transAxes,
            ha="left",
            va="center",
            fontsize=4.9,
            color=COLORS["muted"],
        )

    fig.subplots_adjust(left=0.095, right=0.985, top=0.72, bottom=0.22)
    save_figure(fig, "fig_extended_dataset_split", 183, 70, ["final_dataset_split_check.csv", "final_dataset_split_overlap.csv"])


def plot_simulation_effect_size() -> None:
    import runpy

    builder = runpy.run_path(str(Path(__file__).with_name("fig7_main_result_final_v7.py")))["build_figure"]
    for out_dir in (FIGS, MANUSCRIPT_FIGS):
        fig = builder(str(out_dir / "fig7_main_result_final_v7"))
        plt.close(fig)
    return

    df = read_source("fig_simulation_effect_size_source.csv")
    metrics = read_source("figure_stress_leader_metrics.csv")
    benchmark = read_source("main_benchmark_source.csv")
    fig = plt.figure(figsize=(mm(183), mm(118)), constrained_layout=False)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.06, 1.0], height_ratios=[1.0, 1.0], hspace=0.58, wspace=0.44)

    ax_a = fig.add_subplot(gs[0, 0])
    panel_label(ax_a, "a", "Blackout route outcome")
    bench = benchmark.set_index("method").reindex(METHOD_ORDER).reset_index()
    y = np.arange(len(bench))
    success = bench["success_rate"].astype(float).to_numpy() * 100.0
    lost = bench["lost_rate"].astype(float).to_numpy() * 100.0
    collision = bench["collision_rate"].astype(float).to_numpy() * 100.0
    ax_a.barh(y, success, color=COLORS["success"], edgecolor="black", linewidth=0.25, label="success")
    ax_a.barh(y, lost, left=success, color=COLORS["lost"], edgecolor="black", linewidth=0.25, label="lost")
    ax_a.barh(y, collision, left=success + lost, color=COLORS["collision"], edgecolor="black", linewidth=0.25, label="collision")
    for yi, row, s, l, cval in zip(y, bench.itertuples(), success, lost, collision):
        total = int(row.n)
        if s > 14:
            ax_a.text(s / 2, yi, f"{int(row.success)}/{total}", ha="center", va="center", fontsize=4.6, color="white")
        if cval > 14:
            ax_a.text(s + l + cval / 2, yi, f"{int(row.collision)}/{total}", ha="center", va="center", fontsize=4.6, color="white")
    ax_a.set_xlim(0, 100)
    ax_a.set_yticks(y)
    ax_a.set_yticklabels([METHOD_LABELS.get(m, m) for m in bench["method"]])
    ax_a.invert_yaxis()
    ax_a.set_xlabel("route outcome (%)")
    clean_axis(ax_a, grid=True, axis="x")
    ax_a.legend(ncol=3, loc="lower left", bbox_to_anchor=(0.00, -0.34), handlelength=1.0, columnspacing=0.8)
    ax_a.text(
        0.99,
        1.02,
        "N=300; blind=1.0 s",
        transform=ax_a.transAxes,
        ha="right",
        va="bottom",
        fontsize=5.1,
        color=COLORS["muted"],
    )

    ax_b = fig.add_subplot(gs[0, 1])
    panel_label(ax_b, "b", "LeaderAcc dumbbell")
    leader_pairs = [
        ("FP10 vs no query", "fp_10", "No query"),
        ("FP10 vs rule", "fp_10", "Rule"),
        ("ID switch vs Std KF", "idswitch", "Std KF"),
        ("ID switch vs rule", "idswitch", "Rule"),
    ]
    leader_rows = []
    for label, condition, comparator in leader_pairs:
        qgip_value = float(metrics[(metrics["condition_id"] == condition) & (metrics["display"] == "QGIP")]["leaderacc_mean"].iloc[0]) * 100.0
        comp_value = float(metrics[(metrics["condition_id"] == condition) & (metrics["display"] == comparator)]["leaderacc_mean"].iloc[0]) * 100.0
        leader_rows.append({"label": label, "comparator": comp_value, "qgip": qgip_value, "gain": qgip_value - comp_value})
    leader_df = pd.DataFrame(leader_rows).iloc[::-1].reset_index(drop=True)
    yb = np.arange(len(leader_df))
    for yi, row in leader_df.iterrows():
        ax_b.plot([row["comparator"], row["qgip"]], [yi, yi], color="#B6BEC7", linewidth=1.2, zorder=1)
    ax_b.scatter(leader_df["comparator"], yb, s=24, facecolor="#E2E6EA", edgecolor=COLORS["rule"], linewidth=0.55, label="comparator", zorder=3)
    ax_b.scatter(leader_df["qgip"], yb, s=28, facecolor=COLORS["qgip"], edgecolor="white", linewidth=0.55, label="QGIP-Net", zorder=4)
    for yi, row in leader_df.iterrows():
        ax_b.text(row["qgip"] + 1.2, yi, f"+{row['gain']:.1f} pp", ha="left", va="center", fontsize=5.3, color=COLORS["qgip"], fontweight="bold")
    ax_b.set_xlim(35, 98)
    ax_b.set_yticks(yb)
    ax_b.set_yticklabels([wrap_label(v, 18) for v in leader_df["label"]])
    ax_b.set_xlabel("LeaderAcc (%)")
    clean_axis(ax_b, grid=True, axis="x")
    ax_b.legend(loc="center right", handletextpad=0.4)

    ax_c = fig.add_subplot(gs[1, 0])
    b = df[df["panel"] == "b_leaderacc_effect_size"].iloc[::-1].copy()
    y = np.arange(len(b))
    vals = b["value"].astype(float).to_numpy() * 100.0
    err = np.array([ci_values(row, 100.0) for _, row in b.iterrows()]).T
    ax_c.errorbar(vals, y, xerr=err, fmt="o", color=COLORS["qgip"], ecolor=COLORS["text"], elinewidth=0.70, capsize=2.1, markersize=3.4)
    ax_c.axvline(0, color="#9AA2AA", linewidth=0.55)
    for yi, (_, row) in enumerate(b.iterrows()):
        high = safe_float(row["ci_high"], safe_float(row["value"])) * 100.0
        value = safe_float(row["value"]) * 100.0
        ax_c.text(high + 0.9, yi, f"{value:.1f}", ha="left", va="center", fontsize=5.2, color=COLORS["qgip"])
    ax_c.set_yticks(y)
    ax_c.set_yticklabels([wrap_label(v, 18) for v in b["condition_label"]])
    ax_c.set_xlabel("LeaderAcc gain (percentage points)")
    ax_c.set_xlim(24, 57)
    clean_axis(ax_c, grid=True, axis="x")
    panel_label(ax_c, "c", "Paired-gain forest plot")

    ax_d = fig.add_subplot(gs[1, 1])
    panel_label(ax_d, "d", "ID-switch burden dumbbell")
    switch_pairs = [
        ("FP10 vs no query", "fp_10", "No query"),
        ("FP10 vs rule", "fp_10", "Rule"),
        ("ID switch vs Std KF", "idswitch", "Std KF"),
        ("ID switch vs rule", "idswitch", "Rule"),
    ]
    switch_rows = []
    for label, condition, comparator in switch_pairs:
        qgip_value = float(metrics[(metrics["condition_id"] == condition) & (metrics["display"] == "QGIP")]["idswitches_mean"].iloc[0])
        comp_value = float(metrics[(metrics["condition_id"] == condition) & (metrics["display"] == comparator)]["idswitches_mean"].iloc[0])
        switch_rows.append({"label": label, "comparator": comp_value, "qgip": qgip_value, "delta": qgip_value - comp_value})
    switch_df = pd.DataFrame(switch_rows).iloc[::-1].reset_index(drop=True)
    yd = np.arange(len(switch_df))
    for yi, row in switch_df.iterrows():
        line_color = COLORS["qgip"] if row["delta"] < 0 else COLORS["collision"]
        ax_d.plot([row["comparator"], row["qgip"]], [yi, yi], color=line_color, linewidth=1.2, alpha=0.85, zorder=1)
    ax_d.scatter(switch_df["comparator"], yd, s=24, facecolor="#E2E6EA", edgecolor=COLORS["rule"], linewidth=0.55, label="comparator", zorder=3)
    ax_d.scatter(switch_df["qgip"], yd, s=28, facecolor=COLORS["qgip"], edgecolor="white", linewidth=0.55, label="QGIP-Net", zorder=4)
    for yi, row in switch_df.iterrows():
        color = COLORS["qgip"] if row["delta"] < 0 else COLORS["collision"]
        ax_d.text(max(row["comparator"], row["qgip"]) + 6, yi, f"delta={row['delta']:+.1f}", ha="left", va="center", fontsize=5.2, color=color)
    ax_d.set_xlim(0, 215)
    ax_d.set_yticks(yd)
    ax_d.set_yticklabels([wrap_label(v, 18) for v in switch_df["label"]])
    ax_d.set_xlabel("ID switches / episode")
    clean_axis(ax_d, grid=True, axis="x")

    fig.subplots_adjust(left=0.105, right=0.985, top=0.90, bottom=0.15)
    save_figure(fig, "fig_simulation_effect_size", 183, 118, ["fig_simulation_effect_size_source.csv", "figure_stress_leader_metrics.csv", "main_benchmark_source.csv"])


def plot_target_consistency_breakdown() -> None:
    import runpy

    builder = runpy.run_path(str(Path(__file__).with_name("fig8_wrong_leader_exposure_diagnostic_v5.py")))["build_figure"]
    for out_dir in (FIGS, MANUSCRIPT_FIGS):
        fig = builder(str(out_dir / "fig8_wrong_leader_exposure_diagnostic_v5"))
        plt.close(fig)


def plot_stress_metric(metric: str, out_name: str, ylabel: str, scale: float = 1.0) -> None:
    df = read_source("figure_stress_leader_metrics.csv")
    conditions = list(dict.fromkeys(df["condition_id"].astype(str)))
    methods_by_condition = {c: list(df[df["condition_id"] == c]["display"]) for c in conditions}
    method_colors = {"Rule": COLORS["rule"], "No query": COLORS["noquery"], "Std KF": COLORS["stdkf"], "QGIP": COLORS["qgip"]}
    fig, ax = plt.subplots(figsize=(mm(89), mm(54)))
    x = np.arange(len(conditions))
    width = 0.18
    for ci, condition in enumerate(conditions):
        methods = methods_by_condition[condition]
        offsets = np.linspace(-(len(methods) - 1) / 2, (len(methods) - 1) / 2, len(methods)) * width
        for method, offset in zip(methods, offsets):
            hit = df[(df["condition_id"] == condition) & (df["display"] == method)].iloc[0]
            ax.bar(
                x[ci] + offset,
                safe_float(hit[metric]) * scale,
                width=width * 0.9,
                color=method_colors.get(method, "#CCCCCC"),
                edgecolor="black",
                linewidth=0.25,
            )
    handles = [Patch(facecolor=method_colors[m], edgecolor="black", linewidth=0.25, label=m) for m in ["Rule", "No query", "Std KF", "QGIP"]]
    ax.set_xticks(x)
    ax.set_xticklabels([COND_LABELS.get(c, c) for c in conditions], rotation=32, ha="right")
    ax.set_ylabel(ylabel)
    clean_axis(ax, grid=True)
    ax.legend(handles=handles, ncol=2, loc="upper right", handlelength=1.0, columnspacing=0.8)
    panel_label(ax, "a", ylabel)
    fig.subplots_adjust(left=0.18, right=0.985, top=0.86, bottom=0.31)
    save_figure(fig, out_name, 89, 54, ["figure_stress_leader_metrics.csv"])


def plot_extended_stress_outcomes() -> None:
    import runpy

    builder = runpy.run_path(str(Path(__file__).with_name("fig9_extended_stress_operating_envelope_refined_v3.py")))["build_figure"]
    for out_dir in (FIGS, MANUSCRIPT_FIGS):
        fig = builder(str(out_dir / "fig9_extended_stress_operating_envelope_refined_v3"))
        plt.close(fig)


def plot_extended_nis_response() -> None:
    import runpy

    builder = runpy.run_path(str(Path(__file__).with_name("fig10_nis_regime_bubble_map_refined_v5.py")))["build_figure"]
    for out_dir in (FIGS, MANUSCRIPT_FIGS):
        fig = builder(str(out_dir / "fig10_nis_regime_bubble_map_refined_v5"))
        plt.close(fig)


def plot_safety_case_evidence_map() -> None:
    import runpy

    builder = runpy.run_path(str(Path(__file__).with_name("fig11_claim_boundary_bowtie_v4.py")))["build_figure"]
    for out_dir in (FIGS, MANUSCRIPT_FIGS):
        fig = builder(str(out_dir / "fig11_claim_boundary_bowtie_v4"))
        plt.close(fig)


def plot_pre_real_robot_validation_boundary() -> None:
    import runpy

    name = "fig12_validation_boundary_narrative_v4"
    builder = runpy.run_path(str(Path(__file__).with_name(f"{name}.py")))["build_figure"]
    FIGS.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_FIGS.mkdir(parents=True, exist_ok=True)
    fig = builder(str(FIGS / name))
    plt.close(fig)
    for suffix in EXPORTS:
        path = FIGS / f"{name}{suffix}"
        shutil.copy2(path, MANUSCRIPT_FIGS / path.name)
    AUDIT_ROWS.append(
        {
            "figure": name,
            "width_mm": "183.0",
            "height_mm": "61.0",
            "source_files": f"{name}_source_data.csv; pre_real_robot_gate_audit.csv",
            "outputs": "; ".join([f"{name}{suffix}" for suffix in EXPORTS]),
            "font_contract": "pdf.fonttype=42; svg.fonttype=none; text editable",
        }
    )


def contiguous_segments(df: pd.DataFrame, key: str, value: object) -> list[tuple[float, float]]:
    if df.empty:
        return []
    times = df["stamp_s"].astype(float).to_numpy()
    dt = float(np.median(np.diff(times))) if len(times) > 1 else 0.05
    segments: list[tuple[float, float]] = []
    start: float | None = None
    last = times[0]
    for _, row in df.iterrows():
        t = float(row["stamp_s"])
        hit = row[key] == value
        if hit and start is None:
            start = t
        if (not hit) and start is not None:
            segments.append((start, last + dt))
            start = None
        last = t
    if start is not None:
        segments.append((start, last + dt))
    return segments


def span_faults(ax: plt.Axes, df: pd.DataFrame) -> None:
    for start, end in contiguous_segments(df, "fault_tag", "software_dropout"):
        ax.axvspan(start, end, color="#ECEFF3", zorder=0, linewidth=0)
    for start, end in contiguous_segments(df, "fault_tag", "high_nis_recovery_offset"):
        ax.axvspan(start, end, color="#DDEAF8", zorder=0, linewidth=0)


def plot_real_robot_offline_dryrun() -> None:
    import runpy

    name = "fig13_offline_dryrun_contract_timeline_v2"
    builder = runpy.run_path(str(Path(__file__).with_name(f"{name}.py")))["build_figure"]
    FIGS.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_FIGS.mkdir(parents=True, exist_ok=True)
    fig = builder(str(FIGS / name))
    plt.close(fig)
    for suffix in EXPORTS:
        path = FIGS / f"{name}{suffix}"
        shutil.copy2(path, MANUSCRIPT_FIGS / path.name)
    AUDIT_ROWS.append(
        {
            "figure": name,
            "width_mm": "183.0",
            "height_mm": "81.0",
            "source_files": f"{name}_source_data.csv; real_robot_offline_dryrun_trace.csv; ros2_runtime_telemetry_dryrun_summary.csv",
            "outputs": "; ".join([f"{name}{suffix}" for suffix in EXPORTS]),
            "font_contract": "pdf.fonttype=42; svg.fonttype=none; text editable",
        }
    )


def write_generation_audit() -> None:
    path = SOURCE / "nature_style_figure_generation_audit.csv"
    fieldnames = ["figure", "width_mm", "height_mm", "source_files", "outputs", "font_contract"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(AUDIT_ROWS)


def main() -> None:
    backup_existing_outputs()
    plot_nature_system_evidence()
    plot_query_guided_attention()
    plot_pop_ghost_tracking()
    plot_main_target_selection_nature()
    plot_main_safety_availability_nature()
    plot_main_nis_diagnostic_nature()
    plot_evidence_coverage_matrix()
    plot_simulation_stress_atlas()
    plot_extended_dataset_split()
    plot_simulation_effect_size()
    plot_target_consistency_breakdown()
    plot_stress_metric("leaderacc_mean", "figure_stress_leaderacc", "LeaderAcc (%)", 100.0)
    plot_stress_metric("idswitches_mean", "figure_stress_idswitch", "ID switches / episode", 1.0)
    plot_extended_stress_outcomes()
    plot_extended_nis_response()
    plot_safety_case_evidence_map()
    plot_pre_real_robot_validation_boundary()
    plot_real_robot_offline_dryrun()
    write_generation_audit()
    print("Generated Nature-style figures:")
    for row in AUDIT_ROWS:
        print(f"- {row['figure']} ({row['width_mm']} x {row['height_mm']} mm)")
    print(f"Audit: {SOURCE / 'nature_style_figure_generation_audit.csv'}")


if __name__ == "__main__":
    main()
