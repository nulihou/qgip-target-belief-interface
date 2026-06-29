"""
Fig.9 (redesigned): Leader-consistency degradation under escalating stress.

Shows per-condition distributions across the full stress spectrum, from nominal
through ambiguity to boundary conditions. Every mark is one CARLA episode.

Panel a: LeaderAcc cascade — per-condition violin+swarm for QGIP-Net and SORT,
         ordered by increasing stress severity. Connected medians show the
         degradation gradient.
Panel b: ID-switch escalation — same structure for ID-switch burden.
         Reveals the trade-off: QGIP-Net sacrifices a few LeaderAcc points
         for dramatic ID-switch suppression as stress increases.
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D

# ---- rc ----
plt.rcParams.update({
    "font.family": "STIXGeneral", "mathtext.fontset": "stix",
    "font.size": 7.0, "axes.labelsize": 7.5, "xtick.labelsize": 6.0,
    "ytick.labelsize": 6.2, "legend.fontsize": 5.8, "axes.linewidth": 0.72,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})

# ---- paths ----
ROOT = Path(__file__).resolve().parents[1]
PAIRED = ROOT / "07_computer_experiments" / "carla_stress_paired_metrics300" / "paper"
BOUNDARY = ROOT / "07_computer_experiments" / "carla_stress_boundary100" / "paper"
CRITICAL = ROOT / "07_computer_experiments" / "critical_experiments_20260606"
OUT_PICTURE = ROOT / "01_manuscript" / "paper_picture"
OUT_FIGS = ROOT / "08_paper_ready_outputs" / "figures"

# ---- colours ----
C = {
    "qgip": "#0B63B6", "sort": "#D55E00",
    "grid": "#E2E7EE", "text": "#111111", "muted": "#6B7280",
    "qgip_light": "#D0E2F7", "sort_light": "#FAD4C0",
}

# ---- condition registry (ordered by severity) ----
CONDITIONS = [
    ("nominal",   "Nominal\n(N=1000)",  1000, False),
    ("fp_10",     "fp_10\n(N=300)",      300, True),
    ("idswitch",  "idswitch\n(N=300)",   300, True),
    ("fp_20",     "fp_20\n(N=100)",      100, False),
    ("idswitch_40", "idsw_40\n(N=100)",  100, False),
    ("boundary",  "fp20+idsw20\n(N=100)", 100, False),
]

def load_episodes(condition, method_key):
    """Load per-episode CSV, return DataFrame or None."""
    if condition == "nominal":
        if method_key == "qgip":
            p = ROOT / "07_computer_experiments" / "carla_main1000_qgip" / "paper" / "main_default" / "qgip.csv"
        elif method_key == "sort":
            return None  # SORT not run for nominal 1000
        else:
            return None
    elif condition in ("fp_10", "idswitch"):
        if method_key == "sort":
            p = CRITICAL / f"sort_mpc_{condition}" / "sort_mpc.csv"
        else:
            p = PAIRED / condition / f"{method_key}.csv"
    elif condition in ("fp_20", "idswitch_40"):
        p = BOUNDARY / condition / f"{method_key}.csv"
    elif condition == "boundary":
        p = BOUNDARY / "fp20_idswitch20" / f"{method_key}.csv"
    else:
        return None
    if not p.exists():
        return None
    df = pd.read_csv(p)
    for c in ["LeaderAcc", "IDSwitches"]:
        if c not in df.columns:
            return None
    df["LeaderAcc_pct"] = df["LeaderAcc"] * 100
    return df


def draw_cascade(ax, conditions, methods, metric, ylabel, ylim, title, panel_label):
    """Generic cascade plot: violin + swarm + connected medians across conditions."""
    n_cond = len(conditions)
    n_meth = len(methods)
    ax.set_xlim(-0.6, n_cond - 0.4)
    ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", fontsize=8.2, fontweight="bold", pad=4, color=C["text"])

    # background bands for N=1000 vs N=300 vs N=100
    for i, (cid, clabel, n_ep, is_primary) in enumerate(conditions):
        if n_ep == 1000:
            ax.axvspan(i - 0.42, i + 0.42, color="#EAF6F1", alpha=0.22, zorder=-5)
        elif n_ep == 100:
            ax.axvspan(i - 0.42, i + 0.42, color="#FCF5E7", alpha=0.22, zorder=-5)

    # store medians for connecting lines
    medians = {m: [] for m in methods}
    valid_indices = {m: [] for m in methods}

    for i, (cid, clabel, n_ep, is_primary) in enumerate(conditions):
        for j, mk in enumerate(methods):
            df = load_episodes(cid, mk)
            if df is None or len(df) == 0:
                medians[mk].append(np.nan)
                continue
            vals = df[metric].dropna().values
            if metric == "IDSwitches":
                vals_plot = vals  # already per-episode counts
            else:
                vals_plot = vals
            if len(vals) == 0:
                medians[mk].append(np.nan)
                continue

            offset = (j - (n_meth - 1) / 2) * 0.14
            x_pos = i + offset

            # small violin
            vp = ax.violinplot(vals_plot, positions=[x_pos], vert=True,
                               showmeans=False, showmedians=False, showextrema=False,
                               widths=0.10)
            color = C["qgip"] if mk == "qgip" else C["sort"]
            for b in vp["bodies"]:
                b.set_facecolor(color)
                b.set_alpha(0.30)
                b.set_edgecolor(color)
                b.set_linewidth(0.4)

            # jittered swarm
            jit = np.random.default_rng(42 + i * 7 + j * 13).uniform(-0.05, 0.05, len(vals_plot))
            ax.scatter(np.full(len(vals_plot), x_pos) + jit, vals_plot, s=2.5,
                       color=color, alpha=0.28, edgecolor="none", zorder=3)

            # median bar
            med = np.median(vals_plot)
            ax.plot([x_pos - 0.08, x_pos + 0.08], [med, med], color=color,
                    linewidth=1.8, zorder=8)
            medians[mk].append(med)
            valid_indices[mk].append(x_pos)

    # connect medians with lines
    for mk in methods:
        xs = valid_indices[mk]
        ys = medians[mk]
        # filter nans
        xs_clean = [x for x, y in zip(xs, ys) if not np.isnan(y)]
        ys_clean = [y for y in ys if not np.isnan(y)]
        if len(xs_clean) >= 2:
            color = C["qgip"] if mk == "qgip" else C["sort"]
            ls = "-" if mk == "qgip" else "--"
            ax.plot(xs_clean, ys_clean, color=color, linewidth=1.3, linestyle=ls,
                    alpha=0.65, zorder=1)

    # condition labels
    ax.set_xticks(range(n_cond))
    ax.set_xticklabels([cl for _, cl, _, _ in conditions], fontsize=5.8)

    # legend
    handles = [
        Line2D([0], [0], color=C["qgip"], linewidth=2.0, label="QGIP-Net (median)"),
        Line2D([0], [0], color=C["sort"], linewidth=2.0, linestyle="--", label="SORT+MPC (median)"),
    ]
    ax.legend(handles=handles, fontsize=5.4, loc="upper right" if "ID" not in metric else "lower right",
              frameon=True, framealpha=0.85, borderpad=0.2, handlelength=1.2)

    ax.grid(axis="y", color=C["grid"], lw=0.3, zorder=-3)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="both", length=2.2, width=0.52)

    # N annotations
    for i, (cid, clabel, n_ep, is_primary) in enumerate(conditions):
        ax.text(i, ylim[0] + (ylim[1] - ylim[0]) * 0.02, f"N={n_ep}",
                ha="center", va="bottom", fontsize=5.0, color=C["muted"])

    # vertical divider between primary and boundary
    ax.axvline(2.5, color=C["muted"], lw=0.55, linestyle=":", zorder=-1)
    ax.text(1.25, ylim[0] + (ylim[1] - ylim[0]) * 0.96, "primary (N=300)",
            ha="center", va="top", fontsize=5.2, color=C["text"], alpha=0.7)
    ax.text(4.0, ylim[0] + (ylim[1] - ylim[0]) * 0.96, "boundary (N=100)",
            ha="center", va="top", fontsize=5.2, color=C["text"], alpha=0.7)


# ---- build ----
def build_figure(save_base="fig9_stress_escalation_cascade"):
    fig = plt.figure(figsize=(7.50, 4.60), dpi=300)
    gs = GridSpec(2, 1, figure=fig, height_ratios=[1.0, 1.0], hspace=0.24)

    ax_a = fig.add_subplot(gs[0])
    draw_cascade(ax_a, CONDITIONS, ["qgip", "sort"],
                 metric="LeaderAcc_pct", ylabel="LeaderAcc (%)", ylim=(25, 103),
                 title="a  Leader-accuracy cascade under escalating stress",
                 panel_label="a")

    ax_b = fig.add_subplot(gs[1])
    draw_cascade(ax_b, CONDITIONS, ["qgip", "sort"],
                 metric="IDSwitches", ylabel="ID switches / episode", ylim=(-8, 320),
                 title="b  ID-switch escalation under increasing perturbation",
                 panel_label="b")

    fig.text(0.065, 0.012,
             "Violins = per-episode distribution; connected markers = condition median. N=1000 nominal; N=300 primary; N=100 boundary. SORT data not available for nominal N=1000.",
             fontsize=5.3, color=C["muted"], ha="left", va="center")

    fig.subplots_adjust(left=0.100, right=0.988, top=0.97, bottom=0.07)

    for out_dir in (OUT_PICTURE, OUT_FIGS):
        for suffix, kwargs in [(".pdf", {}), (".svg", {}),
                                (".png", {"dpi": 600}), (".tiff", {"dpi": 600})]:
            fig.savefig(out_dir / f"{save_base}{suffix}", bbox_inches="tight", **kwargs)
    print(f"Saved {save_base}.* to {OUT_PICTURE} and {OUT_FIGS}")
    return fig


if __name__ == "__main__":
    build_figure("fig9_stress_escalation_cascade")
