#!/usr/bin/env python3
"""Generate extended paper artifacts for the no-page-limit manuscript.

The extended version is designed for internal review and high-standard submission
preparation. It keeps the RA-L short paper intact, but adds richer traceability,
split-audit, stress-suite, and NIS-response material derived from the same source
CSV files used by the verified short package.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "RA_L_optimization_20260528"
OUT = WORK / "08_paper_ready_outputs"
SRC = OUT / "source_data"
TABLES = OUT / "tables"
FIGS = OUT / "figures"
MANUSCRIPT_FIGS = WORK / "01_manuscript" / "paper_picture"


def main() -> None:
    ensure_dirs()
    stress = read_csv(SRC / "stress_summary_combined.csv")
    pairwise = read_csv(SRC / "pairwise_stats_combined.csv")
    main1000 = read_csv(SRC / "main1000_nominal_source.csv")
    split = read_csv(SRC / "final_dataset_split_check.csv")
    overlap = read_csv(SRC / "final_dataset_split_overlap.csv")
    nis_noise = read_csv(SRC / "carla_nis_noise_sweep_qgip100_summary.csv")
    nis_outlier = read_csv(SRC / "carla_nis_outlier_qgip100_summary.csv")
    dryrun_summary = read_csv(SRC / "real_robot_offline_dryrun_summary.csv")
    gate_audit = read_csv(SRC / "pre_real_robot_gate_audit.csv")

    claim_rows = build_claim_evidence(
        stress,
        pairwise,
        main1000,
        nis_noise,
        nis_outlier,
        split,
        overlap,
        dryrun_summary,
        gate_audit,
    )
    extended_rows = build_extended_stress_rows(stress)
    write_csv(SRC / "claim_evidence_matrix.csv", claim_rows)
    write_csv(SRC / "extended_stress_qgip_summary.csv", extended_rows)
    write_text(TABLES / "table_claim_evidence_matrix.tex", claim_evidence_tex(claim_rows))
    write_text(TABLES / "table_dataset_split_audit.tex", dataset_split_tex(split, overlap))
    write_text(TABLES / "table_extended_stress_qgip_summary.tex", extended_stress_tex(extended_rows))
    write_extended_figures(split, overlap, extended_rows, nis_noise, nis_outlier)
    print(f"Wrote extended artifacts under {OUT}")


def ensure_dirs() -> None:
    for directory in (SRC, TABLES, FIGS, MANUSCRIPT_FIGS):
        directory.mkdir(parents=True, exist_ok=True)


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


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def row_by(rows: list[dict[str, str]], **keys: str) -> dict[str, str]:
    for row in rows:
        if all(row.get(key) == value for key, value in keys.items()):
            return row
    raise KeyError(f"missing row {keys}")


def pct(value: str | float) -> str:
    return f"{100.0 * float(value):.1f}\\%"


def pct_plain(value: str | float) -> str:
    return f"{100.0 * float(value):.1f}%"


def num(value: str | float, digits: int = 1) -> str:
    return f"{float(value):.{digits}f}"


def latex_escape(text: str) -> str:
    return (
        text.replace("\\", "\\textbackslash{}")
        .replace("_", "\\_")
        .replace("%", "\\%")
        .replace("&", "\\&")
    )


def build_claim_evidence(
    stress: list[dict[str, str]],
    pairwise: list[dict[str, str]],
    main1000: list[dict[str, str]],
    nis_noise: list[dict[str, str]],
    nis_outlier: list[dict[str, str]],
    split: list[dict[str, str]],
    overlap: list[dict[str, str]],
    dryrun_summary: list[dict[str, str]],
    gate_audit: list[dict[str, str]],
) -> list[dict[str, str]]:
    fp = row_by(stress, condition_id="fp_10", method="qgip")
    fp_nq = row_by(stress, condition_id="fp_10", method="qgip_no_query")
    ids = row_by(stress, condition_id="idswitch", method="qgip")
    ids_kf = row_by(stress, condition_id="idswitch", method="std_kf")
    boundary = row_by(stress, condition_id="fp20_idswitch20", method="qgip")
    main_qgip = row_by(main1000, method="qgip")
    noise_10 = row_by(nis_noise, condition_id="noise_10")
    outlier_fp = row_by(nis_outlier, condition_id="fp_10")
    split_summary = "; ".join(f"{row['split']}={row['n']}" for row in split)
    overlap_summary = "; ".join(f"{row['pair']}={row['overlap_paths']}" for row in overlap)
    fp_pair = row_by(pairwise, condition_id="fp_10", reference_method="qgip", comparison_method="qgip_no_query")
    ids_pair = row_by(pairwise, condition_id="idswitch", reference_method="qgip", comparison_method="std_kf")
    dryrun_status_ok = sum(1 for row in dryrun_summary if row.get("status") == "PASS")
    dryrun_count = len(dryrun_summary)
    dryrun_trace = row_by(dryrun_summary, check_id="trace_row_count")
    dryrun_modes = row_by(dryrun_summary, check_id="ghost_mode_present")
    dryrun_safety = row_by(dryrun_summary, check_id="lost_triggers_safety_stop")
    gate_status_ok = sum(1 for row in gate_audit if row.get("status") == "PASS")
    gate_count = len(gate_audit)
    stage_counts: dict[str, int] = {}
    for row in gate_audit:
        stage = row["stage"].split()[0]
        stage_counts[stage] = stage_counts.get(stage, 0) + 1
    gate_stage_summary = "; ".join(f"{stage}={stage_counts[stage]}" for stage in ("A", "B", "C", "D", "E", "F"))

    return [
        {
            "claim": "Dataset split is auditable and non-overlapping.",
            "primary_evidence": split_summary,
            "quantitative_support": overlap_summary,
            "boundary": "Route-level generalization is not claimed as unrestricted deployment.",
            "source": "final_dataset_split_check.csv; final_dataset_split_overlap.csv",
            "source_display": "split audit CSVs",
            "verifier_gate": "dataset split counts and overlap checks",
        },
        {
            "claim": "Nominal low-ambiguity completion is dominated by the shared conservative safety layer.",
            "primary_evidence": "QGIP, Std-KF, and Rule all have 735/1000 Success, 265/1000 Lost, 0 collisions, 0 near-misses.",
            "quantitative_support": f"QGIP mean NIS {num(main_qgip['nis_mean'], 3)}; mean min distance {num(main_qgip['mean_min_distance_m'], 2)} m.",
            "boundary": "Not used as the main query-guidance evidence.",
            "source": "main1000_nominal_source.csv",
            "source_display": "main1000 CSV",
            "verifier_gate": "N=1000 nominal source counts",
        },
        {
            "claim": "Query/symbolic leader selection improves target consistency under adjacent-lane false positives.",
            "primary_evidence": f"LeaderAcc {pct_plain(fp['leaderacc_mean'])} vs no-query {pct_plain(fp_nq['leaderacc_mean'])}.",
            "quantitative_support": f"Paired gain +{float(fp_pair['leaderacc_diff_ref_minus_cmp']):.3f} [{float(fp_pair['leaderacc_diff_ci95_low']):.3f}, {float(fp_pair['leaderacc_diff_ci95_high']):.3f}].",
            "boundary": "Route-level success remains equal because conservative stopping dominates completion.",
            "source": "stress_summary_combined.csv; pairwise_stats_combined.csv",
            "source_display": "stress + CI CSVs",
            "verifier_gate": "main text LeaderAcc and paired-CI checks",
        },
        {
            "claim": "Query/symbolic leader selection reduces identity ambiguity under ID switches.",
            "primary_evidence": f"LeaderAcc {pct_plain(ids['leaderacc_mean'])} vs Std-KF {pct_plain(ids_kf['leaderacc_mean'])}.",
            "quantitative_support": f"ID switches {num(ids['idswitches_mean'], 1)} vs Std-KF {num(ids_kf['idswitches_mean'], 1)}; paired gain +{float(ids_pair['leaderacc_diff_ref_minus_cmp']):.3f}.",
            "boundary": "Supports target consistency, not universal completion superiority.",
            "source": "stress_summary_combined.csv; pairwise_stats_combined.csv",
            "source_display": "stress + CI CSVs",
            "verifier_gate": "main text ID-switch and LeaderAcc checks",
        },
        {
            "claim": "Boundary ambiguity stress preserves the same target-consistency pattern.",
            "primary_evidence": f"QGIP LeaderAcc {pct_plain(boundary['leaderacc_mean'])} in fp20+idswitch20.",
            "quantitative_support": f"Route success {pct_plain(boundary['success_rate'])}; collision {pct_plain(boundary['collision_rate'])}.",
            "boundary": "Supplemental N=100 stress, not the primary statistical test.",
            "source": "stress_summary_combined.csv; table_boundary_stress.tex",
            "source_display": "stress + boundary table",
            "verifier_gate": "scenario coverage and source-data checks",
        },
        {
            "claim": "NIS/mode instrumentation responds to detector degradation and outliers.",
            "primary_evidence": f"Noise 1.0 m: NIS p95 {num(noise_10['nisp95_mean'], 3)}; FP outlier: NIS p95 {num(outlier_fp['nisp95_mean'], 1)}.",
            "quantitative_support": f"FP outlier hard resets {num(outlier_fp['kfhardresets_mean'], 1)} per episode.",
            "boundary": "Closed-loop diagnostic only; not a final real-sensor calibration study.",
            "source": "carla_nis_noise_sweep_qgip100_summary.csv; carla_nis_outlier_qgip100_summary.csv",
            "source_display": "NIS noise/outlier CSVs",
            "verifier_gate": "NIS monotonicity, outlier p95, and hard-reset checks",
        },
        {
            "claim": "The real-robot preflight logic has a deterministic ROS2-less behavioral dry run.",
            "primary_evidence": f"{dryrun_status_ok}/{dryrun_count} dry-run checks PASS; {dryrun_trace['actual']}.",
            "quantitative_support": f"{dryrun_modes['actual']}; {dryrun_safety['actual']}.",
            "boundary": "Desktop dry run only; it is not ROS2 build, launch, rosbag, timing, or physical robot evidence.",
            "source": "real_robot_offline_dryrun_summary.csv; real_robot_offline_dryrun_trace.csv; fig13_offline_dryrun_contract_timeline_v2_source_data.csv",
            "source_display": "offline dry-run CSVs",
            "verifier_gate": "offline dry-run summary, trace, and figure-source checks",
        },
        {
            "claim": "Pre-real-robot execution gates are documented and auditable before any physical claim.",
            "primary_evidence": f"{gate_status_ok}/{gate_count} gate rows PASS across Stage A-F.",
            "quantitative_support": f"Gate coverage: {gate_stage_summary}.",
            "boundary": "Prepared gate package only; physical claims require signed manifests, ROS2/HIL bags, timing logs, and robot trials.",
            "source": "pre_real_robot_gate_audit.csv; table_pre_real_robot_gate_audit.tex; pre_real_robot_gate_audit_report_20260604.md",
            "source_display": "pre-real gate audit",
            "verifier_gate": "pre-real-robot gate audit checks and manuscript non-claim boundary",
        },
    ]


def build_extended_stress_rows(stress: list[dict[str, str]]) -> list[dict[str, str]]:
    specs = [
        ("ambiguity", "fp_10", "qgip", "Adjacent-lane false positive"),
        ("ambiguity", "idswitch", "qgip", "ID-switch ambiguity"),
        ("detector/timing", "fn_50", "qgip", "False-negative detector timing"),
        ("detector/timing", "delay_200", "qgip", "200 ms object-message delay"),
        ("raw-like", "raw_glare", "qgip", "Glare-like detector degradation"),
        ("raw-like", "raw_lidar_dropout", "qgip", "LiDAR-dropout-like degradation"),
        ("boundary", "fp20_idswitch20", "qgip", "Combined boundary ambiguity"),
    ]
    rows = []
    for suite, condition, method, label in specs:
        row = row_by(stress, condition_id=condition, method=method)
        rows.append(
            {
                "suite": suite,
                "condition_id": condition,
                "label": label,
                "method": method,
                "n": row["n"],
                "success_rate": row["success_rate"],
                "lost_rate": row["lost_rate"],
                "collision_rate": row["collision_rate"],
                "near_miss_rate": row.get("near_miss_rate", ""),
                "leaderacc_mean": row.get("leaderacc_mean", ""),
                "idswitches_mean": row.get("idswitches_mean", ""),
            }
        )
    return rows


def claim_evidence_tex(rows: list[dict[str, str]]) -> str:
    lines = [
        "% Auto-generated by generate_extended_artifacts.py",
        "\\begin{tabular}{@{}>{\\raggedright\\arraybackslash}p{0.22\\linewidth} >{\\raggedright\\arraybackslash}p{0.31\\linewidth} >{\\raggedright\\arraybackslash}p{0.25\\linewidth} >{\\raggedright\\arraybackslash}p{0.13\\linewidth}@{}}",
        "\\toprule",
        "\\textbf{Claim} & \\textbf{Evidence} & \\textbf{Boundary} & \\textbf{Source} \\\\",
        "\\midrule",
    ]
    for row in rows:
        source_display = row.get("source_display", row["source"])
        lines.append(
            f"{latex_escape(row['claim'])} & {latex_escape(row['primary_evidence'] + ' ' + row['quantitative_support'])} & "
            f"{latex_escape(row['boundary'])} & {latex_escape(source_display)} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def dataset_split_tex(split: list[dict[str, str]], overlap: list[dict[str, str]]) -> str:
    lines = [
        "% Auto-generated by generate_extended_artifacts.py",
        "\\begin{tabular}{lrrrl}",
        "\\toprule",
        "\\textbf{Split} & \\textbf{N} & \\textbf{Existing} & \\textbf{Missing} & \\textbf{Town counts} \\\\",
        "\\midrule",
    ]
    for row in split:
        lines.append(
            f"\\texttt{{{latex_escape(row['split'])}}} & {row['n']} & {row['existing_files']} & {row['missing_files']} & {latex_escape(row['town_counts'])} \\\\"
        )
    lines.append("\\midrule")
    for row in overlap:
        lines.append(f"\\multicolumn{{4}}{{l}}{{{latex_escape(row['pair'])}}} & overlap {row['overlap_paths']} \\\\")
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def extended_stress_tex(rows: list[dict[str, str]]) -> str:
    lines = [
        "% Auto-generated by generate_extended_artifacts.py",
        "\\begin{tabular}{l l r r r r r}",
        "\\toprule",
        "\\textbf{Suite} & \\textbf{Condition} & \\textbf{N} & \\textbf{Success} & \\textbf{Lost} & \\textbf{LeaderAcc} & \\textbf{IDSwitches} \\\\",
        "\\midrule",
    ]
    for row in rows:
        lines.append(
            f"{latex_escape(row['suite'])} & \\texttt{{{latex_escape(row['condition_id'])}}} & {row['n']} & "
            f"{pct(row['success_rate'])} & {pct(row['lost_rate'])} & {pct(row['leaderacc_mean'])} & {num(row['idswitches_mean'], 1)} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines)


def write_extended_figures(
    split: list[dict[str, str]],
    overlap: list[dict[str, str]],
    stress_rows: list[dict[str, str]],
    nis_noise: list[dict[str, str]],
    nis_outlier: list[dict[str, str]],
) -> None:
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 7,
            "axes.labelsize": 6,
            "xtick.labelsize": 5.5,
            "ytick.labelsize": 5.5,
            "legend.fontsize": 5.5,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )
    plot_split_composition(split, overlap)
    plot_stress_outcomes(stress_rows)
    plot_nis_outlier_response(nis_noise, nis_outlier)


def save_figure(fig, name: str) -> None:
    for suffix in (".pdf", ".svg", ".tiff", ".png"):
        path = FIGS / f"{name}{suffix}"
        if suffix == ".png":
            fig.savefig(path, dpi=300)
        elif suffix == ".tiff":
            fig.savefig(path, dpi=600)
        else:
            fig.savefig(path)
        manuscript_path = MANUSCRIPT_FIGS / f"{name}{suffix}"
        manuscript_path.write_bytes(path.read_bytes())


def plot_split_composition(split: list[dict[str, str]], overlap: list[dict[str, str]]) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    split_order = ["train", "val", "test_unseen"]
    split_display = {"train": "train", "val": "validation", "test_unseen": "unseen test"}
    training_domain_towns = ["Town03", "Town04", "Town10HD"]
    heldout_town = "Town05"
    towns = training_domain_towns + [heldout_town]
    extra_towns = sorted({item.split(":")[0] for row in split for item in row["town_counts"].split("; ") if item.split(":")[0] not in towns})
    towns += extra_towns
    values = {row["split"]: {town: 0 for town in towns} for row in split}
    for row in split:
        for item in row["town_counts"].split("; "):
            town, count = item.split(":")
            values[row["split"]][town] = int(count)
    split_rows = {row["split"]: row for row in split}
    totals = {name: int(split_rows[name]["n"]) for name in split_order}
    missing = {name: int(split_rows[name]["missing_files"]) for name in split_order}
    map_assignment_violations = (
        sum(values[name].get(heldout_town, 0) for name in ["train", "val"])
        + sum(values["test_unseen"].get(town, 0) for town in training_domain_towns)
    )
    pairwise_path_overlaps = sum(int(row["overlap_paths"]) for row in overlap)

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 6.2,
            "axes.labelsize": 6.2,
            "xtick.labelsize": 5.5,
            "ytick.labelsize": 5.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )

    colors = {"Town03": "#8FB6D6", "Town04": "#C9A646", "Town05": "#4F8F6B", "Town10HD": "#B7A6D6"}
    fig = plt.figure(figsize=(3.50, 2.44))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.50, 1.0], wspace=0.10)
    ax_matrix = fig.add_subplot(gs[0, 0])
    ax_total = fig.add_subplot(gs[0, 1], sharey=ax_matrix)

    for i, split_name in enumerate(split_order):
        for j, town in enumerate(towns):
            value = values[split_name].get(town, 0)
            ax_matrix.add_patch(
                Rectangle(
                    (j - 0.5, i - 0.5),
                    1.0,
                    1.0,
                    facecolor=colors.get(town, "#D6DADD") if value else "white",
                    edgecolor="#AEB4BB",
                    linewidth=0.45,
                )
            )
            ax_matrix.text(
                j,
                i,
                f"{value:,}" if value else "0",
                ha="center",
                va="center",
                fontsize=5.4,
                color="white" if value and town == heldout_town else ("#20262D" if value else "#9AA2AA"),
                fontweight="bold" if value else "normal",
            )
    ax_matrix.axvline(len(training_domain_towns) - 0.5, color="#4B5563", linestyle="--", linewidth=0.55)
    ax_matrix.set_xlim(-0.5, len(towns) - 0.5)
    ax_matrix.set_ylim(len(split_order) - 0.5, -0.5)
    ax_matrix.set_xticks(range(len(towns)))
    ax_matrix.set_xticklabels(towns)
    ax_matrix.xaxis.tick_top()
    ax_matrix.tick_params(axis="x", top=True, bottom=False, labeltop=True, labelbottom=False, length=0, pad=2)
    ax_matrix.set_yticks(range(len(split_order)))
    ax_matrix.set_yticklabels([split_display[name] for name in split_order])
    ax_matrix.tick_params(axis="y", length=0)
    for spine in ax_matrix.spines.values():
        spine.set_visible(False)
    ax_matrix.text(-0.24, 1.36, "a", transform=ax_matrix.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax_matrix.text(0.0, 1.36, "Map allocation by split", transform=ax_matrix.transAxes, fontsize=7, fontweight="bold", ha="left", va="bottom")
    ax_matrix.text(0.37, 1.24, "training-domain maps", transform=ax_matrix.transAxes, ha="center", va="bottom", fontsize=5.2, color="#66707A")
    ax_matrix.text(0.88, 1.24, "held-out map", transform=ax_matrix.transAxes, ha="center", va="bottom", fontsize=5.2, color="#66707A")

    y = range(len(split_order))
    ax_total.barh(list(y), [totals[name] for name in split_order], height=0.56, color="#E5E9EE", edgecolor="#4B5563", linewidth=0.45)
    xmax = max(totals.values()) * 1.55
    ax_total.set_xlim(0, xmax)
    ax_total.set_xticks([0, 2000, 4000])
    ax_total.set_xlabel("split-manifest records, n")
    ax_total.tick_params(axis="y", left=False, labelleft=False)
    ax_total.grid(True, axis="x", color="#D9DEE3", linewidth=0.35, alpha=0.7)
    ax_total.set_axisbelow(True)
    for spine in ["top", "right", "left"]:
        ax_total.spines[spine].set_visible(False)
    for i, split_name in enumerate(split_order):
        n_value = totals[split_name]
        pct_value = 100.0 * n_value / sum(totals.values())
        ax_total.text(
            n_value + xmax * 0.025,
            i,
            f"n = {n_value:,}\n{pct_value:.1f}%\nmissing = {missing[split_name]}",
            ha="left",
            va="center",
            fontsize=5.1,
            color="#20262D",
        )
    ax_total.set_ylim(ax_matrix.get_ylim())
    ax_total.text(-0.16, 1.36, "b", transform=ax_total.transAxes, fontsize=8, fontweight="bold", ha="left", va="bottom")
    ax_total.text(0.03, 1.36, "Split size and QC", transform=ax_total.transAxes, fontsize=7, fontweight="bold", ha="left", va="bottom")
    fig.text(
        0.165,
        0.055,
        f"map-assignment violations = {map_assignment_violations}; pairwise path overlaps = {pairwise_path_overlaps}",
        ha="left",
        va="bottom",
        fontsize=5.2,
        color="#66707A",
    )
    fig.subplots_adjust(left=0.18, right=0.98, top=0.70, bottom=0.25)
    save_figure(fig, "fig_extended_dataset_split")
    plt.close(fig)


def plot_stress_outcomes(rows: list[dict[str, str]]) -> None:
    import matplotlib.pyplot as plt

    labels = [row["condition_id"].replace("_", "\n") for row in rows]
    success = [100.0 * float(row["success_rate"]) for row in rows]
    lost = [100.0 * float(row["lost_rate"]) for row in rows]
    leader = [100.0 * float(row["leaderacc_mean"]) for row in rows]
    x = range(len(rows))
    fig, ax1 = plt.subplots(figsize=(7.0, 2.6))
    ax1.bar(x, success, color="#87b597", edgecolor="black", linewidth=0.3, label="Success")
    ax1.bar(x, lost, bottom=success, color="#d8c27a", edgecolor="black", linewidth=0.3, label="Lost")
    ax1.set_ylim(0, 105)
    ax1.set_ylabel("Route outcome (%)")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, fontsize=6)
    ax1.spines[["top", "right"]].set_visible(False)
    ax2 = ax1.twinx()
    ax2.plot(list(x), leader, color="#325b84", marker="o", linewidth=1.1, label="LeaderAcc")
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("LeaderAcc (%)")
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    fig.tight_layout()
    save_figure(fig, "fig_extended_stress_outcomes")
    plt.close(fig)


def plot_nis_outlier_response(nis_noise: list[dict[str, str]], nis_outlier: list[dict[str, str]]) -> None:
    import matplotlib.pyplot as plt

    noise_order = ["noise_02", "noise_05", "noise_10"]
    outlier_order = ["fp_10", "idswitch_20", "fp10_idswitch20_noise05"]
    noise_rows = [row_by(nis_noise, condition_id=item) for item in noise_order]
    outlier_rows = [row_by(nis_outlier, condition_id=item) for item in outlier_order]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.4))
    for panel_label, ax in zip(("a", "b"), axes):
        ax.text(-0.12, 1.06, panel_label, transform=ax.transAxes, fontweight="bold", fontsize=8, va="bottom", ha="left")
    axes[0].plot([0.2, 0.5, 1.0], [float(row["nismean_mean"]) for row in noise_rows], marker="o", color="#3f7f5f", label="Mean NIS")
    axes[0].plot([0.2, 0.5, 1.0], [float(row["nisp95_mean"]) for row in noise_rows], marker="s", color="#315f9f", label="Episode NIS p95")
    axes[0].axhline(12.0, color="#b08035", linestyle="--", linewidth=0.7)
    axes[0].axhline(20.0, color="#9d4b4b", linestyle=":", linewidth=0.7)
    axes[0].set_xlabel("Injected noise std. (m)")
    axes[0].set_ylabel("NIS")
    axes[0].set_title("Noise sensitivity")
    axes[0].legend(frameon=False, fontsize=6)
    labels = ["FP10", "ID20", "FP+ID+N"]
    p95 = [float(row["nisp95_mean"]) for row in outlier_rows]
    resets = [float(row["kfhardresets_mean"]) for row in outlier_rows]
    axes[1].bar(labels, p95, color="#8aa6c8", edgecolor="black", linewidth=0.3, label="NIS p95")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("NIS p95 (log)")
    axr = axes[1].twinx()
    axr.plot(labels, resets, color="#9b5f5f", marker="o", linewidth=1.1, label="Hard resets")
    axr.set_ylabel("Hard resets / episode")
    axes[1].set_title("Outlier response")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    axr.spines["top"].set_visible(False)
    fig.tight_layout()
    save_figure(fig, "fig_extended_nis_response")
    plt.close(fig)


if __name__ == "__main__":
    main()
