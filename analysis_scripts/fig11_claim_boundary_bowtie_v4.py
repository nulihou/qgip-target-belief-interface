# SUPPLEMENT-ONLY FIGURE (2026-06-14 revision)
# This bow-tie argument diagram is a meta-visualisation of the claim boundary.
# The same claim-boundary information is conveyed in the Introduction, Discussion,
# and Limitations sections. This figure is retained ONLY for the supplementary material.

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from qgip_figure_style import TOP_CONF_COLORS as TOP, apply_top_conference_style


ROOT = Path(__file__).resolve().parents[1]
SOURCE_OUT = ROOT / "08_paper_ready_outputs" / "source_data"
BASE = "fig11_claim_boundary_bowtie_v4"

apply_top_conference_style()
plt.rcParams.update({
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2,
    "legend.fontsize": 5.8,
    "axes.linewidth": 0.82,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "blue": TOP["blue"],
    "blue_fill": TOP["blue_bg"],
    "green": TOP["teal"],
    "green_fill": TOP["teal_light"],
    "red": TOP["brick"],
    "red_fill": TOP["brick_light"],
    "gray": TOP["gray"],
    "gray_fill": TOP["panel"],
    "text": TOP["ink"],
}

left_nodes = [
    ("ODD / split control", "bounded ODD and leakage audit"),
    ("Target-consistency evidence", "ambiguity tests expose target selection"),
    ("Finite-sample safety interpretation", "zero collisions kept as finite-sample evidence"),
    ("Uncertainty-monitor evidence", "NIS outliers trigger recovery logic"),
    ("Source-data / provenance audit", "claim-source drift checks"),
]
right_nodes = [
    ("Live ROS2/HIL timing evidence", "colcon, launch, rosbag, and HIL timing logs"),
    ("Operator-supervised robot trials", "physical closed-loop trial manifests"),
    ("DOI-backed release record", "retrievable evidence package"),
]

source_edges = [
    ("completed_evidence", "ODD / split control", "bounded CARLA simulation claim"),
    ("completed_evidence", "Target-consistency evidence", "bounded CARLA simulation claim"),
    ("completed_evidence", "Finite-sample safety interpretation", "bounded CARLA simulation claim"),
    ("completed_evidence", "Uncertainty-monitor evidence", "bounded CARLA simulation claim"),
    ("completed_evidence", "Source-data / provenance audit", "bounded CARLA simulation claim"),
    ("remaining_requirement", "bounded CARLA simulation claim", "Live ROS2/HIL timing evidence"),
    ("remaining_requirement", "bounded CARLA simulation claim", "Operator-supervised robot trials"),
    ("remaining_requirement", "bounded CARLA simulation claim", "DOI-backed release record"),
    ("boundary", "bounded CARLA simulation claim", "no physical-validation claim"),
]

def round_box(ax, xy, width, height, title, sub=None, fc="white", ec=None, lw=0.8,
              title_color=None, sub_color=None, fs_title=6.0, fs_sub=5.2,
              radius=0.07, z=3):
    ec = TOP["ink"] if ec is None else ec
    title_color = TOP["ink"] if title_color is None else title_color
    sub_color = TOP["gray"] if sub_color is None else sub_color
    x, y = xy
    box = patches.FancyBboxPatch(
        (x, y), width, height,
        boxstyle=f"round,pad=0.016,rounding_size={radius}",
        facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z
    )
    ax.add_patch(box)
    if sub:
        ax.text(x + width/2, y + height*0.62, title, ha="center", va="center",
                fontsize=fs_title, color=title_color, fontweight="bold", linespacing=0.88, zorder=z+1)
        ax.text(x + width/2, y + height*0.28, sub, ha="center", va="center",
                fontsize=fs_sub, color=sub_color, linespacing=0.90, zorder=z+1)
    else:
        ax.text(x + width/2, y + height/2, title, ha="center", va="center",
                fontsize=fs_title, color=title_color, fontweight="bold", linespacing=0.90, zorder=z+1)
    return box

def curved_arrow(ax, start, end, color, lw=0.85, rad=0.0, alpha=1.0, z=2):
    ax.add_patch(patches.FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=8.0,
        connectionstyle=f"arc3,rad={rad}", linewidth=lw,
        color=color, alpha=alpha, zorder=z, shrinkA=2, shrinkB=4
    ))

def write_source_data() -> None:
    SOURCE_OUT.mkdir(parents=True, exist_ok=True)
    out_path = SOURCE_OUT / f"{BASE}_source_data.csv"
    rows = []
    for title, sub in left_nodes:
        rows.append({"side": "completed_evidence", "node": title, "detail": sub})
    rows.append({
        "side": "bounded_claim",
        "node": "bounded CARLA simulation claim",
        "detail": "target consistency + local safety filter within tested ODD",
    })
    for title, sub in right_nodes:
        rows.append({"side": "remaining_requirement", "node": title, "detail": sub})
    rows.append({
        "side": "boundary",
        "node": "no physical-validation claim",
        "detail": "CARLA evidence does not cross into live ROS2/HIL or physical robot validation",
    })
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["side", "node", "detail"])
        writer.writeheader()
        writer.writerows(rows)
    edge_path = SOURCE_OUT / f"{BASE}_edges.csv"
    with edge_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["edge_type", "source", "target"])
        writer.writeheader()
        writer.writerows(
            {"edge_type": edge_type, "source": source, "target": target}
            for edge_type, source, target in source_edges
        )


