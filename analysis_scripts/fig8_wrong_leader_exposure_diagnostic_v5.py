
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.gridspec import GridSpec
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd

plt.rcParams.update({
    "font.family": "STIXGeneral",
    "mathtext.fontset": "stix",
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.1,
    "ytick.labelsize": 6.1,
    "legend.fontsize": 5.8,
    "axes.linewidth": 0.80,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "qgip": "#0B63B6",
    "rule": "#5F6368",
    "noquery": "#E69F00",
    "stdkf": "#5DADE2",
    "sort": "#D55E00",
    "grid": "#D7DDE5",
    "muted": "#6B7280",
    "text": "#111111",
    "boundary_bg": "#FCF5E7",
    "danger_bg": "#FDEFF0",
    "desired_bg": "#EAF6F1",
}

methods = ["Rule", "No query", "Std KF", "SORT", "QGIP-Net"]
style = {
    "Rule": dict(color=COLORS["rule"], marker="s", size=30, z=4),
    "No query": dict(color=COLORS["noquery"], marker="^", size=32, z=4),
    "Std KF": dict(color=COLORS["stdkf"], marker="D", size=30, z=4),
    "SORT": dict(color=COLORS["sort"], marker="P", size=32, z=5),
    "QGIP-Net": dict(color=COLORS["qgip"], marker="o", size=36, z=6),
}

conditions = ["FP10\nN=300", "ID switch\nN=300", "FP20\nN=100", "ID switch 40\nN=100", "Boundary\nN=100"]
groups = ["primary", "primary", "boundary", "boundary", "boundary"]
y = np.arange(len(conditions))[::-1]

leaderacc = {
    "Rule":      [43.8, 47.7, 36.2, 43.0, 36.2],
    "No query":  [53.2, np.nan, 47.8, np.nan, 47.8],
    "Std KF":    [np.nan, 56.0, np.nan, 55.0, np.nan],
    "SORT":      [90.2, 99.8, 83.9, np.nan, 83.9],
    "QGIP-Net":  [86.2, 90.7, 80.0, 90.0, 80.0],
}

wrong_leader = {
    "Rule":      [270, 255, 300, 270, 310],
    "No query":  [230, np.nan, 240, np.nan, 235],
    "Std KF":    [np.nan, 210, np.nan, 215, np.nan],
    "SORT":      [32, 1, 40, np.nan, 45],
    "QGIP-Net":  [70, 45, 90, 45, 95],
}

def add_halo(artist, lw=2.0):
    try:
        artist.set_path_effects([pe.Stroke(linewidth=lw, foreground="white"), pe.Normal()])
    except Exception:
        pass

def draw_method_point(ax, x, yv, method, group, sscale=1.0, zoffset=0):
    st = style[method]
    if group == "primary":
        face = st["color"]
        edge = "#222222"
        alpha = 1.0
        lw = 0.45
    else:
        face = "white"
        edge = st["color"]
        alpha = 0.96
        lw = 0.95
    ax.scatter([x], [yv], s=st["size"]*sscale, marker=st["marker"],
               facecolor=face, edgecolor=edge, linewidth=lw,
               alpha=alpha, zorder=st["z"]+zoffset)

def draw_panel_a(ax):
    ax.set_title("a  Wrong-leader exposure under ambiguity", loc="left", fontsize=8.2, fontweight="bold", pad=6)
    ax.set_xlim(0, 330)
    ax.set_ylim(-0.55, len(conditions)-0.45)
    ax.axhspan(-0.5, 2.5, color=COLORS["boundary_bg"], zorder=-3)
    for yy in y:
        ax.axhline(yy, color="#ECEFF3", lw=0.38, zorder=-2)
    ax.grid(axis="x", color=COLORS["grid"], lw=0.42, zorder=-1)
    for i, yy in enumerate(y):
        vals = [wrong_leader[m][i] for m in methods if np.isfinite(wrong_leader[m][i])]
        if len(vals) >= 2:
            line, = ax.plot([min(vals), max(vals)], [yy, yy], color="#C4CAD3", lw=1.10, zorder=1)
            add_halo(line, 1.9)
        for m in methods:
            val = wrong_leader[m][i]
            if np.isfinite(val):
                draw_method_point(ax, val, yy, m, groups[i])
        qv = wrong_leader["QGIP-Net"][i]
        ax.text(qv + 7, yy + 0.05, f"{qv:.0f}", ha="left", va="center", fontsize=5.45, color=COLORS["qgip"])
    ax.set_yticks(y)
    ax.set_yticklabels(conditions)
    ax.set_xticks([0, 100, 200, 300])
    ax.set_xlabel("wrong-leader frames / episode")
    ax.text(0.98, 1.025, "lower is better", transform=ax.transAxes, ha="right", va="bottom", fontsize=5.55, color=COLORS["muted"])
    ax.text(-0.26, (y[0]+y[1])/2, "primary\npaired", transform=ax.get_yaxis_transform(),
            ha="right", va="center", fontsize=5.55, color=COLORS["muted"], linespacing=0.90)
    ax.text(-0.26, (y[2]+y[4])/2, "supplemental\nboundary", transform=ax.get_yaxis_transform(),
            ha="right", va="center", fontsize=5.55, color="#9A6A00", linespacing=0.90)
    ax.plot([-0.16, -0.16], [y[1]-0.35, y[0]+0.35], transform=ax.get_yaxis_transform(),
            color=COLORS["muted"], lw=0.90, clip_on=False)
    ax.plot([-0.16, -0.16], [y[4]-0.35, y[2]+0.35], transform=ax.get_yaxis_transform(),
            color="#9A6A00", lw=0.90, clip_on=False)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76)
    ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="both", length=2.4, width=0.58)

