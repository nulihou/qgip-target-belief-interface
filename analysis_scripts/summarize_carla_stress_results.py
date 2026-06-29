#!/usr/bin/env python3
"""Summarize enhanced CARLA stress CSV outputs."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


RATE_FIELDS = {
    "success": lambda row: row.get("Result", "").strip() == "Success",
    "collision": lambda row: row.get("Result", "").strip() == "Collision",
    "lost": lambda row: row.get("Result", "").strip() == "Lost",
    "setup_fail": lambda row: row.get("Result", "").strip() == "SetupFail",
    "valid_degradation": lambda row: row.get("Result", "").strip() == "ValidDegradation",
    "near_miss": lambda row: parse_bool(row.get("NearMiss", "")),
}
NUMERIC_FIELDS = [
    "Jerk",
    "JerkP95",
    "MinDistance",
    "MinTTC",
    "MinHeadway",
    "RecoveryTime",
    "LeaderAcc",
    "LeaderFrames",
    "WrongLeaderFrames",
    "IDSwitches",
    "NISFrames",
    "NISMean",
    "NISP95",
    "NISSoftViolations",
    "NISHardViolations",
    "KFInitUpdates",
    "KFNormalUpdates",
    "KFSoftUpdates",
    "KFHardResets",
    "KFHardRejects",
    "KFPredictFrames",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--queue-csv", type=Path, default=None)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    queue_meta = read_queue_meta(args.queue_csv) if args.queue_csv else {}
    rows_by_group = defaultdict(list)
    for csv_path in sorted(args.results_root.rglob("*.csv")):
        if csv_path.name.startswith("queue_") or csv_path.name.startswith("unsupported_"):
            continue
        condition_id = csv_path.parent.name
        method = csv_path.stem
        key = (condition_id, method)
        for row in read_rows(csv_path):
            row["_source"] = str(csv_path)
            rows_by_group[key].append(row)

    summary_rows = []
    for (condition_id, method), rows in sorted(rows_by_group.items()):
        meta = queue_meta.get((condition_id, method), {})
        out = {
            "condition_id": condition_id,
            "method": method,
            "layer": meta.get("layer", ""),
            "scenario": meta.get("scenario", ""),
            "n": len(rows),
        }
        for name, predicate in RATE_FIELDS.items():
            k = sum(1 for row in rows if predicate(row))
            lo, hi = wilson_ci(k, len(rows))
            out[f"{name}_count"] = k
            out[f"{name}_rate"] = k / len(rows) if rows else float("nan")
            out[f"{name}_ci95_low"] = lo
            out[f"{name}_ci95_high"] = hi
            if name == "collision" and k == 0:
                out["zero_collision_rule3_upper"] = 3.0 / len(rows) if rows else float("nan")
        for field in NUMERIC_FIELDS:
            values = [parse_float(row.get(field, "")) for row in rows]
            values = [value for value in values if value is not None]
            out[f"{field.lower()}_mean"] = mean(values) if values else ""
            out[f"{field.lower()}_p95"] = percentile(values, 95.0) if values else ""
        summary_rows.append(out)

    write_csv(summary_rows, args.out_csv)
    if args.out_md:
        write_markdown(summary_rows, args.out_md)
    print(f"Wrote {args.out_csv}")


def read_queue_meta(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    meta = {}
    if not path.exists():
        return meta
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            meta[(row["condition_id"], row["runner_method"])] = row
    return meta


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "Result" not in reader.fieldnames:
            return []
        return list(reader)


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


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return float("nan"), float("nan")
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    spread = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return max(0.0, center - spread), min(1.0, center + spread)


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


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# CARLA Stress Summary",
        "",
        "| Condition | Method | N | Success | Collision | Lost | SetupFail | Near-miss | LeaderAcc | IDSwitches | Mean min distance |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {condition_id} | {method} | {n} | {success_rate:.3f} | {collision_rate:.3f} | "
            "{lost_rate:.3f} | {setup_fail_rate:.3f} | {near_miss_rate:.3f} | {leader_acc} | {id_switches} | {mindist} |".format(
                condition_id=row["condition_id"],
                method=row["method"],
                n=row["n"],
                success_rate=row["success_rate"],
                collision_rate=row["collision_rate"],
                lost_rate=row["lost_rate"],
                setup_fail_rate=row["setup_fail_rate"],
                near_miss_rate=row["near_miss_rate"],
                leader_acc=format_optional(row.get("leaderacc_mean", "")),
                id_switches=format_optional(row.get("idswitches_mean", "")),
                mindist=row.get("mindistance_mean", ""),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_optional(value) -> str:
    return "" if value == "" else f"{float(value):.3f}"


if __name__ == "__main__":
    main()
