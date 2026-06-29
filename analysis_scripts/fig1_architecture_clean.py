"""
Fig.1 (redesigned): Clean single-panel system architecture diagram.

Design principles:
- Single panel, no a/b/c/d sub-panels
- Three horizontal layers with clear pipeline flow
- Blue = learned/neural, Green = probabilistic/Kalman, Orange = symbolic/control
- Minimum 7pt fonts throughout
- Component names only on figure; all explanation in caption
- Compact belief-mode cycle inside the POP block
- Closed-loop feedback arrow
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Arc, Polygon
import matplotlib.lines as mlines
import numpy as np

# ---- Professional color palette ----
BLUE = "#2563EB"        # learned / neural
BLUE_LIGHT = "#DBEAFE"
GREEN = "#059669"       # probabilistic / Kalman
GREEN_LIGHT = "#D1FAE5"
ORANGE = "#D97706"      # symbolic / control
ORANGE_LIGHT = "#FEF3C7"
GRAY = "#6B7280"        # annotations
DARK = "#111827"        # text
WHITE = "#FFFFFF"
ARROW = "#9CA3AF"       # connection arrows
FEEDBACK = "#2563EB"    # feedback loop color (solid blue, same as learned)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 8.0,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
})

def rounded_box(ax, x, y, w, h, color, alpha=0.12, lw=1.5, z=2):
    """Draw a rounded rectangle with subtle fill."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.12",
        facecolor=color, edgecolor=color,
        alpha=alpha, linewidth=lw, zorder=z,
    )
    ax.add_patch(box)
    return box

def solid_rounded_box(ax, x, y, w, h, facecolor, edgecolor, lw=1.2, z=3):
    """Draw a solid filled rounded rectangle."""
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.10",
        facecolor=facecolor, edgecolor=edgecolor,
        linewidth=lw, zorder=z,
    )
    ax.add_patch(box)
    return box

def label(ax, x, y, text, color=DARK, size=8.0, weight="bold", ha="center", va="center"):
    """Place a text label."""
    ax.text(x, y, text, fontsize=size, color=color, weight=weight,
            ha=ha, va=va, zorder=10)

def sublabel(ax, x, y, text, color=GRAY, size=6.8):
    """Place a smaller secondary label."""
    ax.text(x, y, text, fontsize=size, color=color, weight="normal",
            ha="center", va="center", zorder=10)

def arrow(ax, x1, y1, x2, y2, color=ARROW, lw=1.6, z=1, style="simple"):
    """Draw an arrow between two points."""
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color,
                                lw=lw, connectionstyle="arc3,rad=0"),
                zorder=z)

def curved_arrow(ax, x1, y1, x2, y2, color=ARROW, lw=1.4, rad=0.3, z=1):
    """Draw a curved arrow with annotation."""
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color,
                                lw=lw, connectionstyle=f"arc3,rad={rad}"),
                zorder=z)

# ---- Figure layout parameters ----
FIG_W = 10.0
FIG_H = 4.2

# Layer Y positions
Y_TOP = 3.05       # top row: input / scene graph
Y_MID = 1.75       # middle row: LLC + POP/NIS
Y_BOT = 0.45       # bottom row: MPC + output

# Block dimensions
BLOCK_H = 1.05
BLOCK_W_INPUT = 1.6    # input block
BLOCK_W_GNN = 1.55     # scene graph / GNN blocks
BLOCK_W_POP = 1.90     # POP/NIS block
BLOCK_W_MPC = 1.60     # MPC block
BLOCK_W_OUT = 1.00     # output block

# X positions
X_INPUT = 0.35
X_SCENE = X_INPUT + BLOCK_W_INPUT + 0.55
X_GNN = X_SCENE + BLOCK_W_GNN + 0.50
X_POP = X_GNN + BLOCK_W_GNN + 0.40
X_MPC = X_POP + BLOCK_W_POP + 0.45
X_OUT = X_MPC + BLOCK_W_MPC + 0.50

# ---- Build figure ----
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.set_aspect("equal")
ax.axis("off")

