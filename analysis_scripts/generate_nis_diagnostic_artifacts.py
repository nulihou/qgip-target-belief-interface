#!/usr/bin/env python3
"""Generate paper-ready artifacts for the CARLA NIS diagnostic sweep."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IN = (
    ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_nis_diagnostic100"
    / "nis_noise_sweep_qgip100_summary.csv"
)
OUTLIER_IN = (
    ROOT
    / "RA_L_optimization_20260528"
    / "07_computer_experiments"
    / "carla_nis_outlier100"
    / "nis_outlier_qgip100_summary.csv"
)
OUT = ROOT / "RA_L_optimization_20260528" / "08_paper_ready_outputs"
SRC = OUT / "source_data"
TABLES = OUT / "tables"
FIGS = OUT / "figures"

ORDER = ["noise_02", "noise_05", "noise_10"]
NOISE_LABELS = {"noise_02": "0.2 m", "noise_05": "0.5 m", "noise_10": "1.0 m"}
OUTLIER_ORDER = ["fp_10", "idswitch_20", "fp10_idswitch20_noise05"]
OUTLIER_LABELS = {
    "fp_10": "FP 10\\%",
    "idswitch_20": "ID switch 20\\%",
    "fp10_idswitch20_noise05": "FP 10\\% + ID 20\\% + 0.5 m",
}


def main() -> None:
    rows = read_rows(IN, ORDER)
    outlier_rows = read_rows(OUTLIER_IN, OUTLIER_ORDER)
    write_source(rows, outlier_rows)
    write_table(rows)
    write_outlier_table(outlier_rows)
    write_figure(rows)
    print(f"Wrote NIS diagnostic artifacts from {IN} and {OUTLIER_IN}")


def read_rows(path: Path, order: list[str]) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    by_condition = {row["condition_id"]: row for row in rows}
    return [by_condition[item] for item in order if item in by_condition]


def write_source(rows: list[dict[str, str]], outlier_rows: list[dict[str, str]]) -> None:
    SRC.mkdir(parents=True, exist_ok=True)
    if IN.exists():
        shutil.copyfile(IN, SRC / "carla_nis_noise_sweep_qgip100_summary.csv")
    if OUTLIER_IN.exists():
        shutil.copyfile(OUTLIER_IN, SRC / "carla_nis_outlier_qgip100_summary.csv")
    with (SRC / "carla_nis_noise_sweep_figure_data.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "condition_id",
            "noise_std_m",
            "success_rate",
            "lost_rate",
            "collision_rate",
            "near_miss_rate",
            "nismean_mean",
            "nisp95_mean",
            "nisp95_p95",
            "nissoftviolations_mean",
            "nishardviolations_mean",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "condition_id": row["condition_id"],
                    "noise_std_m": NOISE_LABELS[row["condition_id"]].replace(" m", ""),
                    "success_rate": row["success_rate"],
                    "lost_rate": row["lost_rate"],
                    "collision_rate": row["collision_rate"],
                    "near_miss_rate": row["near_miss_rate"],
                    "nismean_mean": row["nismean_mean"],
                    "nisp95_mean": row["nisp95_mean"],
                    "nisp95_p95": row["nisp95_p95"],
                    "nissoftviolations_mean": row["nissoftviolations_mean"],
                    "nishardviolations_mean": row["nishardviolations_mean"],
                }
            )
    with (SRC / "carla_nis_outlier_figure_data.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "condition_id",
            "perturbation",
            "success_rate",
            "lost_rate",
            "collision_rate",
            "leaderacc_mean",
            "nismean_mean",
            "nisp95_mean",
            "nisp95_p95",
            "nishardviolations_mean",
            "kfsoftupdates_mean",
            "kfhardresets_mean",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in outlier_rows:
            writer.writerow(
                {
                    "condition_id": row["condition_id"],
                    "perturbation": OUTLIER_LABELS[row["condition_id"]].replace("\\%", "%"),
                    "success_rate": row["success_rate"],
                    "lost_rate": row["lost_rate"],
                    "collision_rate": row["collision_rate"],
                    "leaderacc_mean": row["leaderacc_mean"],
                    "nismean_mean": row["nismean_mean"],
                    "nisp95_mean": row["nisp95_mean"],
                    "nisp95_p95": row["nisp95_p95"],
                    "nishardviolations_mean": row["nishardviolations_mean"],
                    "kfsoftupdates_mean": row["kfsoftupdates_mean"],
                    "kfhardresets_mean": row["kfhardresets_mean"],
                }
            )


def write_table(rows: list[dict[str, str]]) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    lines = [
        "\\begin{tabular}{lrrrrrr}",
        "\\toprule",
        "\\textbf{Noise} & \\textbf{N} & \\textbf{Success} & \\textbf{Lost} & \\textbf{NIS mean} & \\textbf{NIS p95} & \\textbf{Soft/Hard} \\\\",
        "\\midrule",
    ]
    for row in rows:
        n = int(row["n"])
        success = 100.0 * float(row["success_rate"])
        lost = 100.0 * float(row["lost_rate"])
        soft = float(row["nissoftviolations_mean"])
        hard = float(row["nishardviolations_mean"])
        lines.append(
            f"{NOISE_LABELS[row['condition_id']]} & {n} & {success:.1f}\\% & {lost:.1f}\\% & "
            f"{float(row['nismean_mean']):.3f} & {float(row['nisp95_mean']):.3f} & {soft:.1f}/{hard:.1f} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLES / "table_carla_nis_noise_sweep.tex").write_text("\n".join(lines), encoding="utf-8")


def write_outlier_table(rows: list[dict[str, str]]) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    lines = [
        "\\begin{tabular}{lrrrrrr}",
        "\\toprule",
        "\\textbf{Perturbation} & \\textbf{N} & \\textbf{Succ./Lost} & \\textbf{LeaderAcc} & \\textbf{NIS mean} & \\textbf{NIS p95} & \\textbf{Hard resets} \\\\",
        "\\midrule",
    ]
    for row in rows:
        n = int(row["n"])
        success = 100.0 * float(row["success_rate"])
        lost = 100.0 * float(row["lost_rate"])
        leader = 100.0 * float(row["leaderacc_mean"])
        lines.append(
            f"{OUTLIER_LABELS[row['condition_id']]} & {n} & {success:.1f}/{lost:.1f}\\% & "
            f"{leader:.1f}\\% & {float(row['nismean_mean']):.1f} & "
            f"{float(row['nisp95_mean']):.1f} & {float(row['kfhardresets_mean']):.1f} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLES / "table_carla_nis_outlier_sweep.tex").write_text("\n".join(lines), encoding="utf-8")


def write_figure(rows: list[dict[str, str]]) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        (FIGS / "NIS_DIAGNOSTIC_FIGURE_SKIPPED.txt").write_text(str(exc), encoding="utf-8")
        return

    FIGS.mkdir(parents=True, exist_ok=True)
    xs = [float(NOISE_LABELS[row["condition_id"]].replace(" m", "")) for row in rows]
    means = [float(row["nismean_mean"]) for row in rows]
    p95s = [float(row["nisp95_mean"]) for row in rows]
    soft = [float(row["nissoftviolations_mean"]) for row in rows]
    hard = [float(row["nishardviolations_mean"]) for row in rows]

    fig, ax1 = plt.subplots(figsize=(5.0, 2.8))
    ax1.plot(xs, means, marker="o", color="#1f6f50", label="Mean NIS")
    ax1.plot(xs, p95s, marker="s", color="#355c9a", label="Episode NIS p95")
    ax1.axhline(12.0, color="#b36b00", linewidth=0.8, linestyle="--", label="Soft gate")
    ax1.axhline(20.0, color="#8f1f1f", linewidth=0.8, linestyle=":", label="Hard gate")
    ax1.set_xlabel("Injected position noise std. (m)")
    ax1.set_ylabel("NIS")
    ax1.set_ylim(0, 22)
    ax1.grid(axis="y", linewidth=0.5, alpha=0.25)

    ax2 = ax1.twinx()
    ax2.bar([x - 0.035 for x in xs], soft, width=0.06, color="#d5963f", alpha=0.35, label="Soft violations")
    ax2.bar([x + 0.035 for x in xs], hard, width=0.06, color="#9a3d3d", alpha=0.35, label="Hard violations")
    ax2.set_ylabel("Violations / episode")
    ax2.set_ylim(0, max(40, max(soft + hard) * 1.25))

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, fontsize=7, ncol=2, frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_carla_nis_noise_sweep.pdf")
    fig.savefig(FIGS / "fig_carla_nis_noise_sweep.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()
