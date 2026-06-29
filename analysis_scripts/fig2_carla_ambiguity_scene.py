"""
Fig. 2: CARLA object-list ambiguity replay.

The figure is a controlled protocol schematic: all three panels reuse the same
bird's-eye scene layout, and only the object-list perturbation changes. The
upper half of each panel shows the world/object layout; the lower half shows
the controller-facing object list.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib as mpl
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
OUT_DIRS = [
    ROOT / "01_manuscript" / "paper_picture",
    ROOT / "08_paper_ready_outputs" / "figures",
    ROOT / "10_TASE_submission_20260610" / "01_manuscript" / "paper_picture",
]
SOURCE_DIR = ROOT / "08_paper_ready_outputs" / "source_data"
ASSET_DIR = ROOT / "08_paper_ready_outputs" / "figure_assets" / "fig2_carla_real"

FIG_W_MM = 183
FIG_H_MM = 92


COL = {
    "ego": "#2F6EEB",
    "leader": "#009B72",
    "fp": "#D62728",
    "warn": "#E68A00",
    "other": "#8C96A3",
    "road": "#F6F7F9",
    "lane": "#D4D9E1",
    "ink": "#18202B",
    "muted": "#667085",
    "panel": "#FFFFFF",
    "panel_edge": "#D0D5DD",
    "table_head": "#F1F3F6",
}


mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 6.2,
        "axes.linewidth": 0.5,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
    }
)


PANELS = [
    {
        "label": "a",
        "title": "Nominal",
        "subtitle": "All objects as detected",
        "perturbation": "none",
        "bottom_note": "Clean object list — world and controller agree",
    },
    {
        "label": "b",
        "title": "fp_10",
        "subtitle": "Adjacent-lane false positive injected",
        "perturbation": "false_positive",
        "bottom_note": "Extra row in object list — nearest-object rule may fail",
    },
    {
        "label": "c",
        "title": "idswitch",
        "subtitle": "Same vehicle, different object ID",
        "perturbation": "idswitch",
        "bottom_note": "Leader ID changes (002→042) — spatial position unchanged",
    },
]

OBJECTS = [
    ("ego", "Ego", 1.8, 0.0, "ego"),
    ("leader", "Leader", 8.6, 0.0, "leader"),
    ("other", "Veh B", 12.9, 1.65, "other"),
]

REAL_IMAGES = {
    "nominal": ASSET_DIR / "fig2_carla_nominal.png",
    "fp_10": ASSET_DIR / "fig2_carla_fp10.png",
}


def mm(value: float) -> float:
    return value / 25.4


def rounded_box(ax, xy, width, height, face, edge, lw=0.6, radius=0.06, z=1, alpha=1.0):
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle=f"round,pad=0.015,rounding_size={radius}",
        facecolor=face,
        edgecolor=edge,
        linewidth=lw,
        alpha=alpha,
        zorder=z,
    )
    ax.add_patch(patch)
    return patch


def draw_vehicle(ax, x, y, name, key, dashed=False, alpha=1.0, label_offset=-0.48):
    color = COL[key]
    face = "white" if dashed else color
    edge = color
    rounded_box(ax, (x - 0.70, y - 0.30), 1.40, 0.60, face, edge, lw=1.0, radius=0.08, z=6, alpha=alpha)
    ax.add_patch(
        Rectangle(
            (x - 0.43, y - 0.17),
            0.86,
            0.34,
            facecolor="white" if not dashed else "#FFF7F7",
            edgecolor=edge,
            linewidth=0.55,
            linestyle="--" if dashed else "-",
            zorder=7,
            alpha=0.95,
        )
    )
    ax.plot([x + 0.42, x + 0.60], [y + 0.18, y + 0.18], color=edge, lw=0.8, zorder=8)
    ax.plot([x + 0.42, x + 0.60], [y - 0.18, y - 0.18], color=edge, lw=0.8, zorder=8)
    ax.text(x, y + label_offset, name, ha="center", va="top", fontsize=5.6, color=COL["ink"], zorder=8)


def label_box(ax, x, y, text, edge, ha="center", va="center", fs=5.4, weight="bold"):
    ax.text(
        x,
        y,
        text,
        transform=ax.transAxes,
        ha=ha,
        va=va,
        fontsize=fs,
        color=COL["ink"],
        weight=weight,
        zorder=12,
        bbox={
            "boxstyle": "round,pad=0.16",
            "facecolor": "white",
            "edgecolor": edge,
            "linewidth": 0.75,
            "alpha": 0.92,
        },
    )


def draw_image_annotations(ax, panel):
    ax.annotate(
        "",
        xy=(0.515, 0.455),
        xytext=(0.515, 0.245),
        xycoords=ax.transAxes,
        textcoords=ax.transAxes,
        arrowprops={"arrowstyle": "->", "lw": 1.15, "color": COL["leader"]},
        zorder=11,
    )
    label_box(ax, 0.515, 0.225, "Ego", COL["ego"], fs=5.0)
    label_box(ax, 0.565, 0.555, "Leader", COL["leader"], fs=5.0)
    label_box(ax, 0.455, 0.780, "Veh B", COL["other"], fs=5.0)
    ax.text(
        0.535,
        0.355,
        "follow",
        transform=ax.transAxes,
        ha="left",
        va="center",
        fontsize=5.0,
        color=COL["leader"],
        weight="bold",
        zorder=12,
    )
    if panel["perturbation"] == "false_positive":
        label_box(ax, 0.420, 0.535, "FP", COL["fp"], fs=5.1)
        ax.add_patch(
            Rectangle(
                (0.432, 0.455),
                0.064,
                0.120,
                transform=ax.transAxes,
                facecolor="none",
                edgecolor=COL["fp"],
                linewidth=1.0,
                linestyle="--",
                zorder=10,
            )
        )
    if panel["perturbation"] == "idswitch":
        label_box(ax, 0.570, 0.635, "ID 002 -> 042", COL["warn"], fs=5.0)


def draw_scene(ax, panel):
    ax.axis("off")
    image_key = "fp_10" if panel["perturbation"] == "false_positive" else "nominal"
    image_path = REAL_IMAGES[image_key]
    if not image_path.exists():
        raise FileNotFoundError(f"Missing CARLA screenshot for Fig. 2: {image_path}")
    img = mpimg.imread(image_path)
    ax.imshow(img, interpolation="lanczos", aspect="equal")
    draw_image_annotations(ax, panel)


def object_rows(panel):
    if panel["perturbation"] == "false_positive":
        return [
            ("001", "Ego", "self vehicle", "ego"),
            ("002", "Veh A", "semantic leader", "leader"),
            ("003", "Veh B", "distractor", "other"),
            ("004", "FP", "adjacent-lane false positive", "fp"),
        ]
    if panel["perturbation"] == "idswitch":
        return [
            ("001", "Ego", "self vehicle", "ego"),
            ("042", "Veh A'", "same leader, new ID", "warn"),
            ("003", "Veh B", "distractor", "other"),
        ]
    return [
        ("001", "Ego", "self vehicle", "ego"),
        ("002", "Veh A", "semantic leader", "leader"),
        ("003", "Veh B", "distractor", "other"),
    ]


def controller_points(panel):
    ego_x = next(x for _, _, x, _, key in OBJECTS if key == "ego")
    points = [
        ("001", "Ego", 0.0, 0.0, "ego"),
        ("002", "Leader", 8.6 - ego_x, 0.0, "leader"),
        ("003", "Veh B", 12.9 - ego_x, 1.65, "other"),
    ]
    if panel["perturbation"] == "false_positive":
        points.append(("004", "FP", 7.5 - ego_x, 1.65, "fp"))
    if panel["perturbation"] == "idswitch":
        points[1] = ("042", "Leader", 8.6 - ego_x, 0.0, "warn")
    return points


def draw_object_data_plot(ax, panel):
    points = controller_points(panel)
    ax.set_facecolor("white")
    ax.set_xlim(-0.6, 12.0)
    ax.set_ylim(-0.55, 2.35)
    ax.set_xticks([0, 4, 8, 12])
    ax.set_yticks([0.0, 1.65])
    ax.set_yticklabels(["ego lane", "adj. lane"])
    ax.tick_params(axis="both", labelsize=4.8, width=0.45, length=2.0, colors=COL["muted"], pad=1.5)
    ax.grid(True, color="#E7EAF0", lw=0.45, zorder=0)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(COL["panel_edge"])
        ax.spines[side].set_linewidth(0.55)
    ax.axhline(0.0, color=COL["leader"], lw=0.7, alpha=0.25, zorder=0)
    ax.axhline(1.65, color=COL["other"], lw=0.7, alpha=0.22, zorder=0)
    ax.set_xlabel("longitudinal gap from ego (m)", fontsize=5.0, color=COL["muted"], labelpad=1.5)
    ax.set_title("controller object-list coordinates", loc="left", fontsize=5.8, weight="bold", color=COL["ink"], pad=2.2)
    ax.text(1.0, 1.04, panel["title"], transform=ax.transAxes, ha="right", va="bottom",
            fontsize=5.0, color=COL["muted"])

    for obj_id, name, x, y, key in points:
        face = COL["leader"] if key == "warn" else COL[key]
        edge = COL["warn"] if key == "warn" else "white"
        lw = 1.15 if key == "warn" else 0.75
        marker = "s" if key == "ego" else "o"
        ax.scatter([x], [y], s=42 if key != "fp" else 50, marker=marker, color=face,
                   edgecolor=edge, linewidth=lw, zorder=4)
        label_y = y + (0.23 if y <= 0.2 else -0.26)
        va = "bottom" if y <= 0.2 else "top"
        ax.text(x, label_y, f"ID {obj_id}\n{name}", ha="center", va=va, fontsize=4.9,
                color=COL["ink"], zorder=5,
                bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.80})

    if panel["perturbation"] == "false_positive":
        fp = next(p for p in points if p[4] == "fp")
        ax.annotate("extra object-list point", xy=(fp[2], fp[3]), xytext=(fp[2] - 2.0, 2.12),
                    ha="center", va="center", fontsize=4.9, color=COL["fp"],
                    arrowprops={"arrowstyle": "->", "lw": 0.75, "color": COL["fp"]})
    if panel["perturbation"] == "idswitch":
        leader = next(p for p in points if p[4] == "warn")
        ax.annotate("ID 002 -> 042", xy=(leader[2], leader[3]), xytext=(leader[2] + 2.2, 0.75),
                    ha="center", va="center", fontsize=4.9, color=COL["warn"], weight="bold",
                    arrowprops={"arrowstyle": "->", "lw": 0.75, "color": COL["warn"]})


def add_panel_frame(fig, left, bottom, width, height, panel):
    ax_bg = fig.add_axes([left, bottom, width, height], zorder=-1)
    ax_bg.set_xlim(0, 1)
    ax_bg.set_ylim(0, 1)
    ax_bg.axis("off")
    ax_bg.add_patch(Rectangle((0.0, 0.0), 1.0, 1.0, facecolor=COL["panel"], edgecolor="none", zorder=0))
    ax_bg.text(0.025, 0.965, panel["label"], ha="left", va="top", fontsize=8.0, weight="bold", color=COL["ink"])
    ax_bg.text(0.092, 0.965, panel["title"], ha="left", va="top", fontsize=6.7, weight="bold", color=COL["ink"])
    ax_bg.text(0.092, 0.905, panel["subtitle"], ha="left", va="top", fontsize=5.3, color=COL["muted"])
    # Bottom note — clean single line, no table
    ax_bg.text(0.025, 0.038, panel["bottom_note"], ha="left", va="bottom", fontsize=5.4, color=COL["muted"])
    return ax_bg


def write_source_data():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    path = SOURCE_DIR / "fig2_carla_ambiguity_scene_source.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["panel", "condition", "layer", "object_id", "object_name", "x_m", "lane_y", "role", "note"])
        for panel in PANELS:
            image_key = "fp_10" if panel["perturbation"] == "false_positive" else "nominal"
            writer.writerow([panel["label"], panel["title"], "raster", REAL_IMAGES[image_key].as_posix(), "", "", "", "", "CARLA RGB camera screenshot"])
            for obj_id, name, x, y, key in OBJECTS:
                writer.writerow([panel["label"], panel["title"], "world", obj_id, name, x, y, key, "same across panels"])
            for obj_id, name, x_gap, y_lat, key in controller_points(panel):
                writer.writerow([panel["label"], panel["title"], "controller_plot", obj_id, name, x_gap, y_lat, key, "controller-facing object-list coordinate"])
            if panel["perturbation"] == "false_positive":
                writer.writerow([panel["label"], panel["title"], "world", "fp", "false positive", 7.5, 1.65, "fp", "injected adjacent-lane detection"])
            if panel["perturbation"] == "idswitch":
                writer.writerow([panel["label"], panel["title"], "world", "002->042", "leader id swap", 8.6, 0.0, "warn", "same position, different controller-facing ID"])
    return path


def get_image_aspect_ratio():
    """Read actual CARLA screenshot aspect ratio."""
    img = mpimg.imread(REAL_IMAGES["nominal"])
    return img.shape[1] / img.shape[0]  # w / h"""


