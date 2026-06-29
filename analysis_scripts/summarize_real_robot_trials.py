#!/usr/bin/env python3
"""Summarize real-robot trial CSVs with confidence intervals."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


BOOL_FIELDS = ["completion", "contact", "safety_stop", "near_miss", "lost"]
NUMERIC_FIELDS = [
    "min_distance_m",
    "min_ttc_s",
    "recovery_time_s",
    "tracking_rmse_m",
    "latency_p95_ms",
    "latency_p99_ms",
    "frame_drop_count",
    "clock_drift_p95_ms",
    "cmd_vel_safe_age_p95_ms",
    "cpu_load_mean_percent",
    "gpu_load_mean_percent",
    "gpu_memory_peak_mb",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--group-by", default="method,scenario,fault_type")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    group_fields = [item.strip() for item in args.group_by.split(",") if item.strip()]
    rows = read_rows(args.csv_path)
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = tuple(row.get(field, "") for field in group_fields)
        grouped[key].append(row)

    summaries = []
    for key, group in sorted(grouped.items()):
        out = {field: value for field, value in zip(group_fields, key)}
        out["n"] = len(group)
        for field in BOOL_FIELDS:
            successes = sum(parse_bool(row.get(field, "")) for row in group)
            low, high = wilson_ci(successes, len(group))
            out[f"{field}_rate"] = successes / len(group) if group else float("nan")
            out[f"{field}_ci95_low"] = low
            out[f"{field}_ci95_high"] = high
        for field in NUMERIC_FIELDS:
            values = [parse_float(row.get(field, "")) for row in group]
            values = [value for value in values if value is not None]
            out[f"{field}_mean"] = mean(values) if values else ""
            out[f"{field}_p95"] = percentile(values, 95.0) if values else ""
        summaries.append(out)

    fieldnames = ordered_fieldnames(group_fields, summaries)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summaries)
    else:
        writer = csv.DictWriter(open(1, "w", newline="", closefd=False), fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_float(value: str) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def wilson_ci(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    phat = successes / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q / 100.0
    lo = int(math.floor(position))
    hi = int(math.ceil(position))
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def ordered_fieldnames(group_fields: list[str], summaries: list[dict]) -> list[str]:
    fields = list(group_fields)
    if "n" not in fields:
        fields.append("n")
    for row in summaries:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


if __name__ == "__main__":
    main()