# ============================================================
# REGION LABELS (subtle background bands)
# ============================================================
# Learned region (left side)
ax.axvspan(0.08, X_POP - 0.10, ymin=0.08, ymax=0.92,
           facecolor=BLUE_LIGHT, alpha=0.28, zorder=0)
# Symbolic region (right side)
ax.axvspan(X_POP - 0.10, FIG_W - 0.08, ymin=0.08, ymax=0.92,
           facecolor=ORANGE_LIGHT, alpha=0.22, zorder=0)

# Region labels at top
label(ax, (X_INPUT + X_GNN + BLOCK_W_GNN) / 2, FIG_H - 0.22,
      "Learned (neural)", BLUE, 7.2, "bold")
label(ax, (X_POP + X_MPC + BLOCK_W_MPC) / 2, FIG_H - 0.22,
      "Explicit (symbolic / probabilistic)", ORANGE, 7.2, "bold")

# Subtle divider
ax.axvline(X_POP - 0.15, ymin=0.10, ymax=0.90,
           color=GRAY, lw=0.6, linestyle=":", alpha=0.5, zorder=0)

# ============================================================
# ROW 1: INPUT → SCENE GRAPH → GNN (learned)
# ============================================================
# Input block
rounded_box(ax, X_INPUT, Y_TOP - BLOCK_H/2, BLOCK_W_INPUT, BLOCK_H, DARK, 0.06, 1.5, 3)
label(ax, X_INPUT + BLOCK_W_INPUT/2, Y_TOP + 0.22, "Object list", DARK, 8.5)
sublabel(ax, X_INPUT + BLOCK_W_INPUT/2, Y_TOP - 0.08, "+ ego state + query")

# Arrow: input → scene graph
arrow(ax, X_INPUT + BLOCK_W_INPUT, Y_TOP,
      X_SCENE + 0.08, Y_TOP, ARROW, 1.8, 3)

# Scene graph block (lighter, preparatory)
rounded_box(ax, X_SCENE, Y_TOP - BLOCK_H/2, BLOCK_W_GNN, BLOCK_H, BLUE, 0.10, 1.4, 3)
label(ax, X_SCENE + BLOCK_W_GNN/2, Y_TOP + 0.18, "Intent-conditioned", DARK, 8.0)
label(ax, X_SCENE + BLOCK_W_GNN/2, Y_TOP - 0.18, "scene graph", DARK, 8.0, "bold")
sublabel(ax, X_SCENE + BLOCK_W_GNN/2, Y_TOP - 0.52, "FiLM-GATv2 encoder")

# Arrow: scene graph → GNN
arrow(ax, X_SCENE + BLOCK_W_GNN, Y_TOP,
      X_GNN + 0.08, Y_TOP, ARROW, 1.8, 3)

# GNN / LLC block (the learned selector)
solid_rounded_box(ax, X_GNN, Y_TOP - BLOCK_H/2, BLOCK_W_GNN, BLOCK_H, BLUE, BLUE, 1.5, 4)
label(ax, X_GNN + BLOCK_W_GNN/2, Y_TOP + 0.20, "LLC", WHITE, 11.0)
label(ax, X_GNN + BLOCK_W_GNN/2, Y_TOP - 0.18, "Leader-Likelihood", WHITE, 7.2)
label(ax, X_GNN + BLOCK_W_GNN/2, Y_TOP - 0.46, "Classifier", WHITE, 7.2, "bold")

# Arrow: GNN → POP (output: selected leader ID + confidence)
arrow(ax, X_GNN + BLOCK_W_GNN, Y_TOP,
      X_POP + 0.08, Y_TOP, ARROW, 1.8, 3)
# Label on arrow
label(ax, X_GNN + BLOCK_W_GNN + (X_POP - X_GNN - BLOCK_W_GNN)/2, Y_TOP + 0.32,
      "leader ID", GRAY, 6.5, "normal")
