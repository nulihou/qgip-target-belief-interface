# SUPPLEMENT-ONLY FIGURE (2026-06-14 revision)
# This meta-diagram visualises the evidence-to-claim mapping.
# It is retained as supplementary material; it is NOT intended for the main manuscript.
# The same information is conveyed in the main text through Table I and narrative.

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from qgip_figure_style import TOP_CONF_COLORS as TOP, apply_top_conference_style

apply_top_conference_style()
plt.rcParams.update({
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2,
    "legend.fontsize": 6.0,
    "axes.linewidth": 0.80,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "direct": TOP["blue"],
    "support": TOP["blue_light"],
    "context_edge": TOP["gray"],
    "grid": TOP["grid"],
    "muted": TOP["gray"],
    "text": TOP["ink"],
    "line": TOP["gray_mid"],
    "group_bg_1": TOP["blue_bg"],
    "group_bg_2": TOP["panel"],
    "group_bg_3": "#FBF5E8",
}

cols = [
    "ODD /\nsplit",
    "Target\nconsistency",
    "Finite-sample\nsafety",
    "Uncertainty\nresponse",
    "Reproducibility /\nprovenance",
    "Validation\nboundary",
]
rows = [
    "Main blackout\nbenchmark",
    "Primary ambiguity\ntests",
    "Detector/timing/\nraw-like stress",
    "NIS noise/outlier\ndiagnostics",
    "ODD and split\ncontrol",
    "Statistical/claim\ntraceability",
    "Figure/table/\nsource-data QA",
    "ROS2 / pre-real\nreadiness assets",
]
M = np.array([
    [1, 1, 2, 1, 1, 0],
    [1, 3, 1, 0, 1, 0],
    [2, 2, 2, 1, 1, 0],
    [0, 1, 1, 3, 1, 0],
    [3, 0, 0, 0, 1, 0],
    [2, 2, 2, 2, 3, 1],
    [1, 1, 1, 1, 3, 1],
    [0, 0, 0, 1, 2, 1],
], dtype=int)

def draw_marker(ax, x, y, val):
    if val == 0:
        return
    if val == 3:
        ax.scatter(x, y, s=58, marker="o", facecolor=COLORS["direct"], edgecolor=TOP["ink"], linewidth=0.62, zorder=5)
    elif val == 2:
        ax.scatter(x, y, s=54, marker="o", facecolor=COLORS["support"], edgecolor=COLORS["direct"], linewidth=0.62, zorder=5)
    elif val == 1:
        ax.scatter(x, y, s=50, marker="o", facecolor="white", edgecolor=COLORS["context_edge"], linewidth=0.90, zorder=5)

def build_matrix_only(save_base="fig4_claim_support_matrix_only_v3"):
    fig, ax = plt.subplots(figsize=(7.15, 3.05), dpi=300)
    ax.set_title("Claim-support matrix for the simulation-first evidence suite", loc="left", fontsize=8.5, fontweight="bold", pad=8)
    nrows, ncols = M.shape
    y_positions = np.arange(nrows)[::-1]
    x_positions = np.arange(ncols)
    ax.set_xlim(-2.82, ncols - 0.30)
    ax.set_ylim(-0.72, nrows + 0.92)
    ax.axhspan(3.5, 7.5, color=COLORS["group_bg_1"], zorder=-3)
    ax.axhspan(0.5, 3.5, color=COLORS["group_bg_2"], zorder=-3)
    ax.axhspan(-0.5, 0.5, color=COLORS["group_bg_3"], zorder=-3)
    for x in x_positions:
        ax.axvline(x, color=COLORS["grid"], linewidth=0.42, zorder=-1)
    for yy in y_positions:
        ax.axhline(yy, color=COLORS["grid"], linewidth=0.34, zorder=-1)
    for sep in [3.5, 0.5]:
        ax.axhline(sep, color=COLORS["line"], linewidth=0.76, zorder=0)
    for i, label in enumerate(rows):
        ax.text(-0.34, y_positions[i], label, ha="right", va="center", fontsize=6.15, color=COLORS["text"], linespacing=0.92)
    for j, label in enumerate(cols):
        ax.text(j, nrows + 0.08, label, ha="center", va="bottom", fontsize=6.10, color=COLORS["text"], linespacing=0.92)
    groups = [
        ("Simulation\nprotocols", 5.5, COLORS["direct"], 3.65, 7.35),
        ("Audit /\nprovenance", 2.0, COLORS["muted"], 0.65, 3.35),
        ("Readiness\nboundary", 0.0, TOP["copper_dark"], -0.35, 0.35),
    ]
    for txt, y, c, y0, y1 in groups:
        ax.text(-2.46, y, txt, ha="center", va="center", fontsize=5.75, color=c, rotation=90, fontweight="bold", linespacing=0.90)
        ax.plot([-2.14, -2.14], [y0, y1], color=c, lw=1.15)
    for i in range(nrows):
        for j in range(ncols):
            draw_marker(ax, x_positions[j], y_positions[i], M[i, j])
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["direct"], markeredgecolor=TOP["ink"], markeredgewidth=0.62, markersize=5.2, label="direct"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["support"], markeredgecolor=COLORS["direct"], markeredgewidth=0.62, markersize=5.0, label="supporting"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="white", markeredgecolor=COLORS["context_edge"], markeredgewidth=0.90, markersize=4.9, label="context / boundary"),
    ]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(-0.01, -0.10), frameon=False, ncol=3, handletextpad=0.35, columnspacing=0.90, borderaxespad=0.0)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    fig.subplots_adjust(left=0.035, right=0.985, top=0.87, bottom=0.13)
    fig.savefig(f"{save_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{save_base}.svg", bbox_inches="tight")
    fig.savefig(f"{save_base}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{save_base}.tiff", dpi=600, bbox_inches="tight")
    return fig

if __name__ == "__main__":
    build_matrix_only("fig4_claim_support_matrix_only_v3")
    plt.show()
