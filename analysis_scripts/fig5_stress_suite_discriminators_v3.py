
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
import numpy as np
import csv
from pathlib import Path

plt.rcParams.update({
    "font.family": "STIXGeneral",
    "mathtext.fontset": "stix",
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.2,
    "ytick.labelsize": 6.2,
    "legend.fontsize": 5.9,
    "axes.linewidth": 0.82,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "blue": "#0B63B6",
    "blue_light": "#A8C9EE",
    "green": "#18A57A",
    "orange": "#E69F00",
    "red": "#D55E5E",
    "gray": "#6B7280",
    "grid": "#D7DDE5",
    "line": "#BFC7D1",
    "bg_blue": "#F4F8FD",
    "bg_orange": "#FCF5E7",
    "bg_red": "#FDEFF0",
    "text": "#111111",
}

WORK = Path(__file__).resolve().parents[1]
SOURCE = WORK / "08_paper_ready_outputs" / "source_data"

def add_halo(artist, lw=2.0):
    artist.set_path_effects([pe.Stroke(linewidth=lw, foreground="white"), pe.Normal()])

suite_names = ["Nominal sanity", "Main blackout", "Primary ambiguity", "Detector / timing", "Detector-output screen", "Boundary stress", "NIS diagnostic"]
suite_records = np.array([3000, 1500, 1800, 1800, 400, 1100, 600])
suite_targets = ["shared-controller sanity", "blackout safety / availability", "target-consistency primary test", "fault-layer coverage", "detector-level degradation", "combined-stress boundary", "uncertainty monitor response"]

gain_labels = ["FP10 vs\nNo query", "FP10 vs\nRule", "ID switch vs\nStd KF", "ID switch vs\nRule"]
gain_mean = np.array([33.1, 42.5, 34.6, 43.0])
gain_low = np.array([30.4, 37.8, 31.5, 39.4])
gain_high = np.array([35.8, 47.1, 37.8, 46.7])

conditions = ["0.2 m", "0.5 m", "1.0 m", "FP10", "ID20", "Combo"]
nis_p95 = np.array([1.432, 3.757, 13.118, 1621.8, 971.8, 1506.3])
hard_viol = np.array([0.0, 0.0, 2.9, 80.4, 25.9, 72.2])
TAU_SOFT = 12.0
TAU_HARD = 20.0

def apply_source_data():
    source_path = SOURCE / "fig_simulation_stress_atlas_source.csv"
    if not source_path.exists():
        return

    rows = []
    with source_path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    suite_order = ["nominal", "main_blackout", "ambiguity", "detector_timing", "raw_like", "boundary", "nis_diagnostic"]
    suite_rows = [row for row in rows if row.get("panel") == "a_evidence_scale"]
    suite_by_id = {row.get("evidence_id"): row for row in suite_rows}
    display_label = {
        "Raw-like screen": "Detector-output screen",
        "raw-like screen": "Detector-output screen",
        "Raw-like": "Detector-output",
        "raw-like": "Detector-output",
    }
    if all(key in suite_by_id for key in suite_order):
        global suite_names, suite_records
        suite_names = [display_label.get(suite_by_id[key]["condition_label"], suite_by_id[key]["condition_label"]) for key in suite_order]
        suite_records = np.array([float(suite_by_id[key]["value"]) for key in suite_order])

    gain_order = [
        ("fp_10", "qgip_no_query"),
        ("fp_10", "rule"),
        ("idswitch", "std_kf"),
        ("idswitch", "rule"),
    ]
    gain_rows = [
        row for row in rows
        if row.get("panel") == "c_primary_ambiguity_effects"
        and row.get("metric") == "leaderacc_gain_pp"
    ]
    gain_by_key = {(row.get("condition_id"), row.get("comparison_method")): row for row in gain_rows}
    if all(key in gain_by_key for key in gain_order):
        global gain_mean, gain_low, gain_high
        gain_mean = np.array([float(gain_by_key[key]["value"]) for key in gain_order])
        gain_low = np.array([float(gain_by_key[key]["ci_low"]) for key in gain_order])
        gain_high = np.array([float(gain_by_key[key]["ci_high"]) for key in gain_order])

    nis_order = ["noise_02", "noise_05", "noise_10", "fp_10", "idswitch_20", "fp10_idswitch20_noise05"]
    nis_rows = [
        row for row in rows
        if row.get("panel") == "d_nis_diagnostic_response"
        and row.get("metric") == "nisp95_mean"
    ]
    hard_rows = [
        row for row in rows
        if row.get("panel") == "d_nis_diagnostic_response"
        and row.get("metric") == "nishardviolations_mean"
    ]
    nis_by_id = {row.get("condition_id"): row for row in nis_rows}
    hard_by_id = {row.get("condition_id"): row for row in hard_rows}
    if all(key in nis_by_id and key in hard_by_id for key in nis_order):
        global nis_p95, hard_viol
        nis_p95 = np.array([float(nis_by_id[key]["value"]) for key in nis_order])
        hard_viol = np.array([float(hard_by_id[key]["value"]) for key in nis_order])

def draw_panel_a(ax):
    ax.set_title("a  Stress-suite coverage map", loc="left", fontsize=8.2, fontweight="bold", pad=6)
    y = np.arange(len(suite_names))[::-1]
    max_records = 3000
    ax.set_xlim(0, max_records * 1.10)
    ax.set_ylim(-0.7, len(suite_names) - 0.3)

    # Subtle group bands: only structure, no PPT-like blocks.
    ax.axhspan(4.5, 6.5, color=COLORS["bg_blue"], zorder=-3)
    ax.axhspan(2.5, 4.5, color="#F7F7F8", zorder=-3)
    ax.axhspan(0.5, 2.5, color=COLORS["bg_orange"], zorder=-3)
    ax.axhspan(-0.5, 0.5, color=COLORS["bg_red"], zorder=-3)

    for xx in [0, 1000, 2000, 3000]:
        ax.axvline(xx, color=COLORS["grid"], linewidth=0.45, zorder=-1)

    # background tracks
    ax.hlines(y, 0, max_records, color="#D9DEE7", linewidth=2.2, zorder=1)

    # main bars
    for i, (name, val) in enumerate(zip(suite_names, suite_records)):
        yy = y[i]
        if name == "Primary ambiguity":
            c, lw = COLORS["blue"], 2.9
        elif name == "Boundary stress":
            c, lw = COLORS["orange"], 2.9
        elif name == "NIS diagnostic":
            c, lw = COLORS["red"], 2.9
        else:
            c, lw = "#4C6A82", 2.1
        line, = ax.plot([0, val], [yy, yy], color=c, linewidth=lw, solid_capstyle="butt", zorder=3)
        add_halo(line, lw=lw+1.6)
        ax.scatter([val], [yy], s=18, color=c, edgecolor="white", linewidth=0.55, zorder=4)
        ax.text(val + 60, yy + 0.13, f"{int(round(val)):,}", ha="left", va="bottom", fontsize=5.75, color=c)

    # row labels as proper y ticks, not text columns.
    ax.set_yticks(y)
    ax.set_yticklabels(suite_names)
    ax.tick_params(axis="y", length=0, pad=3)

    # small in-plot note, kept away from panel b.
    ax.text(0.02, 0.04, "highlighted rows: primary ambiguity, boundary stress, NIS diagnostic",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=5.45, color=COLORS["gray"])

    ax.set_xlabel("processed episode-method records")
    ax.set_xticks([0, 1000, 2000, 3000])
    ax.set_xticklabels(["0", "1k", "2k", "3k"])

    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="x", length=2.5, width=0.6)