label(ax, X_GNN + BLOCK_W_GNN + (X_POP - X_GNN - BLOCK_W_GNN)/2, Y_TOP + 0.05,
      "+ confidence", GRAY, 6.5, "normal")

# ============================================================
# ROW 2: POP/NIS-KF (probabilistic belief — the core contribution)
# ============================================================
# Large POP block spanning both learned and symbolic zones
rounded_box(ax, X_POP, Y_MID - BLOCK_H/2 - 0.12, BLOCK_W_POP, BLOCK_H + 0.24,
            GREEN, 0.12, 1.8, 5)

# POP title area
solid_rounded_box(ax, X_POP + 0.08, Y_MID + 0.28, BLOCK_W_POP - 0.16, 0.40,
                  GREEN, GREEN, 1.0, 6)
label(ax, X_POP + BLOCK_W_POP/2, Y_MID + 0.48, "POP / NIS-KF Belief", WHITE, 8.5)

# Four belief modes as a horizontal row of small boxes inside POP
mode_w = 0.38
mode_h = 0.32
mode_y = Y_MID - 0.10
mode_x_start = X_POP + 0.12
mode_gap = 0.06

modes = [
    ("TRACK", BLUE, "update"),
    ("GHOST", "#6366F1", "predict"),
    ("DEGRADED", ORANGE, "hold"),
    ("LOST", "#DC2626", "stop"),
]

for i, (mode_name, mode_color, mode_action) in enumerate(modes):
    mx = mode_x_start + i * (mode_w + mode_gap)
    solid_rounded_box(ax, mx, mode_y, mode_w, mode_h, mode_color, mode_color, 0.8, 7)
    label(ax, mx + mode_w/2, mode_y + mode_h/2 + 0.03, mode_name, WHITE, 6.8)
    sublabel(ax, mx + mode_w/2, mode_y + mode_h/2 - 0.12, mode_action, "#E5E7EB", 5.5)
    # Arrows between modes
    if i < 3:
        arrow(ax, mx + mode_w, mode_y + mode_h/2,
              mx + mode_w + mode_gap, mode_y + mode_h/2, "#9CA3AF", 1.0, 7)

# NIS gate annotation below modes
label(ax, X_POP + BLOCK_W_POP/2, mode_y - 0.30,
      "NIS-gated: τ_soft = 12  |  τ_hard = 20  |  T_g = 1.5 s",
      GRAY, 6.2, "normal")

# Input label inside POP
label(ax, X_POP + BLOCK_W_POP/2, Y_MID + 0.05,
      "selected leader → belief state → controller",
      GRAY, 6.2, "normal")

# Arrow: POP → MPC
arrow(ax, X_POP + BLOCK_W_POP, Y_MID,
      X_MPC + 0.08, Y_MID, ARROW, 1.8, 3)
# Label
label(ax, X_POP + BLOCK_W_POP + (X_MPC - X_POP - BLOCK_W_POP)/2, Y_MID + 0.28,
      "belief state", GRAY, 6.5, "normal")
label(ax, X_POP + BLOCK_W_POP + (X_MPC - X_POP - BLOCK_W_POP)/2, Y_MID + 0.02,
      "+ POP mode", GRAY, 6.5, "normal")

# ============================================================
# ROW 3: Lattice MPC → ACC output (symbolic control)
# ============================================================
rounded_box(ax, X_MPC, Y_BOT - BLOCK_H/2, BLOCK_W_MPC, BLOCK_H, ORANGE, 0.10, 1.4, 4)
label(ax, X_MPC + BLOCK_W_MPC/2, Y_BOT + 0.22, "Lattice MPC", DARK, 9.0)
sublabel(ax, X_MPC + BLOCK_W_MPC/2, Y_BOT - 0.06, "18 candidates × 15 steps")
sublabel(ax, X_MPC + BLOCK_W_MPC/2, Y_BOT - 0.36, "collision-feasibility filter")

# Arrow: MPC → output
arrow(ax, X_MPC + BLOCK_W_MPC, Y_BOT,
      X_OUT + 0.05, Y_BOT, ARROW, 1.8, 3)

