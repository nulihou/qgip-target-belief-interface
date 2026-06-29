
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.patheffects as pe
import numpy as np

plt.rcParams.update({
    "font.family": "STIXGeneral",
    "mathtext.fontset": "stix",
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2,
    "legend.fontsize": 5.8,
    "axes.linewidth": 0.82,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "qgip": "#0B63B6", "rule": "#5F6368", "noquery": "#E69F00", "stdkf": "#5DADE2",
    "sort": "#D55E00",
    "success": "#18A57A", "lost": "#D7DCE2", "collision": "#D55E00",
    "grid": "#D7DDE5", "muted": "#6B7280", "text": "#111111", "boundary": "#A36A00",
}

def add_halo(artist, lw=2.0):
    artist.set_path_effects([pe.Stroke(linewidth=lw, foreground="white"), pe.Normal()])

methods = ["E2E\n(no MPC)", "Modular\nPID", "Rule\n+ MPC", "Std KF\n+ MPC", "QGIP-Net", "SORT\n+ MPC"]
success = np.array([8.3, 33.0, 69.0, 73.3, 76.7, 73.0])
lost = np.array([5.3, 8.3, 31.0, 26.7, 23.3, 27.0])
collision = np.array([86.3, 58.7, 0.0, 0.0, 0.0, 0.0])
success_counts = np.array([25, 99, 207, 220, 230, 219])
lost_counts = np.array([16, 25, 93, 80, 70, 81])
collision_counts = np.array([259, 176, 0, 0, 0, 0])

leader_rows = [
    ("FP10 vs\nNo query", "No query", 53.2, 86.2, 33.1),
    ("FP10 vs\nRule",   "Rule",   43.8, 86.2, 42.5),
    ("FP10 vs\nSORT",   "SORT",   86.8, 86.2, -0.6),
    ("ID sw vs\nStd KF","Std KF", 56.0, 90.7, 34.6),
    ("ID sw vs\nRule",  "Rule",   47.7, 90.7, 43.0),
    ("ID sw vs\nSORT",  "SORT",   99.5, 90.7, -8.8),
]
ids_rows = [
    ("FP10 vs\nNo query", "No query", 151.1, 62.5, -88.6),
    ("FP10 vs\nRule",   "Rule",   57.1,  62.5, +5.4),
    ("FP10 vs\nSORT",   "SORT",   53.6,  62.5, +8.9),
    ("ID sw vs\nStd KF", "Std KF", 180.6, 39.2, -141.4),
    ("ID sw vs\nRule",  "Rule",   155.2, 39.2, -116.0),
    ("ID sw vs\nSORT",  "SORT",   108.8, 39.2, -69.6),
]
method_color = {"No query": COLORS["noquery"], "Rule": COLORS["rule"], "Std KF": COLORS["stdkf"], "SORT": COLORS["sort"]}
method_marker = {"No query": "^", "Rule": "s", "Std KF": "D", "SORT": "P"}

def panel_label_legend(ax, text):
    ax.text(0.01, 1.035, text, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=5.45, color=COLORS["muted"], clip_on=False)

def draw_panel_a(ax):
    ax.set_title("a  Blackout route outcome", loc="left", fontsize=8.2, fontweight="bold", pad=6)
    y = np.arange(len(methods))[::-1]
    ax.set_xlim(0, 100); ax.set_ylim(-0.55, len(methods)-0.45)
    h = 0.62
    ax.barh(y, success, height=h, color=COLORS["success"], edgecolor="white", linewidth=0.55, zorder=3)
    ax.barh(y, lost, left=success, height=h, color=COLORS["lost"], edgecolor="white", linewidth=0.55, zorder=3)
    ax.barh(y, collision, left=success+lost, height=h, color=COLORS["collision"], edgecolor="white", linewidth=0.55, zorder=3)
    for i, yy in enumerate(y):
        if success[i] >= 25:
            ax.text(success[i]/2, yy, f"{success_counts[i]}/300", ha="center", va="center", fontsize=5.65, color="white", fontweight="bold")
        elif success[i] > 0:
            ax.text(success[i] + 1.0, yy + 0.20, f"{success_counts[i]}/300", ha="left", va="center",
                    fontsize=5.35, color=COLORS["success"],
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.86, pad=0.05))
        if collision[i] >= 18:
            ax.text(success[i] + lost[i] + collision[i]/2, yy, f"{collision_counts[i]}/300", ha="center", va="center", fontsize=5.65, color="white", fontweight="bold")
        if lost[i] >= 18 and collision[i] == 0:
            ax.text(success[i] + lost[i]/2, yy, f"{lost_counts[i]}/300", ha="center", va="center", fontsize=5.65, color=COLORS["text"])
    ax.set_yticks(y); ax.set_yticklabels(methods)
    ax.set_xlabel("episodes (%)"); ax.set_xticks([0, 25, 50, 75, 100])
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.42, zorder=0)
    # legend note described in caption
    for side in ["top", "right"]: ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76); ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="both", length=2.4, width=0.58)

