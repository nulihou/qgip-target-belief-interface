
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
FIGS = ROOT / "08_paper_ready_outputs" / "figures"
MANUSCRIPT_FIGS = ROOT / "01_manuscript" / "paper_picture"
FIGURE_ID = "fig13_offline_dryrun_contract_timeline_v2"


def mm(value):
    return value / 25.4

plt.rcParams.update({
    "font.family": "STIXGeneral",
    "mathtext.fontset": "stix",
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.1,
    "ytick.labelsize": 6.1,
    "legend.fontsize": 5.7,
    "axes.linewidth": 0.82,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "target": "#0B63B6",
    "tracking": "#0B63B6",
    "ghost": "#E69F00",
    "lost": "#D55E5E",
    "recover": "#18A57A",
    "speed": "#0C8F68",
    "boundary": "#6B7280",
    "grid": "#D7DDE5",
    "muted": "#6B7280",
    "text": "#111111",
    "dropout": "#EEF3F7",
    "recover_bg": "#EAF2FC",
    "gate": "#BFC7D1",
    "gate_fill": "#F4F5F7",
}

mode_intervals = pd.DataFrame([
    (0.00, 0.75, "TRACKING", COLORS["tracking"]),
    (0.75, 1.65, "GHOST", COLORS["ghost"]),
    (1.65, 2.45, "LOST", COLORS["lost"]),
    (2.45, 2.65, "RESET", COLORS["recover"]),
    (2.65, 4.20, "TRACKING", COLORS["tracking"]),
], columns=["t0", "t1", "mode", "color"])

t = np.linspace(0, 4.2, 181)
speed = np.piecewise(
    t,
    [t < 0.75, (t >= 0.75) & (t < 1.60), (t >= 1.60) & (t < 2.45),
     (t >= 2.45) & (t < 2.65), t >= 2.65],
    [0.50, lambda x: 0.26 - 0.02*(x - 0.75), 0.04, lambda x: 0.04 + 2.4*(x - 2.45), 0.50]
)
speed = np.clip(speed, 0.0, 0.50)
nis = np.zeros_like(t)
nis += 1.0 * np.exp(-0.5*((t - 0.85)/0.04)**2)
nis += 32.0 * np.exp(-0.5*((t - 2.55)/0.035)**2)

latency_df = pd.DataFrame({
    "statistic": ["mean", "p95", "p99"],
    "dry_run_ms": [9.1, 11.1, 11.5],
    "gate_ms": [18.0, 28.0, 32.0],
})


def write_source_data():
    SOURCE.mkdir(parents=True, exist_ok=True)
    rows = []
    for _, r in mode_intervals.iterrows():
        rows.append({
            "panel": "a_contract_timeline",
            "record_type": "mode_interval",
            "time_s": "",
            "t0_s": r["t0"],
            "t1_s": r["t1"],
            "mode": r["mode"],
            "speed_mps": "",
            "nis": "",
            "statistic": "",
            "dry_run_ms": "",
            "gate_ms": "",
            "note": "offline desktop dry-run contract interval",
        })
    for ti, speed_i, nis_i in zip(t, speed, nis):
        mode = mode_intervals.loc[(mode_intervals["t0"] <= ti) & (ti < mode_intervals["t1"]), "mode"]
        rows.append({
            "panel": "a_contract_timeline",
            "record_type": "time_series",
            "time_s": round(float(ti), 4),
            "t0_s": "",
            "t1_s": "",
            "mode": mode.iloc[0] if len(mode) else "TRACKING",
            "speed_mps": round(float(speed_i), 5),
            "nis": round(float(nis_i), 5),
            "statistic": "",
            "dry_run_ms": "",
            "gate_ms": "",
            "note": "selected leader retained; synthetic event trace for figure rendering",
        })
    for _, r in latency_df.iterrows():
        rows.append({
            "panel": "b_telemetry_gate",
            "record_type": "latency_gate",
            "time_s": "",
            "t0_s": "",
            "t1_s": "",
            "mode": "",
            "speed_mps": "",
            "nis": "",
            "statistic": r["statistic"],
            "dry_run_ms": r["dry_run_ms"],
            "gate_ms": r["gate_ms"],
            "note": "synthetic parser QA only, not live ROS2 timing",
        })
    pd.DataFrame(rows).to_csv(SOURCE / f"{FIGURE_ID}_source_data.csv", index=False)

def rounded_interval(ax, x0, x1, y, h, fc, ec=None, lw=0.0, alpha=1.0, label=None, text_color="white"):
    rect = patches.FancyBboxPatch(
        (x0, y - h/2), x1-x0, h,
        boxstyle="round,pad=0.01,rounding_size=0.035",
        facecolor=fc, edgecolor=ec if ec else fc, linewidth=lw,
        alpha=alpha, zorder=3
    )
    ax.add_patch(rect)
    if label:
        ax.text((x0+x1)/2, y, label, ha="center", va="center",
                fontsize=5.75, color=text_color, fontweight="bold", zorder=4)
    return rect

def draw_panel_a(ax):
    ax.set_title("a  Offline dry-run contract timeline", loc="left", fontsize=8.3, fontweight="bold", pad=7)
    ax.set_xlim(0, 4.2)
    ax.set_ylim(0.0, 3.85)
    ax.axvspan(0.75, 2.45, color=COLORS["dropout"], zorder=-5)
    ax.axvspan(2.45, 2.65, color=COLORS["recover_bg"], zorder=-4)
    ax.text(1.60, 3.58, "scripted measurement dropout", ha="center", va="top", fontsize=5.6, color=COLORS["muted"])
    ax.text(2.64, 3.50, "recovery", ha="center", va="top", fontsize=5.6, color=COLORS["target"])
    ax.text(-0.04, 3.10, "selected\nleader", transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=5.7, color=COLORS["text"], linespacing=0.90)
    ax.text(-0.04, 2.24, "POP\nmode", transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=5.7, color=COLORS["text"], linespacing=0.90)
    ax.text(-0.04, 1.42, "NIS\nevent", transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=5.7, color=COLORS["text"], linespacing=0.90)
    ax.text(-0.04, 0.62, "controller\nproxy", transform=ax.get_yaxis_transform(), ha="right", va="center", fontsize=5.7, color=COLORS["text"], linespacing=0.90)
    y_leader = 3.08
    ax.plot([0.0, 4.2], [y_leader, y_leader], color=COLORS["target"], lw=1.35, zorder=2)
    ax.scatter([0.0, 4.2], [y_leader, y_leader], s=20, color=COLORS["target"], edgecolor="#063F78", linewidth=0.45, zorder=3)
    ax.text(3.85, y_leader + 0.12, "target retained", ha="right", va="bottom", fontsize=5.55, color=COLORS["target"])
    y_mode = 2.25
    for _, r in mode_intervals.iterrows():
        label = r["mode"]
        if label == "RESET":
            label = None
        rounded_interval(ax, r["t0"], r["t1"], y_mode, 0.36, fc=r["color"], label=label,
                         text_color="white" if r["mode"] not in ["GHOST", "RESET"] else "#111111")
    y_nis = 1.43
    ax.plot([0, 4.2], [y_nis, y_nis], color="#DDE3EA", lw=0.9, zorder=1)
    ax.vlines(2.55, y_nis - 0.24, y_nis + 0.34, color=COLORS["lost"], lw=1.3, zorder=4)
    ax.scatter([2.55], [y_nis + 0.34], s=34, marker="^", facecolor=COLORS["lost"], edgecolor="#222222", linewidth=0.45, zorder=5)
    ax.text(2.68, y_nis + 0.26, r"NIS $>\tau_{\rm hard}$", ha="left", va="center", fontsize=5.55, color=COLORS["lost"])
    ax.text(2.55, y_mode + 0.34, "reset", ha="center", va="bottom", fontsize=5.35, color=COLORS["recover"])
    ax.text(0.10, y_nis + 0.17, "quiet during dropout", ha="left", va="center", fontsize=5.35, color=COLORS["muted"])
    y_base, y_scale = 0.40, 0.62
    y_speed = y_base + y_scale * (speed / 0.50)
    ax.plot(t, y_speed, color=COLORS["speed"], lw=1.1, zorder=3)
    ax.fill_between(t, y_base, y_speed, color=COLORS["speed"], alpha=0.10, zorder=2)
    ax.text(1.95, y_base + 0.26, "safe stop during LOST", ha="center", va="bottom", fontsize=5.45, color=COLORS["lost"])
    ax.text(4.15, y_base + y_scale + 0.03, "bounded command after recovery", ha="right", va="bottom", fontsize=5.45, color=COLORS["speed"])
    ax.set_xlabel("offline episode time (s)")
    ax.set_xticks([0, 1, 2, 3, 4])
    ax.set_yticks([])
    ax.grid(axis="x", color=COLORS["grid"], lw=0.35, zorder=-2)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="x", length=2.4, width=0.58)

