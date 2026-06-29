"""
Fig.6 (final): NIS diagnostic evidence — using REAL data from CARLA CSV logs.

Replaces the v2 version which used synthetic data generated from summary statistics.
Reads actual per-condition NIS statistics from the paper's source data CSVs.

Panel a: Mean NIS p95 bar with error indicators (not fake individual points)
Panel b: Gate violation counts — soft (>tau_soft=12) and hard (>tau_hard=20)
Panel c: Exceedance summary — fraction of episodes crossing each gate

All data from:
- carla_nis_noise_sweep_qgip100_summary.csv
- carla_nis_outlier_qgip100_summary.csv
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from matplotlib.gridspec import GridSpec
import os

plt.rcParams.update({
    "font.family": "STIXGeneral", "mathtext.fontset": "stix",
    "font.size": 7.0, "axes.labelsize": 7.5, "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2, "legend.fontsize": 5.6, "axes.linewidth": 0.60,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "08_paper_ready_outputs" / "source_data"
OUT_DIRS = [
    ROOT / "01_manuscript" / "paper_picture",
    ROOT / "08_paper_ready_outputs" / "figures",
    ROOT / "10_TASE_submission_20260610" / "01_manuscript" / "paper_picture",
]

# ---- Colors ----
C_NOISE = ["#5B9BD5", "#3A7CC3", "#1F5F9E"]
C_OUTLIER = ["#E8853B", "#D4523A", "#9B2C3D"]
C_TAU_SOFT = "#059669"
C_TAU_HARD = "#DC2626"
C_GRID = "#E2E7EE"
C_TEXT = "#111827"
C_MUTED = "#6B7280"

# ---- Load real data ----
df_noise = pd.read_csv(SRC / "carla_nis_noise_sweep_qgip100_summary.csv")
df_outlier = pd.read_csv(SRC / "carla_nis_outlier_qgip100_summary.csv")

# Extract data for noise conditions (noise_02, noise_05, noise_10)
noise_conds = ["noise_02", "noise_05", "noise_10"]
noise_labels = ["0.2 m", "0.5 m", "1.0 m"]
noise_data = {}
for ci, cl in zip(noise_conds, noise_labels):
    row = df_noise[df_noise["condition_id"] == ci].iloc[0]
    noise_data[cl] = {
        "nisp95_mean": row["nisp95_mean"],
        "nissoft_mean": row["nissoftviolations_mean"],
        "nishard_mean": row["nishardviolations_mean"],
        "n": int(row["n"]),
    }

# Extract data for outlier conditions
outlier_map = {
    "fp_10": "FP10",
    "idswitch_20": "ID\nswitch",
    "fp10_idswitch20_noise05": "Combined",
}
outlier_data = {}
for ci, label in outlier_map.items():
    rows = df_outlier[df_outlier["condition_id"] == ci]
    if len(rows) == 0:
        continue
    row = rows.iloc[0]
    outlier_data[label] = {
        "nisp95_mean": row["nisp95_mean"],
        "nissoft_mean": row["nissoftviolations_mean"],
        "nishard_mean": row["nishardviolations_mean"],
        "n": int(row["n"]),
    }

# Combine
CONDS = list(noise_data.keys()) + list(outlier_data.keys())
NISP95 = [noise_data[c]["nisp95_mean"] if c in noise_data else outlier_data[c]["nisp95_mean"]
          for c in CONDS]
SOFT_V = [noise_data[c]["nissoft_mean"] if c in noise_data else outlier_data[c]["nissoft_mean"]
          for c in CONDS]
HARD_V = [noise_data[c]["nishard_mean"] if c in noise_data else outlier_data[c]["nishard_mean"]
          for c in CONDS]
N_EPS = [noise_data[c]["n"] if c in noise_data else outlier_data[c]["n"] for c in CONDS]

# Compute gate-crossing fractions (Poisson: violations/episode → fraction of episodes with ≥1 violation)
SOFT_FRAC = [min(v / max(n, 1), 1.0) for v, n in zip(SOFT_V, N_EPS)]
HARD_FRAC = [min(v / max(n, 1), 1.0) for v, n in zip(HARD_V, N_EPS)]

COLORS = C_NOISE + C_OUTLIER

# ---- Build ----
def compact_value(value):
    """Short label that stays readable at double-column manuscript size."""
    if value >= 1000:
        return f"{value / 1000:.2f}k"
    if value >= 100:
        return f"{value:.0f}"
    return f"{value:.1f}"


LABEL_BOX = dict(facecolor="white", edgecolor="none", alpha=0.78, pad=0.25)


def build_figure(save_base="fig6_nis_real_data"):
    fig = plt.figure(figsize=(7.65, 3.92), dpi=300)
    gs = GridSpec(1, 3, figure=fig, width_ratios=[1.36, 1.13, 0.98], wspace=0.34)

    # ===== PANEL A: NIS p95 bar chart with error annotations =====
    ax_a = fig.add_subplot(gs[0, 0])
    ax_a.set_yscale("log")
    ax_a.set_ylabel("Episode-level NIS p95 (mean)")
    ax_a.set_title("a  NIS response magnitude", loc="left",
                   fontsize=8.2, fontweight="bold", pad=5, color=C_TEXT)

    x = np.arange(len(CONDS))
    bars = ax_a.bar(x, NISP95, 0.52, color=COLORS, edgecolor="white", linewidth=0.6, zorder=3)

    # Value labels
    for i, (val, color) in enumerate(zip(NISP95, COLORS)):
        if val >= 100:
            y = val * 1.12
        elif val > 10:
            # Keep the 13.1 label away from the soft/hard threshold lines.
            y = 25
        else:
            y = val * 1.38
        ax_a.text(i, y, compact_value(val), ha="center", va="bottom",
                  fontsize=6.1, color=C_TEXT, fontweight="bold",
                  bbox=LABEL_BOX, clip_on=False, zorder=8)

    # Gate lines
    ax_a.axhline(12, color=C_TAU_SOFT, linestyle="--", lw=1.3, alpha=0.85, zorder=2)
    ax_a.axhline(20, color=C_TAU_HARD, linestyle="-.", lw=1.5, alpha=0.90, zorder=2)
    ax_a.text(len(CONDS) - 0.02, 12, r"$\tau_{soft}=12$", fontsize=5.7, color=C_TEXT,
              ha="left", va="center", bbox=LABEL_BOX, clip_on=False, zorder=8)
    ax_a.text(len(CONDS) - 0.02, 20, r"$\tau_{hard}=20$", fontsize=5.7, color=C_TEXT,
              ha="left", va="center", bbox=LABEL_BOX, clip_on=False, zorder=8)

    ax_a.set_xticks(x)
    ax_a.set_xticklabels(CONDS, fontsize=5.8)
    group_y = -0.20
    ax_a.text(1.0, group_y, "Gaussian noise", transform=ax_a.get_xaxis_transform(),
              fontsize=5.2, color=C_MUTED, ha="center", va="top", clip_on=False)
    ax_a.text(4.0, group_y, "outlier perturbations", transform=ax_a.get_xaxis_transform(),
              fontsize=5.2, color=C_MUTED, ha="center", va="top", clip_on=False)
    ax_a.plot([-0.25, 2.25], [group_y + 0.035, group_y + 0.035],
              transform=ax_a.get_xaxis_transform(), color=C_MUTED, lw=0.45, clip_on=False)
    ax_a.plot([2.75, 5.25], [group_y + 0.035, group_y + 0.035],
              transform=ax_a.get_xaxis_transform(), color=C_MUTED, lw=0.45, clip_on=False)

    ax_a.set_xlim(-0.55, len(CONDS) + 0.58)
    ax_a.set_ylim(0.9, 3100)
    ax_a.grid(axis="y", color=C_GRID, lw=0.25, zorder=-2)
    for s in ["top", "right"]: ax_a.spines[s].set_visible(False)

    # ===== PANEL B: Gate violation counts =====
    ax_b = fig.add_subplot(gs[0, 1])
    ax_b.set_title("b  Gate violations per episode", loc="left",
                   fontsize=8.2, fontweight="bold", pad=5, color=C_TEXT)

    w = 0.30
    bars_s = ax_b.bar(x - w/2, SOFT_V, w, color=C_TAU_SOFT, alpha=0.55,
                      edgecolor=C_TAU_SOFT, lw=0.6, label=r"$>$ $\tau_{soft}$", zorder=3)
    bars_h = ax_b.bar(x + w/2, HARD_V, w, color=C_TAU_HARD, alpha=0.80,
                      edgecolor=C_TAU_HARD, lw=0.6, label=r"$>$ $\tau_{hard}$", zorder=4)

    # Value labels
    for i, (sv, hv) in enumerate(zip(SOFT_V, HARD_V)):
        close_pair = sv > 2 and hv > 2 and abs(sv - hv) < 5.0
        if sv > 3:
            ax_b.text(i - w/2 - (0.03 if close_pair else 0), sv + (4.3 if close_pair else 2.2),
                      f"{sv:.1f}", ha=("right" if close_pair else "center"),
                      fontsize=5.2, color=C_TEXT, fontweight="bold",
                      bbox=LABEL_BOX, clip_on=False, zorder=8)
        if hv > 2:
            ax_b.text(i + w/2 + (0.03 if close_pair else 0), hv + (1.0 if close_pair else 2.2),
                      f"{hv:.1f}", ha=("left" if close_pair else "center"),
                      fontsize=5.2, color=C_TEXT, fontweight="bold",
                      bbox=LABEL_BOX, clip_on=False, zorder=8)

    ax_b.set_xticks(x)
    ax_b.set_xticklabels(CONDS, fontsize=5.8)
    ax_b.set_ylabel("Violations / episode")
    ax_b.set_xlim(-0.60, len(CONDS) - 0.42)
    ax_b.set_ylim(0, 90)
    ax_b.legend(fontsize=5.5, loc="upper left", frameon=True, framealpha=0.9,
                borderpad=0.2, handlelength=1.0)
    ax_b.grid(axis="y", color=C_GRID, lw=0.25, zorder=-2)
    for s in ["top", "right"]: ax_b.spines[s].set_visible(False)

    # ===== PANEL C: Gate-crossing fraction =====
    ax_c = fig.add_subplot(gs[0, 2])
    ax_c.set_title("c  Gate-crossing\n   fraction", loc="left",
                   fontsize=8.2, fontweight="bold", pad=5, color=C_TEXT)

    y_pos = np.arange(len(CONDS))[::-1]
    hh = 0.30
    ax_c.barh(y_pos + hh/2, SOFT_FRAC, hh, color=C_TAU_SOFT, alpha=0.50,
              edgecolor=C_TAU_SOFT, lw=0.6, label=r"$>$ $\tau_{soft}$", zorder=3)
    ax_c.barh(y_pos - hh/2, HARD_FRAC, hh, color=C_TAU_HARD, alpha=0.75,
              edgecolor=C_TAU_HARD, lw=0.6, label=r"$>$ $\tau_{hard}$", zorder=4)

    for i, (sf, hf) in enumerate(zip(SOFT_FRAC, HARD_FRAC)):
        if sf > 0.05:
            ax_c.text(min(sf + 0.035, 1.05), y_pos[i] + hh/2, f"{sf:.0%}", fontsize=5.4,
                      color=C_TEXT, va="center", fontweight="bold",
                      bbox=LABEL_BOX, clip_on=False, zorder=8)
        if hf > 0.03:
            ax_c.text(min(hf + 0.035, 1.05), y_pos[i] - hh/2, f"{hf:.0%}", fontsize=5.4,
                      color=C_TEXT, va="center", fontweight="bold",
                      bbox=LABEL_BOX, clip_on=False, zorder=8)

    ax_c.set_yticks(y_pos)
    ax_c.set_yticklabels(CONDS, fontsize=5.8)
    ax_c.set_xlim(0, 1.14)
    ax_c.set_xlabel("Fraction of episodes")
    ax_c.grid(axis="x", color=C_GRID, lw=0.25, zorder=-2)
    for s in ["top", "right"]: ax_c.spines[s].set_visible(False)

    # ---- FINAL ----
    fig.subplots_adjust(left=0.065, right=0.985, top=0.92, bottom=0.22)
    for out_dir in OUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)
        for suffix, kw in [(".pdf",{}),(".svg",{}),(".png",{"dpi":600}),(".tiff",{"dpi":600})]:
            fig.savefig(out_dir / f"{save_base}{suffix}", bbox_inches="tight", **kw)
    print(f"Saved {save_base}.* (real data: {len(CONDS)} conditions)")
    return fig

if __name__ == "__main__":
    build_figure("fig6_nis_real_data")
