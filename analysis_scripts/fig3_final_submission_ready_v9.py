
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
    "xtick.labelsize": 6.1,
    "ytick.labelsize": 6.1,
    "legend.fontsize": 5.9,
    "axes.linewidth": 0.82,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "obs": TOP["blue"],
    "obs_fill": TOP["blue_light"],
    "pred": TOP["copper"],
    "pred_fill": TOP["copper_light"],
    "gt": TOP["ink"],
    "grid": TOP["grid"],
    "lane": TOP["gray_mid"],
    "green": TOP["teal"],
    "orange": TOP["copper"],
    "red": TOP["brick"],
    "gray": TOP["gray"],
    "phase_blue": TOP["blue_bg"],
    "phase_ghost": "#FBF4E8",
    "phase_reset": TOP["brick_light"],
    "phase_safe": TOP["panel"],
}

TAU_SOFT = 12.0
TAU_HARD = 20.0
TG = 1.5

def add_halo(line, lw=2.2):
    line.set_path_effects([pe.Stroke(linewidth=lw, foreground="white"), pe.Normal()])

def draw_vehicle(ax, x, y, heading=0, mode="solid", alpha=1.0, uncertainty=False):
    w, h = 1.52, 3.25
    th = np.radians(heading)
    c, s = np.cos(th), np.sin(th)
    R = np.array([[c, -s], [s, c]])
    rect = np.array([[-w/2, -h/2], [w/2, -h/2], [w/2, h/2], [-w/2, h/2]])
    rect = rect @ R.T + np.array([x, y])

    if mode == "solid":
        fc, ec, ls, lw, z = COLORS["obs_fill"], COLORS["obs"], "-", 1.18, 10
    elif mode == "ghost":
        fc, ec, ls, lw, z = "none", COLORS["pred"], "--", 1.18, 9
    else:
        fc, ec, ls, lw, z = "none", COLORS["gt"], ":", 0.95, 8

    if uncertainty:
        ell = patches.Ellipse((x, y), width=w*1.95, height=h*1.52, angle=heading,
                              fc=COLORS["pred_fill"], ec=COLORS["pred"], lw=0.75,
                              ls=":", alpha=0.18, zorder=z-1)
        ax.add_patch(ell)

    poly = patches.Polygon(rect, closed=True, fc=fc, ec=ec, lw=lw, ls=ls, alpha=alpha, zorder=z)
    ax.add_patch(poly)

    arr = ax.arrow(x, y, 2.15*s, 2.15*c, head_width=0.46, head_length=0.66,
                   fc=ec, ec=ec, alpha=alpha, length_includes_head=True, zorder=z+1)
    ax.plot(x, y, "o", color=ec, markersize=3.5, zorder=z+1)
    return poly, arr

def setup_lane_axis(ax, title, show_ylabel=False):
    ax.set_aspect("equal")
    ax.set_xlim(-4, 4)
    ax.set_ylim(-2, 22)
    ax.set_xticks(np.arange(-4, 5, 2))
    ax.set_yticks(np.arange(0, 23, 5))
    ax.grid(True, color=COLORS["grid"], linewidth=0.40)
    ax.axvline(-3.5, color="black", lw=1.12)
    ax.axvline(3.5, color="black", lw=1.12)
    ax.axvline(0, color=COLORS["lane"], lw=0.88, linestyle="--", dashes=(5, 5))
    ax.set_xlabel("Lateral position (m)")
    if show_ylabel:
        ax.set_ylabel("Longitudinal position (m)")
    else:
        ax.set_yticklabels([])
    ax.set_title(title, fontsize=7.9, fontweight="bold", pad=6)

