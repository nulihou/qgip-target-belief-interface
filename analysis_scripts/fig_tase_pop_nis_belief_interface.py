"""Compact T-ASE Fig. 2: POP/NIS belief interface.

This script reuses the already audited POP/NIS drawing primitives from
fig3_final_submission_ready_v9.py and removes the scene-snapshot row so the
main text keeps only the controller-facing mechanism.
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

from fig3_final_submission_ready_v9 import draw_row_b, draw_row_c, draw_row_d


def build_figure(save_base: Path) -> None:
    fig = plt.figure(figsize=(7.35, 4.05), dpi=300)
    gs = GridSpec(
        2,
        2,
        figure=fig,
        height_ratios=[1.08, 1.0],
        width_ratios=[1.0, 1.0],
        hspace=0.54,
        wspace=0.36,
    )

    ax_top = fig.add_subplot(gs[0, :])
    draw_row_b(ax_top, with_inset=False)
    ax_top.set_title(
        "a  Dropout, ghost prediction, and re-association",
        loc="left",
        fontsize=8.2,
        fontweight="bold",
        pad=6,
    )

    ax_map = fig.add_subplot(gs[1, 0])
    draw_row_c(ax_map)
    ax_map.set_title(
        "b  NIS-gated belief-mode map",
        loc="left",
        fontsize=8.2,
        fontweight="bold",
        pad=6,
    )

    ax_trace = fig.add_subplot(gs[1, 1])
    draw_row_d(ax_trace)
    ax_trace.set_title(
        "c  Mode/action trace exposed to control",
        loc="left",
        fontsize=8.2,
        fontweight="bold",
        pad=6,
    )

    fig.subplots_adjust(left=0.075, right=0.985, top=0.955, bottom=0.105)
    for suffix, kwargs in {
        ".pdf": {},
        ".svg": {},
        ".png": {"dpi": 600},
        ".tiff": {"dpi": 600},
    }.items():
        fig.savefig(str(save_base) + suffix, bbox_inches="tight", **kwargs)
    plt.close(fig)


if __name__ == "__main__":
    out_dir = (
        Path(__file__).resolve().parents[1]
        / "10_TASE_submission_20260610"
        / "01_manuscript"
        / "paper_picture"
    )
    build_figure(out_dir / "fig_tase_pop_nis_belief_interface")
