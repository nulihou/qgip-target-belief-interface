#!/usr/bin/env python3
"""Generate a Nature-style simulation stress atlas figure.

The atlas is a reader-facing synthesis of the completed simulation evidence:
stress-layer scale, QGIP-Net outcome envelope, primary ambiguity effect sizes,
and POP/NIS diagnostic response. It reuses processed source data only and does
not add new simulation or physical-robot evidence.
"""

from __future__ import annotations

import csv
import shutil
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "08_paper_ready_outputs" / "source_data"
FIGS = ROOT / "08_paper_ready_outputs" / "figures"
MANUSCRIPT_FIGS = ROOT / "01_manuscript" / "paper_picture"

MAIN = SOURCE / "main_benchmark_source.csv"
NOMINAL = SOURCE / "main1000_nominal_source.csv"
STRESS = SOURCE / "stress_summary_combined.csv"
QGIP_STRESS = SOURCE / "extended_stress_qgip_summary.csv"
PAIRWISE = SOURCE / "pairwise_stats_combined.csv"
NIS_NOISE = SOURCE / "carla_nis_noise_sweep_qgip100_summary.csv"
NIS_OUTLIER = SOURCE / "carla_nis_outlier_qgip100_summary.csv"

OUT_SOURCE = SOURCE / "fig_simulation_stress_atlas_source.csv"
FIGURE_ID = "fig_simulation_stress_atlas"


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


LAYER_ORDER = [
    ("nominal", "Nominal\nsanity"),
    ("main_blackout", "Main\nblackout"),
    ("ambiguity", "Primary\nambiguity"),
    ("detector_timing", "Detector /\ntiming"),
    ("raw_like", "Raw-like\nscreen"),
    ("boundary", "Boundary\nstress"),
    ("nis_diagnostic", "NIS\ndiagnostic"),
]

SUITE_TO_LAYER = {
    "ambiguity300": "ambiguity",
    "detector_timing300": "detector_timing",
    "raw_sensor_like": "raw_like",
    "boundary100": "boundary",
}

STRESS_LABELS = {
    "fp_10": "FP10",
    "idswitch": "ID switch",
    "fn_50": "FN50",
    "delay_200": "Delay200",
    "raw_glare": "Raw glare",
    "raw_lidar_dropout": "LiDAR drop",
    "fp20_idswitch20": "Boundary",
}

METRIC_COLUMNS = [
    ("success_rate", "Success\n%", 0.0, 1.0, "{:.0f}"),
    ("lost_rate", "Lost\n%", 0.0, 0.35, "{:.0f}"),
    ("leaderacc_mean", "LeaderAcc\n%", 0.75, 1.0, "{:.0f}"),
    ("idswitches_mean", "ID switches\n/ep", 0.0, 130.0, "{:.0f}"),
    ("rule3_upper", "Rule-of-3\nupper %", 0.0, 0.035, "{:.1f}"),
]

COMPARISONS = [
    ("fp_10", "qgip_no_query", "FP10\nno query"),
    ("fp_10", "rule", "FP10\nrule"),
    ("idswitch", "std_kf", "ID switch\nStd KF"),
    ("idswitch", "rule", "ID switch\nrule"),
]

NIS_LABELS = {
    "noise_02": "Noise\n0.2 m",
    "noise_05": "Noise\n0.5 m",
    "noise_10": "Noise\n1.0 m",
    "fp_10": "FP10\noutlier",
    "idswitch_20": "ID switch\n20",
    "fp10_idswitch20_noise05": "Combined\noutlier",
}

COLORS = {
    "nominal": "#BFD7EA",
    "main_blackout": "#D8C8A9",
    "ambiguity": "#5AAE93",
    "detector_timing": "#9BC3D5",
    "raw_like": "#C7B8D8",
    "boundary": "#D8A194",
    "nis_diagnostic": "#A7B3C2",
    "success": "#5AAE93",
    "lost": "#C8D0D5",
    "accent": "#2166AC",
    "dark": "#26323B",
    "soft": "#EEF3F1",
    "boundary": "#B56B5F",
}

