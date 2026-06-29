#!/usr/bin/env python3
"""Summarize existing per-episode CSV experiment outputs for RA-L reporting.

This does not rerun CARLA. It recomputes counts, rates, Wilson confidence
intervals, rule-of-three collision bounds, and simple continuous summaries from
the CSV files already present in the workspace.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "RA_L_optimization_20260528" / "07_computer_experiments"


@dataclass
class EpisodeRecord:
    source: str
    suite: str
    method: str
    episode: str
    result: str
    jerk: Optional[float]


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    spread = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))


def rule_of_three_upper(n: int) -> float:
    return float("nan") if n <= 0 else min(1.0, 3.0 / n)


def pct(value: float) -> str:
    if math.isnan(value):
        return "nan"
    return f"{100.0 * value:.1f}"


def infer_suite(path: Path) -> str:
    parts = [p.lower() for p in path.parts]
    if "final_300" in parts:
        return "CARLA final_300 historical"
    if "01_main_town05" in parts:
        return "CARLA Town05 historical"
    if "02_generalization_town03" in parts:
        return "CARLA Town03 historical"
    if "03_ablation" in parts:
        return "CARLA ablation historical"
    if "04_robustness" in parts:
        if "sweep_1.5s" in parts:
            return "CARLA robustness 1.5s historical"
        if "sweep_2.0s" in parts:
            return "CARLA robustness 2.0s historical"
        return "CARLA robustness historical"
    if "sensitivity_analysis" in parts:
        return "CARLA ghost-horizon sensitivity historical"
    return "historical"


def infer_method(path: Path) -> str:
    stem = path.stem.lower()
    name_map = {
        "results_ours": "QGIP-Net full",
        "run_log": "QGIP-Net full",
        "ours_100": "QGIP-Net full",
        "ours_town03_100": "QGIP-Net full",
        "baseline_rule_300": "Rule + MPC",
        "baseline_nokf_300": "No KF",
        "baseline_e2e_300": "E2E/PID baseline",
        "results_std_kf": "Std KF + MPC",
        "results_modular_pid": "Modular PID",
        "results_pid": "Modular PID",
        "ablation_no_query_200": "QGIP w/o query",
        "ablation_nokf": "QGIP w/o KF",
        "nokf_100": "No KF",
        "ambiguity_test_ours_50": "QGIP ambiguity",
        "ambiguity_test_no_query_50": "No-query ambiguity",
        "ambiguity_test_ours_randomized_50": "QGIP ambiguity randomized",
        "ambiguity_test_no_query_randomized_50": "No-query ambiguity randomized",
        "ambiguity_v2_hard_ours_50": "QGIP hard ambiguity",
        "ambiguity_v2_hard_no_query_50": "No-query hard ambiguity",
        "ambiguity_v2_hard_ours_gated_50": "QGIP hard ambiguity gated",
    }
    if stem in name_map:
        return name_map[stem]
    if stem.startswith("results_tg_"):
        return f"Ghost horizon {stem.replace('results_tg_', '')}"
    return path.stem


def is_archival_or_smoketest(path: Path) -> bool:
    lowered = [part.lower() for part in path.parts]
    return any(part.startswith("archive") or part.startswith("smoketest") for part in lowered)


def is_paper_candidate_source(source: str) -> bool:
    normalized = source.replace("/", "\\").lower()
    if "archive_" in normalized or "smoketest_" in normalized:
        return False
    if normalized.startswith("docs\\experiments\\"):
        return True
    allowed_final = {
        "scripts\\experiments\\final_300\\results_ours.csv",
        "scripts\\experiments\\final_300\\results_std_kf.csv",
        "scripts\\experiments\\final_300\\results_modular_pid.csv",
    }
    return normalized in allowed_final


def result_flags(result: str) -> Dict[str, bool]:
    normalized = result.strip().lower()
    return {
        "success": normalized == "success",
        "collision": normalized == "collision",
        "lost": normalized == "lost",
        "valid_degradation": normalized in {"validdegradation", "valid_degradation", "degradation"},
        "setup_fail": normalized in {"setupfail", "setup_fail"},
    }


def discover_csvs(root: Path) -> List[Path]:
    candidates: List[Path] = []
    for base in [root / "docs" / "experiments", root / "scripts" / "experiments"]:
        if not base.exists():
            continue
        candidates.extend(sorted(base.rglob("*.csv")))
    return [path for path in candidates if path.name.lower() != "summary.csv"]


def read_episode_csv(path: Path, root: Path) -> List[EpisodeRecord]:
    rows: List[EpisodeRecord] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "Result" not in reader.fieldnames:
            return rows
        source = str(path.relative_to(root))
        suite = infer_suite(path)
        method = infer_method(path)
        for idx, row in enumerate(reader, start=1):
            result = (row.get("Result") or "").strip()
            if not result:
                continue
            jerk: Optional[float] = None
            if row.get("Jerk") not in (None, ""):
                try:
                    jerk = float(row["Jerk"])
                except ValueError:
                    jerk = None
            rows.append(
                EpisodeRecord(
                    source=source,
                    suite=suite,
                    method=method,
                    episode=(row.get("Episode") or str(idx)).strip(),
                    result=result,
                    jerk=jerk,
                )
            )
    return rows


def write_normalized(records: Iterable[EpisodeRecord], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "source",
            "suite",
            "method",
            "episode_id",
            "result",
            "success",
            "collision",
            "lost",
            "valid_degradation",
            "setup_fail",
            "jerk",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in records:
            flags = result_flags(rec.result)
            writer.writerow(
                {
                    "source": rec.source,
                    "suite": rec.suite,
                    "method": rec.method,
                    "episode_id": rec.episode,
                    "result": rec.result,
                    "success": int(flags["success"]),
                    "collision": int(flags["collision"]),
                    "lost": int(flags["lost"]),
                    "valid_degradation": int(flags["valid_degradation"]),
                    "setup_fail": int(flags["setup_fail"]),
                    "jerk": "" if rec.jerk is None else f"{rec.jerk:.6f}",
                }
            )


def summarize(records: List[EpisodeRecord]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, str, str], List[EpisodeRecord]] = {}
    for rec in records:
        grouped.setdefault((rec.source, rec.suite, rec.method), []).append(rec)

    summaries: List[Dict[str, object]] = []
    for (source, suite, method), group in sorted(grouped.items()):
        n = len(group)
        counts = {key: 0 for key in ["success", "collision", "lost", "valid_degradation", "setup_fail"]}
        for rec in group:
            flags = result_flags(rec.result)
            for key in counts:
                counts[key] += int(flags[key])

        success_low, success_high = wilson_ci(counts["success"], n)
        collision_low, collision_high = wilson_ci(counts["collision"], n)
        lost_low, lost_high = wilson_ci(counts["lost"], n)
        jerks = [rec.jerk for rec in group if rec.jerk is not None]
        summaries.append(
            {
                "source": source,
                "suite": suite,
                "method": method,
                "paper_candidate": int(is_paper_candidate_source(source)),
                "n": n,
                "success": counts["success"],
                "success_rate": counts["success"] / n if n else float("nan"),
                "success_ci_low": success_low,
                "success_ci_high": success_high,
                "collision": counts["collision"],
                "collision_rate": counts["collision"] / n if n else float("nan"),
                "collision_ci_low": collision_low,
                "collision_ci_high": collision_high,
                "zero_collision_rule3_upper": rule_of_three_upper(n) if counts["collision"] == 0 else "",
                "lost": counts["lost"],
                "lost_rate": counts["lost"] / n if n else float("nan"),
                "lost_ci_low": lost_low,
                "lost_ci_high": lost_high,
                "valid_degradation": counts["valid_degradation"],
                "setup_fail": counts["setup_fail"],
                "mean_jerk": mean(jerks) if jerks else "",
            }
        )
    return summaries


def write_summary_csv(rows: List[Dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source",
        "suite",
        "method",
        "paper_candidate",
        "n",
        "success",
        "success_rate",
        "success_ci_low",
        "success_ci_high",
        "collision",
        "collision_rate",
        "collision_ci_low",
        "collision_ci_high",
        "zero_collision_rule3_upper",
        "lost",
        "lost_rate",
        "lost_ci_low",
        "lost_ci_high",
        "valid_degradation",
        "setup_fail",
        "mean_jerk",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary_md(rows: List[Dict[str, object]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Computer-Runnable Existing CSV Summary",
        "",
        "This table recomputes statistics from existing per-episode CSV files. It does not rerun CARLA.",
        "",
        "| Suite | Method | n | Success | Collision | Lost | Zero-collision 95% upper | Mean jerk | Source |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        n = int(row["n"])
        success = f"{row['success']}/{n} ({pct(float(row['success_rate']))}%)"
        collision = f"{row['collision']}/{n} ({pct(float(row['collision_rate']))}%)"
        lost = f"{row['lost']}/{n} ({pct(float(row['lost_rate']))}%)"
        rule3 = row["zero_collision_rule3_upper"]
        rule3_s = "" if rule3 == "" else f"{pct(float(rule3))}%"
        jerk = row["mean_jerk"]
        jerk_s = "" if jerk == "" else f"{float(jerk):.4f}"
        lines.append(
            f"| {row['suite']} | {row['method']} | {n} | {success} | {collision} | "
            f"{lost} | {rule3_s} | {jerk_s} | `{row['source']}` |"
        )
    lines.append("")
    lines.append("Use `zero_collision_rule3_upper` only as a binomial upper bound after zero observed collisions; it is not a proof of zero risk.")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    records: List[EpisodeRecord] = []
    for path in discover_csvs(args.root):
        records.extend(read_episode_csv(path, args.root))

    normalized_path = args.out_dir / "normalized_existing_episode_results.csv"
    summary_path = args.out_dir / "existing_episode_summary.csv"
    md_path = args.out_dir / "existing_episode_summary.md"
    paper_summary_path = args.out_dir / "paper_candidate_existing_episode_summary.csv"
    paper_md_path = args.out_dir / "paper_candidate_existing_episode_summary.md"

    write_normalized(records, normalized_path)
    summary_rows = summarize(records)
    paper_rows = [row for row in summary_rows if int(row["paper_candidate"]) == 1]
    write_summary_csv(summary_rows, summary_path)
    write_summary_md(summary_rows, md_path)
    write_summary_csv(paper_rows, paper_summary_path)
    write_summary_md(paper_rows, paper_md_path)

    print(f"[OK] episode CSV files parsed: {len({r.source for r in records})}")
    print(f"[OK] normalized episodes: {len(records)} -> {normalized_path}")
    print(f"[OK] summary rows: {len(summary_rows)} -> {summary_path}")
    print(f"[OK] markdown summary -> {md_path}")
    print(f"[OK] paper-candidate rows: {len(paper_rows)} -> {paper_summary_path}")
    print(f"[OK] paper-candidate markdown -> {paper_md_path}")


if __name__ == "__main__":
    main()
