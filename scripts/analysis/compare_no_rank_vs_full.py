#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比no_rank和Full模型的3个sanity check结果
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
    
    navsucc_8m = success_8m / total * 100 if total > 0 else 0.0
    navsucc_4m = success_4m / total * 100 if total > 0 else 0.0
    semantic_navsucc_8m = semantic_success / total * 100 if total > 0 else 0.0
    gs_at_1 = gs_correct / total * 100 if total > 0 else 0.0
    
    avg_min_dist = sum(r.get("min_dist", 0.0) for r in results) / total if total > 0 else 0.0
    
    return {
        "total": total,
        "navsucc_8m": navsucc_8m,
        "navsucc_4m": navsucc_4m,
        "semantic_navsucc_8m": semantic_navsucc_8m,
        "gs_at_1": gs_at_1,
        "avg_min_dist": avg_min_dist,
    }


def main():
    # Check 1: 离线分组统计
    print("="*80)
    print("Check 1: Offline Grouped Analysis")
    print("="*80)
    
    full_offline = json.load(open("results/proto_main_eval/offline_grouped_analysis.json", 'r', encoding='utf-8'))
    no_rank_offline = json.load(open("results/proto_main_eval/offline_grouped_analysis_no_rank.json", 'r', encoding='utf-8'))
    
    print(f"\nFull (baseline):")
    print(f"  Overall: {full_offline['overall_accuracy']:.1f}% ({full_offline['overall_correct']}/{full_offline['total']})")
    print(f"  K=2: {full_offline['by_k']['2']['accuracy']:.1f}%")
    print(f"  K=3: {full_offline['by_k']['3']['accuracy']:.1f}%")
    
    print(f"\nNo_rank:")
    print(f"  Overall: {no_rank_offline['overall_accuracy']:.1f}% ({no_rank_offline['overall_correct']}/{no_rank_offline['total']})")
    print(f"  K=2: {no_rank_offline['by_k']['2']['accuracy']:.1f}%")
    print(f"  K=3: {no_rank_offline['by_k']['3']['accuracy']:.1f}%")
    
    diff_overall = no_rank_offline['overall_accuracy'] - full_offline['overall_accuracy']
    print(f"\n差异: {diff_overall:+.1f}个百分点")
    
    # Check 2: Protocol-level GS@1
    print("\n" + "="*80)
    print("Check 2: Protocol-level GS@1")
    print("="*80)
    
    full_proto = load_jsonl(Path("logs_v2/proto_main_eval/ablation/full.jsonl"))
    no_rank_proto = load_jsonl(Path("logs_v2/proto_main_eval/ablation/no_rank.jsonl"))
    
    full_proto_gs1 = sum(1 for r in full_proto if r.get("gs_correct", False)) / len(full_proto) * 100 if full_proto else 0.0
    no_rank_proto_gs1 = sum(1 for r in no_rank_proto if r.get("gs_correct", False)) / len(no_rank_proto) * 100 if no_rank_proto else 0.0
    
    print(f"\nFull (baseline): {full_proto_gs1:.1f}% ({sum(1 for r in full_proto if r.get('gs_correct', False))}/{len(full_proto)})")
    print(f"No_rank: {no_rank_proto_gs1:.1f}% ({sum(1 for r in no_rank_proto if r.get('gs_correct', False))}/{len(no_rank_proto)})")
    
    diff_proto = no_rank_proto_gs1 - full_proto_gs1
    print(f"\n差异: {diff_proto:+.1f}个百分点")
    
    # Check 3: 小规模在线评估（10 episodes）
    print("\n" + "="*80)
    print("Check 3: Small-scale Online Evaluation (10 episodes)")
    print("="*80)
    
    full_online_10ep = load_jsonl(Path("logs_v2/proto_main_eval/gs_proto_driven.jsonl"))[:10]  # 取前10个
    no_rank_online_10ep = load_jsonl(Path("logs_v2/proto_main_eval/ablation/no_rank_online_10ep.jsonl"))
    
    full_metrics = calculate_metrics(full_online_10ep)
    no_rank_metrics = calculate_metrics(no_rank_online_10ep)
    
    print(f"\nFull (baseline) - 10 episodes:")
    print(f"  NavSucc@8m: {full_metrics.get('navsucc_8m', 0):.1f}%")
    print(f"  Semantic-NavSucc@8m: {full_metrics.get('semantic_navsucc_8m', 0):.1f}%")
    print(f"  GS@1 (proto): {full_metrics.get('gs_at_1', 0):.1f}%")
    print(f"  Avg min_dist: {full_metrics.get('avg_min_dist', 0):.2f}m")
    
    print(f"\nNo_rank - 10 episodes:")
    print(f"  NavSucc@8m: {no_rank_metrics.get('navsucc_8m', 0):.1f}%")
    print(f"  Semantic-NavSucc@8m: {no_rank_metrics.get('semantic_navsucc_8m', 0):.1f}%")
    print(f"  GS@1 (proto): {no_rank_metrics.get('gs_at_1', 0):.1f}%")
    print(f"  Avg min_dist: {no_rank_metrics.get('avg_min_dist', 0):.2f}m")
    
    diff_navsucc = no_rank_metrics.get('navsucc_8m', 0) - full_metrics.get('navsucc_8m', 0)
    diff_semantic = no_rank_metrics.get('semantic_navsucc_8m', 0) - full_metrics.get('semantic_navsucc_8m', 0)
    
    print(f"\n差异:")
    print(f"  NavSucc@8m: {diff_navsucc:+.1f}个百分点")
    print(f"  Semantic-NavSucc@8m: {diff_semantic:+.1f}个百分点")
    
    # 总结
    print("\n" + "="*80)
    print("Summary")
    print("="*80)
    
    print(f"\n[OK] Check 1 (Offline Grouped):")
    print(f"   No_rank在离线分组统计上 {'略优于' if diff_overall > 0 else '略低于' if diff_overall < 0 else '等于'} Full")
    print(f"   差异: {diff_overall:+.1f}个百分点")
    
    print(f"\n[OK] Check 2 (Protocol-level):")
    print(f"   No_rank在protocol-level上 {'等于' if abs(diff_proto) < 0.1 else '略优于' if diff_proto > 0 else '略低于'} Full")
    print(f"   差异: {diff_proto:+.1f}个百分点")
    
    print(f"\n[OK] Check 3 (Online 10ep):")
    print(f"   No_rank在在线导航上:")
    print(f"     NavSucc@8m: {diff_navsucc:+.1f}个百分点")
    print(f"     Semantic-NavSucc@8m: {diff_semantic:+.1f}个百分点")
    
    # 结论
    print("\n" + "="*80)
    print("Conclusion")
    print("="*80)
    
    if no_rank_proto_gs1 >= full_proto_gs1 - 1.0:  # 允许1%的误差
        print("\n[OK] No_rank在protocol-level上表现与Full相当或更好")
        if diff_overall >= 0:
            print("[OK] No_rank在离线分组统计上表现与Full相当或更好")
            if diff_semantic >= -5.0:  # 允许5%的误差
                print("[OK] No_rank在在线导航上表现与Full相当")
                print("\n[CONCLUSION] No_rank是一个'可晋升的一等公民候选'！")
            else:
                print("[WARNING] No_rank在在线导航上略低于Full，需要更多episodes验证")
        else:
            print("[WARNING] No_rank在离线分组统计上略低于Full，但差异很小")
    else:
        print("\n[ERROR] No_rank在protocol-level上明显低于Full")
        print("   建议: 继续使用Full作为baseline")


if __name__ == "__main__":
    main()