def build_figure(save_base: str = "fig2_carla_ambiguity_scene"):
    img_aspect = get_image_aspect_ratio()  # e.g. 1.778 for 16:9

    lefts = [0.018, 0.342, 0.666]
    width = 0.314
    panel_bottom = 0.045
    panel_height = 0.915

    # Compute scene height so its aspect ratio matches the image
    scene_margin_h = 0.016  # left/right margin inside panel
    scene_width_frac = width - 2 * scene_margin_h
    # scene_height = scene_width / img_aspect, converted to figure fraction
    scene_height = (scene_width_frac * mm(FIG_W_MM)) / img_aspect / mm(FIG_H_MM)
    scene_y = panel_bottom + 0.425
    data_y = panel_bottom + 0.112
    data_h = 0.245

    fig = plt.figure(figsize=(mm(FIG_W_MM), mm(FIG_H_MM)), dpi=300)
    fig.patch.set_facecolor("white")

    for left, panel in zip(lefts, PANELS):
        add_panel_frame(fig, left, panel_bottom, width, panel_height, panel)
        scene_ax = fig.add_axes([
            left + scene_margin_h,
            scene_y,
            scene_width_frac,
            scene_height,
        ])
        draw_scene(scene_ax, panel)
        data_ax = fig.add_axes([
            left + scene_margin_h,
            data_y,
            scene_width_frac,
            data_h,
        ])
        draw_object_data_plot(data_ax, panel)

    for out_dir in OUT_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_dir / f"{save_base}.pdf", bbox_inches="tight")
        fig.savefig(out_dir / f"{save_base}.svg", bbox_inches="tight")
        fig.savefig(out_dir / f"{save_base}.png", dpi=600, bbox_inches="tight")
        fig.savefig(out_dir / f"{save_base}.tiff", dpi=600, bbox_inches="tight")

    source_path = write_source_data()
    print(f"Saved {save_base} to {len(OUT_DIRS)} output directories")
    print(f"Source data: {source_path}")


if __name__ == "__main__":
    build_figure()
