#!/usr/bin/env python3
"""Paired statistical comparisons for CARLA stress results.

The CARLA stress runner uses paired episode seeds across methods. This script
uses the episode intersection for each condition/method pair and reports:

- success/lost/collision rate differences with exact McNemar p-values;
- paired bootstrap CIs for LeaderAcc, WrongLeaderFrames, and IDSwitches.

It is dependency-light so it works in the CARLA Python 3.7 environment.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Callable, Dict, Iterable, List, Optional, Tuple


BOOL_METRICS = {
    "success": lambda row: row.get("Result", "").strip() == "Success",
    "collision": lambda row: row.get("Result", "").strip() == "Collision",
    "lost": lambda row: row.get("Result", "").strip() == "Lost",
    "near_miss": lambda row: parse_bool(row.get("NearMiss", "")),
}

CONTINUOUS_METRICS = ["LeaderAcc", "WrongLeaderFrames", "IDSwitches"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--queue-csv", type=Path, default=None)
    parser.add_argument("--reference-method", default="qgip")
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260603)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)
    groups = load_groups(args.results_root, args.queue_csv)
    rows = []

    for condition_id in sorted(groups):
        methods = groups[condition_id]
        if args.reference_method not in methods:
            continue
        reference_rows = methods[args.reference_method]
        for method in sorted(methods):
            if method == args.reference_method:
                continue
            rows.append(
                compare_methods(
                    condition_id,
                    args.reference_method,
                    reference_rows,
                    method,
                    methods[method],
                    args.bootstrap,
                    rng,
                )
            )

    write_csv(rows, args.out_csv)
    if args.out_md:
        write_markdown(rows, args.out_md)
    print(f"Wrote {args.out_csv}")


def load_groups(results_root: Path, queue_csv: Optional[Path]) -> Dict[str, Dict[str, List[Dict[str, str]]]]:
    groups: Dict[str, Dict[str, List[Dict[str, str]]]] = defaultdict(dict)
    if queue_csv and queue_csv.exists():
        with queue_csv.open("r", newline="", encoding="utf-8-sig") as handle:
            for queue_row in csv.DictReader(handle):
                condition_id = queue_row["condition_id"]
                method = queue_row["runner_method"]
                path = Path(queue_row["output_csv"])
                if not path.is_absolute():
                    path = Path.cwd() / path
                rows = read_episode_rows(path)
                if rows:
                    groups[condition_id][method] = rows
        return groups

    for path in sorted(results_root.rglob("*.csv")):
        if path.name.startswith("queue_") or path.name.startswith("unsupported_"):
            continue
        rows = read_episode_rows(path)
        if not rows:
            continue
        groups[path.parent.name][path.stem] = rows
    return groups


def read_episode_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "Episode" not in reader.fieldnames or "Result" not in reader.fieldnames:
            return []
        return list(reader)


def compare_methods(
    condition_id: str,
    ref_method: str,
    ref_rows: List[Dict[str, str]],
    cmp_method: str,
    cmp_rows: List[Dict[str, str]],
    bootstrap_n: int,
    rng: random.Random,
) -> Dict[str, object]:
    ref_by_episode = {row["Episode"]: row for row in ref_rows}
    cmp_by_episode = {row["Episode"]: row for row in cmp_rows}
    episodes = sorted(set(ref_by_episode) & set(cmp_by_episode), key=episode_sort_key)
    paired_ref = [ref_by_episode[episode] for episode in episodes]
    paired_cmp = [cmp_by_episode[episode] for episode in episodes]

    out: Dict[str, object] = {
        "condition_id": condition_id,
        "reference_method": ref_method,
        "comparison_method": cmp_method,
        "paired_n": len(episodes),
    }

    for metric, predicate in BOOL_METRICS.items():
        ref_values = [predicate(row) for row in paired_ref]
        cmp_values = [predicate(row) for row in paired_cmp]
        ref_rate = rate(ref_values)
        cmp_rate = rate(cmp_values)
        b, c = discordant_counts(ref_values, cmp_values)
        out[f"{metric}_ref_rate"] = ref_rate
        out[f"{metric}_cmp_rate"] = cmp_rate
        out[f"{metric}_diff_ref_minus_cmp"] = ref_rate - cmp_rate
        out[f"{metric}_discordant_ref0_cmp1"] = b
        out[f"{metric}_discordant_ref1_cmp0"] = c
        out[f"{metric}_mcnemar_p"] = mcnemar_exact(b, c)

    for metric in CONTINUOUS_METRICS:
        pairs = paired_numeric_values(paired_ref, paired_cmp, metric)
        diffs = [ref - cmp for ref, cmp in pairs]
        ci_low, ci_high = bootstrap_mean_ci(diffs, bootstrap_n, rng)
        out[f"{metric.lower()}_paired_n"] = len(diffs)
        out[f"{metric.lower()}_ref_mean"] = mean([ref for ref, _cmp in pairs]) if pairs else ""
        out[f"{metric.lower()}_cmp_mean"] = mean([cmp for _ref, cmp in pairs]) if pairs else ""
        out[f"{metric.lower()}_diff_ref_minus_cmp"] = mean(diffs) if diffs else ""
        out[f"{metric.lower()}_diff_ci95_low"] = ci_low
        out[f"{metric.lower()}_diff_ci95_high"] = ci_high

    return out


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_float(value: str) -> Optional[float]:
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def rate(values: Iterable[bool]) -> float:
    values = list(values)
    return float("nan") if not values else sum(1 for value in values if value) / len(values)


def discordant_counts(ref_values: List[bool], cmp_values: List[bool]) -> Tuple[int, int]:
    ref0_cmp1 = 0
    ref1_cmp0 = 0
    for ref, cmp_value in zip(ref_values, cmp_values):
        if (not ref) and cmp_value:
            ref0_cmp1 += 1
        elif ref and (not cmp_value):
            ref1_cmp0 += 1
    return ref0_cmp1, ref1_cmp0


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(0, min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def comb(n: int, k: int) -> int:
    """Small dependency-free n-choose-k for Python 3.7 compatibility."""
    if k < 0 or k > n:
        return 0
    k = min(k, n - k)
    result = 1
    for i in range(1, k + 1):
        result = result * (n - k + i) // i
    return result


def paired_numeric_values(
    ref_rows: List[Dict[str, str]], cmp_rows: List[Dict[str, str]], metric: str
) -> List[Tuple[float, float]]:
    values = []
    for ref_row, cmp_row in zip(ref_rows, cmp_rows):
        ref_value = parse_float(ref_row.get(metric, ""))
        cmp_value = parse_float(cmp_row.get(metric, ""))
        if ref_value is None or cmp_value is None:
            continue
        values.append((ref_value, cmp_value))
    return values


def bootstrap_mean_ci(diffs: List[float], bootstrap_n: int, rng: random.Random) -> Tuple[object, object]:
    if not diffs:
        return "", ""
    if len(diffs) == 1 or bootstrap_n <= 0:
        value = mean(diffs)
        return value, value
    samples = []
    n = len(diffs)
    for _ in range(bootstrap_n):
        samples.append(mean(diffs[rng.randrange(n)] for _j in range(n)))
    samples.sort()
    return percentile_sorted(samples, 2.5), percentile_sorted(samples, 97.5)


def percentile_sorted(values: List[float], q: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * q / 100.0
    lo = int(math.floor(position))
    hi = int(math.ceil(position))
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def episode_sort_key(value: str) -> Tuple[int, str]:
    try:
        return int(value), value
    except ValueError:
        return 10**12, value


def write_csv(rows: List[Dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: List[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: List[Dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CARLA Paired Statistics",
        "",
        "Positive differences mean the reference method is larger than the comparison method.",
        "For LeaderAcc, larger is better; for IDSwitches and WrongLeaderFrames, smaller is better.",
        "",
        "| Condition | Reference | Comparison | N | Success diff | McNemar p | LeaderAcc diff [95% CI] | IDSwitch diff [95% CI] |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {condition} | {ref} | {cmp} | {n} | {success_diff} | {p} | {leader} | {switches} |".format(
                condition=row["condition_id"],
                ref=row["reference_method"],
                cmp=row["comparison_method"],
                n=row["paired_n"],
                success_diff=format_float(row["success_diff_ref_minus_cmp"]),
                p=format_float(row["success_mcnemar_p"]),
                leader=format_ci(
                    row.get("leaderacc_diff_ref_minus_cmp", ""),
                    row.get("leaderacc_diff_ci95_low", ""),
                    row.get("leaderacc_diff_ci95_high", ""),
                ),
                switches=format_ci(
                    row.get("idswitches_diff_ref_minus_cmp", ""),
                    row.get("idswitches_diff_ci95_low", ""),
                    row.get("idswitches_diff_ci95_high", ""),
                ),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_float(value: object) -> str:
    if value == "":
        return ""
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def format_ci(mean_value: object, low: object, high: object) -> str:
    if mean_value == "":
        return ""
    return f"{format_float(mean_value)} [{format_float(low)}, {format_float(high)}]"


if __name__ == "__main__":
    main()
