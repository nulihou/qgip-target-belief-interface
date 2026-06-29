
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import shutil
from pathlib import Path

from qgip_figure_style import TOP_CONF_COLORS as TOP, apply_top_conference_style

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
FIGS = ROOT / "08_paper_ready_outputs" / "figures"
MANUSCRIPT_FIGS = ROOT / "01_manuscript" / "paper_picture"
FIGURE_ID = "fig12_validation_boundary_narrative_v4"


def mm(value):
    return value / 25.4

apply_top_conference_style()
plt.rcParams.update({
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.1,
    "ytick.labelsize": 6.1,
    "legend.fontsize": 5.8,
    "axes.linewidth": 0.82,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

COLORS = {
    "ready": TOP["teal"],
    "ready_light": TOP["teal_light"],
    "required": TOP["brick"],
    "required_light": TOP["brick_light"],
    "boundary": TOP["gray"],
    "line": TOP["gray_mid"],
    "text": TOP["ink"],
    "muted": TOP["gray"],
}

stages = pd.DataFrame([
    {"stage": "Gate package", "status": "prepared", "x": 0.85,
     "headline": "A-F gate audit", "sub": "23/23 gate rows\nprepared locally"},
    {"stage": "Desktop preflight", "status": "prepared", "x": 2.45,
     "headline": "ROS2-less dry run", "sub": "12/12 checks pass\ntelemetry parser ready"},
    {"stage": "Live ROS2/HIL", "status": "required", "x": 4.55,
     "headline": "live timing evidence", "sub": "colcon, launch,\nrosbag, HIL logs"},
    {"stage": "Physical trial", "status": "required", "x": 6.35,
     "headline": "operator-supervised trials", "sub": "trial bags, manifests,\nmetrics, incident reports"},
])

def stage_text(ax, x, y, headline, sub, color):
    ax.text(x, y + 0.28, headline, ha="center", va="bottom",
            fontsize=6.25, fontweight="bold", color=color, linespacing=0.92)
    ax.text(x, y - 0.06, sub, ha="center", va="top",
            fontsize=5.45, color=COLORS["text"], linespacing=0.90)


def write_source_data():
    SOURCE.mkdir(parents=True, exist_ok=True)
    rows = stages.copy()
    rows["marker"] = rows["status"].map({"prepared": "filled", "required": "open"})
    rows["claim_boundary_role"] = rows["status"].map({
        "prepared": "prepared local evidence only",
        "required": "external live ROS2/HIL or physical evidence still required",
    })
    rows["validation_boundary_x"] = 3.35
    rows.to_csv(SOURCE / f"{FIGURE_ID}_source_data.csv", index=False)


def build_figure(save_base="fig12_validation_boundary_narrative_v4"):
    write_source_data()
    fig, ax = plt.subplots(figsize=(mm(183), mm(61)), dpi=300)
    ax.set_xlim(0, 7.25)
    ax.set_ylim(0, 2.75)
    ax.axis("off")
    ax.add_patch(patches.Rectangle((0.15, 0.55), 3.00, 1.65,
                                   facecolor=COLORS["ready_light"], edgecolor="none",
                                   alpha=0.82, zorder=-5))
    ax.add_patch(patches.Rectangle((3.55, 0.55), 3.45, 1.65,
                                   facecolor=COLORS["required_light"], edgecolor="none",
                                   alpha=0.65, zorder=-5))
    ax.text(1.65, 2.26, "completed local readiness", ha="center", va="bottom",
            fontsize=6.15, fontweight="bold", color=COLORS["ready"])
    ax.text(5.27, 2.26, "external validation still required", ha="center", va="bottom",
            fontsize=6.15, fontweight="bold", color=COLORS["required"])
    yrail = 1.42
    ax.plot([0.85, 2.45], [yrail, yrail], color=COLORS["ready"], lw=1.75,
            solid_capstyle="round", zorder=1)
    ax.plot([2.45, 3.35], [yrail, yrail], color=COLORS["line"], lw=1.20,
            linestyle=(0, (3, 2)), zorder=1)
    ax.plot([3.35, 6.35], [yrail, yrail], color=COLORS["required"], lw=1.25,
            linestyle=(0, (3, 2)), zorder=1)
    xb = 3.35
    ax.axvline(xb, ymin=0.25, ymax=0.87, color=COLORS["boundary"],
               lw=1.05, linestyle=(0, (3, 2)), zorder=0)
    ax.text(xb - 0.13, 2.11, "validation\nboundary", ha="right", va="top",
            fontsize=5.75, color=COLORS["boundary"], linespacing=0.88)
    ax.text(xb - 0.12, 0.42, "current manuscript stops here",
            ha="right", va="center", fontsize=5.50, color=COLORS["boundary"])
    for _, r in stages.iterrows():
        prepared = r["status"] == "prepared"
        color = COLORS["ready"] if prepared else COLORS["required"]
        if prepared:
            ax.scatter(r["x"], yrail, s=90, marker="o", facecolor=color,
                       edgecolor=TOP["teal_dark"], linewidth=0.75, zorder=4)
        else:
            ax.scatter(r["x"], yrail, s=90, marker="o", facecolor="white",
                       edgecolor=color, linewidth=1.25, zorder=4)
        stage_text(ax, r["x"], 0.92, r["headline"], r["sub"], color)
    ax.text(6.95, 2.05, "no ROS2/HIL or\nphysical-validation claim",
            ha="right", va="top", fontsize=5.55, color=COLORS["boundary"],
            linespacing=0.90)
    ax.text(0.16, 0.20,
            "filled markers: prepared local evidence   |   open markers: external evidence required before any live-validation claim",
            ha="left", va="center", fontsize=5.45, color=COLORS["muted"])
    fig.subplots_adjust(left=0.035, right=0.985, top=0.96, bottom=0.12)
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