def draw_panel_b(ax):
    ax.set_title("b  LeaderAcc dumbbell", loc="left", fontsize=8.2, fontweight="bold", pad=6)
    y = np.arange(len(leader_rows))[::-1]
    ax.set_xlim(30, 105); ax.set_ylim(-0.55, len(leader_rows)-0.45)
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.42, zorder=0)
    for yy, (label, comp_name, comp_val, q_val, delta) in zip(y, leader_rows):
        line, = ax.plot([comp_val, q_val], [yy, yy], color="#BFC7D1", linewidth=1.3, zorder=1)
        add_halo(line, 2.2)
        ax.scatter([comp_val], [yy], s=30, marker=method_marker[comp_name], color=method_color[comp_name], edgecolor="#222222", linewidth=0.45, zorder=3)
        ax.scatter([q_val], [yy], s=34, marker="o", color=COLORS["qgip"], edgecolor="#063F78", linewidth=0.55, zorder=4)
        sign = "+" if delta >= 0 else ""
        delta_color = COLORS["qgip"] if delta >= 0 else COLORS["sort"]
        if delta < 0:
            ax.text(q_val - 1.0, yy + 0.06, f"{delta:.1f}", ha="right", va="center", fontsize=5.7, color=delta_color,
                    fontweight="bold")
        else:
            ax.text(q_val + 0.8, yy + 0.06, f"{sign}{delta:.1f}", ha="left", va="center", fontsize=5.7, color=delta_color)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in leader_rows])
    ax.set_xlabel("LeaderAcc (%)")
    # legend note described in caption
    for side in ["top", "right"]: ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76); ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="both", length=2.4, width=0.58)

def draw_panel_d(ax):
    ax.set_title("c  ID-switch burden dumbbell", loc="left", fontsize=8.2, fontweight="bold", pad=6)
    y = np.arange(len(ids_rows))[::-1]
    ax.set_xlim(0, 210); ax.set_ylim(-0.55, len(ids_rows)-0.45)
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.42, zorder=0)
    for yy, (label, comp_name, comp_val, q_val, delta) in zip(y, ids_rows):
        line, = ax.plot([q_val, comp_val], [yy, yy], color="#BFC7D1", linewidth=1.3, zorder=1)
        add_halo(line, 2.2)
        ax.scatter([q_val], [yy], s=34, marker="o", color=COLORS["qgip"], edgecolor="#063F78", linewidth=0.55, zorder=4)
        ax.scatter([comp_val], [yy], s=30, marker=method_marker[comp_name], color=method_color[comp_name], edgecolor="#222222", linewidth=0.45, zorder=3)
        mid = (q_val + comp_val) / 2
        color = COLORS["qgip"] if delta < 0 else COLORS["sort"]
        ax.text(mid, yy + 0.13, f"{delta:+.1f}", ha="center", va="bottom", fontsize=5.55, color=color,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.80, pad=0.08), zorder=5)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in ids_rows])
    ax.set_xlabel("ID switches / episode")
    # legend note described in caption
    for side in ["top", "right"]: ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76); ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="both", length=2.4, width=0.58)

def build_figure(save_base="fig7_main_result_final_v7"):
    fig = plt.figure(figsize=(7.50, 3.80), dpi=300)
    gs = GridSpec(2, 2, figure=fig, width_ratios=[1.0, 1.0], height_ratios=[1.0, 1.05],
                  wspace=0.42, hspace=0.32)
    # Panel a: route outcome (spans full width top row)
    ax_a = fig.add_subplot(gs[0, :])
    draw_panel_a(ax_a)
    # Panel b: LeaderAcc dumbbell (bottom left)
    ax_b = fig.add_subplot(gs[1, 0])
    draw_panel_b(ax_b)
    # Panel d: ID-switch dumbbell (bottom right)
    ax_d = fig.add_subplot(gs[1, 1])
    draw_panel_d(ax_d)
    fig.subplots_adjust(left=0.115, right=0.985, top=0.94, bottom=0.14)
    fig.savefig(f"{save_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{save_base}.svg", bbox_inches="tight")
    fig.savefig(f"{save_base}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{save_base}.tiff", dpi=600, bbox_inches="tight")
    return fig

if __name__ == "__main__":
    build_figure("fig7_main_result_final_v7")