def draw_panel_b(ax):
    ax.set_title("b  Runtime-telemetry parser gates", loc="left", fontsize=8.3, fontweight="bold", pad=7)
    ax.set_xlim(0, 36)
    ax.set_ylim(-0.55, 2.55)
    ax.set_xlabel("latency (ms)")
    y = np.arange(len(latency_df))[::-1]
    for i, (_, r) in enumerate(latency_df.iterrows()):
        yy = y[i]
        ax.add_patch(patches.FancyBboxPatch((0, yy - 0.18), r["gate_ms"], 0.36,
                     boxstyle="round,pad=0.01,rounding_size=0.035", facecolor=COLORS["gate_fill"],
                     edgecolor="#CAD0D8", linewidth=0.55, zorder=1))
        ax.scatter([r["dry_run_ms"]], [yy], s=38, marker="o", facecolor=COLORS["target"], edgecolor="#063F78", linewidth=0.55, zorder=3)
        ax.scatter([r["gate_ms"]], [yy], s=38, marker="|", color=COLORS["boundary"], linewidth=1.3, zorder=4)
        ax.text(r["dry_run_ms"] + 0.8, yy + 0.11, f"{r['dry_run_ms']:.1f}", ha="left", va="bottom", fontsize=5.35, color=COLORS["target"])
        ax.text(r["gate_ms"] - 0.8, yy + 0.11, f"gate {r['gate_ms']:.0f}", ha="right", va="bottom", fontsize=5.35, color=COLORS["boundary"])
    ax.set_yticks(y)
    ax.set_yticklabels(latency_df["statistic"].tolist())
    ax.set_xticks([0, 10, 20, 30])
    ax.grid(axis="x", color=COLORS["grid"], lw=0.35, zorder=-2)
    ax.text(0.04, 0.06, "synthetic parser QA only,\nnot live ROS2 timing", transform=ax.transAxes,
            ha="left", va="bottom", fontsize=5.45, color=COLORS["muted"], linespacing=0.90)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_linewidth(0.76)
    ax.spines["bottom"].set_linewidth(0.76)
    ax.tick_params(axis="both", length=2.4, width=0.58)

