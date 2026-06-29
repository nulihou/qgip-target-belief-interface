#!/usr/bin/env python3
"""Check final_dataset train/val/test split counts, towns, overlap, and files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Set


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "data" / "final_dataset"
DEFAULT_OUT = ROOT / "RA_L_optimization_20260528" / "07_computer_experiments"
TOWN_RE = re.compile(r"(Town\d+HD|Town\d+)", re.IGNORECASE)


def load_split(path: Path) -> List[Dict[str, object]]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return data


def extract_town(item_path: str) -> str:
    match = TOWN_RE.search(item_path.replace("/", "\\"))
    return match.group(1) if match else "UNKNOWN"


def write_summary_md(path: Path, split_rows: List[Dict[str, object]], overlap_rows: List[Dict[str, object]]) -> None:
    lines = [
        "# Final Dataset Split Check",
        "",
        "This check inspects `data/final_dataset/{train,val,test_unseen}.json` for path counts, town composition, missing files, and split overlap.",
        "",
        "## Split Summary",
        "",
        "| Split | n | Existing files | Missing files | Town counts | Difficulty counts |",
        "|---|---:|---:|---:|---|---|",
    ]
    for row in split_rows:
        lines.append(
            f"| {row['split']} | {row['n']} | {row['existing_files']} | {row['missing_files']} | "
            f"{row['town_counts']} | {row['difficulty_counts']} |"
        )
    lines.extend(["", "## Overlap", "", "| Pair | Overlap paths |", "|---|---:|"])
    for row in overlap_rows:
        lines.append(f"| {row['pair']} | {row['overlap_paths']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    split_files = {
        "train": args.dataset_dir / "train.json",
        "val": args.dataset_dir / "val.json",
        "test_unseen": args.dataset_dir / "test_unseen.json",
    }
    split_items = {name: load_split(path) for name, path in split_files.items()}

    split_rows: List[Dict[str, object]] = []
    path_sets: Dict[str, Set[str]] = {}
    for name, items in split_items.items():
        paths = [str(item.get("path", "")).replace("/", "\\") for item in items]
        path_sets[name] = set(paths)
        towns: Dict[str, int] = {}
        difficulties: Dict[str, int] = {}
        existing = 0
        for item, rel_path in zip(items, paths):
            towns[extract_town(rel_path)] = towns.get(extract_town(rel_path), 0) + 1
            diff = str(item.get("difficulty", "UNKNOWN"))
            difficulties[diff] = difficulties.get(diff, 0) + 1
            if (ROOT / rel_path).exists():
                existing += 1
        split_rows.append(
            {
                "split": name,
                "n": len(items),
                "existing_files": existing,
                "missing_files": len(items) - existing,
                "town_counts": "; ".join(f"{k}:{v}" for k, v in sorted(towns.items())),
                "difficulty_counts": "; ".join(f"{k}:{v}" for k, v in sorted(difficulties.items())),
            }
        )

    names = list(path_sets)
    overlap_rows: List[Dict[str, object]] = []
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            overlap_rows.append(
                {
                    "pair": f"{left} vs {right}",
                    "overlap_paths": len(path_sets[left] & path_sets[right]),
                }
            )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "final_dataset_split_check.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(split_rows[0].keys()))
        writer.writeheader()
        writer.writerows(split_rows)

    overlap_path = args.out_dir / "final_dataset_split_overlap.csv"
    with overlap_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(overlap_rows[0].keys()))
        writer.writeheader()
        writer.writerows(overlap_rows)

    md_path = args.out_dir / "final_dataset_split_check.md"
    write_summary_md(md_path, split_rows, overlap_rows)
    print(f"[OK] split summary -> {csv_path}")
    print(f"[OK] split overlap -> {overlap_path}")
    print(f"[OK] markdown report -> {md_path}")


if __name__ == "__main__":
    main()