def draw_panel_b(ax):
    ax.set_title("b  Primary ambiguity discriminator", loc="left", fontsize=8.2, fontweight="bold", pad=6)
    y = np.arange(len(gain_labels))[::-1]
    ax.set_xlim(25, 50)
    ax.set_ylim(-0.60, len(gain_labels)-0.40)
    for xx in [30, 40, 50]:
        ax.axvline(xx, color=COLORS["grid"], linewidth=0.50, zorder=0)
    for yy, mean, low, high in zip(y, gain_mean, gain_low, gain_high):
        ax.plot([low, high], [yy, yy], color="#5F6368", linewidth=0.95, zorder=2)
        ax.plot([low, low], [yy-0.055, yy+0.055], color="#5F6368", linewidth=0.90, zorder=2)
        ax.plot([high, high], [yy-0.055, yy+0.055], color="#5F6368", linewidth=0.90, zorder=2)
        ax.scatter([mean], [yy], s=30, color=COLORS["blue"], edgecolor="#063F78", linewidth=0.55, zorder=3)
        ax.text(mean + 0.6, yy + 0.05, f"+{mean:.1f}", ha="left", va="center", fontsize=5.85, color=COLORS["blue"])
    ax.set_yticks(y)
    ax.set_yticklabels(gain_labels)
    ax.set_xlabel("LeaderAcc gain vs comparator (percentage points)")
    ax.text(49.5, -0.47, r"$N=300$ paired episodes; whiskers, 95\% bootstrap CI", ha="right", va="bottom", fontsize=5.55, color=COLORS["gray"])
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76)
    ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="both", length=2.5, width=0.6)

