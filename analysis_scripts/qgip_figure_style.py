"""Shared publication figure style for the QGIP manuscript.

The palette is intentionally restrained: low-saturation, colorblind-conscious,
and semantically stable across all manuscript figures.
"""

from __future__ import annotations

import matplotlib as mpl


TOP_CONF_COLORS = {
    "blue": "#2F5E8E",
    "blue_mid": "#7FA4C3",
    "blue_light": "#DCE8F2",
    "blue_bg": "#F3F7FB",
    "teal": "#4C9A78",
    "teal_dark": "#2F755D",
    "teal_light": "#E8F3EE",
    "copper": "#B88A3A",
    "copper_dark": "#866425",
    "copper_light": "#F6E9CF",
    "brick": "#B45A4E",
    "brick_dark": "#884137",
    "brick_light": "#F4E4E2",
    "violet": "#7567A7",
    "violet_light": "#ECE8F5",
    "ink": "#1F2933",
    "charcoal": "#3E4A56",
    "gray": "#68727D",
    "gray_mid": "#AEB7C2",
    "gray_light": "#E7EBF0",
    "panel": "#F7F9FC",
    "paper": "#FFFFFF",
    "grid": "#E2E7EE",
}


TOP_CONF_RCPARAMS = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "sans-serif"],
    "mathtext.fontset": "dejavusans",
    "font.size": 6.8,
    "axes.labelsize": 6.8,
    "axes.titlesize": 8.0,
    "xtick.labelsize": 6.0,
    "ytick.labelsize": 6.0,
    "legend.fontsize": 5.8,
    "axes.linewidth": 0.72,
    "xtick.major.width": 0.55,
    "ytick.major.width": 0.55,
    "xtick.major.size": 2.3,
    "ytick.major.size": 2.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
}


def apply_top_conference_style() -> None:
    mpl.rcParams.update(TOP_CONF_RCPARAMS)
