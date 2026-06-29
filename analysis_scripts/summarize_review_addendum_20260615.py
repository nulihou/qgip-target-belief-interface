#!/usr/bin/env python3
"""Summarize review-addendum CARLA experiments.

Inputs are the queue CSV and per-episode CARLA logs produced by
``review_addendum_queue_20260615.csv``. Outputs are source-data CSV plus compact
LaTeX tables for the manuscript/supplement.
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "RA_L_optimization_20260528/04_simulation_stress/review_addendum_queue_20260615.csv"
SOURCE = ROOT / "RA_L_optimization_20260528/08_paper_ready_outputs/source_data"
TABLES = ROOT / "RA_L_optimization_20260528/08_paper_ready_outputs/tables"


METHOD_LABELS = {
    "sort_pop_nis_mpc": "SORT+POP/NIS+MPC",
    "bytetrack_pop_nis_mpc": "ByteTrack+POP/NIS+MPC",
    "qgip_gnn_selector": "GNN selector",
    "qgip_gnn_no_query": "GNN no-query",
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(row: dict[str, str], key: str) -> float | None:
    value = (row.get(key) or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def pct(value: float) -> str:
    return f"{100.0 * value:.1f}\\%"


def one_decimal(value: float) -> str:
    return f"{value:.1f}"


def summarize_episode_csv(path: Path) -> dict[str, float | int | str]:
    rows = read_rows(path)
    n = len(rows)
    result_counts = {"Success": 0, "Collision": 0, "Lost": 0, "ValidDegradation": 0, "SetupFail": 0}
    for row in rows:
        result = row.get("Result", "")
        if result in result_counts:
            result_counts[result] += 1

    leaderacc_values = [v for row in rows if (v := fnum(row, "LeaderAcc")) is not None]
    wrong_values = [v for row in rows if (v := fnum(row, "WrongLeaderFrames")) is not None]
    switch_values = [v for row in rows if (v := fnum(row, "IDSwitches")) is not None]
    hard_values = [v for row in rows if (v := fnum(row, "NISHardViolations")) is not None]
    soft_values = [v for row in rows if (v := fnum(row, "NISSoftViolations")) is not None]
    nis_mean_values = [v for row in rows if (v := fnum(row, "NISMean")) is not None]
    nis_p95_values = [v for row in rows if (v := fnum(row, "NISP95")) is not None]
    near_miss_values = [v for row in rows if (v := fnum(row, "NearMiss")) is not None]

    return {
        "observed_n": n,
        "success": result_counts["Success"],
        "collision": result_counts["Collision"],
        "lost": result_counts["Lost"],
        "valid_degradation": result_counts["ValidDegradation"],
        "setup_fail": result_counts["SetupFail"],
        "strict_sr": result_counts["Success"] / n if n else 0.0,
        "loose_sr": (result_counts["Success"] + result_counts["ValidDegradation"]) / n if n else 0.0,
        "leaderacc_mean": mean(leaderacc_values),
        "wrong_leader_frames_mean": mean(wrong_values),
        "idswitches_mean": mean(switch_values),
        "nis_mean_episode_mean": mean(nis_mean_values),
        "nis_p95_episode_mean": mean(nis_p95_values),
        "nis_soft_violations_mean": mean(soft_values),
        "nis_hard_violations_mean": mean(hard_values),
        "near_miss_rate": mean(near_miss_values),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def latex_table_frontend(rows: list[dict[str, object]]) -> str:
    selected = [row for row in rows if row["condition_id"] in {"fp_10", "idswitch"}]
    lines = [
        "\\begin{tabular}{llrrrrr}",
        "\\toprule",
        "\\textbf{Condition} & \\textbf{Method} & \\textbf{N} & \\textbf{Succ./Lost} & \\textbf{LeaderAcc} & \\textbf{IDSwitches} & \\textbf{Hard gates} \\\\",
        "\\midrule",
    ]
    for row in selected:
        lines.append(
            f"{row['condition_id'].replace('_', '\\_')} & {METHOD_LABELS.get(str(row['method']), str(row['method']))} "
            f"& {row['observed_n']} & {row['success']}/{row['lost']} "
            f"& {pct(float(row['leaderacc_mean']))} "
            f"& {one_decimal(float(row['idswitches_mean']))} "
            f"& {one_decimal(float(row['nis_hard_violations_mean']))} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines) + "\n"


def latex_table_query(rows: list[dict[str, object]]) -> str:
    selected = [row for row in rows if row["condition_id"] == "query_left"]
    lines = [
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "\\textbf{Method} & \\textbf{N} & \\textbf{Succ./Lost} & \\textbf{Query LeaderAcc} & \\textbf{Wrong frames} \\\\",
        "\\midrule",
    ]
    for row in selected:
        lines.append(
            f"{METHOD_LABELS.get(str(row['method']), str(row['method']))} "
            f"& {row['observed_n']} & {row['success']}/{row['lost']} "
            f"& {pct(float(row['leaderacc_mean']))} "
            f"& {one_decimal(float(row['wrong_leader_frames_mean']))} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    return "\n".join(lines) + "\n"


def main() -> None:
    queue_rows = read_rows(QUEUE)
    summary_rows: list[dict[str, object]] = []
    for queue_row in queue_rows:
        path = Path(queue_row["output_csv"])
        if not path.exists():
            raise FileNotFoundError(path)
        summary = summarize_episode_csv(path)
        expected = int(queue_row["episodes"])
        if summary["observed_n"] < expected:
            raise RuntimeError(f"{queue_row['queue_id']} incomplete: {summary['observed_n']}/{expected}")
        summary_rows.append(
            {
                "queue_id": queue_row["queue_id"],
                "condition_id": queue_row["condition_id"],
                "method": queue_row["method"],
                "expected_n": expected,
                "source_csv": str(path),
                **summary,
            }
        )

    write_csv(SOURCE / "review_addendum_summary_20260615.csv", summary_rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    (TABLES / "table_frontend_pop_nis_addendum_20260615.tex").write_text(
        latex_table_frontend(summary_rows), encoding="utf-8"
    )
    (TABLES / "table_query_sensitive_addendum_20260615.tex").write_text(
        latex_table_query(summary_rows), encoding="utf-8"
    )
    print(f"Wrote {len(summary_rows)} summary rows.")


if __name__ == "__main__":
    main()
