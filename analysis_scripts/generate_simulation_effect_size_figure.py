#!/usr/bin/env python3
"""Generate a Nature-style simulation effect-size and boundary figure.

The figure condenses the quantitative simulation story into one reviewer-facing
visual: route-level benchmark outcomes, paired target-consistency effect sizes,
wrong-leader-frame reductions, and the finite-sample boundary around zero
observed collisions.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
FIGS = ROOT / "08_paper_ready_outputs" / "figures"
MANUSCRIPT_FIGS = ROOT / "01_manuscript" / "paper_picture"

MAIN = SOURCE / "main_benchmark_source.csv"
PAIRWISE = SOURCE / "pairwise_stats_combined.csv"
STRESS = SOURCE / "extended_stress_qgip_summary.csv"

OUT_SOURCE = SOURCE / "fig_simulation_effect_size_source.csv"
FIGURE_ID = "fig_simulation_effect_size"


mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 6,
        "axes.labelsize": 6,
        "xtick.labelsize": 5.5,
        "ytick.labelsize": 5.5,
        "legend.fontsize": 5.5,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.5,
        "ytick.major.width": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    }
)


METHOD_ORDER = [
    "E2E Baseline (No MPC)",
    "Modular PID",
    "Rule-Based + MPC",
    "Std KF + MPC",
    "QGIP-Net (Ours)",
]

METHOD_LABELS = {
    "E2E Baseline (No MPC)": "E2E\n(no MPC)",
    "Modular PID": "Modular\nPID",
    "Rule-Based + MPC": "Rule\n+ MPC",
    "Std KF + MPC": "Std KF\n+ MPC",
    "QGIP-Net (Ours)": "QGIP-Net",
}

COMPARISONS = [
    ("fp_10", "qgip_no_query", "FP10 vs\nno query"),
    ("fp_10", "rule", "FP10 vs\nrule"),
    ("idswitch", "std_kf", "ID switch vs\nStd KF"),
    ("idswitch", "rule", "ID switch vs\nrule"),
    ("fp20_idswitch20", "qgip_no_query", "Boundary vs\nno query"),
    ("fp20_idswitch20", "rule", "Boundary vs\nrule"),
]

STRESS_LABELS = {
    "fp_10": "FP10",
    "idswitch": "ID switch",
    "fn_50": "FN50",
    "delay_200": "Delay200",
    "raw_glare": "Raw glare",
    "raw_lidar_dropout": "LiDAR drop",
    "fp20_idswitch20": "Boundary",
}

COLORS = {
    "success": "#5AAE93",
    "lost": "#BFC7CD",
    "collision": "#B56B5F",
    "qgip": "#2166AC",
    "ci": "#29323A",
    "boundary": "#7A7F86",
}


def mm(value: float) -> float:
    return value / 25.4


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def row_by(rows: list[dict[str, str]], **keys: str) -> dict[str, str]:
    for row in rows:
        if all(row.get(key) == value for key, value in keys.items()):
            return row
    raise KeyError(f"missing row {keys}")


def pct(value: float) -> float:
    return 100.0 * value


def panel_label(ax: plt.Axes, label: str, title: str) -> None:
    ax.text(-0.08, 1.04, label, transform=ax.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax.text(0.0, 1.04, title, transform=ax.transAxes, fontsize=7, fontweight="bold", ha="left", va="bottom")


def build_source_rows() -> list[dict[str, str]]:
    main = read_csv(MAIN)
    pairwise = read_csv(PAIRWISE)
    stress = read_csv(STRESS)
    rows: list[dict[str, str]] = []

    for item in sorted(main, key=lambda row: METHOD_ORDER.index(row["method"])):
        for metric, low_key, high_key in (
            ("success_rate", "success_ci_low", "success_ci_high"),
            ("lost_rate", "", ""),
            ("collision_rate", "", ""),
        ):
            rows.append(
                {
                    "panel": "a_main_benchmark_outcomes",
                    "evidence_id": f"{item['method']}::{metric}",
                    "condition_id": "main300_blackout",
                    "condition_label": "Main N=300 blackout benchmark",
                    "method": item["method"],
                    "comparison_method": "",
                    "metric": metric,
                    "value": item[metric],
                    "ci_low": item.get(low_key, "") if low_key else "",
                    "ci_high": item.get(high_key, "") if high_key else "",
                    "n": item["n"],
                    "source_file": MAIN.name,
                    "interpretation": "Route-level benchmark outcome; collision and Lost must be read separately.",
                    "boundary": "Benchmark is simulation-first and does not imply real-world safety.",
                }
            )

    for condition_id, comparison, label in COMPARISONS:
        item = row_by(pairwise, condition_id=condition_id, reference_method="qgip", comparison_method=comparison)
        rows.append(
            {
                "panel": "b_leaderacc_effect_size",
                "evidence_id": f"{condition_id}::leaderacc::{comparison}",
                "condition_id": condition_id,
                "condition_label": label.replace("\n", " "),
                "method": "qgip",
                "comparison_method": comparison,
                "metric": "leaderacc_diff_ref_minus_cmp",
                "value": item["leaderacc_diff_ref_minus_cmp"],
                "ci_low": item["leaderacc_diff_ci95_low"],
                "ci_high": item["leaderacc_diff_ci95_high"],
                "n": item["leaderacc_paired_n"],
                "source_file": PAIRWISE.name,
                "interpretation": "Positive values mean QGIP-Net has higher LeaderAcc in the paired comparison.",
                "boundary": "Effect size supports target consistency, not universal route-completion superiority.",
            }
        )
        rows.append(
            {
                "panel": "c_wrongleader_reduction",
                "evidence_id": f"{condition_id}::wrongleaderframes::{comparison}",
                "condition_id": condition_id,
                "condition_label": label.replace("\n", " "),
                "method": "qgip",
                "comparison_method": comparison,
                "metric": "wrongleaderframes_reduction_cmp_minus_ref",
                "value": str(-float(item["wrongleaderframes_diff_ref_minus_cmp"])),
                "ci_low": str(-float(item["wrongleaderframes_diff_ci95_high"])),
                "ci_high": str(-float(item["wrongleaderframes_diff_ci95_low"])),
                "n": item["wrongleaderframes_paired_n"],
                "source_file": PAIRWISE.name,
                "interpretation": "Positive values mean fewer wrong-leader frames for QGIP-Net.",
                "boundary": "Frame-count reduction is a target-consistency metric, not a direct collision-risk proof.",
            }
        )

    for item in stress:
        condition_id = item["condition_id"]
        label = item["label"]
        n = float(item["n"])
        for metric, value in (
            ("success_rate", item["success_rate"]),
            ("lost_rate", item["lost_rate"]),
            ("observed_collision_rate", item["collision_rate"]),
            ("rule_of_three_collision_upper", str(3.0 / n)),
        ):
            rows.append(
                {
                    "panel": "d_finite_sample_boundary",
                    "evidence_id": f"{condition_id}::{metric}",
                    "condition_id": condition_id,
                    "condition_label": label,
                    "method": "qgip",
                    "comparison_method": "",
                    "metric": metric,
                    "value": value,
                    "ci_low": "",
                    "ci_high": "",
                    "n": item["n"],
                    "source_file": STRESS.name,
                    "interpretation": "Zero observed collision is paired with a finite-sample upper bound and Lost trade-off.",
                    "boundary": "Rule-of-three bound is not a real-world safety guarantee.",
                }
            )

    return rows


def write_source(rows: list[dict[str, str]]) -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    with OUT_SOURCE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def draw_main_outcomes(ax: plt.Axes, rows: list[dict[str, str]]) -> None:
    panel = [row for row in rows if row["panel"] == "a_main_benchmark_outcomes"]
    by_method: dict[str, dict[str, float]] = {}
    for row in panel:
        by_method.setdefault(row["method"], {})[row["metric"]] = pct(float(row["value"]))

    y = np.arange(len(METHOD_ORDER))
    success = np.array([by_method[method]["success_rate"] for method in METHOD_ORDER])
    lost = np.array([by_method[method]["lost_rate"] for method in METHOD_ORDER])
    collision = np.array([by_method[method]["collision_rate"] for method in METHOD_ORDER])
    ax.barh(y, success, color=COLORS["success"], height=0.58, label="Success")
    ax.barh(y, lost, left=success, color=COLORS["lost"], height=0.58, label="Lost")
    ax.barh(y, collision, left=success + lost, color=COLORS["collision"], height=0.58, label="Collision")
    ax.set_yticks(y)
    ax.set_yticklabels([METHOD_LABELS[method] for method in METHOD_ORDER])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("episode outcome (%)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.55, -0.16), ncol=3, handlelength=1.0, columnspacing=0.8)
    panel_label(ax, "a", "Main benchmark separates success from collision")


def draw_forest(
    ax: plt.Axes,
    rows: list[dict[str, str]],
    panel_name: str,
    title: str,
    xlabel: str,
    scale: float,
    marker_color: str,
) -> None:
    panel = [row for row in rows if row["panel"] == panel_name]
    y = np.arange(len(panel))
    values = np.array([float(row["value"]) * scale for row in panel])
    low = np.array([float(row["ci_low"]) * scale for row in panel])
    high = np.array([float(row["ci_high"]) * scale for row in panel])
    labels = [row["condition_label"] for row in panel]
    ax.axvline(0, color="#8A8F93", lw=0.7)
    for idx, (value, lo, hi) in enumerate(zip(values, low, high)):
        ax.plot([lo, hi], [idx, idx], color=COLORS["ci"], lw=1.1)
        ax.plot(value, idx, "o", color=marker_color, ms=3.5)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    right_pad = max(high) * 0.12 if len(high) else 1.0
    ax.set_xlim(min(0, min(low) - right_pad), max(high) + right_pad)
    panel_label(ax, "b" if panel_name.startswith("b_") else "c", title)


def draw_boundary(ax: plt.Axes, rows: list[dict[str, str]]) -> None:
    panel = [row for row in rows if row["panel"] == "d_finite_sample_boundary"]
    by_condition: dict[str, dict[str, str]] = {}
    for row in panel:
        by_condition.setdefault(row["condition_id"], {"label": row["condition_label"], "n": row["n"]})[row["metric"]] = row["value"]

    condition_ids = [row["condition_id"] for row in read_csv(STRESS)]
    x = np.arange(len(condition_ids))
    lost = np.array([pct(float(by_condition[condition]["lost_rate"])) for condition in condition_ids])
    rule3 = np.array([pct(float(by_condition[condition]["rule_of_three_collision_upper"])) for condition in condition_ids])
    observed = np.array([pct(float(by_condition[condition]["observed_collision_rate"])) for condition in condition_ids])
    ax.bar(x, lost, color=COLORS["lost"], width=0.62, label="Lost")
    ax.plot(x, rule3, "o-", color=COLORS["boundary"], lw=1.0, ms=3.0, label="Rule-of-three upper")
    ax.plot(x, observed, "_", color=COLORS["collision"], ms=8.0, mew=1.2, label="Observed collision")
    ax.set_xticks(x)
    ax.set_xticklabels([STRESS_LABELS.get(condition, condition) for condition in condition_ids], rotation=28, ha="right")
    ax.set_ylabel("rate (%)")
    ax.set_ylim(0, max(32, lost.max() + 5))
    ax.legend(loc="upper right", handlelength=1.6)
    panel_label(ax, "d", "Zero observed collision remains finite-sample evidence")


def draw_figure(rows: list[dict[str, str]]) -> plt.Figure:
    fig = plt.figure(figsize=(mm(183), mm(150)), constrained_layout=False)
    grid = fig.add_gridspec(2, 2, left=0.08, right=0.98, top=0.94, bottom=0.10, wspace=0.36, hspace=0.42)
    ax_a = fig.add_subplot(grid[0, 0])
    ax_b = fig.add_subplot(grid[0, 1])
    ax_c = fig.add_subplot(grid[1, 0])
    ax_d = fig.add_subplot(grid[1, 1])

    draw_main_outcomes(ax_a, rows)
    draw_forest(
        ax_b,
        rows,
        "b_leaderacc_effect_size",
        "Paired LeaderAcc effect size",
        "LeaderAcc gain (percentage points)",
        100.0,
        COLORS["qgip"],
    )
    draw_forest(
        ax_c,
        rows,
        "c_wrongleader_reduction",
        "Wrong-leader exposure reduction",
        "fewer wrong-leader frames per episode",
        1.0,
        "#4C78A8",
    )
    draw_boundary(ax_d, rows)

    for ax in (ax_a, ax_b, ax_c, ax_d):
        ax.tick_params(length=2.5, width=0.5)
        ax.grid(axis="x", color="#E6E8EA", lw=0.45)
        ax.set_axisbelow(True)

    fig.text(
        0.08,
        0.018,
        "Source data: main_benchmark_source.csv, pairwise_stats_combined.csv, and extended_stress_qgip_summary.csv. "
        "All panels are processed CARLA simulation evidence; physical-robot and live ROS2 validation remain outside this figure.",
        fontsize=5.5,
        ha="left",
        va="bottom",
    )
    return fig


def export(fig: plt.Figure) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_FIGS.mkdir(parents=True, exist_ok=True)
    base = FIGS / FIGURE_ID
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
    fig.savefig(base.with_suffix(".png"), dpi=220, bbox_inches="tight")
    plt.close(fig)

    for suffix in (".pdf", ".svg", ".tiff", ".png"):
        shutil.copy2(base.with_suffix(suffix), MANUSCRIPT_FIGS / f"{FIGURE_ID}{suffix}")


def main() -> None:
    rows = build_source_rows()
    write_source(rows)
    fig = draw_figure(rows)
    export(fig)
    print(OUT_SOURCE)
    for suffix in (".pdf", ".svg", ".tiff", ".png"):
        print(FIGS / f"{FIGURE_ID}{suffix}")


if __name__ == "__main__":
    main()