def build_figure(save_base="fig13_offline_dryrun_contract_timeline_v2"):
    write_source_data()
    fig = plt.figure(figsize=(mm(183), mm(81)), dpi=300)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.75, 1.00], wspace=0.34)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    draw_panel_a(ax_a)
    draw_panel_b(ax_b)
    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["target"],
               markeredgecolor="#063F78", markeredgewidth=0.55, markersize=4.8, label="dry-run value"),
        Line2D([0], [0], color=COLORS["tracking"], lw=3.0, label="tracking"),
        Line2D([0], [0], color=COLORS["ghost"], lw=3.0, label="ghost"),
        Line2D([0], [0], color=COLORS["lost"], lw=3.0, label="lost / reset"),
    ]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.57, 0.985),
               frameon=False, ncol=4, handletextpad=0.35, columnspacing=0.85)
    fig.subplots_adjust(left=0.085, right=0.985, top=0.80, bottom=0.17)
    fig.savefig(f"{save_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{save_base}.svg", bbox_inches="tight")
    fig.savefig(f"{save_base}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{save_base}.tiff", dpi=600, bbox_inches="tight")
    return fig

if __name__ == "__main__":
    FIGS.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_FIGS.mkdir(parents=True, exist_ok=True)
    figure = build_figure(str(FIGS / FIGURE_ID))
    plt.close(figure)
    for suffix in (".pdf", ".svg", ".png", ".tiff"):
        source_path = FIGS / f"{FIGURE_ID}{suffix}"
        shutil.copy2(source_path, MANUSCRIPT_FIGS / source_path.name)
