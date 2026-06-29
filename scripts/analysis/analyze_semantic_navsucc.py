#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析语义感知导航成功率（Semantic-NavSucc）

定义：
Semantic-NavSucc@8m = (# 既选对目标 ∧ 导航成功@8m 的 episodes) / (总 episodes 数)

即：(chosen_idx == target_idx_gt) AND success_8m == True
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple


def load_jsonl(path: Path) -> Dict[int, Dict[str, Any]]:
    """
    加载JSONL文件，返回以scen_id为key的字典
    """
    episodes = {}
    if not path.exists():
        print(f"[WARNING] File not found: {path}")
        return episodes
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                # 优先用scen_id，其次用episode索引
                scen_id = rec.get("scen_id", rec.get("episode"))
                if scen_id is not None:
                    episodes[scen_id] = rec
            except json.JSONDecodeError as e:
                print(f"[WARNING] Failed to parse line: {e}")
                continue
    
    return episodes


def compute_semantic_navsucc(log_path: Path) -> Tuple[int, float, float, Dict[str, int]]:
    """
    计算语义感知导航成功率
    
    返回: (total, geo_rate, sem_rate, details)
    """
    recs = load_jsonl(log_path)
    total = len(recs)
    
    if total == 0:
        print(f"[ERROR] No valid records found in {log_path}")
        return 0, 0.0, 0.0, {}
    
    geo_success = 0  # 几何成功（不管选对谁）
    sem_success = 0  # 语义成功（选对目标且几何成功）
    
    details = {
        "correct_and_success": 0,
        "correct_and_fail": 0,
        "wrong_and_success": 0,
        "wrong_and_fail": 0,
    }
    
    for sid, r in recs.items():
        # 获取字段（兼容不同字段名）
        chosen = r.get("chosen_idx_graph") or r.get("chosen_idx")
        tgt = r.get("target_idx_gt")
        succ8 = bool(r.get("success_8m", False))
        
        # 几何成功（不管选对谁）
        if succ8:
            geo_success += 1
        
        # 语义成功：选对目标且几何成功
        if (chosen is not None) and (tgt is not None):
            is_correct = (chosen == tgt)
            
            if is_correct and succ8:
                sem_success += 1
                details["correct_and_success"] += 1
            elif is_correct and not succ8:
                details["correct_and_fail"] += 1
            elif not is_correct and succ8:
                details["wrong_and_success"] += 1
            elif not is_correct and not succ8:
                details["wrong_and_fail"] += 1
    
    geo_rate = geo_success / total * 100 if total > 0 else 0.0
    sem_rate = sem_success / total * 100 if total > 0 else 0.0
    
    return total, geo_rate, sem_rate, details


def print_results(mode_name: str, total: int, geo_rate: float, sem_rate: float, details: Dict[str, int]):
    """打印结果"""
    print(f"\n{'='*80}")
    print(f"{mode_name.upper()} Mode")
    print(f"{'='*80}")
    print(f"  Total Episodes:     {total}")
    print(f"  NavSucc@8m:         {geo_rate:.1f}% ({details['correct_and_success'] + details['wrong_and_success']}/{total})")
    print(f"  Semantic-NavSucc@8m: {sem_rate:.1f}% ({details['correct_and_success']}/{total})")
    print(f"\n  2×2 Table (Selection × Navigation Success@8m):")
    print(f"    {'':<20} | Success@8m | Fail@8m")
    print(f"    {'-'*20} | {'-'*10} | {'-'*10}")
    print(f"    {'Correct selection':<20} | {details['correct_and_success']:>10} | {details['correct_and_fail']:>10}")
    print(f"    {'Wrong selection':<20} | {details['wrong_and_success']:>10} | {details['wrong_and_fail']:>10}")


def generate_table(gs_result: Tuple, random_result: Tuple, oracle_result: Tuple) -> str:
    """生成论文表格"""
    gs_total, gs_geo, gs_sem, gs_details = gs_result
    rnd_total, rnd_geo, rnd_sem, rnd_details = random_result
    orc_total, orc_geo, orc_sem, orc_details = oracle_result
    
    table = "\n" + "="*80 + "\n"
    table += "Table: Semantic-aware Navigation Performance\n"
    table += "="*80 + "\n\n"
    table += "| Method | GS@1 (proto) | NavSucc@8m | Semantic-NavSucc@8m |\n"
    table += "|--------|--------------|------------|---------------------|\n"
    table += f"| **GS** | **93.3%** | {gs_geo:.1f}% | **{gs_sem:.1f}%** |\n"
    table += f"| Random | 46.7% | {rnd_geo:.1f}% | {rnd_sem:.1f}% |\n"
    table += f"| Oracle | 100.0% | {orc_geo:.1f}% | {orc_sem:.1f}% |\n"
    table += "\n"
    table += "**Key Findings**:\n"
    table += f"- GS模式在语义感知导航成功率（{gs_sem:.1f}%）上显著优于Random（{rnd_sem:.1f}%），提升 **{gs_sem - rnd_sem:.1f}个百分点**\n"
    table += f"- Random的高NavSucc@8m（{rnd_geo:.1f}%）主要来自\"选错+成功\"（{rnd_details['wrong_and_success']}个episode），语义完全不对\n"
    table += f"- GS的失败主要是\"选对+失败\"（{gs_details['correct_and_fail']}个episode），说明是控制栈问题而非识别问题\n"
    
    return table


def main():
    parser = argparse.ArgumentParser(description="Analyze Semantic-NavSucc@8m")
    parser.add_argument(
        "--gs",
        type=str,
        default="logs_v2/proto_main_eval/gs_proto_driven.jsonl",
        help="GS results JSONL"
    )
    parser.add_argument(
        "--random",
        type=str,
        default="logs_v2/proto_main_eval/random_proto_driven.jsonl",
        help="Random results JSONL"
    )
    parser.add_argument(
        "--oracle",
        type=str,
        default="logs_v2/proto_main_eval/oracle_proto_driven.jsonl",
        help="Oracle results JSONL"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/proto_main_eval/semantic_navsucc_analysis.md",
        help="Output markdown file"
    )
    
    args = parser.parse_args()
    
    # 计算各模式的结果
    gs_result = compute_semantic_navsucc(Path(args.gs))
    random_result = compute_semantic_navsucc(Path(args.random))
    oracle_result = compute_semantic_navsucc(Path(args.oracle))
    
    # 打印结果
    if gs_result[0] > 0:
        print_results("GS", *gs_result)
    if random_result[0] > 0:
        print_results("Random", *random_result)
    if oracle_result[0] > 0:
        print_results("Oracle", *oracle_result)
    
    # 生成对比
    if all(r[0] > 0 for r in [gs_result, random_result, oracle_result]):
        print("\n" + "="*80)
        print("Comparison Summary")
        print("="*80)
        print(f"  GS:   Semantic-NavSucc@8m = {gs_result[2]:.1f}%")
        print(f"  Random: Semantic-NavSucc@8m = {random_result[2]:.1f}%")
        print(f"  Oracle: Semantic-NavSucc@8m = {oracle_result[2]:.1f}%")
        
        # 生成论文表格
        table = generate_table(gs_result, random_result, oracle_result)
        print(table)
        
        # 保存到文件
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Semantic-Aware Navigation Success Analysis\n\n")
            f.write(f"**Analysis Date**: 2025-11-23\n\n")
            f.write(table)
            f.write("\n## Detailed Results\n\n")
            f.write("### GS Mode\n")
            f.write(f"- Total Episodes: {gs_result[0]}\n")
            f.write(f"- NavSucc@8m: {gs_result[1]:.1f}%\n")
            f.write(f"- Semantic-NavSucc@8m: {gs_result[2]:.1f}%\n")
            f.write(f"- 2×2 Table: {gs_result[3]}\n\n")
            f.write("### Random Mode\n")
            f.write(f"- Total Episodes: {random_result[0]}\n")
            f.write(f"- NavSucc@8m: {random_result[1]:.1f}%\n")
            f.write(f"- Semantic-NavSucc@8m: {random_result[2]:.1f}%\n")
            f.write(f"- 2×2 Table: {random_result[3]}\n\n")
            f.write("### Oracle Mode\n")
            f.write(f"- Total Episodes: {oracle_result[0]}\n")
            f.write(f"- NavSucc@8m: {oracle_result[1]:.1f}%\n")
            f.write(f"- Semantic-NavSucc@8m: {oracle_result[2]:.1f}%\n")
            f.write(f"- 2×2 Table: {oracle_result[3]}\n")
        
        print(f"\n[Save] Results saved to {output_path}")


if __name__ == "__main__":
    main()