# Output block
solid_rounded_box(ax, X_OUT, Y_BOT - BLOCK_H/2 + 0.05, BLOCK_W_OUT, BLOCK_H - 0.10,
                  DARK, DARK, 1.4, 5)
label(ax, X_OUT + BLOCK_W_OUT/2, Y_BOT + 0.12, "Track", WHITE, 7.0)
label(ax, X_OUT + BLOCK_W_OUT/2, Y_BOT - 0.18, "Slow", "#D1D5DB", 7.0)
label(ax, X_OUT + BLOCK_W_OUT/2, Y_BOT - 0.48, "Stop", "#9CA3AF", 7.0)

# ============================================================
# FEEDBACK LOOP (closed-loop)
# ============================================================
# Curved arrow from output back to input, along the bottom
feedback_y = 0.08
ax.annotate("",
            xy=(X_INPUT + BLOCK_W_INPUT/2, Y_BOT - BLOCK_H/2 - 0.15),
            xytext=(X_OUT + BLOCK_W_OUT/2, Y_BOT - BLOCK_H/2 - 0.15),
            arrowprops=dict(arrowstyle="->", color=FEEDBACK, lw=2.0,
                            connectionstyle="arc3,rad=0.35",
                            linestyle="dashed"),
            zorder=1)
label(ax, (X_INPUT + X_OUT + BLOCK_W_OUT)/2 + 0.3, feedback_y,
      "closed-loop execution (next frame)", FEEDBACK, 7.0, "bold")

# ============================================================
# INTER-LAYER CONNECTIONS (vertical data flow)
# ============================================================
# Dashed vertical line showing query injection into scene graph
ax.annotate("", xy=(X_SCENE + BLOCK_W_GNN/2, Y_TOP - BLOCK_H/2),
            xytext=(X_INPUT + BLOCK_W_INPUT/2, Y_TOP - BLOCK_H/2 - 0.25),
            arrowprops=dict(arrowstyle="->", color=FEEDBACK, lw=1.0,
                            connectionstyle="arc3,rad=-0.2", linestyle="dotted"),
            zorder=1)
label(ax, X_INPUT + BLOCK_W_INPUT/2 - 0.70, Y_TOP - BLOCK_H/2 - 0.45,
      "query", BLUE, 6.2, "normal")

# ============================================================
# LEGEND at bottom-right
# ============================================================
legend_x = X_MPC + 0.05
legend_y = Y_MID - BLOCK_H/2 - 0.70
legend_items = [
    (BLUE, "Learned (neural)"),
    (GREEN, "Probabilistic (belief)"),
    (ORANGE, "Symbolic (control)"),
]
for i, (color, desc) in enumerate(legend_items):
    lx = legend_x + i * 1.55
    ax.add_patch(plt.Rectangle((lx, legend_y), 0.18, 0.18,
                                facecolor=color, edgecolor=color,
                                linewidth=0.8, zorder=10))
    label(ax, lx + 0.28, legend_y + 0.09, desc, DARK, 6.5, "normal", "left")

# ============================================================
# FINAL
# ============================================================
fig.tight_layout(pad=0.5)

# Save
import os
out_dirs = [
    "D:/paper/paper3_lc_org_v2.0/RA_L_optimization_20260528/01_manuscript/paper_picture",
    "D:/paper/paper3_lc_org_v2.0/RA_L_optimization_20260528/08_paper_ready_outputs/figures",
    "D:/paper/paper3_lc_org_v2.0/RA_L_optimization_20260528/10_TASE_submission_20260610/01_manuscript/paper_picture",
]
for out_dir in out_dirs:
    os.makedirs(out_dir, exist_ok=True)
    for ext, kw in [(".pdf", {}), (".svg", {}), (".png", {"dpi": 400}), (".tiff", {"dpi": 400})]:
        fig.savefig(os.path.join(out_dir, f"fig1_architecture_clean{ext}"),
                    bbox_inches="tight", **kw)

print(f"Saved fig1_architecture_clean.* to all output dirs")
plt.close()