def draw_row_a(fig, cell):
    sub = cell.subgridspec(1, 3, wspace=0.26)
    ax1 = fig.add_subplot(sub[0, 0])
    ax2 = fig.add_subplot(sub[0, 1])
    ax3 = fig.add_subplot(sub[0, 2])

    setup_lane_axis(ax1, r"(a1) Active tracking ($t_k$)", show_ylabel=True)
    setup_lane_axis(ax2, r"(a2) Ghost prediction ($t_{k+1}$)")
    setup_lane_axis(ax3, r"(a3) Re-association ($t_{k+2}$)")

    # a1
    ax1.plot([0, 0], [0, 4], color=COLORS["obs"], lw=0.92)
    ax1.plot(0, 0, "x", color=COLORS["obs"], markersize=4.0)
    draw_vehicle(ax1, 0.0, 4.0, heading=5, mode="solid")
    ax1.text(-1.18, 0.72, r"$\mathbf{z}_k$ (Obs)", fontsize=6.0,
             bbox=dict(facecolor="white", alpha=0.88, edgecolor="none", pad=0.10), zorder=30)
    ax1.text(-2.36, 16.95, "Sensor: ON", color=COLORS["obs"], fontweight="bold", fontsize=6.1,
             bbox=dict(facecolor="white", edgecolor=COLORS["obs"], boxstyle="round,pad=0.18", alpha=0.96), zorder=30)

    # a2
    blind = patches.Rectangle((-4, 6.0), 8, 14.0, fc=TOP["gray_light"], ec="none", hatch="\\\\", alpha=0.32, zorder=0)
    ax2.add_patch(blind)
    ax2.text(0.0, 16.65, "OCCLUSION ZONE", ha="center", fontsize=6.0, color=TOP["gray"], fontweight="bold",
             bbox=dict(facecolor="white", edgecolor=TOP["gray_light"], boxstyle="round,pad=0.12", alpha=0.92), zorder=30)
    draw_vehicle(ax2, 0.50, 9.0, heading=5, mode="truth", alpha=0.34)
    ax2.annotate("Ground truth", xy=(0.78, 11.9), xytext=(1.86, 14.12),
                 arrowprops=dict(arrowstyle="->", color=COLORS["gt"], lw=0.68),
                 fontsize=5.95, color=COLORS["gt"],
                 bbox=dict(facecolor="white", alpha=0.90, edgecolor="none", pad=0.08), zorder=35)
    draw_vehicle(ax2, 0.2, 8.8, heading=5, mode="ghost", uncertainty=True)
    ax2.text(0.92, 5.02, r"$\hat{\mathbf{x}}_{k+1|k}$ (Ghost)", fontsize=5.95, color=COLORS["pred"],
             bbox=dict(facecolor="white", alpha=0.90, edgecolor="none", pad=0.08), zorder=35)
    ax2.text(2.74, 6.66, r"$3\sigma$", color=COLORS["pred"], fontsize=5.9, fontweight="bold",
             fontstyle="italic", zorder=35)
    ax2.text(2.00, 2.05, "Kalman propagate", fontsize=5.95, color=COLORS["pred"], ha="center",
             bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", pad=0.08), zorder=35)

    # a3
    draw_vehicle(ax3, 1.22, 14.0, heading=2, mode="solid")
    draw_vehicle(ax3, 0.60, 13.8, heading=5, mode="ghost", alpha=0.55)
    ax3.text(1.33, 11.32, r"$\mathbf{z}_{k+2}$ (Obs)", ha="center", fontsize=5.95,
             bbox=dict(facecolor="white", alpha=0.88, edgecolor="none", pad=0.08), zorder=35)
    ax3.annotate("", xy=(1.22, 14.0), xytext=(0.60, 13.8),
                 arrowprops=dict(arrowstyle="<->", color="black", lw=0.78), zorder=25)
    ax3.text(2.92, 12.35, r"IoU match $>\tau$", ha="center", fontsize=5.95,
             bbox=dict(facecolor="white", alpha=0.82, edgecolor="none", pad=0.08), zorder=35)
    ax3.plot([0, 0.2, 1.2], [4, 8.8, 14], color=COLORS["obs"], lw=1.10, alpha=0.38)

def draw_row_b(ax, with_inset=True):
    ax.set_title("b  Belief evolution during dropout and re-association",
                 loc="left", fontsize=8.2, fontweight="bold", pad=6)

    t = np.linspace(0.0, 1.6, 49)
    truth = 18.0 + 1.25*t + 0.12*np.sin(2*np.pi*(t + 0.10)/1.8)
    dropout_start, dropout_end = 0.38, 0.95
    observed = (t < dropout_start) | (t > dropout_end)
    obs = truth + 0.10*np.sin(10*t)

    ghost_mask = (t >= dropout_start) & (t <= dropout_end)
    t0 = dropout_start
    truth0 = np.interp(t0, t, truth)
    pred = truth0 + 1.03*(t - t0)
    sigma = 0.16 + 0.55*np.maximum(t - t0, 0.0)
    posterior = np.where(observed, obs - 0.03*np.cos(7*t), np.nan)

    ax.axvspan(dropout_start, dropout_end, color=COLORS["orange"], alpha=0.075, linewidth=0, zorder=0)
    ax.text((dropout_start + dropout_end)/2, 20.57, "measurement dropout",
            ha="center", va="center", fontsize=6.25, color=COLORS["gray"])

    ax.fill_between(t[ghost_mask], (pred - 2*sigma)[ghost_mask], (pred + 2*sigma)[ghost_mask],
                    color=COLORS["pred"], alpha=0.11, linewidth=0, zorder=1)

    ln_truth, = ax.plot(t, truth, color=COLORS["gt"], lw=1.03, alpha=0.92, zorder=2)
    add_halo(ln_truth, 2.2)

    ln_pred, = ax.plot(t[ghost_mask], pred[ghost_mask], color=COLORS["pred"], lw=1.18,
                       linestyle=(0, (4, 2)), zorder=4)
    add_halo(ln_pred, 2.45)

    ln_post, = ax.plot(t, posterior, color=COLORS["green"], lw=1.22, marker="o", markersize=2.45,
                       markevery=4, zorder=5)
    add_halo(ln_post, 2.6)

    ax.scatter(t[observed], obs[observed], marker="x", s=22, color=COLORS["obs"],
               linewidths=0.95, zorder=7)

    trec = 1.05
    pred_rec = truth0 + 1.03*(trec - t0)
    obs_rec = np.interp(trec, t, obs)
    ax.scatter([trec], [pred_rec], facecolors="white", edgecolors=COLORS["pred"], s=28,
               linewidths=0.95, zorder=8)
    ax.scatter([trec], [obs_rec], marker="x", s=30, color=COLORS["obs"], linewidths=1.0, zorder=9)

    ax.annotate("innovation checked by NIS",
                xy=(trec, (pred_rec + obs_rec)/2),
                xytext=(1.16, 20.06),
                fontsize=5.95, color=COLORS["red"], ha="left", va="center",
                bbox=dict(facecolor="white", alpha=0.95, edgecolor="none", pad=0.14),
                arrowprops=dict(arrowstyle="->", color=COLORS["red"], lw=0.78,
                                connectionstyle="arc3,rad=-0.25"))

    ax.text(0.18, 17.86, "update", color=COLORS["green"], fontsize=6.25, ha="center")
    ax.text(0.64, 17.86, "ghost", color=COLORS["orange"], fontsize=6.25, ha="center")
    ax.text(1.26, 17.86, "re-associate", color=COLORS["obs"], fontsize=6.25, ha="center")

    ax.set_xlim(0.0, 1.6)
    ax.set_ylim(17.75, 21.05)
    ax.set_xlabel("episode time (s)")
    ax.set_ylabel("relative range to leader (m)")
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.44, alpha=0.82)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.75)
    ax.spines["bottom"].set_linewidth(0.75)

    handles = [
        Line2D([0], [0], color=COLORS["gt"], lw=1.03, label="truth"),
        Line2D([0], [0], marker="x", color=COLORS["obs"], lw=0, markersize=4.2, label=r"$z_t$"),
        Line2D([0], [0], color=COLORS["green"], lw=1.22, marker="o", markersize=3.1, label="posterior"),
        Line2D([0], [0], color=COLORS["pred"], lw=1.18, linestyle=(0, (4, 2)), label="ghost pred."),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=False, ncol=4,
              bbox_to_anchor=(0.004, 0.998), handlelength=1.42,
              columnspacing=0.82, borderaxespad=0.0)

    if with_inset:
        axins = ax.inset_axes([0.70, 0.15, 0.24, 0.30])
        axins.set_xlim(0.985, 1.275)
        axins.set_ylim(19.08, 19.52)
        axins.grid(True, color=TOP["grid"], linewidth=0.34)
        l1, = axins.plot(t, truth, color=COLORS["gt"], lw=0.86)
        l2, = axins.plot(t, posterior, color=COLORS["green"], lw=0.92, marker="o", markersize=1.95, markevery=5)
        axins.scatter(t[observed], obs[observed], marker="x", s=12, color=COLORS["obs"], linewidths=0.72)
        add_halo(l1, 1.7)
        add_halo(l2, 1.8)
        axins.set_title("re-association zoom", fontsize=4.8, pad=1.2)
        axins.tick_params(labelsize=4.7, length=1.8, pad=1)
        for side in ["top", "right"]:
            axins.spines[side].set_visible(False)
        axins.spines["left"].set_linewidth(0.48)
        axins.spines["bottom"].set_linewidth(0.48)
        ax.indicate_inset_zoom(axins, edgecolor=TOP["gray"], linewidth=0.58, alpha=0.8)