def draw_panel_b(ax):
    ax.set_title("b  LeaderAcc-exposure diagnostic plane", loc="left", fontsize=8.2, fontweight="bold", pad=6)
    ax.set_xlim(0, 330)
    ax.set_ylim(30, 100)
    ax.set_xticks([0, 100, 200, 300])
    ax.set_yticks([40, 60, 80, 100])
    ax.set_xlabel("wrong-leader frames / episode")
    ax.set_ylabel("LeaderAcc (%)")
    ax.grid(True, color=COLORS["grid"], lw=0.42, zorder=-1)
    ax.axvspan(0, 110, ymin=(78-30)/(100-30), ymax=1, color=COLORS["desired_bg"], alpha=0.62, zorder=-3)
    ax.axvspan(200, 330, ymin=0, ymax=(60-30)/(100-30), color=COLORS["danger_bg"], alpha=0.50, zorder=-3)
    ax.text(8, 98.5, "desired region", ha="left", va="top", fontsize=5.35, color="#147A55")
    ax.text(320, 58.5, "stable-but-wrong\nregion", ha="right", va="top", fontsize=5.35, color="#A04A4A", linespacing=0.90)
    for i, cond in enumerate(conditions):
        pts = []
        for m in methods:
            x = wrong_leader[m][i]
            yy = leaderacc[m][i]
            if np.isfinite(x) and np.isfinite(yy):
                pts.append((x, yy))
        if len(pts) >= 2:
            xs, ys = zip(*pts)
            order = np.argsort(xs)
            line, = ax.plot(np.array(xs)[order], np.array(ys)[order], color="#CAD0D8", lw=0.95, zorder=1)
            add_halo(line, 1.7)
    for i, cond in enumerate(conditions):
        for m in methods:
            x = wrong_leader[m][i]
            yy = leaderacc[m][i]
            if np.isfinite(x) and np.isfinite(yy):
                draw_method_point(ax, x, yy, m, groups[i], sscale=1.08 if m == "QGIP-Net" else 1.0)
    # No point labels here; panel b is a diagnostic plane rather than a table.
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76)
    ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="both", length=2.4, width=0.58)

def build_figure(save_base="fig8_wrong_leader_exposure_diagnostic_v5"):
    fig = plt.figure(figsize=(7.35, 3.10), dpi=300)
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.05, 1.08], wspace=0.36)
    draw_panel_a(fig.add_subplot(gs[0, 0]))
    draw_panel_b(fig.add_subplot(gs[0, 1]))
    handles = [
        Line2D([0], [0], marker=style[m]["marker"], color="none",
               markerfacecolor=style[m]["color"], markeredgecolor="#222222",
               markeredgewidth=0.45, markersize=4.4, label=m)
        for m in methods
    ]
    handles.append(Line2D([0], [0], marker="o", color="none",
                          markerfacecolor="white", markeredgecolor="#6B7280",
                          markeredgewidth=0.9, markersize=4.4, label="open = boundary"))
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.55, 0.990),
               ncol=6, frameon=False, handletextpad=0.30, columnspacing=0.75)
    fig.text(0.075, 0.055,
             "Unshaded rows/filled markers denote primary paired N=300 ambiguity tests; shaded rows/open markers denote supplemental N=100 boundary conditions.",
             ha="left", va="center", fontsize=5.65, color=COLORS["muted"])
    fig.subplots_adjust(left=0.125, right=0.985, top=0.84, bottom=0.19)
    fig.savefig(f"{save_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{save_base}.svg", bbox_inches="tight")
    fig.savefig(f"{save_base}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{save_base}.tiff", dpi=600, bbox_inches="tight")
    return fig

if __name__ == "__main__":
    build_figure("fig8_wrong_leader_exposure_diagnostic_v5")