HEAT = LinearSegmentedColormap.from_list("stress_atlas", ["#F7F7F7", "#DCEBE4", "#8EC7AD", "#377E63"])


def mm(value: float) -> float:
    return value / 25.4


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def f(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    return float(value)


def row_by(rows: list[dict[str, str]], **keys: str) -> dict[str, str]:
    for row in rows:
        if all(row.get(key) == value for key, value in keys.items()):
            return row
    raise KeyError(f"missing row {keys}")


def panel_label(ax: plt.Axes, label: str, title: str) -> None:
    ax.text(-0.08, 1.09, label, transform=ax.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax.text(0.0, 1.09, title, transform=ax.transAxes, fontsize=7, fontweight="bold", ha="left", va="bottom")


def evidence_layer_rows() -> list[dict[str, str]]:
    main = read_csv(MAIN)
    nominal = read_csv(NOMINAL)
    stress = read_csv(STRESS)
    noise = read_csv(NIS_NOISE)
    outlier = read_csv(NIS_OUTLIER)

    counts: dict[str, float] = defaultdict(float)
    counts["main_blackout"] = sum(f(row, "n") for row in main)
    counts["nominal"] = sum(f(row, "n") for row in nominal)
    for row in stress:
        counts[SUITE_TO_LAYER[row["suite"]]] += f(row, "n")
    counts["nis_diagnostic"] = sum(f(row, "n") for row in noise + outlier)

    source_files = {
        "nominal": NOMINAL.name,
        "main_blackout": MAIN.name,
        "ambiguity": STRESS.name,
        "detector_timing": STRESS.name,
        "raw_like": STRESS.name,
        "boundary": STRESS.name,
        "nis_diagnostic": f"{NIS_NOISE.name}; {NIS_OUTLIER.name}",
    }
    roles = {
        "nominal": "low-ambiguity sanity check",
        "main_blackout": "route-level benchmark continuity",
        "ambiguity": "primary target-consistency test",
        "detector_timing": "fault-layer coverage",
        "raw_like": "raw-sensor-like degradation screen",
        "boundary": "supplemental boundary stress",
        "nis_diagnostic": "uncertainty-monitor diagnostic response",
    }

    rows: list[dict[str, str]] = []
    for layer_id, label in LAYER_ORDER:
        rows.append(
            {
                "panel": "a_evidence_scale",
                "evidence_id": layer_id,
                "condition_id": layer_id,
                "condition_label": label.replace("\n", " "),
                "method": "multiple" if layer_id not in {"nis_diagnostic"} else "qgip",
                "comparison_method": "",
                "metric": "episode_method_rows",
                "value": f"{counts[layer_id]:.0f}",
                "ci_low": "",
                "ci_high": "",
                "n": f"{counts[layer_id]:.0f}",
                "source_file": source_files[layer_id],
                "interpretation": roles[layer_id],
                "boundary": "Counts summarize processed episode-method rows and do not add new simulations.",
            }
        )
    return rows


def qgip_stress_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in read_csv(QGIP_STRESS):
        n = f(item, "n")
        condition_id = item["condition_id"]
        label = item["label"]
        values = {
            "success_rate": f(item, "success_rate"),
            "lost_rate": f(item, "lost_rate"),
            "leaderacc_mean": f(item, "leaderacc_mean"),
            "idswitches_mean": f(item, "idswitches_mean"),
            "rule3_upper": 3.0 / n if n else 0.0,
        }
        for metric, value in values.items():
            rows.append(
                {
                    "panel": "b_qgip_stress_envelope",
                    "evidence_id": f"{condition_id}::{metric}",
                    "condition_id": condition_id,
                    "condition_label": label,
                    "method": "qgip",
                    "comparison_method": "",
                    "metric": metric,
                    "value": f"{value:.6g}",
                    "ci_low": "",
                    "ci_high": "",
                    "n": item["n"],
                    "source_file": QGIP_STRESS.name,
                    "interpretation": "QGIP-Net stress-outcome envelope across completed CARLA stress conditions.",
                    "boundary": "Stress envelope is simulation-only and should be read with finite-sample uncertainty.",
                }
            )
    return rows


def paired_effect_rows() -> list[dict[str, str]]:
    pairwise = read_csv(PAIRWISE)
    rows: list[dict[str, str]] = []
    for condition_id, comparison, label in COMPARISONS:
        item = row_by(pairwise, condition_id=condition_id, reference_method="qgip", comparison_method=comparison)
        metrics = (
            (
                "leaderacc_gain_pp",
                100.0 * f(item, "leaderacc_diff_ref_minus_cmp"),
                100.0 * f(item, "leaderacc_diff_ci95_low"),
                100.0 * f(item, "leaderacc_diff_ci95_high"),
                "Positive percentage points mean higher paired LeaderAcc for QGIP-Net.",
            ),
            (
                "wrongleaderframes_reduction",
                -f(item, "wrongleaderframes_diff_ref_minus_cmp"),
                -f(item, "wrongleaderframes_diff_ci95_high"),
                -f(item, "wrongleaderframes_diff_ci95_low"),
                "Positive frame counts mean fewer wrong-leader frames for QGIP-Net.",
            ),
        )
        for metric, value, ci_low, ci_high, interpretation in metrics:
            rows.append(
                {
                    "panel": "c_primary_ambiguity_effects",
                    "evidence_id": f"{condition_id}::{comparison}::{metric}",
                    "condition_id": condition_id,
                    "condition_label": label.replace("\n", " "),
                    "method": "qgip",
                    "comparison_method": comparison,
                    "metric": metric,
                    "value": f"{value:.6g}",
                    "ci_low": f"{ci_low:.6g}",
                    "ci_high": f"{ci_high:.6g}",
                    "n": item["leaderacc_paired_n"] if metric == "leaderacc_gain_pp" else item["wrongleaderframes_paired_n"],
                    "source_file": PAIRWISE.name,
                    "interpretation": interpretation,
                    "boundary": "Paired effects support target consistency under ambiguity, not universal route-completion superiority.",
                }
            )
    return rows


def nis_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_path, family in ((NIS_NOISE, "Gaussian position noise"), (NIS_OUTLIER, "outlier/ambiguity")):
        for item in read_csv(source_path):
            for metric in ("nisp95_mean", "nishardviolations_mean"):
                rows.append(
                    {
                        "panel": "d_nis_diagnostic_response",
                        "evidence_id": f"{item['condition_id']}::{metric}",
                        "condition_id": item["condition_id"],
                        "condition_label": NIS_LABELS.get(item["condition_id"], item["condition_id"]).replace("\n", " "),
                        "method": "qgip",
                        "comparison_method": "",
                        "metric": metric,
                        "value": f"{f(item, metric):.6g}",
                        "ci_low": "",
                        "ci_high": "",
                        "n": item["n"],
                        "source_file": source_path.name,
                        "interpretation": family,
                        "boundary": "NIS response is a simulation diagnostic, not final real-sensor covariance calibration.",
                    }
                )
    return rows


def build_source_rows() -> list[dict[str, str]]:
    return evidence_layer_rows() + qgip_stress_rows() + paired_effect_rows() + nis_rows()


def write_source(rows: list[dict[str, str]]) -> None:
    OUT_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_SOURCE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def draw_panel_a(ax: plt.Axes, rows: list[dict[str, str]]) -> None:
    panel_rows = [row for row in rows if row["panel"] == "a_evidence_scale"]
    y = np.arange(len(panel_rows))
    values = np.array([float(row["value"]) for row in panel_rows])
    colors = [COLORS[row["condition_id"]] for row in panel_rows]
    ax.barh(y, values, color=colors, edgecolor="#4B5563", linewidth=0.5, height=0.62)
    for yy, value in zip(y, values):
        ax.text(value + max(values) * 0.015, yy, f"{int(value):,}", va="center", ha="left", fontsize=5.5)
    ax.set_yticks(y, [row["condition_label"] for row in panel_rows])
    ax.invert_yaxis()
    ax.set_xlabel("processed episode-method rows")
    ax.set_xlim(0, max(values) * 1.18)
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.5)
    ax.set_axisbelow(True)
    panel_label(ax, "a", "Stress-layer scale")


def draw_panel_b(ax: plt.Axes, rows: list[dict[str, str]]) -> None:
    panel_rows = [row for row in rows if row["panel"] == "b_qgip_stress_envelope"]
    condition_ids = [row["condition_id"] for row in read_csv(QGIP_STRESS)]
    labels = [STRESS_LABELS.get(condition_id, condition_id) for condition_id in condition_ids]
    lookup = {(row["condition_id"], row["metric"]): float(row["value"]) for row in panel_rows}

    ax.set_xlim(0, len(METRIC_COLUMNS))
    ax.set_ylim(0, len(condition_ids))
    ax.invert_yaxis()
    ax.set_xticks(np.arange(len(METRIC_COLUMNS)) + 0.5, [col[1] for col in METRIC_COLUMNS])
    ax.xaxis.tick_top()
    ax.tick_params(axis="x", length=0, pad=2)
    ax.set_yticks(np.arange(len(condition_ids)) + 0.5, labels)
    ax.tick_params(axis="y", length=0)

    for i, condition_id in enumerate(condition_ids):
        for j, (metric, _, vmin, vmax, fmt) in enumerate(METRIC_COLUMNS):
            value = lookup[(condition_id, metric)]
            norm_value = Normalize(vmin=vmin, vmax=vmax, clip=True)(value)
            face = HEAT(norm_value)
            if metric in {"lost_rate", "idswitches_mean", "rule3_upper"}:
                face = LinearSegmentedColormap.from_list("risk", ["#F7F7F7", "#E7D4D0", "#BF7E73"])(norm_value)
            ax.add_patch(Rectangle((j, i), 1, 1, facecolor=face, edgecolor="#FFFFFF", linewidth=1.0))
            if metric in {"success_rate", "lost_rate", "leaderacc_mean", "rule3_upper"}:
                display_value = value * 100.0
            else:
                display_value = value
            ax.text(j + 0.5, i + 0.5, fmt.format(display_value), ha="center", va="center", fontsize=5.4, color="#111827")
    for spine in ax.spines.values():
        spine.set_visible(False)
    panel_label(ax, "b", "QGIP-Net stress envelope")


def draw_panel_c(ax: plt.Axes, rows: list[dict[str, str]]) -> None:
    panel_rows = [row for row in rows if row["panel"] == "c_primary_ambiguity_effects"]
    gain_rows = [row for row in panel_rows if row["metric"] == "leaderacc_gain_pp"]
    frame_rows = [row for row in panel_rows if row["metric"] == "wrongleaderframes_reduction"]
    y = np.arange(len(gain_rows))

    gains = np.array([float(row["value"]) for row in gain_rows])
    low = np.array([float(row["ci_low"]) for row in gain_rows])
    high = np.array([float(row["ci_high"]) for row in gain_rows])
    frames = np.array([float(row["value"]) for row in frame_rows])
    labels = [textwrap.fill(row["condition_label"], width=10) for row in gain_rows]

    ax.barh(y + 0.18, frames, height=0.28, color="#D8DEE4", edgecolor="#6B7280", linewidth=0.4, label="Wrong-leader frames reduced")
    ax.errorbar(gains, y - 0.18, xerr=[gains - low, high - gains], fmt="o", color=COLORS["accent"], ecolor="#27323A", elinewidth=0.8, capsize=2, markersize=4, label="LeaderAcc gain")
    ax.axvline(0, color="#9CA3AF", linewidth=0.6)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("percentage points or frames per episode")
    ax.set_xlim(0, max(frames.max() * 1.12, 240))
    ax.grid(axis="x", color="#E5E7EB", linewidth=0.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.58, -0.18), ncol=2, handlelength=1.4, borderaxespad=0.0)
    panel_label(ax, "c", "Primary ambiguity effects")