def draw_row_c(ax):
    ax.set_title("c  NIS-gated belief-mode map", loc="left", fontsize=8.2, fontweight="bold", pad=6)
    ax.set_xlim(0, 26)
    ax.set_ylim(-0.10, 2.10)

    for x in [0, 6, 12, 20, 26]:
        ax.axvline(x, color=TOP["grid"], lw=0.52, zorder=0)

    y_top, y_bot, h = 1.18, 0.28, 0.58

    top_blocks = [
        (0, 12, TOP["teal_light"], COLORS["green"], "TRACK\nreliable update"),
        (12, 20, TOP["copper_light"], COLORS["orange"], "DEGRADED\nsoft-gated"),
        (20, 26, TOP["brick_light"], COLORS["red"], "DEGRADED\nreset accepted"),
    ]
    for x0, x1, face, edge, label in top_blocks:
        box = patches.FancyBboxPatch((x0, y_top), x1-x0, h,
                                     boxstyle="round,pad=0.02,rounding_size=0.08",
                                     facecolor=face, edgecolor=edge, linewidth=0.92)
        ax.add_patch(box)
        ax.text((x0+x1)/2, y_top+h/2, label, ha="center", va="center",
                fontsize=5.9, fontweight="bold" if x0 in [0, 20] else "normal")

    box = patches.FancyBboxPatch((0, y_bot), 18.8, h,
                                 boxstyle="round,pad=0.02,rounding_size=0.08",
                                 facecolor=TOP["copper_light"], edgecolor=COLORS["orange"], linewidth=0.92)
    ax.add_patch(box)
    ax.text(9.4, y_bot+h/2+0.02, "GHOST prediction\nwhen measurement is missing or rejected",
            ha="center", va="center", fontsize=5.7, linespacing=0.92)

    box = patches.FancyBboxPatch((18.8, y_bot), 7.2, h,
                                 boxstyle="round,pad=0.02,rounding_size=0.08",
                                 facecolor=TOP["gray_light"], edgecolor=TOP["gray"], linewidth=0.92, hatch="///")
    ax.add_patch(box)
    ax.text(22.4, y_bot+h/2, "LOST\nsafe-stop command",
            ha="center", va="center", fontsize=5.7, linespacing=0.92)

    for x, label, color in [(12, r"$\tau_{\rm soft}$", COLORS["orange"]), (20, r"$\tau_{\rm hard}$", COLORS["red"])]:
        ax.axvline(x, ymin=0.10, ymax=0.96, color=color, linestyle=(0, (3, 2)), lw=0.88)
        ax.text(x+0.17, 1.96, label, color=color, fontsize=5.9, va="top")

    ax.text(18.8, 0.04, r"$T_g=1.5$ s loss-age boundary",
            ha="center", va="bottom", fontsize=5.45, color=COLORS["gray"])

    ax.set_yticks([y_top + h/2, y_bot + h/2])
    ax.set_yticklabels([r"accepted $z_t$", "missing / rejected"])
    ax.set_xticks([0, 6, 12, 20, 26])
    ax.set_xticklabels(["0", "6", "12", "20", "26"])
    ax.set_xlabel("NIS when a measurement is accepted")
    ax.tick_params(axis="y", length=0)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76)
    ax.spines["bottom"].set_linewidth(0.76)

