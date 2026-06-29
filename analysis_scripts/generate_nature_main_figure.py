#!/usr/bin/env python3
"""Generate a Nature-style system/evidence composite main figure."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "RA_L_optimization_20260528"
OUT = WORK / "08_paper_ready_outputs"
SRC = OUT / "source_data"
FIGS = OUT / "figures"
MANUSCRIPT_FIGS = WORK / "01_manuscript" / "paper_picture"


def mm(value: float) -> float:
    return value / 25.4


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def row_by(rows: list[dict[str, str]], **keys: str) -> dict[str, str]:
    for row in rows:
        if all(row.get(key) == value for key, value in keys.items()):
            return row
    raise KeyError(f"missing row {keys}")


def build_source_rows(
    stress: list[dict[str, str]],
    nis_noise: list[dict[str, str]],
    nis_outlier: list[dict[str, str]],
) -> list[dict[str, str]]:
    source_rows: list[dict[str, str]] = []
    leader_specs = [
        ("fp_10", "rule", "Rule"),
        ("fp_10", "qgip_no_query", "No query"),
        ("fp_10", "qgip", "QGIP-Net"),
        ("idswitch", "rule", "Rule"),
        ("idswitch", "std_kf", "Std KF"),
        ("idswitch", "qgip", "QGIP-Net"),
    ]
    for condition, method, display in leader_specs:
        row = row_by(stress, condition_id=condition, method=method)
        source_rows.append(
            {
                "panel": "b",
                "condition_id": condition,
                "display_condition": "FP10" if condition == "fp_10" else "ID switch",
                "method": method,
                "display_method": display,
                "metric": "LeaderAcc",
                "value": row["leaderacc_mean"],
                "unit": "fraction",
                "source_file": "stress_summary_combined.csv",
            }
        )

    noise_specs = [
        ("noise_02", "0.2 m noise", nis_noise),
        ("noise_05", "0.5 m noise", nis_noise),
        ("noise_10", "1.0 m noise", nis_noise),
        ("fp_10", "FP10 outlier", nis_outlier),
        ("idswitch_20", "ID20 outlier", nis_outlier),
        ("fp10_idswitch20_noise05", "FP+ID+N", nis_outlier),
    ]
    for condition, label, rows in noise_specs:
        row = row_by(rows, condition_id=condition)
        source_rows.append(
            {
                "panel": "c",
                "condition_id": condition,
                "display_condition": label,
                "method": row.get("method", "qgip"),
                "display_method": "QGIP-Net",
                "metric": "NIS p95",
                "value": row["nisp95_mean"],
                "unit": "dimensionless",
                "source_file": "carla_nis_noise_sweep_qgip100_summary.csv"
                if condition.startswith("noise_")
                else "carla_nis_outlier_qgip100_summary.csv",
            }
        )
    return source_rows


def save_figure(fig, name: str) -> None:
    for directory in (FIGS, MANUSCRIPT_FIGS):
        directory.mkdir(parents=True, exist_ok=True)
    for suffix in (".pdf", ".svg", ".tiff", ".png"):
        path = FIGS / f"{name}{suffix}"
        if suffix == ".png":
            fig.savefig(path, dpi=300)
        elif suffix == ".tiff":
            fig.savefig(path, dpi=600)
        else:
            fig.savefig(path)
        (MANUSCRIPT_FIGS / f"{name}{suffix}").write_bytes(path.read_bytes())


def draw_box(ax, xy, width, height, title, subtitle="", face="#f7f8f9", edge="#4a5562"):
    import matplotlib.patches as patches

    x, y = xy
    box = patches.FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.012",
        linewidth=0.7,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(box)
    ax.text(x + width / 2, y + height * 0.62, title, ha="center", va="center", fontsize=6.2, fontweight="bold")
    if subtitle:
        ax.text(x + width / 2, y + height * 0.31, subtitle, ha="center", va="center", fontsize=5.1, color="#334155")


def arrow(ax, start, end, color="#59616d"):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops=dict(arrowstyle="-|>", lw=0.7, color=color, shrinkA=2, shrinkB=2, mutation_scale=8),
    )


def draw_system_panel(ax) -> None:
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.0, 1.02, "a", fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax.text(0.055, 1.02, "Target-belief-to-control contract", fontsize=7, fontweight="bold", ha="left", va="bottom")

    xs = [0.03, 0.235, 0.44, 0.645, 0.85]
    titles = [
        ("Scene graph", "objects + ego intent"),
        ("Query-guided selector", "task-relevant leader"),
        ("POP belief", "NIS-gated KF state"),
        ("MPC safety filter", "collision-feasible candidates"),
        ("Closed-loop action", "track / slow / stop"),
    ]
    colors = ["#f4f6f8", "#eef4fb", "#eef7f1", "#fff7e6", "#f4f6f8"]
    for x, (title, subtitle), color in zip(xs, titles, colors):
        draw_box(ax, (x, 0.48), 0.13, 0.26, title, subtitle, face=color)
    for x0, x1 in zip(xs[:-1], xs[1:]):
        arrow(ax, (x0 + 0.13, 0.61), (x1, 0.61))

    ax.text(0.303, 0.72, "identity + confidence", fontsize=5, color="#475569", ha="center")
    ax.text(0.515, 0.72, "state + covariance", fontsize=5, color="#475569", ha="center")
    ax.text(0.727, 0.72, "safe trajectory set", fontsize=5, color="#475569", ha="center")

    mode_x = [0.39, 0.50, 0.61]
    mode_labels = [("Reliable", "update"), ("Degraded", "inflate R"), ("Out-of-ODD", "fail-safe")]
    mode_colors = ["#dfeee4", "#fff0c9", "#f1d4d4"]
    for x, (title, subtitle), color in zip(mode_x, mode_labels, mode_colors):
        draw_box(ax, (x, 0.16), 0.092, 0.17, title, subtitle, face=color, edge="#64748b")
    ax.text(0.51, 0.37, "NIS gate partitions tracking mode", fontsize=5.5, ha="center", color="#334155")
    arrow(ax, (0.505, 0.48), (0.505, 0.34), color="#64748b")
    arrow(ax, (0.655, 0.245), (0.725, 0.48), color="#9b5f5f")
    ax.text(0.69, 0.315, "persistent uncertainty", fontsize=5, color="#7f4f4f", rotation=32)


def draw_leader_panel(ax, source_rows: list[dict[str, str]]) -> None:
    import numpy as np

    ax.text(-0.12, 1.06, "b", transform=ax.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax.set_title("Ambiguity exposes target-selection gains", fontsize=7, pad=3)
    rows = [row for row in source_rows if row["panel"] == "b"]
    groups = ["FP10", "ID switch"]
    method_order = {
        "FP10": ["Rule", "No query", "QGIP-Net"],
        "ID switch": ["Rule", "Std KF", "QGIP-Net"],
    }
    colors = {"Rule": "#8b8b8b", "No query": "#d59a26", "Std KF": "#6b8fbf", "QGIP-Net": "#2c8b63"}
    x_centers = np.arange(len(groups))
    width = 0.18
    offsets = [-width, 0, width]
    for group_idx, group in enumerate(groups):
        for offset, method in zip(offsets, method_order[group]):
            row = next(item for item in rows if item["display_condition"] == group and item["display_method"] == method)
            ax.bar(
                x_centers[group_idx] + offset,
                100 * float(row["value"]),
                width=width * 0.9,
                color=colors[method],
                edgecolor="black",
                linewidth=0.25,
                label=method if group_idx == 0 or method == "Std KF" else None,
            )
    ax.set_ylabel("LeaderAcc (%)")
    ax.set_ylim(0, 105)
    ax.set_xticks(x_centers)
    ax.set_xticklabels(groups)
    ax.legend(ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.2), frameon=False, handlelength=1.2)
    ax.spines[["top", "right"]].set_visible(False)


def draw_nis_panel(ax, source_rows: list[dict[str, str]]) -> None:
    rows = [row for row in source_rows if row["panel"] == "c"]
    ax.text(-0.12, 1.06, "c", transform=ax.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax.set_title("NIS exposes detector degradation", fontsize=7, pad=3)
    labels = [row["display_condition"] for row in rows]
    values = [float(row["value"]) for row in rows]
    colors = ["#7fb097", "#7fb097", "#7fb097", "#8aa6c8", "#8aa6c8", "#8aa6c8"]
    ax.bar(range(len(rows)), values, color=colors, edgecolor="black", linewidth=0.25)
    ax.set_yscale("log")
    ax.set_ylabel("Episode NIS p95 (log)")
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels(labels, rotation=28, ha="right")
    ax.axvline(2.5, color="#64748b", linestyle=":", linewidth=0.7)
    ax.text(1.0, 2.2e3, "noise", ha="center", fontsize=5.3, color="#475569")
    ax.text(4.0, 2.2e3, "outliers", ha="center", fontsize=5.3, color="#475569")
    ax.spines[["top", "right"]].set_visible(False)


def main() -> None:
    import matplotlib.pyplot as plt
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 6,
            "axes.labelsize": 6,
            "xtick.labelsize": 5.5,
            "ytick.labelsize": 5.5,
            "legend.fontsize": 5.3,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.5,
            "ytick.major.width": 0.5,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )

    stress = read_csv(SRC / "stress_summary_combined.csv")
    nis_noise = read_csv(SRC / "carla_nis_noise_sweep_qgip100_summary.csv")
    nis_outlier = read_csv(SRC / "carla_nis_outlier_qgip100_summary.csv")
    source_rows = build_source_rows(stress, nis_noise, nis_outlier)
    write_csv(SRC / "fig_nature_system_evidence_source.csv", source_rows)

    fig = plt.figure(figsize=(mm(183), mm(128)))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.08, 1.0], hspace=0.42, wspace=0.34)
    ax_system = fig.add_subplot(grid[0, :])
    ax_leader = fig.add_subplot(grid[1, 0])
    ax_nis = fig.add_subplot(grid[1, 1])
    draw_system_panel(ax_system)
    draw_leader_panel(ax_leader, source_rows)
    draw_nis_panel(ax_nis, source_rows)
    fig.subplots_adjust(left=0.055, right=0.985, top=0.95, bottom=0.17)
    save_figure(fig, "fig_nature_system_evidence")
    plt.close(fig)
    print(f"Wrote {FIGS / 'fig_nature_system_evidence.pdf'}")


if __name__ == "__main__":
    main()

