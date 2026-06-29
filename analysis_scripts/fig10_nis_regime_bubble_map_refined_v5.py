#!/usr/bin/env python3
"""Figure 10 refined: NIS diagnostic regime bubble map."""

from __future__ import annotations

from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from qgip_figure_style import TOP_CONF_COLORS as TOP, apply_top_conference_style


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
BASE = "fig10_nis_regime_bubble_map_refined_v5"

apply_top_conference_style()
plt.rcParams.update(
    {
        "font.size": 7.0,
        "axes.labelsize": 7.0,
        "xtick.labelsize": 6.2,
        "ytick.labelsize": 6.2,
        "legend.fontsize": 5.9,
        "axes.linewidth": 0.72,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    }
)

COLORS = {
    "noise": TOP["blue"],
    "outlier": TOP["brick"],
    "combined": TOP["violet"],
    "grid": TOP["grid"],
    "text": TOP["ink"],
    "muted": TOP["gray"],
    "calibrated": TOP["teal_light"],
    "soft": "#FBF4E8",
    "hard": TOP["brick_light"],
}

LABELS = {
    "noise_02": "noise 0.2 m",
    "noise_05": "noise 0.5 m",
    "noise_10": "noise 1.0 m",
    "fp_10": "adjacent FP",
    "idswitch_20": "ID switch",
    "fp10_idswitch20_noise05": "combined outlier",
}

ORDER = {
    "noise_02": 0,
    "noise_05": 1,
    "noise_10": 2,
    "idswitch_20": 3,
    "fp_10": 4,
    "fp10_idswitch20_noise05": 5,
}


def read_inputs() -> pd.DataFrame:
    noise = pd.read_csv(SOURCE / "carla_nis_noise_sweep_qgip100_summary.csv")
    outlier = pd.read_csv(SOURCE / "carla_nis_outlier_qgip100_summary.csv")
    noise["family"] = "Gaussian noise"
    outlier["family"] = "outlier perturbation"
    df = pd.concat([noise, outlier], ignore_index=True)
    df = df[df["condition_id"].isin(ORDER)].copy()
    df["_order"] = df["condition_id"].map(ORDER)
    df["label"] = df["condition_id"].map(LABELS)
    df["x_nis_p95"] = df["nisp95_mean"].astype(float)
    df["x_nis_p95_episode_p95"] = df["nisp95_p95"].astype(float)
    df["y_hard_gate_or_reset"] = np.maximum(
        df["nishardviolations_mean"].astype(float),
        df["kfhardresets_mean"].astype(float),
    )
    df["hard_gate_or_reset_episode_p95"] = np.maximum(
        df["nishardviolations_p95"].astype(float),
        df["kfhardresets_p95"].astype(float),
    )
    df["mean_nis"] = df["nismean_mean"].astype(float)
    df["marker_area"] = 38.0 + 58.0 * np.log10(df["mean_nis"].clip(lower=0.02) + 1.0)
    df["marker_color"] = np.where(
        df["condition_id"].eq("fp10_idswitch20_noise05"),
        COLORS["combined"],
        np.where(df["family"].eq("Gaussian noise"), COLORS["noise"], COLORS["outlier"]),
    )
    return df.sort_values("_order").reset_index(drop=True)


def add_halo(artist, lw: float = 1.6) -> None:
    artist.set_path_effects([pe.Stroke(linewidth=lw, foreground="white"), pe.Normal()])