def draw_row_d(ax):
    ax.set_title("d  Mode-labelled NIS trace exposed to control",
                 loc="left", fontsize=8.2, fontweight="bold", pad=6)
    t = np.array([0.00, 0.55, 1.10, 1.55])
    nis = np.array([3.2, 12.4, 21.5, 24.2])
    labels = ["TRACK", "GHOST", "DEGRADED", "LOST"]

    phases = [
        (-0.03, 0.38, COLORS["phase_blue"], "update", COLORS["green"]),
        (0.38, 0.92, COLORS["phase_ghost"], "ghost predict", COLORS["orange"]),
        (0.92, 1.33, COLORS["phase_reset"], "reset\naccepted", COLORS["red"]),
        (1.33, 1.63, COLORS["phase_safe"], "safe-stop\ncommand", COLORS["gray"]),
    ]
    for x0, x1, face, txt, c in phases:
        ax.axvspan(x0, x1, facecolor=face, alpha=1.0, zorder=0)
        ax.text((x0+x1)/2, 1.08, txt, ha="center", va="bottom", fontsize=5.45, color=c, linespacing=0.85)

    ax.axhspan(0, TAU_SOFT, facecolor=TOP["teal_light"], zorder=-1)
    ax.axhspan(TAU_SOFT, TAU_HARD, facecolor="#FBF4E8", zorder=-1)
    ax.axhspan(TAU_HARD, 28.5, facecolor=TOP["brick_light"], zorder=-1)

    ax.axhline(TAU_SOFT, color=COLORS["orange"], linestyle=(0, (4, 2.4)), linewidth=0.92)
    ax.axhline(TAU_HARD, color=COLORS["red"], linestyle=(0, (1.5, 2.1)), linewidth=0.98)
    ax.text(1.61, TAU_SOFT + 0.32, r"$\tau_{\rm soft}$", ha="right", va="bottom", fontsize=5.85, color=COLORS["orange"])
    ax.text(1.61, TAU_HARD + 0.32, r"$\tau_{\rm hard}$", ha="right", va="bottom", fontsize=5.85, color=COLORS["red"])

    ln, = ax.plot(t, nis, color=COLORS["obs"], lw=1.38, marker="o", ms=3.9, zorder=5)
    add_halo(ln, 2.4)
    for xi, yi, lab in zip(t, nis, labels):
        off = 0.90 if lab == "LOST" else 0.78
        ax.text(xi, yi + off, lab, ha="center", va="bottom", fontsize=5.95,
                bbox=dict(facecolor="white", alpha=0.88, edgecolor="none", pad=0.08))

    ax.set_xlim(-0.03, 1.63)
    ax.set_ylim(0, 28.5)
    ax.set_xlabel("time in a perception-failure episode (s)")
    ax.set_ylabel("NIS")
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.44)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76)
    ax.spines["bottom"].set_linewidth(0.76)

    handles = [
        Line2D([0], [0], color=COLORS["obs"], marker="o", lw=1.30, markersize=3.7, label="NIS trace"),
        Line2D([0], [0], color=COLORS["orange"], lw=0.92, linestyle=(0, (4, 2.4)), label=r"$\tau_{\rm soft}$"),
        Line2D([0], [0], color=COLORS["red"], lw=0.98, linestyle=(0, (1.5, 2.1)), label=r"$\tau_{\rm hard}$"),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=False, ncol=3,
              borderaxespad=0.08, handlelength=1.4, columnspacing=1.0)