def draw_panel_d(ax: plt.Axes, rows: list[dict[str, str]]) -> None:
    panel_rows = [row for row in rows if row["panel"] == "d_nis_diagnostic_response"]
    p95_rows = [row for row in panel_rows if row["metric"] == "nisp95_mean"]
    reset_rows = [row for row in panel_rows if row["metric"] == "nishardviolations_mean"]
    reset_lookup = {row["condition_id"]: float(row["value"]) for row in reset_rows}
    x = np.arange(len(p95_rows))
    values = np.array([float(row["value"]) for row in p95_rows])
    resets = np.array([reset_lookup[row["condition_id"]] for row in p95_rows])
    colors = ["#7EA6C8" if "noise" in row["condition_id"] else "#C58B7F" for row in p95_rows]
    sizes = 18 + np.sqrt(np.maximum(resets, 0.0)) * 7

    ax.scatter(x, values, s=sizes, color=colors, edgecolor="#26323B", linewidth=0.5, zorder=3)
    ax.plot(x, values, color="#6B7280", linewidth=0.6, zorder=2)
    ax.axhline(12.0, color="#E5A000", linewidth=0.7, linestyle="--", label="soft gate")
    ax.axhline(20.0, color="#D95F02", linewidth=0.7, linestyle="--", label="hard gate")
    ax.set_yscale("log")
    ax.set_ylim(0.8, max(values) * 2.2)
    ax.set_xticks(x, [row["condition_label"].replace(" ", "\n") for row in p95_rows])
    ax.set_ylabel("episode NIS p95 mean (log)")
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.5, which="both")
    ax.legend(loc="upper left", handlelength=1.2, borderaxespad=0.2)
    for xx, value, reset in zip(x, values, resets):
        ax.text(xx, value * 1.25, f"{reset:.0f}", ha="center", va="bottom", fontsize=5.2, color="#111827")
    ax.text(0.98, 0.04, "bubble label = hard resets/episode", transform=ax.transAxes, ha="right", va="bottom", fontsize=5.2)
    panel_label(ax, "d", "NIS diagnostic response")