def draw_regime_map(ax, df: pd.DataFrame) -> None:
    ax.set_title("NIS diagnostic regime map", loc="left", fontsize=8.0, fontweight="bold", pad=5)
    ax.set_xscale("log")
    ax.set_xlim(0.9, 12000)
    ax.set_ylim(-4.5, 92)
    ax.set_xlabel("episode-level NIS p95")
    ax.set_ylabel("hard-gate / reset events per episode")
    ax.set_xticks([1, 3, 10, 30, 100, 300, 1000, 3000, 10000])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.set_yticks([0, 20, 40, 60, 80])
    ax.grid(True, color=COLORS["grid"], lw=0.42, zorder=-5)

    ax.axvspan(0.9, 12, color=COLORS["calibrated"], zorder=-10)
    ax.axvspan(12, 20, color=COLORS["soft"], zorder=-10)
    ax.axvspan(20, 12000, color=COLORS["hard"], alpha=0.72, zorder=-10)
    ax.axvline(12, color=TOP["copper"], lw=0.75, ls="--", zorder=0)
    ax.axvline(20, color=TOP["brick"], lw=0.80, ls=":", zorder=0)
    ax.text(1.1, 88.5, "calibrated", fontsize=5.55, color=TOP["teal_dark"], ha="left", va="top")
    ax.text(12.4, 88.5, "soft", fontsize=5.55, color=TOP["copper_dark"], ha="left", va="top")
    ax.text(24, 88.5, "high-NIS reset regime", fontsize=5.55, color=COLORS["outlier"], ha="left", va="top")

    for _, row in df.iterrows():
        ax.scatter(
            row["x_nis_p95"],
            row["y_hard_gate_or_reset"],
            s=row["marker_area"],
            facecolor=row["marker_color"],
            edgecolor=TOP["ink"],
            linewidth=0.42,
            alpha=0.95,
            zorder=4,
        )

    label_pos = {
        "noise_02": (1.15, 7.0, "left"),
        "noise_05": (3.0, 7.0, "center"),
        "noise_10": (14.0, 8.5, "left"),
        "idswitch_20": (680, 17.0, "right"),
        "fp_10": (2050, 88.0, "left"),
        "fp10_idswitch20_noise05": (900, 78.0, "right"),
    }
    for _, row in df.iterrows():
        x_text, y_text, ha = label_pos[row["condition_id"]]
        line = ax.plot(
            [row["x_nis_p95"], x_text],
            [row["y_hard_gate_or_reset"], y_text],
            color=TOP["gray_mid"],
            lw=0.52,
            zorder=2,
        )[0]
        add_halo(line, 1.05)
        ax.text(
            x_text,
            y_text,
            row["label"],
            fontsize=5.65,
            color=row["marker_color"],
            ha=ha,
            va="center",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.88, "pad": 0.12},
            zorder=6,
        )

    handles = [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["noise"],
               markeredgecolor=TOP["ink"], markeredgewidth=0.42, markersize=4.8, label="Gaussian noise"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["outlier"],
               markeredgecolor=TOP["ink"], markeredgewidth=0.42, markersize=4.8, label="outlier"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=COLORS["combined"],
               markeredgecolor=TOP["ink"], markeredgewidth=0.42, markersize=4.8, label="combined"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=0.94,
              edgecolor=TOP["gray_light"], borderpad=0.35, handletextpad=0.35)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="both", length=2.3, width=0.55)


def write_source_data(df: pd.DataFrame, save_base: str) -> None:
    base = Path(save_base)
    out_dirs = [SOURCE] if SOURCE.exists() else [base.parent]
    source_cols = [
        "condition_id",
        "family",
        "label",
        "x_nis_p95",
        "x_nis_p95_episode_p95",
        "y_hard_gate_or_reset",
        "hard_gate_or_reset_episode_p95",
        "mean_nis",
        "marker_area",
    ]
    for out_dir in out_dirs:
        df[source_cols].to_csv(out_dir / f"{base.name}_source_data.csv", index=False)


def build_figure(save_base: str = BASE):
    df = read_inputs()
    fig, ax = plt.subplots(figsize=(7.15, 3.05), dpi=300)
    draw_regime_map(ax, df)
    fig.subplots_adjust(left=0.080, right=0.985, top=0.91, bottom=0.17)
    for suffix in (".pdf", ".svg", ".png", ".tiff"):
        kwargs = {"bbox_inches": "tight"}
        if suffix in (".png", ".tiff"):
            kwargs["dpi"] = 600
        fig.savefig(f"{save_base}{suffix}", **kwargs)
    write_source_data(df, save_base)
    return fig


if __name__ == "__main__":
    build_figure(BASE)
