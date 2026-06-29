"""
Fig.8 (redesigned): Per-episode target-selection evidence under ambiguity.

Shows the FULL per-episode distribution of LeaderAcc and wrong-leader exposure,
not just aggregate means. Every mark is one CARLA episode.

Panel a: Raincloud (half-violin + jittered swarm) of per-episode LeaderAcc
         for each method under fp_10 and idswitch.
Panel b: Joint distribution scatter: WrongLeaderFrames vs LeaderAcc.
         Each point = one episode. Marginal histograms on axes.
"""

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
from pathlib import Path
from matplotlib.gridspec import GridSpec

# ---- rc ----
plt.rcParams.update({
    "font.family": "STIXGeneral", "mathtext.fontset": "stix",
    "font.size": 7.0, "axes.labelsize": 7.5, "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2, "legend.fontsize": 5.8, "axes.linewidth": 0.72,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
})

# ---- paths ----
ROOT = Path(__file__).resolve().parents[1]
PAIRED = ROOT / "07_computer_experiments" / "carla_stress_paired_metrics300" / "paper"
CRITICAL = ROOT / "07_computer_experiments" / "critical_experiments_20260606"
OUT_PICTURE = ROOT / "01_manuscript" / "paper_picture"
OUT_FIGS = ROOT / "08_paper_ready_outputs" / "figures"

# ---- colours ----
C = {
    "qgip": "#0B63B6", "sort": "#D55E00", "rule": "#8E94A0",
    "noquery": "#E69F00", "stdkf": "#5DADE2",
    "grid": "#E2E7EE", "text": "#111111", "muted": "#6B7280",
}

METHOD_LABEL = {
    "qgip": "QGIP-Net", "sort": "SORT+MPC", "rule": "Rule+MPC",
    "noquery": "No-query+MPC", "stdkf": "Std-KF+MPC",
}
METHOD_COLOR = {"qgip": C["qgip"], "sort": C["sort"], "rule": C["rule"],
                "noquery": C["noquery"], "stdkf": C["stdkf"]}
METHOD_ZORDER = {"qgip": 6, "sort": 5, "rule": 2, "noquery": 2, "stdkf": 2}

# ---- data loading ----
def load_episodes(condition, method_key):
    """Load per-episode CSV. Returns DataFrame with key columns."""
    if method_key == "sort":
        if condition == "fp_10":
            p = CRITICAL / "sort_mpc_fp10" / "sort_mpc.csv"
        elif condition == "idswitch":
            p = CRITICAL / "sort_mpc_idswitch" / "sort_mpc.csv"
        else:
            return None
    else:
        p = PAIRED / condition / f"{method_key}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    required = ["LeaderAcc", "WrongLeaderFrames", "IDSwitches"]
    for c in required:
        if c not in df.columns:
            return None
    df["LeaderAcc_pct"] = df["LeaderAcc"] * 100
    return df

def load_all(condition, methods):
    """Return dict method_key -> DataFrame."""
    out = {}
    for mk in methods:
        df = load_episodes(condition, mk)
        if df is not None:
            out[mk] = df
    return out

# ---- panel a: raincloud ----
def draw_raincloud(ax, data_dict, condition_label, ylim=(0, 105)):
    """Half-violin + jittered swarm + median marker for each method."""
    methods = list(data_dict.keys())
    n = len(methods)
    ax.set_xlim(-0.5, n - 0.5)
    ax.set_ylim(*ylim)
    ax.set_ylabel("LeaderAcc (%)")
    ax.set_title(condition_label, loc="left", fontsize=8.2, fontweight="bold", pad=4,
                 color=C["text"])

    for i, mk in enumerate(methods):
        vals = data_dict[mk]["LeaderAcc_pct"].dropna().values
        if len(vals) == 0:
            continue
        # violin (left half)
        vp = ax.violinplot(vals, positions=[i], vert=True, showmeans=False,
                           showmedians=False, showextrema=False, widths=0.72)
        for b in vp["bodies"]:
            b.set_facecolor(METHOD_COLOR[mk])
            b.set_alpha(0.28)
            b.set_edgecolor(METHOD_COLOR[mk])
            b.set_linewidth(0.5)
        # jittered swarm
        jit = np.random.default_rng(42).uniform(-0.22, 0.22, len(vals))
        ax.scatter(np.full(len(vals), i) + jit, vals, s=4, color=METHOD_COLOR[mk],
                   alpha=0.35, edgecolor="none", zorder=METHOD_ZORDER.get(mk, 2))
        # median bar
        med = np.median(vals)
        ax.plot([i - 0.28, i + 0.28], [med, med], color=METHOD_COLOR[mk],
                linewidth=2.2, zorder=8)
        # mean marker
        mean_v = np.mean(vals)
        ax.scatter([i], [mean_v], s=18, marker="D", color="white",
                   edgecolor=METHOD_COLOR[mk], linewidth=1.0, zorder=9)
        # label
        ax.text(i, ylim[0] + 1.5, f"{mean_v:.1f}", ha="center", va="bottom",
                fontsize=5.8, fontweight="bold", color=METHOD_COLOR[mk])

    ax.set_xticks(range(n))
    ax.set_xticklabels([METHOD_LABEL[m] for m in methods], rotation=18, ha="right",
                       fontsize=6.0)
    ax.grid(axis="y", color=C["grid"], lw=0.35, zorder=-2)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="both", length=2.2, width=0.52)
    # median legend
    ax.plot([], [], color="#333333", linewidth=2.0, label="median")
    ax.scatter([], [], s=14, marker="D", color="white", edgecolor="#333333",
               linewidth=0.9, label="mean")
    ax.legend(fontsize=5.2, loc="lower right", frameon=True, framealpha=0.85,
              borderpad=0.2, handlelength=1.0)