def create_figure(rows: list[dict[str, str]]) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)
    MANUSCRIPT_FIGS.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(mm(183), mm(170)))
    gs = fig.add_gridspec(
        2,
        2,
        left=0.13,
        right=0.985,
        top=0.90,
        bottom=0.18,
        wspace=0.36,
        hspace=0.56,
        height_ratios=[0.94, 1.0],
        width_ratios=[0.9, 1.1],
    )

    draw_panel_a(fig.add_subplot(gs[0, 0]), rows)
    draw_panel_b(fig.add_subplot(gs[0, 1]), rows)
    draw_panel_c(fig.add_subplot(gs[1, 0]), rows)
    draw_panel_d(fig.add_subplot(gs[1, 1]), rows)

    fig.text(
        0.075,
        0.035,
        "Source data: processed CARLA summaries, paired statistics, and NIS diagnostic summaries. "
        "The atlas synthesizes completed simulation evidence only; it is not a raw CARLA rerun, ROS2/HIL timing record, or physical robot validation result.",
        ha="left",
        va="bottom",
        fontsize=5.4,
        color="#2F3A43",
        wrap=True,
    )

    outputs = []
    for suffix in ("pdf", "svg", "tiff", "png"):
        path = FIGS / f"{FIGURE_ID}.{suffix}"
        if suffix == "tiff":
            fig.savefig(path, dpi=600)
        elif suffix == "png":
            fig.savefig(path, dpi=300)
        else:
            fig.savefig(path)
        outputs.append(path)
        shutil.copy2(path, MANUSCRIPT_FIGS / path.name)
    plt.close(fig)
    for path in outputs:
        print(path)


def main() -> None:
    rows = build_source_rows()
    write_source(rows)
    create_figure(rows)
    print(OUT_SOURCE)


if __name__ == "__main__":
    main()
