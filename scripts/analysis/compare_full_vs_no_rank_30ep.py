#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比Full和No_rank模型的30-ep在线评估结果
"""

import json
import sys
import io
from pathlib import Path
from typing import Dict, List, Any

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


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


def calculate_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """计算指标"""
    if not results:
        return {}
    
    total = len(results)
    success_8m = sum(1 for r in results if r.get("success_8m", False))
    success_4m = sum(1 for r in results if r.get("success_4m", False))
    
    # Semantic-NavSucc@8m
    semantic_success = 0
    for r in results:
        chosen = r.get("chosen_idx_graph") or r.get("chosen_idx")
        tgt = r.get("target_idx_gt")
        succ8 = r.get("success_8m", False)
        if (chosen is not None) and (tgt is not None) and (chosen == tgt) and succ8:
            semantic_success += 1
    
    # GS@1 (protocol-level)
    gs_correct = sum(1 for r in results if r.get("gs_correct", False))
    
    # 2x2 table
    correct_and_success = 0
    correct_and_fail = 0
    wrong_and_success = 0
    wrong_and_fail = 0
    
    for r in results:
        chosen = r.get("chosen_idx_graph") or r.get("chosen_idx")
        tgt = r.get("target_idx_gt")
        succ8 = r.get("success_8m", False)
        
        if (chosen is not None) and (tgt is not None):
            correct = (chosen == tgt)
            if correct and succ8:
                correct_and_success += 1
            elif correct and not succ8:
                correct_and_fail += 1
            elif not correct and succ8:
                wrong_and_success += 1
            else:
                wrong_and_fail += 1
    
    navsucc_8m = success_8m / total * 100 if total > 0 else 0.0
    navsucc_4m = success_4m / total * 100 if total > 0 else 0.0
    semantic_navsucc_8m = semantic_success / total * 100 if total > 0 else 0.0
    gs_at_1 = gs_correct / total * 100 if total > 0 else 0.0
    
    avg_min_dist = sum(r.get("min_dist", 0.0) for r in results) / total if total > 0 else 0.0
    avg_steps = sum(r.get("steps", 0) for r in results) / total if total > 0 else 0.0
    stuck_count = sum(1 for r in results if r.get("stuck", False))
    stuck_rate = stuck_count / total * 100 if total > 0 else 0.0
    
    return {
        "total": total,
        "navsucc_8m": navsucc_8m,
        "navsucc_4m": navsucc_4m,
        "semantic_navsucc_8m": semantic_navsucc_8m,
        "gs_at_1": gs_at_1,
        "avg_min_dist": avg_min_dist,
        "avg_steps": avg_steps,
        "stuck_rate": stuck_rate,
        "correct_and_success": correct_and_success,
        "correct_and_fail": correct_and_fail,
        "wrong_and_success": wrong_and_success,
        "wrong_and_fail": wrong_and_fail,
    }


def main():
    print("="*80)
    print("Full vs No_rank: 30-ep Online Evaluation Comparison")
    print("="*80)
    
    # 加载结果
    full_results = load_jsonl(Path("logs_v2/proto_main_eval/gs_proto_driven.jsonl"))
    no_rank_results = load_jsonl(Path("logs_v2/proto_main_eval/ablation/no_rank_gs_30ep.jsonl"))
    
    if not full_results:
        print("[ERROR] Full model results not found!")
        return
    
    if not no_rank_results:
        print("[ERROR] No_rank model results not found!")
        return
    
    # 计算指标
    full_metrics = calculate_metrics(full_results)
    no_rank_metrics = calculate_metrics(no_rank_results)
    
    # 打印对比
    print("\n" + "="*80)
    print("Metrics Comparison")
    print("="*80)
    
    print(f"\n{'Metric':<30} {'Full':<15} {'No_rank':<15} {'Difference':<15}")
    print("-"*80)
    
    metrics_to_compare = [
        ("NavSucc@8m", "navsucc_8m", "%"),
        ("NavSucc@4m", "navsucc_4m", "%"),
        ("Semantic-NavSucc@8m", "semantic_navsucc_8m", "%"),
        ("GS@1 (proto)", "gs_at_1", "%"),
        ("Avg min_dist", "avg_min_dist", "m"),
        ("Avg steps", "avg_steps", ""),
        ("Stuck rate", "stuck_rate", "%"),
    ]
    
    for name, key, unit in metrics_to_compare:
        full_val = full_metrics.get(key, 0.0)
        no_rank_val = no_rank_metrics.get(key, 0.0)
        diff = no_rank_val - full_val
        
        if unit == "%":
            print(f"{name:<30} {full_val:>6.1f}{unit:<8} {no_rank_val:>6.1f}{unit:<8} {diff:>+6.1f}{unit}")
        elif unit == "m":
            print(f"{name:<30} {full_val:>6.2f}{unit:<8} {no_rank_val:>6.2f}{unit:<8} {diff:>+6.2f}{unit}")
        else:
            print(f"{name:<30} {full_val:>6.1f}{unit:<8} {no_rank_val:>6.1f}{unit:<8} {diff:>+6.1f}{unit}")
    
    # 2x2 table对比
    print("\n" + "="*80)
    print("2x2 Table (Selection Correctness x Navigation Success@8m)")
    print("="*80)
    
    print(f"\nFull (baseline):")
    print(f"  Correct & Success: {full_metrics['correct_and_success']}")
    print(f"  Correct & Fail:     {full_metrics['correct_and_fail']}")
    print(f"  Wrong & Success:    {full_metrics['wrong_and_success']}")
    print(f"  Wrong & Fail:       {full_metrics['wrong_and_fail']}")
    
    print(f"\nNo_rank:")
    print(f"  Correct & Success: {no_rank_metrics['correct_and_success']}")
    print(f"  Correct & Fail:     {no_rank_metrics['correct_and_fail']}")
    print(f"  Wrong & Success:    {no_rank_metrics['wrong_and_success']}")
    print(f"  Wrong & Fail:       {no_rank_metrics['wrong_and_fail']}")
    
    # 差异分析
    print("\n" + "="*80)
    print("Difference Analysis")
    print("="*80)
    
    navsucc_diff = no_rank_metrics['navsucc_8m'] - full_metrics['navsucc_8m']
    semantic_diff = no_rank_metrics['semantic_navsucc_8m'] - full_metrics['semantic_navsucc_8m']
    
    print(f"\nNavSucc@8m差异: {navsucc_diff:+.1f}个百分点")
    print(f"Semantic-NavSucc@8m差异: {semantic_diff:+.1f}个百分点")
    
    # 判断
    print("\n" + "="*80)
    print("Conclusion")
    print("="*80)
    
    if abs(navsucc_diff) <= 5.0 and abs(semantic_diff) <= 5.0:
        print("\n[OK] No_rank与Full性能等价（差异≤5个百分点）")
        print("     建议: 可以将No_rank定为主模型（Ours），Full作为消融项")
    elif navsucc_diff < -5.0 or semantic_diff < -5.0:
        print("\n[WARNING] No_rank在线性能明显低于Full（差异>5个百分点）")
        print("     建议: 保留Full模型为主线，No_rank作为消融项")
        print("     说明: 'We tried to remove ranking loss but it slightly harms online navigation, so we keep the multi-loss version as default'")
    else:
        print("\n[INFO] No_rank在某些指标上略优于Full")
        print("     建议: 根据具体指标决定谁是主角")
    
    # 保存结果
    output_path = Path("results/proto_main_eval/ablation/full_vs_no_rank_30ep_comparison.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    comparison = {
        "full": full_metrics,
        "no_rank": no_rank_metrics,
        "differences": {
            "navsucc_8m": navsucc_diff,
            "semantic_navsucc_8m": semantic_diff,
            "gs_at_1": no_rank_metrics['gs_at_1'] - full_metrics['gs_at_1'],
            "avg_min_dist": no_rank_metrics['avg_min_dist'] - full_metrics['avg_min_dist'],
        }
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    
    print(f"\n[Save] Comparison saved to {output_path}")


if __name__ == "__main__":
    main()