def draw_panel_c(ax):
    ax.set_title("c  Diagnostic boundary response", loc="left", fontsize=8.2, fontweight="bold", pad=6)
    x = np.arange(len(conditions))
    ax.set_yscale("log")
    ax.set_ylim(0.8, 5000)
    ax.set_xlim(-0.55, len(conditions)-0.45)
    ax.axhline(TAU_SOFT, color=COLORS["orange"], linestyle=(0, (4, 2.5)), linewidth=0.90, zorder=1)
    ax.axhline(TAU_HARD, color=COLORS["red"], linestyle=(0, (1.5, 2.1)), linewidth=0.95, zorder=1)
    ax.text(len(conditions)-0.48, TAU_SOFT*1.05, r"$\tau_{\rm soft}$", ha="right", va="bottom", fontsize=5.55, color=COLORS["orange"])
    ax.text(len(conditions)-0.48, TAU_HARD*1.08, r"$\tau_{\rm hard}$", ha="right", va="bottom", fontsize=5.55, color=COLORS["red"])
    ax.axvspan(-0.5, 2.5, color=COLORS["bg_blue"], alpha=0.55, zorder=-3)
    ax.axvspan(2.5, 5.5, color=COLORS["bg_red"], alpha=0.42, zorder=-3)
    for xx, yy, hv in zip(x, nis_p95, hard_viol):
        c = COLORS["blue"] if yy <= 20 else COLORS["red"]
        stem, = ax.plot([xx, xx], [1.0, yy], color=c, linewidth=1.0, alpha=0.90, zorder=2)
        add_halo(stem, lw=2.2)
        ax.scatter([xx], [yy], s=34, color=c, edgecolor="#222222", linewidth=0.55, zorder=3)
        if yy <= 20:
            ax.text(xx, yy * 1.65, f"HV {hv:.1f}", ha="center", va="bottom",
                    fontsize=5.25, color=c,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.82, pad=0.08), zorder=4)
        else:
            ax.text(xx + 0.10, yy * 1.12, f"HV {hv:.1f}", ha="left", va="bottom",
                    fontsize=5.25, color=c,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.82, pad=0.08), zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, rotation=30, ha="right")
    ax.set_ylabel("NIS p95 (log scale)")
    ax.set_xlabel("perturbation condition")
    ax.grid(axis="y", which="major", color=COLORS["grid"], linewidth=0.46)
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["blue"],
               markeredgecolor="#222222", markeredgewidth=0.45, markersize=4.0, label="below hard gate"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["red"],
               markeredgecolor="#222222", markeredgewidth=0.45, markersize=4.0, label="beyond hard gate"),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=False, borderaxespad=0.1,
              handletextpad=0.35, labelspacing=0.20)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76)
    ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="both", length=2.5, width=0.6)

def build_figure(save_base):
    apply_source_data()
    fig = plt.figure(figsize=(7.45, 2.95), dpi=300)
    gs = GridSpec(1, 2, figure=fig, width_ratios=[1.00, 1.05], wspace=0.42)
    ax_b = fig.add_subplot(gs[0, 0])
    ax_c = fig.add_subplot(gs[0, 1])
    draw_panel_b(ax_b)
    draw_panel_c(ax_c)
    fig.subplots_adjust(left=0.140, right=0.985, top=0.90, bottom=0.18)
    fig.savefig(f"{save_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{save_base}.svg", bbox_inches="tight")
    fig.savefig(f"{save_base}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{save_base}.tiff", dpi=600, bbox_inches="tight")
    return fig

if __name__ == "__main__":
    build_figure("fig5_stress_suite_discriminators_v3")
    plt.close("all")
