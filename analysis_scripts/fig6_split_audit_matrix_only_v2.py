# SUPPLEMENT-ONLY FIGURE (2026-06-14 revision)
# This data-management diagram visualises the dataset split audit.
# The 12 data points are conveyed in the main text and in the split-audit table.
# This figure is retained ONLY for the supplementary material.

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

plt.rcParams.update({
    "font.family": "STIXGeneral",
    "mathtext.fontset": "stix",
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
    "blue": "#0B63B6",
    "test": "#0B63B6",
    "zero": "#FFFFFF",
    "grid": "#C8D0DA",
    "text": "#111111",
    "muted": "#6B7280",
    "soft_bg": "#F7FAFD",
    "heldout_bg": "#F7F8FA",
}

maps = ["Town03", "Town04", "Town10HD", "Town05"]
splits = ["train", "validation", "unseen test"]
counts = np.array([
    [2227, 900, 923, 0],
    [273, 100, 77, 0],
    [0, 0, 0, 500],
], dtype=int)

def cell_color(value, j):
    if value == 0:
        return COLORS["zero"]
    if j == 3:
        return COLORS["test"]
    import matplotlib.colors as mcolors
    v = np.log10(value + 1) / np.log10(counts.max() + 1)
    c0 = np.array(mcolors.to_rgb("#E9F3FB"))
    c1 = np.array(mcolors.to_rgb("#3B83BD"))
    return c0 * (1 - v) + c1 * v

def is_dark_color(color):
    import matplotlib.colors as mcolors
    rgb = np.array(mcolors.to_rgb(color))
    lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    return lum < 0.55

def draw_split_matrix(ax):
    ax.set_title("Dataset split audit matrix", loc="left", fontsize=8.6, fontweight="bold", pad=8)
    y_positions = np.array([2, 1, 0])
    ax.set_xlim(-1.22, 3.82)
    ax.set_ylim(-0.72, 3.62)
    ax.axis("off")
    ax.axvspan(-0.5, 2.5, ymin=0.20, ymax=0.80, color=COLORS["soft_bg"], zorder=-5)
    ax.axvspan(2.5, 3.5, ymin=0.20, ymax=0.80, color=COLORS["heldout_bg"], zorder=-5)
    y_group = 3.16
    ax.text(1.0, y_group + 0.18, "training-domain maps", ha="center", va="bottom", fontsize=6.3, color=COLORS["muted"])
    ax.plot([-0.5, 2.5], [y_group, y_group], color=COLORS["grid"], lw=0.9)
    ax.plot([-0.5, -0.5], [y_group, y_group - 0.09], color=COLORS["grid"], lw=0.9)
    ax.plot([2.5, 2.5], [y_group, y_group - 0.09], color=COLORS["grid"], lw=0.9)
    ax.text(3.0, y_group + 0.18, "held-out map", ha="center", va="bottom", fontsize=6.3, color=COLORS["muted"])
    ax.plot([2.5, 3.5], [y_group, y_group], color=COLORS["grid"], lw=0.9)
    ax.plot([3.5, 3.5], [y_group, y_group - 0.09], color=COLORS["grid"], lw=0.9)
    for j, m in enumerate(maps):
        ax.text(j, 2.78, m, ha="center", va="center", fontsize=6.7, fontweight="bold" if j == 3 else "normal",
                color=COLORS["blue"] if j == 3 else COLORS["text"])
    for i, s in enumerate(splits):
        ax.text(-0.72, y_positions[i], s, ha="right", va="center", fontsize=6.8, color=COLORS["text"])
    for i, yy in enumerate(y_positions):
        for j in range(len(maps)):
            val = counts[i, j]
            fc = cell_color(val, j)
            rect = patches.Rectangle((j - 0.5, yy - 0.38), 1.0, 0.76, facecolor=fc,
                                     edgecolor=COLORS["grid"], linewidth=0.55)
            ax.add_patch(rect)
            txt_color = "white" if is_dark_color(fc) and val > 0 else COLORS["text"] if val > 0 else "#A5ACB5"
            ax.text(j, yy, f"{val:,}", ha="center", va="center",
                    fontsize=7.2 if val > 0 else 6.4, fontweight="bold" if val > 0 else "normal", color=txt_color)
    ax.plot([2.5, 2.5], [-0.42, 2.42], color=COLORS["muted"], lw=0.85, linestyle=(0, (3, 2)))
    ax.text(-0.50, -0.57, "cell values: split-manifest records", ha="left", va="center", fontsize=5.75, color=COLORS["muted"])
    ax.text(3.50, -0.57, "Town05 appears only in unseen test", ha="right", va="center", fontsize=5.75, color=COLORS["blue"])

def build_figure(save_base="fig6_split_audit_matrix_only_v2"):
    fig, ax = plt.subplots(figsize=(6.40, 2.58), dpi=300)
    draw_split_matrix(ax)
    fig.subplots_adjust(left=0.045, right=0.985, top=0.84, bottom=0.20)
    fig.savefig(f"{save_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{save_base}.svg", bbox_inches="tight")
    fig.savefig(f"{save_base}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{save_base}.tiff", dpi=600, bbox_inches="tight")
    return fig

if __name__ == "__main__":
    build_figure("fig6_split_audit_matrix_only_v2")
