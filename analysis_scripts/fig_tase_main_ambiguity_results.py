"""T-ASE compact main result figure.

Combines the narrative roles of the original Fig. 7 and Fig. 8:
LeaderAcc gain, wrong-leader exposure, ID-switch burden, and route context.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np

from qgip_figure_style import TOP_CONF_COLORS as TOP, apply_top_conference_style


apply_top_conference_style()
plt.rcParams.update(
    {
        "font.size": 7.0,
        "axes.labelsize": 7.0,
        "xtick.labelsize": 6.2,
        "ytick.labelsize": 6.2,
        "legend.fontsize": 5.8,
        "axes.linewidth": 0.8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    }
)


COLORS = {
    "qgip": TOP["blue"],
    "rule": TOP["gray"],
    "gnn": TOP["copper"],
    "stdkf": TOP["blue_mid"],
    "sort": TOP["charcoal"],
    "success": TOP["teal"],
    "lost": TOP["gray_light"],
    "collision": TOP["brick"],
    "grid": TOP["grid"],
    "muted": TOP["gray"],
    "text": TOP["ink"],
    "gap": TOP["gray_mid"],
}


ROUTE_ROWS = [
    ("E2E\n(no MPC)", 8.3, 5.3, 86.3, 25, 16, 259),
    ("Modular\nPID", 33.0, 8.3, 58.7, 99, 25, 176),
    ("Rule\n+ MPC", 69.0, 31.0, 0.0, 207, 93, 0),
    ("Std KF\n+ MPC", 73.3, 26.7, 0.0, 220, 80, 0),
    ("QGIP-Net", 76.7, 23.3, 0.0, 230, 70, 0),
]

GAIN_ROWS = [
    ("FP10 vs Rule", 86.2 - 43.8, "gain"),
    ("FP10 vs GNN selector", 86.2 - 53.6, "gain"),
    ("ID switch vs Rule", 90.7 - 47.7, "gain"),
    ("ID switch vs Std KF", 90.7 - 56.0, "gain"),
    ("FP10 gap to SORT", 86.2 - 90.2, "sort_gap"),
    ("ID switch gap to SORT", 90.7 - 99.8, "sort_gap"),
]

AMBIGUITY_ROWS = [
    ("fp_10", "Rule", 43.8, 269.7, 57.1),
    ("fp_10", "GNN selector", 53.6, 184.0, 102.7),
    ("fp_10", "QGIP-Net", 86.2, 66.6, 62.5),
    ("fp_10", "SORT+MPC", 90.2, 32.1, 53.6),
    ("idswitch", "Rule", 47.7, 252.0, 155.2),
    ("idswitch", "Std KF", 56.0, 208.0, 180.6),
    ("idswitch", "QGIP-Net", 90.7, 46.2, 39.2),
    ("idswitch", "SORT+MPC", 99.8, 0.7, 108.8),
]


METHOD_STYLE = {
    "Rule": ("s", COLORS["rule"]),
    "GNN selector": ("^", COLORS["gnn"]),
    "Std KF": ("D", COLORS["stdkf"]),
    "QGIP-Net": ("o", COLORS["qgip"]),
    "SORT+MPC": ("X", COLORS["sort"]),
}


def add_halo(artist, lw: float = 2.0) -> None:
    artist.set_path_effects([pe.Stroke(linewidth=lw, foreground="white"), pe.Normal()])


def panel_a_gain(ax) -> None:
    labels = [r[0] for r in GAIN_ROWS][::-1]
    values = np.array([r[1] for r in GAIN_ROWS][::-1])
    kinds = [r[2] for r in GAIN_ROWS][::-1]
    y = np.arange(len(labels))

    ax.axvline(0, color=TOP["charcoal"], lw=0.75, zorder=1)
    for yi, val, kind in zip(y, values, kinds):
        color = COLORS["qgip"] if kind == "gain" else COLORS["gap"]
        hatch = "" if kind == "gain" else "///"
        ax.barh(
            yi,
            val,
            height=0.58,
            color=color,
            edgecolor=TOP["ink"] if kind == "sort_gap" else color,
            linewidth=0.45,
            hatch=hatch,
            zorder=3,
        )
        ha = "left" if val >= 0 else "right"
        x = val + (0.9 if val >= 0 else -0.9)
        ax.text(x, yi, f"{val:+.1f}", ha=ha, va="center", fontsize=5.8, color=COLORS["text"])

    ax.set_title("a  LeaderAcc differences", loc="left", fontsize=8.2, fontweight="bold", pad=5)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(-13, 48)
    ax.set_xlabel("QGIP-Net minus comparator (percentage points)")
    ax.grid(axis="x", color=COLORS["grid"], lw=0.42, zorder=0)
    ax.tick_params(axis="both", length=2.4, width=0.58)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)


def grouped_metric(ax, metric: str, title: str, xlabel: str, xlim: tuple[float, float]) -> None:
    conditions = ["fp_10", "idswitch"]
    y_centers = np.array([1.25, 0.0])
    offsets = {
        "Rule": 0.27,
        "GNN selector": 0.09,
        "Std KF": 0.09,
        "QGIP-Net": -0.09,
        "SORT+MPC": -0.27,
    }

    for base_y, cond in zip(y_centers, conditions):
        ax.axhline(base_y, color=TOP["gray_light"], lw=0.36, zorder=0)
        rows = [r for r in AMBIGUITY_ROWS if r[0] == cond]
        for condition, method, leaderacc, wrong, ids in rows:
            value = wrong if metric == "wrong" else ids
            marker, color = METHOD_STYLE[method]
            yy = base_y + offsets[method]
            line = ax.hlines(yy, 0, value, color=TOP["gray_mid"], lw=0.7, zorder=1)
            add_halo(line, 1.4)
            ax.scatter(
                [value],
                [yy],
                s=28 if method != "QGIP-Net" else 34,
                marker=marker,
                color=color,
                edgecolor=TOP["ink"],
                linewidth=0.42,
                zorder=3,
            )
            if method in {"QGIP-Net", "SORT+MPC"}:
                ax.text(
                    value + (4 if metric == "wrong" else 3),
                    yy,
                    f"{value:.1f}",
                    va="center",
                    ha="left",
                    fontsize=5.35,
                    color=COLORS["text"],
                )

    ax.set_title(title, loc="left", fontsize=8.2, fontweight="bold", pad=5)
    ax.set_yticks(y_centers)
    ax.set_yticklabels(["FP10", "ID switch"])
    ax.set_xlim(*xlim)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", color=COLORS["grid"], lw=0.42, zorder=0)
    ax.text(0.98, 1.02, "lower is better", transform=ax.transAxes, ha="right", va="bottom", fontsize=5.55, color=COLORS["muted"])
    ax.tick_params(axis="both", length=2.4, width=0.58)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)


def panel_d_route(ax) -> None:
    labels = [r[0] for r in ROUTE_ROWS][::-1]
    success = np.array([r[1] for r in ROUTE_ROWS][::-1])
    lost = np.array([r[2] for r in ROUTE_ROWS][::-1])
    collision = np.array([r[3] for r in ROUTE_ROWS][::-1])
    success_counts = np.array([r[4] for r in ROUTE_ROWS][::-1])
    lost_counts = np.array([r[5] for r in ROUTE_ROWS][::-1])
    collision_counts = np.array([r[6] for r in ROUTE_ROWS][::-1])
    y = np.arange(len(labels))

    ax.barh(y, success, height=0.62, color=COLORS["success"], edgecolor="white", linewidth=0.45, zorder=3)
    ax.barh(y, lost, left=success, height=0.62, color=COLORS["lost"], edgecolor="white", linewidth=0.45, zorder=3)
    ax.barh(y, collision, left=success + lost, height=0.62, color=COLORS["collision"], edgecolor="white", linewidth=0.45, zorder=3)
    for i, yy in enumerate(y):
        if success[i] >= 24:
            ax.text(success[i] / 2, yy, f"{success_counts[i]}/300", ha="center", va="center", fontsize=5.35, color="white", fontweight="bold")
        elif success[i] > 0:
            ax.text(success[i] + 1.0, yy + 0.17, f"{success_counts[i]}/300", ha="left", va="center", fontsize=5.1, color=COLORS["success"])
        if lost[i] >= 18 and collision[i] == 0:
            ax.text(success[i] + lost[i] / 2, yy, f"{lost_counts[i]}/300", ha="center", va="center", fontsize=5.35, color=COLORS["text"])
        if collision[i] >= 18:
            ax.text(success[i] + lost[i] + collision[i] / 2, yy, f"{collision_counts[i]}/300", ha="center", va="center", fontsize=5.35, color="white", fontweight="bold")

    ax.set_title("d  Route outcome context", loc="left", fontsize=8.2, fontweight="bold", pad=5)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("episodes (%)")
    ax.grid(axis="x", color=COLORS["grid"], lw=0.42, zorder=0)
    ax.tick_params(axis="both", length=2.4, width=0.58)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)


def write_source_data(out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["figure", "panel", "condition", "method_or_comparison", "metric", "value"])
        for label, value, kind in GAIN_ROWS:
            writer.writerow(["fig_tase_main_ambiguity_results", "a", "", label, "leaderacc_difference_pp", f"{value:.3f}"])
        for condition, method, leaderacc, wrong, ids in AMBIGUITY_ROWS:
            writer.writerow(["fig_tase_main_ambiguity_results", "b", condition, method, "wrong_leader_frames_per_episode", f"{wrong:.3f}"])
            writer.writerow(["fig_tase_main_ambiguity_results", "c", condition, method, "idswitches_per_episode", f"{ids:.3f}"])
            writer.writerow(["fig_tase_main_ambiguity_results", "source", condition, method, "leaderacc_percent", f"{leaderacc:.3f}"])
        for method, success, lost, collision, success_n, lost_n, collision_n in ROUTE_ROWS:
            writer.writerow(["fig_tase_main_ambiguity_results", "d", "primary_blackout", method.replace("\n", " "), "success_percent", f"{success:.3f}"])
            writer.writerow(["fig_tase_main_ambiguity_results", "d", "primary_blackout", method.replace("\n", " "), "lost_percent", f"{lost:.3f}"])
            writer.writerow(["fig_tase_main_ambiguity_results", "d", "primary_blackout", method.replace("\n", " "), "collision_percent", f"{collision:.3f}"])
            writer.writerow(["fig_tase_main_ambiguity_results", "d", "primary_blackout", method.replace("\n", " "), "success_count", str(success_n)])
            writer.writerow(["fig_tase_main_ambiguity_results", "d", "primary_blackout", method.replace("\n", " "), "lost_count", str(lost_n)])
            writer.writerow(["fig_tase_main_ambiguity_results", "d", "primary_blackout", method.replace("\n", " "), "collision_count", str(collision_n)])


def build_figure(save_base: Path, source_csv: Path) -> None:
    fig = plt.figure(figsize=(7.35, 4.45), dpi=300)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.02, 1.0], height_ratios=[1.0, 1.0], wspace=0.40, hspace=0.58)

    panel_a_gain(fig.add_subplot(gs[0, 0]))
    grouped_metric(fig.add_subplot(gs[0, 1]), "wrong", "b  Wrong-leader exposure", "wrong-leader frames / episode", (0, 290))
    grouped_metric(fig.add_subplot(gs[1, 0]), "ids", "c  ID-switch burden", "ID switches / episode", (0, 195))
    panel_d_route(fig.add_subplot(gs[1, 1]))

    handles = []
    for method in ["Rule", "GNN selector", "Std KF", "QGIP-Net", "SORT+MPC"]:
        marker, color = METHOD_STYLE[method]
        handles.append(
            plt.Line2D(
                [0],
                [0],
                marker=marker,
                color="none",
                markerfacecolor=color,
                markeredgecolor=TOP["ink"],
                markeredgewidth=0.45,
                markersize=4.2,
                label=method,
            )
        )
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.54, 0.992), ncol=5, frameon=False, handletextpad=0.34, columnspacing=0.86)
    fig.subplots_adjust(left=0.105, right=0.985, top=0.895, bottom=0.105)

    for suffix, kwargs in {
        ".pdf": {},
        ".svg": {},
        ".png": {"dpi": 600},
        ".tiff": {"dpi": 600},
    }.items():
        fig.savefig(str(save_base) + suffix, bbox_inches="tight", **kwargs)
    plt.close(fig)
    write_source_data(source_csv)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "10_TASE_submission_20260610" / "01_manuscript" / "paper_picture"
    source_dir = root / "10_TASE_submission_20260610" / "08_paper_ready_outputs" / "source_data"
    build_figure(
        out_dir / "fig_tase_main_ambiguity_results",
        source_dir / "fig_tase_main_ambiguity_results.csv",
    )
