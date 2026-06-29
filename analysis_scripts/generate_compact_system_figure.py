"""Generate a lightweight vector system overview figure for the RA-L manuscript."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "01_manuscript" / "paper_picture"
PDF_OUT = OUT_DIR / "qgip_net_architecture_compact.pdf"
PNG_OUT = OUT_DIR / "qgip_net_architecture_compact.png"


def box(ax, xy, wh, title, body, face, edge="#27303f"):
    x, y = xy
    w, h = wh
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.018,rounding_size=0.025",
        linewidth=1.15,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    title_lines = title.count("\n") + 1
    body_offset = 0.58 if title_lines > 1 else 0.48
    ax.text(
        x + 0.05 * w,
        y + h - 0.17 * h,
        title,
        fontsize=8.5,
        fontweight="bold",
        va="top",
        color="#111827",
        linespacing=0.92,
    )
    ax.text(x + 0.05 * w, y + h - body_offset * h, body, fontsize=6.6, va="top", color="#27303f", linespacing=1.06)


def arrow(ax, start, end, text=None, rad=0.0):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=10,
        linewidth=1.1,
        color="#334155",
        shrinkA=4,
        shrinkB=4,
        connectionstyle=f"arc3,rad={rad}",
    )
    ax.add_patch(patch)
    if text:
        mx = (start[0] + end[0]) / 2
        my = (start[1] + end[1]) / 2
        ax.text(mx, my + 0.02, text, fontsize=7.0, color="#475569", ha="center", va="bottom")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.2, 3.05))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    colors = {
        "input": "#eef2ff",
        "neural": "#ecfeff",
        "state": "#f0fdf4",
        "control": "#fff7ed",
        "safety": "#fef2f2",
    }

    box(
        ax,
        (0.03, 0.58),
        (0.18, 0.27),
        "Sensor\nCandidates",
        "object list, confidence,\nego-relative state",
        colors["input"],
    )
    box(
        ax,
        (0.27, 0.58),
        (0.19, 0.27),
        "Query-Guided\nGNN",
        "FiLM intent conditioning\nscene-graph attention\nleader selection",
        colors["neural"],
    )
    box(
        ax,
        (0.52, 0.58),
        (0.18, 0.27),
        "POP /\nNIS-KF",
        "innovation gating\nghost prediction\nrecovery reset",
        colors["state"],
    )
    box(
        ax,
        (0.77, 0.58),
        (0.18, 0.27),
        "Safety\nMPC",
        "lattice rollout\ncollision filtering\nemergency brake",
        colors["control"],
    )
    box(
        ax,
        (0.27, 0.12),
        (0.19, 0.27),
        "Symbolic\nRules",
        "lane consistency\nquery constraints\nleader identity checks",
        colors["safety"],
    )
    box(
        ax,
        (0.52, 0.12),
        (0.18, 0.27),
        "Fail-safe\nState",
        "Reliable / Degraded\nOut-of-ODD\nconservative stop",
        colors["safety"],
    )

    arrow(ax, (0.21, 0.715), (0.27, 0.715))
    arrow(ax, (0.46, 0.715), (0.52, 0.715))
    arrow(ax, (0.70, 0.715), (0.77, 0.715))
    arrow(ax, (0.86, 0.58), (0.86, 0.42))
    arrow(ax, (0.365, 0.58), (0.365, 0.39))
    arrow(ax, (0.46, 0.28), (0.52, 0.28))
    arrow(ax, (0.61, 0.39), (0.61, 0.58))
    arrow(ax, (0.70, 0.28), (0.77, 0.62), rad=-0.15)

    ax.text(
        0.5,
        0.93,
        "QGIP-Net: learned target selection with explicit state estimation and deterministic safety filtering",
        ha="center",
        va="center",
        fontsize=9.5,
        fontweight="bold",
        color="#111827",
    )
    ax.text(
        0.5,
        0.055,
        "Simulation evidence focuses on target consistency under CARLA ambiguity stress; real-robot deployment remains future validation.",
        ha="center",
        va="center",
        fontsize=7.2,
        color="#475569",
    )

    fig.savefig(PDF_OUT, bbox_inches="tight", pad_inches=0.04)
    fig.savefig(PNG_OUT, dpi=220, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)
    print(PDF_OUT)
    print(PNG_OUT)


if __name__ == "__main__":
    main()
