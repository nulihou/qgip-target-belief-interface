
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
import numpy as np

from qgip_figure_style import TOP_CONF_COLORS as TOP, apply_top_conference_style

apply_top_conference_style()
plt.rcParams.update({
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2,
    "legend.fontsize": 6.0,
    "axes.linewidth": 0.85,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "follow": TOP["blue"],
    "lane": TOP["copper"],
    "follow_fill": TOP["blue_light"],
    "lane_fill": TOP["copper_light"],
    "ego": TOP["charcoal"],
    "other_fill": TOP["gray_light"],
    "other_edge": TOP["gray"],
    "grid": TOP["grid"],
    "lane_mark": TOP["gray_mid"],
    "road": TOP["panel"],
    "muted": TOP["gray"],
    "line": TOP["gray_mid"],
    "text": TOP["ink"],
}

follow_scores = {"same lane": 0.95, "left lane": 0.05, "far leader": 0.10, "right lane": 0.02}
lane_scores = {"same lane": 0.30, "left lane": 0.85, "far leader": 0.05, "right lane": 0.01}

objects = {
    "ego": (0.0, 1.4),
    "same lane": (0.0, 8.0),
    "far leader": (0.0, 17.6),
    "left lane": (-2.35, 10.0),
    "right lane": (2.35, 7.3),
}

def add_halo(artist, lw=2.0):
    artist.set_path_effects([pe.Stroke(linewidth=lw, foreground="white"), pe.Normal()])

def draw_vehicle(ax, x, y, mode="other", heading=0, alpha=1.0, z=5):
    w, h = 1.12, 2.55
    th = np.radians(heading)
    c, s = np.cos(th), np.sin(th)
    R = np.array([[c, -s], [s, c]])
    corners = np.array([[-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]])
    corners = corners @ R.T + np.array([x, y])
    if mode == "ego":
        fc, ec, lw, ls = COLORS["ego"], TOP["ink"], 1.10, "-"
    elif mode == "follow":
        fc, ec, lw, ls = COLORS["follow_fill"], COLORS["follow"], 1.25, "-"
    elif mode == "lane":
        fc, ec, lw, ls = COLORS["lane_fill"], COLORS["lane"], 1.25, "-"
    else:
        fc, ec, lw, ls = COLORS["other_fill"], COLORS["other_edge"], 0.95, "-"
    poly = patches.Polygon(corners, closed=True, facecolor=fc, edgecolor=ec, lw=lw, ls=ls, alpha=alpha, zorder=z)
    ax.add_patch(poly)
    ax.plot(x, y, "o", color=ec, markersize=3.0, alpha=alpha, zorder=z+1)
    arrow_len = 1.60
    ax.arrow(x, y+0.18, arrow_len*s, arrow_len*c, head_width=0.42, head_length=0.58,
             color=ec, length_includes_head=True, alpha=alpha, lw=0, zorder=z+1)
    return poly

def setup_road_axis(ax, title, show_ylabel=False):
    ax.set_aspect("equal")
    ax.set_xlim(-4.2, 4.2)
    ax.set_ylim(-0.7, 20.8)
    ax.set_xticks([-4, -2, 0, 2, 4])
    ax.set_yticks([0, 5, 10, 15, 20])
    ax.grid(True, color=COLORS["grid"], linewidth=0.40, zorder=0)
    ax.axvline(-3.5, color="black", lw=1.08, zorder=1)
    ax.axvline(3.5, color="black", lw=1.08, zorder=1)
    ax.axvline(0, color=COLORS["lane_mark"], linestyle="--", dashes=(5, 5), lw=0.85, zorder=1)
    ax.set_xlabel("Lateral position (m)")
    if show_ylabel:
        ax.set_ylabel("Longitudinal position (m)")
    else:
        ax.set_yticklabels([])
    ax.set_title(title, fontsize=8.0, fontweight="bold", pad=6)

def arrow_to_candidate(ax, target_name, color, selected=False):
    ex, ey = objects["ego"]
    tx, ty = objects[target_name]
    line, = ax.plot([ex, tx], [ey+1.25, ty-1.45],
                    color=color if selected else TOP["gray_mid"],
                    lw=1.60 if selected else 0.80,
                    linestyle="-" if selected else (0, (3, 3)),
                    alpha=0.98 if selected else 0.70,
                    zorder=2)
    add_halo(line, lw=3.0 if selected else 1.7)
    arr = patches.FancyArrowPatch((ex, ey+1.25), (tx, ty-1.45),
                                  arrowstyle="-|>", mutation_scale=11 if selected else 7,
                                  color=color if selected else TOP["gray_mid"], lw=0,
                                  alpha=0.98 if selected else 0.70, zorder=3)
    ax.add_patch(arr)

def label_score(ax, name, score, selected=False, color=COLORS["follow"], xytext=None, ha="center"):
    x, y = objects[name]
    if xytext is None:
        xytext = (x, y)
    label = {"same lane": "same", "left lane": "left", "far leader": "far", "right lane": "right"}[name]
    ax.text(xytext[0], xytext[1], f"{label}\n{score:.2f}",
            ha=ha, va="center", fontsize=5.9, linespacing=0.88,
            color=color if selected else COLORS["text"],
            fontweight="bold" if selected else "normal",
            bbox=dict(facecolor="white", alpha=0.92, edgecolor="none", pad=0.16), zorder=20)

def draw_query_scene(ax, query_title, scores, selected_key, selected_color, selected_mode, panel_letter, show_ylabel=False):
    setup_road_axis(ax, rf"{panel_letter}  {query_title}", show_ylabel=show_ylabel)
    for obj in ["far leader", "same lane", "left lane", "right lane"]:
        arrow_to_candidate(ax, obj, selected_color, selected=(obj == selected_key))
    draw_vehicle(ax, *objects["ego"], mode="ego", z=8)
    ax.text(0.95, 0.70, "ego", ha="left", va="center", fontsize=6.0, color=COLORS["text"], bbox=dict(facecolor="white", alpha=0.80, edgecolor="none", pad=0.08), zorder=21)
    for obj in ["far leader", "same lane", "left lane", "right lane"]:
        draw_vehicle(ax, *objects[obj], mode=selected_mode if obj == selected_key else "other",
                     alpha=1.0 if obj == selected_key else 0.88, z=9 if obj == selected_key else 6)
    label_pos = {"far leader": (-1.25, 18.6), "same lane": (1.35, 8.2),
                 "left lane": (-3.20, 10.0), "right lane": (3.22, 7.2)}
    ha_map = {"left lane": "right", "right lane": "left"}
    for obj in ["far leader", "same lane", "left lane", "right lane"]:
        label_score(ax, obj, scores[obj], selected=(obj == selected_key), color=selected_color,
                    xytext=label_pos[obj], ha=ha_map.get(obj, "center"))

def draw_dumbbell(ax):
    ax.set_title("c  Query-conditioned target-score shift", loc="left", fontsize=8.0, fontweight="bold", pad=6)
    labels = ["same lane", "left lane", "far leader", "right lane"]
    y = np.arange(len(labels))[::-1]
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.58, len(labels) - 0.42)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xticks([0, 0.25, 0.50, 0.75, 1.00])
    ax.set_xticklabels(["0", "0.25", "0.50", "0.75", "1.00"])
    ax.set_xlabel("relative target score")
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.42, zorder=0)
    for i, lab in enumerate(labels):
        yy = y[i]
        xf, xl = follow_scores[lab], lane_scores[lab]
        conn, = ax.plot([min(xf, xl), max(xf, xl)], [yy, yy], color=COLORS["line"], lw=1.25, zorder=1)
        add_halo(conn, lw=2.2)
        ax.scatter([xf], [yy], s=34, marker="o", color=COLORS["follow"], edgecolor=TOP["ink"], linewidth=0.55, zorder=3,
                   label="follow leader" if i == 0 else None)
        ax.scatter([xl], [yy], s=34, marker="D", color=COLORS["lane"], edgecolor=TOP["copper_dark"], linewidth=0.55, zorder=3,
                   label="lane change left" if i == 0 else None)
    row = {lab: y[i] for i, lab in enumerate(labels)}
    for lab, x, txt, dy, c in [
        ("same lane", follow_scores["same lane"], "0.95", 0.18, COLORS["follow"]),
        ("same lane", lane_scores["same lane"], "0.30", -0.28, COLORS["lane"]),
        ("left lane", follow_scores["left lane"], "0.05", -0.28, COLORS["follow"]),
        ("left lane", lane_scores["left lane"], "0.85", 0.18, COLORS["lane"]),
    ]:
        ax.text(x, row[lab]+dy, txt, ha="center", va="center", fontsize=5.9, color=c,
                bbox=dict(facecolor="white", alpha=0.90, edgecolor="none", pad=0.10), zorder=4)
    ax.text(0.18, row["far leader"]+0.20, "low scores", fontsize=5.5, color=COLORS["muted"], ha="left", va="center")
    ax.text(0.18, row["right lane"]+0.20, "near zero", fontsize=5.5, color=COLORS["muted"], ha="left", va="center")
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.78)
    ax.spines["bottom"].set_linewidth(0.78)
    ax.tick_params(axis="both", length=2.5, width=0.6)
    ax.legend(loc="lower right", frameon=False, handletextpad=0.45, borderpad=0.15, labelspacing=0.28)

def build_figure(save_base):
    fig = plt.figure(figsize=(7.35, 2.85), dpi=300)
    gs = GridSpec(1, 3, figure=fig, width_ratios=[1.0, 1.0, 1.34], wspace=0.42)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[0, 2])
    draw_query_scene(ax_a, r"$q$: follow leader", follow_scores, "same lane", COLORS["follow"], "follow", "a", show_ylabel=True)
    draw_query_scene(ax_b, r"$q$: lane change left", lane_scores, "left lane", COLORS["lane"], "lane", "b", show_ylabel=False)
    draw_dumbbell(ax_c)
    fig.subplots_adjust(left=0.060, right=0.988, top=0.88, bottom=0.18)
    fig.savefig(f"{save_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{save_base}.svg", bbox_inches="tight")
    fig.savefig(f"{save_base}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{save_base}.tiff", dpi=600, bbox_inches="tight")
    return fig

if __name__ == "__main__":
    build_figure("fig2_final_submission_ready_v2")
    plt.show()
