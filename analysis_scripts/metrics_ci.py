#!/usr/bin/env python3
"""Rate and paired-test utilities for RA-L experiment reporting.

This script is intentionally small and dependency-light. It can be used from
CSV exports where each row is one episode/trial.

Expected optional columns:
  method, seed, success, collision, near_miss, lost, intervention

Boolean columns may be 0/1, true/false, yes/no.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


TRUE_VALUES = {"1", "true", "yes", "y", "t"}


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in TRUE_VALUES


def wilson_ci(k: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    spread = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return (max(0.0, center - spread), min(1.0, center + spread))


def rule_of_three_upper(n: int) -> float:
    if n <= 0:
        return float("nan")
    return 3.0 / n


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value.

    b: method A fails and method B succeeds.
    c: method A succeeds and method B fails.
    """
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


@dataclass
class RateSummary:
    method: str
    metric: str
    k: int
    n: int
    rate: float
    ci_low: float
    ci_high: float


def load_rows(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def summarize_rates(rows: Iterable[Dict[str, str]], metrics: Iterable[str]) -> List[RateSummary]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("method", "unknown")].append(row)

    summaries: List[RateSummary] = []
    for method, method_rows in sorted(grouped.items()):
        n = len(method_rows)
        for metric in metrics:
            if metric not in method_rows[0]:
                continue
            k = sum(as_bool(row.get(metric, "")) for row in method_rows)
            low, high = wilson_ci(k, n)
            summaries.append(
                RateSummary(
                    method=method,
                    metric=metric,
                    k=k,
                    n=n,
                    rate=k / n if n else float("nan"),
                    ci_low=low,
                    ci_high=high,
                )
            )
    return summaries


def print_rate_table(summaries: Iterable[RateSummary]) -> None:
    print("method,metric,k,n,rate,ci95_low,ci95_high,rule_of_three_if_zero")
    for s in summaries:
        upper = rule_of_three_upper(s.n) if s.k == 0 else ""
        print(
            f"{s.method},{s.metric},{s.k},{s.n},"
            f"{s.rate:.6f},{s.ci_low:.6f},{s.ci_high:.6f},{upper}"
        )


def paired_mcnemar(rows: List[Dict[str, str]], method_a: str, method_b: str, metric: str) -> None:
    by_seed: Dict[str, Dict[str, Dict[str, str]]] = defaultdict(dict)
    for row in rows:
        seed = row.get("seed") or row.get("episode_id") or row.get("trial_id")
        method = row.get("method")
        if seed and method:
            by_seed[seed][method] = row

    b = 0
    c = 0
    paired = 0
    for seed_rows in by_seed.values():
        if method_a not in seed_rows or method_b not in seed_rows:
            continue
        paired += 1
        a = as_bool(seed_rows[method_a].get(metric, ""))
        b_val = as_bool(seed_rows[method_b].get(metric, ""))
        if (not a) and b_val:
            b += 1
        elif a and (not b_val):
            c += 1

    print(f"paired={paired}, b={b}, c={c}, exact_mcnemar_p={mcnemar_exact(b, c):.6g}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument(
        "--metrics",
        default="success,collision,near_miss,lost,intervention",
        help="Comma-separated boolean metrics to summarize.",
    )
    parser.add_argument("--mcnemar", nargs=3, metavar=("METHOD_A", "METHOD_B", "METRIC"))
    args = parser.parse_args()

    rows = load_rows(args.csv_path)
    metrics = [item.strip() for item in args.metrics.split(",") if item.strip()]
    print_rate_table(summarize_rates(rows, metrics))

    if args.mcnemar:
        method_a, method_b, metric = args.mcnemar
        paired_mcnemar(rows, method_a, method_b, metric)


if __name__ == "__main__":
    main()
