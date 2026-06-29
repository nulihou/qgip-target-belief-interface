"""
Fig.8 (v2): Per-stage latency decomposition — elegant scientific visualization.

Panel a: Horizontal waterfall — per-stage latency with proportional colored blocks,
         showing the decomposition of the 39.4ms frame into 5 stages.
Panel b: Latency × object-count scaling — how pipeline latency grows with scene complexity.
Panel c: Compact method comparison — effective Hz for Rule/SORT/QGIP/QGIP-GPU.
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from matplotlib.gridspec import GridSpec
import os

plt.rcParams.update({
    "font.family": "STIXGeneral", "mathtext.fontset": "stix",
    "font.size": 7.0, "axes.labelsize": 7.5, "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2, "legend.fontsize": 5.8, "axes.linewidth": 0.55,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})

ROOT = Path(__file__).resolve().parents[1]
OUT_DIRS = [
    ROOT / "01_manuscript" / "paper_picture",
    ROOT / "08_paper_ready_outputs" / "figures",
    ROOT / "10_TASE_submission_20260610" / "01_manuscript" / "paper_picture",
]

# ---- data ----
STAGES = [
    ("Detect\n   ingest",   597,   "#B0BEC5"),
    ("GATv2\n   LLC",       25331, "#2563EB"),
    ("POP/\n   NIS-KF",     555,   "#059669"),
    ("MPC\n   planner",     12396, "#D97706"),
    ("Cmd\n   out",         100,   "#B0BEC5"),
]
TOTAL_US = 39428

METHODS = [
    ("Rule",      597+100+555+12396+100, "#78909C"),
    ("SORT",      597+100+555+12396+100, "#78909C"),
    ("QGIP\n(CPU)",  TOTAL_US,           "#2563EB"),
    ("QGIP\n(GPU\nproj.)",  597+2000+555+12396+100, "#6366F1"),
]

# ---- build ----
LABEL_BOX = dict(facecolor="white", edgecolor="none", alpha=0.82, pad=0.20)


def build_figure(save_base="fig8_latency_breakdown_v2"):
    fig = plt.figure(figsize=(7.55, 3.86), dpi=300)
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.58, 1.0], wspace=0.39)

    # ============================================================
    # PANEL A: Horizontal waterfall breakdown
    # ============================================================
    ax_a = fig.add_subplot(gs[0, 0])
    ax_a.set_title("a  Where 39.4 ms goes: per-stage decomposition",
                   loc="left", fontsize=8.2, fontweight="bold", pad=5, color="#111827")

    n = len(STAGES)
    y_pos = np.arange(n)[::-1] * 0.85
    bar_h = 0.55

    cumsum = 0
    for i, (name, val, color) in enumerate(STAGES):
        yy = y_pos[i]
        # Main bar
        ax_a.barh(yy, val/1000, bar_h, left=cumsum/1000, color=color,
                  edgecolor="white", linewidth=0.6, zorder=3)

        pct = val / TOTAL_US * 100
        x_end = (cumsum + val) / 1000

        # Stage label on left
        ax_a.text(-1.2, yy, name, ha="right", va="center", fontsize=6.2,
                  color="#374151", linespacing=0.85)

        # µs value on right
        if pct >= 5:
            label = f"{val/1000:.1f} ms  ({pct:.1f}%)"
            label_x = min(x_end + 0.40, 38.95)
        else:
            label = f"{val/1000:.1f} ms\n{pct:.1f}%"
            label_x = 39.65 if name.startswith("Cmd") else x_end + 0.48
        ax_a.text(label_x, yy, label, ha="left", va="center",
                  fontsize=5.8, color="#111827", linespacing=0.88,
                  bbox=LABEL_BOX, clip_on=False, zorder=7)

        cumsum += val

    # Total marker
    ax_a.axvline(TOTAL_US/1000, color="#111827", lw=1.0, linestyle="--", alpha=0.5, zorder=1)
    ax_a.text(TOTAL_US/1000 + 0.5, y_pos[0] + 0.55, f"{TOTAL_US/1000:.1f} ms total\n(25.4 Hz)",
              fontsize=6.8, color="#111827", fontweight="bold", ha="left", va="top")

    ax_a.set_xlim(-2.5, TOTAL_US/1000 * 1.135)
    ax_a.set_ylim(y_pos[-1] - 0.58, y_pos[0] + 0.86)
    ax_a.set_yticks([])
    ax_a.set_xlabel("Cumulative latency (ms)")
    ax_a.grid(axis="x", color="#E2E7EE", lw=0.25, zorder=-2)

    # Subtle region annotations, separated from title and numeric labels.
    region_y = y_pos[0] + 0.47
    ax_a.text(0.6/2, region_y, "I/O", fontsize=5.2, color="#9CA3AF", ha="center",
              va="center", bbox=LABEL_BOX)
    ax_a.text(0.6 + 25.3/2, region_y, "learned", fontsize=5.2, color="#2563EB", ha="center",
              va="center", bbox=LABEL_BOX)
    ax_a.text(0.6+25.3+0.55/2, region_y, "belief", fontsize=5.2, color="#059669", ha="center",
              va="center", bbox=LABEL_BOX)
    ax_a.text(0.6+25.3+0.55+12.4/2, region_y, "control", fontsize=5.2, color="#D97706", ha="center",
              va="center", bbox=LABEL_BOX)

    for s in ["top", "right", "left"]:
        ax_a.spines[s].set_visible(False)
    ax_a.spines["bottom"].set_linewidth(0.6)
    ax_a.tick_params(axis="both", length=2.2, width=0.5)

    # ============================================================
    # PANEL B: Effective frame rate + scalability
    # ============================================================
    ax_b = fig.add_subplot(gs[0, 1])

    # --- Sub-panel b1: Frame rate comparison ---
    method_names = [m[0] for m in METHODS]
    method_us = [m[1] for m in METHODS]
    method_colors = [m[2] for m in METHODS]
    method_hz = [1e6/m for m in method_us]

    x = np.arange(len(METHODS))
    bars = ax_b.bar(x, method_hz, 0.54, color=method_colors, edgecolor="white",
                    linewidth=0.6, zorder=3)

    # Hz values on bars
    for i, (hz, color) in enumerate(zip(method_hz, method_colors)):
        ax_b.text(i, hz + 2.0, f"{hz:.1f}", ha="center", fontsize=8.5,
                  color="#111827", fontweight="bold", bbox=LABEL_BOX,
                  clip_on=False, zorder=7)

    # 20 Hz target
    ax_b.axhline(20, color="#DC2626", linestyle="--", lw=1.4, alpha=0.80, zorder=2)
    ax_b.text(3.45, 21.5, "20 Hz\nCARLA target", fontsize=5.5, color="#DC2626",
              ha="center", va="bottom", linespacing=0.85, bbox=LABEL_BOX)

    ax_b.set_xticks(x)
    ax_b.set_xticklabels(method_names, fontsize=6.0, linespacing=0.85)
    ax_b.set_ylabel("Effective frame rate (Hz)")
    ax_b.set_ylim(0, 90)
    ax_b.set_title("b  Frame rate by method", loc="left",
                   fontsize=8.2, fontweight="bold", pad=5, color="#111827")
    ax_b.grid(axis="y", color="#E2E7EE", lw=0.25, zorder=-2)

    # Annotation
    ax_b.annotate("GPU\nprojection", xy=(3, 57), xytext=(3.35, 68),
                  fontsize=5.3, color="#6366F1", ha="center", linespacing=0.85,
                  arrowprops=dict(arrowstyle="->", color="#6366F1", lw=0.7))

    for s in ["top", "right"]:
        ax_b.spines[s].set_visible(False)

    # ============================================================
    # FINAL
    # ============================================================
    fig.subplots_adjust(left=0.080, right=0.990, top=0.91, bottom=0.16)

    for out_dir in OUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)
        for suffix, kw in [(".pdf",{}),(".svg",{}),(".png",{"dpi":600}),(".tiff",{"dpi":600})]:
            fig.savefig(out_dir / f"{save_base}{suffix}", bbox_inches="tight", **kw)
    print(f"Saved {save_base}.*")
    return fig

if __name__ == "__main__":
    build_figure("fig8_latency_breakdown_v2")
