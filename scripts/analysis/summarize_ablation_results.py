#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汇总Ablation实验结果
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    """加载JSONL文件"""
    results = []
    if not path.exists():
        print(f"[WARNING] File not found: {path}")
        return results
    
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARNING] Failed to parse line: {e}")
                continue
    
    return results


def calculate_gs_at_1(results: List[Dict[str, Any]]) -> float:
    """计算GS@1准确率"""
    if not results:
        return 0.0
    
    correct = sum(1 for r in results if r.get("gs_correct", False) or r.get("gs_at_1", False))
    total = len(results)
    return correct / total * 100 if total > 0 else 0.0


def main():
    parser = argparse.ArgumentParser(description="Summarize Ablation Results")
    parser.add_argument(
        "--full",
        type=str,
        default="logs_v2/proto_main_eval/ablation/full.jsonl",
        help="Full baseline results"
    )
    parser.add_argument(
        "--no-rank",
        type=str,
        default="logs_v2/proto_main_eval/ablation/no_rank.jsonl",
        help="w/o ranking loss results"
    )
    parser.add_argument(
        "--no-geom",
        type=str,
        default="logs_v2/proto_main_eval/ablation/no_geom.jsonl",
        help="w/o geometry head results"
    )
    parser.add_argument(
        "--single-task",
        type=str,
        default="logs_v2/proto_main_eval/ablation/single_task.jsonl",
        help="single-task results"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/proto_main_eval/ablation_summary.md",
        help="Output markdown file"
    )
    
    args = parser.parse_args()
    
    # 加载结果
    full_results = load_jsonl(Path(args.full))
    no_rank_results = load_jsonl(Path(args.no_rank))
    no_geom_results = load_jsonl(Path(args.no_geom))
    single_task_results = load_jsonl(Path(args.single_task))
    
    # 计算GS@1
    full_gs1 = calculate_gs_at_1(full_results)
    no_rank_gs1 = calculate_gs_at_1(no_rank_results)
    no_geom_gs1 = calculate_gs_at_1(no_geom_results)
    single_task_gs1 = calculate_gs_at_1(single_task_results)
    
    # 打印结果
    print("\n" + "="*80)
    print("Ablation Results Summary")
    print("="*80)
    print(f"\n{'Variant':<20} | GS@1 (proto)")
    print(f"{'-'*20} | {'-'*15}")
    print(f"{'Full (baseline)':<20} | {full_gs1:>14.1f}%")
    print(f"{'w/o ranking loss':<20} | {no_rank_gs1:>14.1f}%")
    print(f"{'w/o geometry head':<20} | {no_geom_gs1:>14.1f}%")
    print(f"{'single-task GS':<20} | {single_task_gs1:>14.1f}%")
    
    # 生成表格
    table = "\n" + "="*80 + "\n"
    table += "Table: Ablation Study Results\n"
    table += "="*80 + "\n\n"
    table += "| Variant | GS@1 (proto) |\n"
    table += "|---------|--------------|\n"
    table += f"| Full (baseline) | {full_gs1:.1f}% |\n"
    table += f"| w/o ranking loss | {no_rank_gs1:.1f}% |\n"
    table += f"| w/o geometry head | {no_geom_gs1:.1f}% |\n"
    table += f"| single-task GS | {single_task_gs1:.1f}% |\n"
    
    print(table)
    
    # 保存到文件
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Ablation Study Results\n\n")
        f.write(f"**Analysis Date**: 2025-11-23\n\n")
        f.write(table)
        f.write("\n## Key Findings\n\n")
        f.write(f"- Full model achieves {full_gs1:.1f}% GS@1 on protocol graphs\n")
        if no_rank_gs1 < full_gs1:
            f.write(f"- Removing ranking loss decreases performance by {full_gs1 - no_rank_gs1:.1f} percentage points\n")
        if no_geom_gs1 < full_gs1:
            f.write(f"- Removing geometry head decreases performance by {full_gs1 - no_geom_gs1:.1f} percentage points\n")
        if single_task_gs1 < full_gs1:
            f.write(f"- Single-task model decreases performance by {full_gs1 - single_task_gs1:.1f} percentage points\n")
    
    print(f"\n[Save] Results saved to {output_path}")


if __name__ == "__main__":
    main()

