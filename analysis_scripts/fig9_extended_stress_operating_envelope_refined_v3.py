#!/usr/bin/env python3
"""Figure 9 refined: extended-stress operating envelope.

The figure compresses the extended stress suite into an operating-envelope
scatter and a finite-sample zero-collision bound. It intentionally avoids
replotting the paired-comparison graphics used elsewhere in the manuscript.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D

from qgip_figure_style import TOP_CONF_COLORS as TOP, apply_top_conference_style


ROOT = Path(__file__).resolve().parents[1]
SOURCE_OUT = ROOT / "08_paper_ready_outputs" / "source_data"
BASE = "fig9_extended_stress_operating_envelope_refined_v3"

apply_top_conference_style()
plt.rcParams.update(
    {
        "font.size": 7.0,
        "axes.labelsize": 7.0,
        "xtick.labelsize": 6.2,
        "ytick.labelsize": 6.2,
        "legend.fontsize": 5.9,
        "axes.linewidth": 0.72,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    }
)

COLORS = {
    "ambiguity": TOP["blue"],
    "detector/timing": TOP["teal"],
    "detector-output": TOP["blue_mid"],
    "boundary": TOP["brick"],
    "grid": TOP["grid"],
    "muted": TOP["gray"],
    "text": TOP["ink"],
    "safe_bg": TOP["teal_light"],
    "watch_bg": "#FBF4E8",
    "boundary_bg": TOP["brick_light"],
}

SOURCE_ROWS = [
    ("FP10", "ambiguity", 300, 73.0, 27.0, 86.2, 62.5),
    ("ID switch", "ambiguity", 300, 73.0, 27.0, 90.7, 39.2),
    ("FN50", "detector/timing", 300, 72.7, 27.3, 100.0, 0.0),
    ("Delay200", "detector/timing", 300, 72.7, 27.3, 100.0, 0.0),
    ("Glare degradation", "detector-output", 100, 76.0, 24.0, 100.0, 0.0),
    ("LiDAR-dropout profile", "detector-output", 100, 76.0, 24.0, 100.0, 0.0),
    ("Boundary", "boundary", 100, 77.0, 23.0, 80.0, 126.5),
]

POINTS = [
    {
        "label": "FP10",
        "family": "ambiguity",
        "N": 300,
        "lost": 27.0,
        "leaderacc": 86.2,
        "ids": 62.5,
        "members": "FP10",
    },
    {
        "label": "ID switch",
        "family": "ambiguity",
        "N": 300,
        "lost": 27.0,
        "leaderacc": 90.7,
        "ids": 39.2,
        "members": "ID switch",
    },
    {
        "label": "FN50 / Delay200",
        "family": "detector/timing",
        "N": 300,
        "lost": 27.3,
        "leaderacc": 100.0,
        "ids": 0.0,
        "members": "FN50; Delay200",
    },
    {
        "label": "Glare / dropout",
        "family": "detector-output",
        "N": 100,
        "lost": 24.0,
        "leaderacc": 100.0,
        "ids": 0.0,
        "members": "glare degradation; LiDAR-dropout profile",
    },
    {
        "label": "Boundary",
        "family": "boundary",
        "N": 100,
        "lost": 23.0,
        "leaderacc": 80.0,
        "ids": 126.5,
        "members": "fp20_idswitch20",
    },
]

MARKERS = {
    "ambiguity": "o",
    "detector/timing": "s",
    "detector-output": "^",
    "boundary": "D",
}


def add_halo(artist, lw: float = 1.6) -> None:
    artist.set_path_effects([pe.Stroke(linewidth=lw, foreground="white"), pe.Normal()])


def marker_size(ids: float) -> float:
    return 42.0 + 0.74 * float(ids)


def panel_label(ax, letter: str, title: str) -> None:
    ax.set_title(f"{letter}  {title}", loc="left", fontsize=8.0, fontweight="bold", pad=5)


def draw_operating_envelope(ax) -> None:
    panel_label(ax, "a", "Extended-stress operating envelope")
    ax.set_xlim(21.4, 29.2)
    ax.set_ylim(76, 103)
    ax.set_xlabel("fail-safe Lost (%)")
    ax.set_ylabel("LeaderAcc (%)")
    ax.set_xticks([22, 24, 26, 28])
    ax.set_yticks([80, 90, 100])
    ax.grid(True, color=COLORS["grid"], lw=0.42, zorder=-5)

    ax.axvspan(21.4, 25.0, ymin=(90 - 76) / 27, ymax=1.0, color=COLORS["safe_bg"], zorder=-10)
    ax.axvspan(25.0, 29.2, color=COLORS["watch_bg"], alpha=0.44, zorder=-11)
    ax.axvspan(21.4, 24.5, ymin=0.0, ymax=(84 - 76) / 27, color=COLORS["boundary_bg"], zorder=-10)
    ax.text(21.65, 101.6, "high consistency", fontsize=5.4, color=TOP["teal_dark"], ha="left", va="top")
    ax.text(22.15, 77.5, "boundary\nstress", fontsize=5.25, color=COLORS["boundary"], ha="left", va="bottom")

    path = ["Glare / dropout", "FN50 / Delay200", "ID switch", "FP10", "Boundary"]
    coords = {p["label"]: (p["lost"], p["leaderacc"]) for p in POINTS}
    line = ax.plot(
        [coords[label][0] for label in path],
        [coords[label][1] for label in path],
        color=TOP["gray_mid"],
        lw=0.85,
        zorder=1,
    )[0]
    add_halo(line)

    for p in POINTS:
        face = COLORS[p["family"]] if p["N"] == 300 else "white"
        edge = COLORS[p["family"]]
        ax.scatter(
            p["lost"],
            p["leaderacc"],
            s=marker_size(p["ids"]),
            marker=MARKERS[p["family"]],
            facecolor=face,
            edgecolor=edge,
            linewidth=0.95 if p["N"] == 100 else 0.45,
            zorder=4,
        )

    label_xy = {
        "Glare / dropout": (24.28, 101.8, "left", "center"),
        "FN50 / Delay200": (27.55, 100.5, "left", "center"),
        "ID switch": (27.32, 91.5, "left", "center"),
        "FP10": (27.32, 85.5, "left", "center"),
        "Boundary": (23.15, 82.35, "left", "center"),
    }
    for p in POINTS:
        x, y, ha, va = label_xy[p["label"]]
        ax.text(
            x,
            y,
            p["label"],
            fontsize=5.55,
            color=COLORS[p["family"]],
            ha=ha,
            va=va,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.86, "pad": 0.12},
            zorder=6,
        )

    handles = [
        Line2D([0], [0], marker=MARKERS[key], color="none", markerfacecolor=COLORS[key],
               markeredgecolor=COLORS[key], markersize=4.2, label=label)
        for key, label in [
            ("ambiguity", "ambiguity"),
            ("detector/timing", "detector/timing"),
            ("detector-output", "detector-output"),
            ("boundary", "boundary"),
        ]
    ]
    ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.94,
              edgecolor=TOP["gray_light"], borderpad=0.35, handletextpad=0.35)

    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="both", length=2.3, width=0.55)


def draw_collision_bounds(ax) -> None:
    panel_label(ax, "b", "Zero-collision finite-sample bound")
    groups = pd.DataFrame(
        {
            "protocols": [r"$N=300$", r"$N=100$"],
            "upper_bound": [3.0 / 300 * 100, 3.0 / 100 * 100],
            "y": [1.0, 0.0],
            "color": [COLORS["ambiguity"], COLORS["boundary"]],
        }
    )
    ax.set_xlim(0, 3.35)
    ax.set_ylim(-0.55, 1.55)
    ax.set_xlabel("rule-of-three upper bound (%)")
    ax.set_yticks(groups["y"])
    ax.set_yticklabels(groups["protocols"])
    ax.set_xticks([0, 1, 2, 3])
    ax.grid(axis="x", color=COLORS["grid"], lw=0.42, zorder=-5)

    for _, row in groups.iterrows():
        ax.plot([0, row["upper_bound"]], [row["y"], row["y"]], color=TOP["gray_mid"], lw=1.2, zorder=1)
        ax.scatter(row["upper_bound"], row["y"], s=34, color=row["color"], edgecolor=TOP["ink"], linewidth=0.4, zorder=3)
        ax.text(row["upper_bound"] + 0.09, row["y"], f"{row['upper_bound']:.1f}%",
                fontsize=6.0, color=COLORS["text"], ha="left", va="center")

    ax.text(
        0.12,
        1.39,
        "0 observed collisions",
        fontsize=5.7,
        color=COLORS["muted"],
        ha="left",
        va="top",
    )
    ax.text(
        0.12,
        -0.40,
        "upper bounds are finite-sample evidence, not a zero-risk claim",
        fontsize=5.35,
        color=COLORS["muted"],
        ha="left",
        va="bottom",
    )

    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="both", length=2.3, width=0.55)


def write_source_data(save_base: str) -> None:
    base = Path(save_base)
    out_dirs = [SOURCE_OUT] if SOURCE_OUT.exists() else [base.parent]

    df_source = pd.DataFrame(
        SOURCE_ROWS,
        columns=[
            "condition",
            "family",
            "N",
            "success_percent",
            "lost_percent",
            "LeaderAcc_percent",
            "IDSwitches_per_episode",
        ],
    )
    df_source["rule_of_three_upper_bound_percent"] = 3.0 / df_source["N"] * 100.0

    df_points = pd.DataFrame(POINTS)
    df_points["rule_of_three_upper_bound_percent"] = 3.0 / df_points["N"] * 100.0
    for out_dir in out_dirs:
        df_source.to_csv(out_dir / f"{base.name}_source_data.csv", index=False)
        df_points.to_csv(out_dir / f"{base.name}_aggregated_points.csv", index=False)


def build_figure(save_base: str = BASE):
    fig = plt.figure(figsize=(5.20, 3.05), dpi=300)
    gs = GridSpec(1, 1, figure=fig)
    ax_a = fig.add_subplot(gs[0, 0])
    draw_operating_envelope(ax_a)
    fig.text(
        0.115,
        0.055,
        "Marker area encodes ID-switch burden; filled markers denote N=300, open markers denote N=100.",
        fontsize=5.55,
        color=COLORS["muted"],
        ha="left",
        va="center",
    )
    fig.subplots_adjust(left=0.105, right=0.985, top=0.92, bottom=0.20)
    for suffix in (".pdf", ".svg", ".png", ".tiff"):
        kwargs = {"bbox_inches": "tight"}
        if suffix in (".png", ".tiff"):
            kwargs["dpi"] = 600
        fig.savefig(f"{save_base}{suffix}", **kwargs)
    write_source_data(save_base)
    return fig


if __name__ == "__main__":
    build_figure(BASE)