def build_and_save(base_name="fig3_final_submission_ready_v9"):
    fig = plt.figure(figsize=(8.35, 8.92), dpi=300)
    gs = GridSpec(4, 1, figure=fig, height_ratios=[1.58, 1.10, 0.67, 0.88], hspace=0.48)

    draw_row_a(fig, gs[0])
    fig.text(0.070, 0.988, "a", fontsize=10.0, fontweight="bold", va="top")
    fig.text(0.090, 0.988, "Predictive Object Permanence snapshots", fontsize=8.7, fontweight="bold", va="top")

    ax_b = fig.add_subplot(gs[1]); draw_row_b(ax_b, with_inset=True)
    ax_c = fig.add_subplot(gs[2]); draw_row_c(ax_c)
    ax_d = fig.add_subplot(gs[3]); draw_row_d(ax_d)

    fig.subplots_adjust(left=0.088, right=0.988, top=0.945, bottom=0.070)
    fig.savefig(base_name + ".pdf", bbox_inches="tight")
    fig.savefig(base_name + ".svg", bbox_inches="tight")
    fig.savefig(base_name + ".png", dpi=600, bbox_inches="tight")
    fig.savefig(base_name + ".tiff", dpi=600, bbox_inches="tight")
    return fig

if __name__ == "__main__":
    fig = build_and_save("fig3_final_submission_ready_v9")
    plt.show()