def build_figure(save_base=BASE):
    fig, ax = plt.subplots(figsize=(7.35, 3.70), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.7)
    ax.axis("off")
    ax.set_title("Safety-case claim boundary as a bow-tie argument",
                 loc="left", fontsize=8.8, fontweight="bold", pad=8)
    ax.add_patch(patches.Rectangle((0.05, 0.75), 4.05, 5.15, facecolor=COLORS["blue_fill"], edgecolor="none", zorder=-5))
    ax.add_patch(patches.Rectangle((4.20, 0.75), 1.82, 5.15, facecolor=TOP["teal_light"], edgecolor="none", zorder=-5))
    ax.add_patch(patches.Rectangle((6.10, 0.75), 3.85, 5.15, facecolor=COLORS["red_fill"], edgecolor="none", zorder=-5))
    ax.text(0.18, 6.05, "completed in this manuscript", ha="left", va="bottom",
            fontsize=6.05, color=COLORS["blue"], fontweight="bold")
    ax.text(4.45, 6.05, "bounded claim", ha="left", va="bottom",
            fontsize=6.05, color=COLORS["green"], fontweight="bold")
    ax.text(6.25, 6.05, "not yet claimed", ha="left", va="bottom",
            fontsize=6.05, color=COLORS["red"], fontweight="bold")
    left_x, box_w, box_h = 0.30, 2.75, 0.74
    y_positions = [5.10, 4.18, 3.26, 2.34, 1.42]
    for (title, sub), y in zip(left_nodes, y_positions):
        round_box(ax, (left_x, y), box_w, box_h, title, sub,
                  fc="white", ec=TOP["blue_mid"], lw=0.70,
                  fs_title=5.75, fs_sub=4.95, radius=0.07)
    round_box(ax, (4.05, 2.75), 2.04, 1.26,
              "bounded CARLA\nsimulation claim",
              "target consistency + local\nsafety filter within tested ODD",
              fc=COLORS["green_fill"], ec=COLORS["green"], lw=1.05,
              fs_title=6.25, fs_sub=5.05, radius=0.08, z=5)
    right_x, right_w, right_h = 6.85, 2.70, 0.78
    right_y = [4.85, 3.35, 1.85]
    for (title, sub), y in zip(right_nodes, right_y):
        round_box(ax, (right_x, y), right_w, right_h, title, sub,
                  fc="white", ec=COLORS["red"], lw=0.95,
                  fs_title=5.75, fs_sub=4.95, radius=0.07)
    ax.axvline(6.43, ymin=0.14, ymax=0.89, color=TOP["gray_mid"],
               linewidth=1.0, linestyle=(0, (3, 2)), zorder=1)
    ax.text(6.31, 5.70, "validation boundary", ha="right", va="bottom",
            fontsize=5.65, color=COLORS["gray"],
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.90, pad=0.10))
    target_points = [(4.05, 3.56), (4.05, 3.43), (4.05, 3.30), (4.05, 3.17), (4.05, 3.04)]
    for i, y in enumerate(y_positions):
        curved_arrow(ax, (left_x + box_w, y + box_h/2), target_points[i],
                     COLORS["blue"], lw=0.80, rad=0.05 if i < 2 else -0.05, alpha=0.88)
    for i, y in enumerate(right_y):
        curved_arrow(ax, (6.09, 3.38), (right_x, y + right_h/2),
                     COLORS["red"], lw=0.80, rad=0.13 if i == 0 else (-0.13 if i == 2 else 0.0), alpha=0.85)
    round_box(ax, (6.12, 0.98), 1.68, 0.62,
              "no physical-\nvalidation claim", None,
              fc=COLORS["gray_fill"], ec=COLORS["gray"],
              lw=0.85, fs_title=5.65, radius=0.06, z=4)
    curved_arrow(ax, (6.00, 2.93), (6.86, 1.30), COLORS["gray"], lw=0.75, rad=-0.20, alpha=0.85)
    ax.text(0.30, 0.42,
            "Left-side evidence supports only the bounded CARLA claim; right-side items are required before ROS2/HIL or physical-robot validation claims.",
            ha="left", va="center", fontsize=5.55, color=COLORS["gray"])
    fig.subplots_adjust(left=0.03, right=0.985, top=0.86, bottom=0.07)
    fig.savefig(f"{save_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{save_base}.svg", bbox_inches="tight")
    fig.savefig(f"{save_base}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{save_base}.tiff", dpi=600, bbox_inches="tight")
    write_source_data()
    return fig

if __name__ == "__main__":
    build_figure(BASE)
