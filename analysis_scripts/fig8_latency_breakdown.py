"""
Fig.8 (redesigned): Per-stage latency breakdown — replaces the validation-boundary
flowchart with a genuine data figure.

Shows where the 39.4ms frame time is spent, demonstrating that:
1. GATv2 LLC dominates (64.3% of frame time)
2. POP/NIS-KF is negligible (1.4%)
3. MPC is moderate (31.5%)
4. The "interface" overhead (POP + MPC serialization) is ~33% — small enough
   to not dominate real-time behavior, large enough to provide auditable logging.

Panel a: Horizontal stacked bar — per-stage latency breakdown.
Panel b: Comparison bar — GATv2 vs POP vs MPC vs total for Rule/SORT/QGIP.
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import os

# ---- rc ----
plt.rcParams.update({
    "font.family": "STIXGeneral", "mathtext.fontset": "stix",
    "font.size": 7.0, "axes.labelsize": 7.2, "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2, "legend.fontsize": 6.0, "axes.linewidth": 0.65,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})

# ---- paths ----
ROOT = Path(__file__).resolve().parents[1]
OUT_DIRS = [
    ROOT / "01_manuscript" / "paper_picture",
    ROOT / "08_paper_ready_outputs" / "figures",
    ROOT / "10_TASE_submission_20260610" / "01_manuscript" / "paper_picture",
]

# ---- data (from paper Table: Desktop replay pipeline timing) ----
STAGES = [
    ("Detection ingest\n(JSON deserialize)",   597,   "#9CA3AF"),
    ("Leader selection\n(GATv2 LLC, CPU)",     25331, "#2563EB"),
    ("POP / NIS-KF\n(4D Kalman)",              555,   "#059669"),
    ("MPC planning\n(18×15 lattice)",           12396, "#D97706"),
    ("Command output\n(serialize)",            100,   "#9CA3AF"),
]

METHODS = [
    ("Rule+MPC",    [597, 100, 555, 12396, 100], "#9CA3AF", 67.8),
    ("SORT+MPC",    [597, 100, 555, 12396, 100], "#9CA3AF", 70.7),
    ("QGIP-Net",    [597, 25331, 555, 12396, 100], "#2563EB", 25.7),
    ("QGIP (GPU)",  [597, 2000, 555, 12396, 100], "#6366F1", 52.0),
]

# ---- build ----
def build_figure(save_base="fig8_latency_breakdown"):
    fig = plt.figure(figsize=(7.50, 4.30), dpi=300)

    # ================================================================
    # Panel a: Horizontal stacked bar — where does 39.4ms go?
    # ================================================================
    ax_a = fig.add_axes([0.08, 0.52, 0.90, 0.42])
    ax_a.set_title("a  Per-stage latency breakdown (desktop CPU replay)",
                   loc="left", fontsize=8.2, fontweight="bold", pad=5, color="#111827")

    y_pos = 0
    bar_h = 0.55
    x_start = 0
    colors = [s[2] for s in STAGES]
    labels = [s[0] for s in STAGES]
    values = [s[1] for s in STAGES]
    total = sum(values)

    cumsum = 0
    for i, (val, color) in enumerate(zip(values, colors)):
        ax_a.barh(y_pos, val, bar_h, left=cumsum, color=color, edgecolor="white",
                  linewidth=0.8, zorder=3)
        # Percentage label
        pct = val / total * 100
        if pct > 3:
            ax_a.text(cumsum + val/2, y_pos, f"{pct:.1f}%",
                      ha="center", va="center", fontsize=6.5, color="white",
                      fontweight="bold")
        # Stage label above bar
        ax_a.text(cumsum + val/2, y_pos + bar_h/2 + 0.16, labels[i].split('\n')[0],
                  ha="center", va="bottom", fontsize=5.5, color="#374151")
        if '\n' in labels[i]:
            ax_a.text(cumsum + val/2, y_pos + bar_h/2 + 0.04, labels[i].split('\n')[1],
                      ha="center", va="bottom", fontsize=5.0, color="#6B7280")
        cumsum += val

    # Total label
    ax_a.text(total + 500, y_pos, f"{total/1000:.1f} ms/frame\n({1000/total:.1f} Hz)",
              ha="left", va="center", fontsize=6.8, color="#111827", fontweight="bold")

    ax_a.set_xlim(0, total + 12000)
    ax_a.set_ylim(-0.45, 0.75)
    ax_a.set_yticks([])
    ax_a.set_xlabel("Cumulative latency (μs)")
    ax_a.grid(axis="x", color="#E2E7EE", lw=0.3, zorder=-2)
    for s in ["top", "right", "left"]:
        ax_a.spines[s].set_visible(False)
    ax_a.spines["bottom"].set_linewidth(0.6)

    # Legend
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color="#2563EB", linewidth=6, label="GATv2 LLC (learned)"),
        Line2D([0], [0], color="#059669", linewidth=6, label="POP/NIS-KF (belief)"),
        Line2D([0], [0], color="#D97706", linewidth=6, label="Lattice MPC (control)"),
        Line2D([0], [0], color="#9CA3AF", linewidth=6, label="I/O (serialization)"),
    ]
    ax_a.legend(handles=handles, fontsize=5.3, loc="lower right", frameon=True,
                framealpha=0.9, borderpad=0.25, handlelength=1.2, ncol=2)

    # ================================================================
    # Panel b: Effective frame rate comparison
    # ================================================================
    ax_b = fig.add_axes([0.08, 0.06, 0.90, 0.36])
    ax_b.set_title("b  Effective pipeline rate by method (≥20 Hz target)",
                   loc="left", fontsize=8.2, fontweight="bold", pad=5, color="#111827")

    method_names = [m[0] for m in METHODS]
    method_hz = [m[3] for m in METHODS]
    method_colors = [m[2] for m in METHODS]
    x = np.arange(len(METHODS))

    bars = ax_b.bar(x, method_hz, 0.55, color=method_colors, edgecolor="white",
                    linewidth=0.8, zorder=3)

    # Hz labels
    for i, (hz, color) in enumerate(zip(method_hz, method_colors)):
        ax_b.text(i, hz + 1.5, f"{hz:.1f} Hz", ha="center", fontsize=7.2,
                  color=color, fontweight="bold")

    # 20 Hz target line
    ax_b.axhline(20, color="#DC2626", linestyle="--", linewidth=1.3, alpha=0.8, zorder=2)
    ax_b.text(3.3, 20.8, "20 Hz CARLA target", fontsize=5.5, color="#DC2626",
              ha="right", va="bottom")

    ax_b.set_xticks(x)
    ax_b.set_xticklabels(method_names, fontsize=6.5)
    ax_b.set_ylabel("Effective frame rate (Hz)")
    ax_b.set_ylim(0, 85)
    ax_b.grid(axis="y", color="#E2E7EE", lw=0.3, zorder=-2)
    for s in ["top", "right"]:
        ax_b.spines[s].set_visible(False)

    # Annotation: QGIP GPU projection
    ax_b.annotate("projected\nGPU inference",
                  xy=(3, 52.0), xytext=(3.4, 60),
                  fontsize=5.2, color="#6366F1", ha="center",
                  arrowprops=dict(arrowstyle="->", color="#6366F1", lw=0.8))

    # ================================================================
    # FINAL
    # ================================================================
    for out_dir in OUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)
        for suffix, kwargs in [(".pdf", {}), (".svg", {}),
                                (".png", {"dpi": 600}), (".tiff", {"dpi": 600})]:
            fig.savefig(out_dir / f"{save_base}{suffix}", bbox_inches="tight", **kwargs)
    print(f"Saved {save_base}.* to all output dirs")
    return fig


if __name__ == "__main__":
    build_figure("fig8_latency_breakdown")
