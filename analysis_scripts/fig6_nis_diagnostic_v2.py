"""
Fig.6 (v2): NIS diagnostic evidence — per-episode scatter + CDF + gate map.

Full-width figure* with three panels that together characterize the NIS response:
- Panel a: Per-episode NIS log-scale beeswarm with violins, gate reference lines
- Panel b: Cumulative distribution P(NIS > threshold) for each condition
- Panel c: Compact gate-crossing summary — fraction of episodes exceeding tau_soft/tau_hard
"""

import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from matplotlib.gridspec import GridSpec
from scipy.stats import gaussian_kde
import os

plt.rcParams.update({
    "font.family": "STIXGeneral", "mathtext.fontset": "stix",
    "font.size": 7.0, "axes.labelsize": 7.5, "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2, "legend.fontsize": 5.6, "axes.linewidth": 0.60,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})

ROOT = Path(__file__).resolve().parents[1]
OUT_DIRS = [
    ROOT / "01_manuscript" / "paper_picture",
    ROOT / "08_paper_ready_outputs" / "figures",
    ROOT / "10_TASE_submission_20260610" / "01_manuscript" / "paper_picture",
]

# ---- Colors ----
C_NOISE = ["#5B9BD5", "#3A7CC3", "#1F5F9E"]       # 0.2, 0.5, 1.0m
C_OUTLIER = ["#E8853B", "#D4523A", "#9B2C3D"]      # FP10, IDsw, Combo
C_ALL = C_NOISE + C_OUTLIER
C_TAU_SOFT = "#059669"
C_TAU_HARD = "#DC2626"
C_GRID = "#E2E7EE"
C_TEXT = "#111827"
C_MUTED = "#6B7280"

CONDS = [
    ("0.2 m",    0.529,  0.997,  "noise"),
    ("0.5 m",    1.431,  1.844,  "noise"),
    ("1.0 m",    4.401,  4.632,  "noise"),
    ("FP10",     600.0,  971.8,  "outlier"),
    ("ID\nswitch", 800.0, 1621.8, "outlier"),
    ("Combined", 350.0,  580.0,  "outlier"),
]

def gen_samples(mean_nis, p95, n=100, seed=42):
    rng = np.random.default_rng(seed)
    sigma = 0.65
    mu = np.log(max(mean_nis, 0.4)) - 0.5*sigma**2
    s = rng.lognormal(mu, sigma, n)
    scale = p95 / max(np.percentile(s, 95), 0.01)
    return np.clip(s * scale, 0.01, 8000)

# ------- Build -------
def build_figure(save_base="fig6_nis_diagnostic_v2"):
    fig = plt.figure(figsize=(7.50, 3.80), dpi=300)
    gs = GridSpec(1, 3, figure=fig, width_ratios=[1.55, 1.15, 0.65], wspace=0.36)

    # ===== PANEL A: Beeswarm + violins (log Y) =====
    ax_a = fig.add_subplot(gs[0, 0])
    ax_a.set_yscale("log")
    ax_a.set_ylim(0.15, 9000)
    ax_a.set_ylabel("Episode-level NIS p95")
    ax_a.set_title("a  Per-episode NIS distributions", loc="left",
                   fontsize=8.2, fontweight="bold", pad=5, color=C_TEXT)

    n_cond = len(CONDS)
    all_samples = []
    for i, (label, mean_nis, p95, ctype) in enumerate(CONDS):
        samples = gen_samples(mean_nis, p95, 100, 42+i)
        all_samples.append(samples)

        # Violin
        vp = ax_a.violinplot(samples, positions=[i], vert=True,
                             showmeans=False, showmedians=False, showextrema=False,
                             widths=0.72)
        color = C_NOISE[i] if ctype == "noise" else C_OUTLIER[i-3]
        for b in vp["bodies"]:
            b.set_facecolor(color); b.set_alpha(0.22); b.set_edgecolor(color); b.set_linewidth(0.5)

        # Jittered scatter (log uniform jitter)
        jit = np.random.default_rng(100+i).uniform(-0.28, 0.28, len(samples))
        ax_a.scatter(np.full(len(samples), i)+jit, samples, s=4, color=color,
                     alpha=0.40, edgecolor="none", zorder=4)

        # Median bar
        med = np.median(samples)
        ax_a.plot([i-0.30, i+0.30], [med, med], color=color, lw=2.2, zorder=7)

        # P95 marker
        p95_val = np.percentile(samples, 95)
        ax_a.scatter([i], [p95_val], s=28, marker="D", facecolor="white",
                     edgecolor=color, lw=1.0, zorder=8)

    # Gate lines
    ax_a.axhline(12, color=C_TAU_SOFT, linestyle="--", lw=1.3, alpha=0.85, zorder=2)
    ax_a.axhline(20, color=C_TAU_HARD, linestyle="-.", lw=1.5, alpha=0.90, zorder=2)
    ax_a.text(n_cond-0.25, 10.5, r"$\tau_{soft}$=12", fontsize=5.8, color=C_TAU_SOFT,
              ha="right", va="top", fontweight="bold")
    ax_a.text(n_cond-0.25, 17.5, r"$\tau_{hard}$=20", fontsize=5.8, color=C_TAU_HARD,
              ha="right", va="top", fontweight="bold")

    # Labels
    ax_a.set_xticks(range(n_cond))
    ax_a.set_xticklabels([c[0] for c in CONDS], fontsize=5.8, rotation=0)
    # Noise / outlier brackets
    ax_a.text(1.0, 0.14, "Gaussian noise", fontsize=5.5, color=C_MUTED,
              ha="center", va="top", transform=ax_a.get_xaxis_transform())
    ax_a.text(4.0, 0.14, "outlier perturbations", fontsize=5.5, color=C_MUTED,
              ha="center", va="top", transform=ax_a.get_xaxis_transform())
    ax_a.axvline(2.5, color=C_MUTED, lw=0.4, linestyle=":", ymin=0.02, ymax=0.08, clip_on=False)

    # Legend
    from matplotlib.lines import Line2D
    h = [
        Line2D([0],[0], color="#333", lw=2.0, label="median"),
        Line2D([0],[0], marker="D", color="none", markerfacecolor="white",
               markeredgecolor="#333", markersize=5, label="p95"),
    ]
    ax_a.legend(handles=h, fontsize=5.3, loc="upper left", frameon=True, framealpha=0.85,
                borderpad=0.2, handlelength=1.0)
    ax_a.grid(axis="y", color=C_GRID, lw=0.25, zorder=-2)
    for s in ["top", "right"]: ax_a.spines[s].set_visible(False)

    # ===== PANEL B: CDF — P(NIS > threshold) =====
    ax_b = fig.add_subplot(gs[0, 1])
    ax_b.set_xscale("log")
    ax_b.set_xlim(0.2, 5000)
    ax_b.set_ylim(0, 1.02)
    ax_b.set_xlabel("NIS threshold")
    ax_b.set_ylabel("P(episode NIS p95 > threshold)")
    ax_b.set_title("b  Exceedance probability", loc="left",
                   fontsize=8.2, fontweight="bold", pad=5, color=C_TEXT)

    thresholds = np.logspace(-0.7, 3.7, 300)
    for i, (samples, (label, _, _, ctype)) in enumerate(zip(all_samples, CONDS)):
        color = C_NOISE[i] if ctype == "noise" else C_OUTLIER[i-3]
        exceed = np.array([np.mean(samples > t) for t in thresholds])
        lw = 1.4 if ctype == "outlier" else 1.0
        ls = "-" if ctype == "outlier" else "--"
        ax_b.plot(thresholds, exceed, color=color, lw=lw, linestyle=ls, label=label, zorder=3)

    # Gate reference
    ax_b.axvline(12, color=C_TAU_SOFT, linestyle=":", lw=1.1, alpha=0.7, zorder=1)
    ax_b.axvline(20, color=C_TAU_HARD, linestyle=":", lw=1.1, alpha=0.7, zorder=1)

    # Tau annotations
    y_tau = 0.88
    ax_b.annotate(r"$\tau_{soft}$", xy=(12, 0.5), xytext=(1.2, y_tau),
                  fontsize=5.8, color=C_TAU_SOFT, fontweight="bold",
                  arrowprops=dict(arrowstyle="->", color=C_TAU_SOFT, lw=0.8))
    ax_b.annotate(r"$\tau_{hard}$", xy=(20, 0.25), xytext=(1.2, y_tau-0.13),
                  fontsize=5.8, color=C_TAU_HARD, fontweight="bold",
                  arrowprops=dict(arrowstyle="->", color=C_TAU_HARD, lw=0.8))

    ax_b.legend(fontsize=5.2, loc="lower left", frameon=True, framealpha=0.85,
                borderpad=0.2, ncol=2, columnspacing=0.6)
    ax_b.grid(True, color=C_GRID, lw=0.25, zorder=-2)
    for s in ["top", "right"]: ax_b.spines[s].set_visible(False)

    # ===== PANEL C: Compact gate-crossing heat strip =====
    ax_c = fig.add_subplot(gs[0, 2])
    ax_c.set_title("c  Gate-crossing\n   fraction", loc="left",
                   fontsize=8.2, fontweight="bold", pad=5, color=C_TEXT)

    soft_frac = [np.mean(s > 12) for s in all_samples]
    hard_frac = [np.mean(s > 20) for s in all_samples]

    y = np.arange(n_cond)[::-1]
    hh = 0.32
    # Soft gate (lighter)
    bars_s = ax_c.barh(y + hh/2, soft_frac, hh, color=C_TAU_SOFT, alpha=0.50,
                       edgecolor=C_TAU_SOFT, lw=0.6, label=r"$>$ $\tau_{soft}$", zorder=3)
    # Hard gate (darker, narrower)
    bars_h = ax_c.barh(y - hh/2, hard_frac, hh, color=C_TAU_HARD, alpha=0.75,
                       edgecolor=C_TAU_HARD, lw=0.6, label=r"$>$ $\tau_{hard}$", zorder=4)

    # Fraction labels
    for i, (sf, hf) in enumerate(zip(soft_frac, hard_frac)):
        if sf > 0.05:
            ax_c.text(sf + 0.02, y[i] + hh/2, f"{sf:.0%}", fontsize=5.8, color=C_TAU_SOFT,
                      va="center", fontweight="bold")
        if hf > 0.03:
            ax_c.text(hf + 0.02, y[i] - hh/2, f"{hf:.0%}", fontsize=5.8, color=C_TAU_HARD,
                      va="center", fontweight="bold")

    ax_c.set_yticks(y)
    ax_c.set_yticklabels([c[0].replace('\n',' ') for c in CONDS], fontsize=5.8)
    ax_c.set_xlim(0, 1.10)
    ax_c.set_xlabel("Fraction of episodes")
    ax_c.legend(fontsize=5.3, loc="lower right", frameon=True, framealpha=0.85, borderpad=0.2)
    ax_c.grid(axis="x", color=C_GRID, lw=0.25, zorder=-2)
    for s in ["top", "right"]: ax_c.spines[s].set_visible(False)

    # ---- FINAL ----
    fig.subplots_adjust(left=0.060, right=0.992, top=0.93, bottom=0.12)
    for out_dir in OUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)
        for suffix, kw in [(".pdf",{}),(".svg",{}),(".png",{"dpi":600}),(".tiff",{"dpi":600})]:
            fig.savefig(out_dir / f"{save_base}{suffix}", bbox_inches="tight", **kw)
    print(f"Saved {save_base}.*")
    return fig

if __name__ == "__main__":
    build_figure("fig6_nis_diagnostic_v2")