# ---- panel b: joint distribution scatter ----
def draw_joint_scatter(ax, fp10_data, idsw_data):
    """Scatter of WrongLeaderFrames vs LeaderAcc with marginal histograms."""
    ax.set_xlim(-5, 340)
    ax.set_ylim(25, 103)
    ax.set_xlabel("Wrong-leader frames / episode")
    ax.set_ylabel("LeaderAcc (%)")
    ax.set_title("Joint distribution: LeaderAcc vs wrong-leader exposure",
                 loc="left", fontsize=8.2, fontweight="bold", pad=4, color=C["text"])

    # background regions
    ax.axvspan(0, 80, ymin=(78 - 25) / 78, ymax=1, color="#EAF6F1", alpha=0.55, zorder=-4)
    ax.axvspan(200, 340, ymin=0, ymax=(55 - 25) / 78, color="#FDEFF0", alpha=0.45, zorder=-4)
    ax.text(3, 101.5, "desired", fontsize=5.2, color="#147A55", ha="left", va="top")
    ax.text(325, 51, "stable-but-\nwrong", fontsize=5.2, color="#A04A4A", ha="right", va="top",
            linespacing=0.88)

    all_data = {}
    for mk, df in fp10_data.items():
        all_data[("fp_10", mk)] = df
    for mk, df in idsw_data.items():
        all_data[("idswitch", mk)] = df

    for (cond, mk), df in all_data.items():
        if df is None or len(df) == 0:
            continue
        marker = "o" if cond == "fp_10" else "s"
        x = df["WrongLeaderFrames"].values
        y = df["LeaderAcc_pct"].values
        ax.scatter(x, y, s=7, color=METHOD_COLOR[mk], marker=marker,
                   alpha=0.32, edgecolor="none", zorder=METHOD_ZORDER.get(mk, 1))

    # marginal rug plots on axes
    for cond, data_dict in [("fp_10", fp10_data), ("idswitch", idsw_data)]:
        for mk, df in data_dict.items():
            if df is None: continue
            y_base = 23.5 if cond == "fp_10" else 24.3
            ax.plot(df["WrongLeaderFrames"].values, np.full(len(df), y_base), "|",
                    color=METHOD_COLOR[mk], alpha=0.15, markersize=3, markeredgewidth=0.4)

    # legend
    from matplotlib.lines import Line2D
    handles = [Line2D([0], [0], marker="o", color="none", markerfacecolor="grey",
                      markersize=4.5, label="fp_10 (N=300)"),
               Line2D([0], [0], marker="s", color="none", markerfacecolor="grey",
                      markersize=4.5, label="idswitch (N=300)")]
    for mk in ["qgip", "sort", "rule", "noquery", "stdkf"]:
        handles.append(Line2D([0], [0], marker="o", color="none",
                              markerfacecolor=METHOD_COLOR[mk], markersize=5,
                              label=METHOD_LABEL[mk]))
    ax.legend(handles=handles, fontsize=4.8, loc="lower left", frameon=True,
              framealpha=0.88, ncol=2, borderpad=0.25, handletextpad=0.3,
              columnspacing=1.0)

    ax.grid(True, color=C["grid"], lw=0.3, zorder=-3)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="both", length=2.2, width=0.52)


# ---- build ----
def build_figure(save_base="fig8_per_episode_target_selection"):
    fp10 = load_all("fp_10", ["qgip", "sort", "rule", "noquery"])
    idsw = load_all("idswitch", ["qgip", "sort", "rule", "stdkf"])

    fig = plt.figure(figsize=(7.50, 5.50), dpi=300)
    gs = GridSpec(2, 1, figure=fig, height_ratios=[1.05, 1.0], hspace=0.26)

    # Panel a: raincloud (top half split into 2 columns)
    gs_top = gs[0].subgridspec(1, 2, wspace=0.38)
    ax_a1 = fig.add_subplot(gs_top[0, 0])
    ax_a2 = fig.add_subplot(gs_top[0, 1])
    draw_raincloud(ax_a1, fp10, "a  fp_10  —  adjacent false positives")
    draw_raincloud(ax_a2, idsw, "b  idswitch  —  identity-switch perturbation")

    # Panel b: joint scatter (bottom, full width)
    ax_b = fig.add_subplot(gs[1])
    draw_joint_scatter(ax_b, fp10, idsw)

    fig.text(0.06, 0.015,
             "Panel a: violin = per-episode distribution (N=300 each); bar = median; diamond = mean. Panel b: each point = one episode (300 per condition per method).",
             fontsize=5.5, color=C["muted"], ha="left", va="center")

    fig.subplots_adjust(left=0.085, right=0.988, top=0.97, bottom=0.07)

    for out_dir in (OUT_PICTURE, OUT_FIGS):
        for suffix, kwargs in [(".pdf", {}), (".svg", {}),
                                (".png", {"dpi": 600}), (".tiff", {"dpi": 600})]:
            fig.savefig(out_dir / f"{save_base}{suffix}", bbox_inches="tight", **kwargs)
    print(f"Saved {save_base}.* to {OUT_PICTURE} and {OUT_FIGS}")
    return fig


if __name__ == "__main__":
    build_figure("fig8_per_episode_target_selection")
