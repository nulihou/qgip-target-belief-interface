#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评测自洽性审计（Step 1.2）

3条硬性一致性检查：
1. Oracle必须满足：is_correct == True（100%）
2. Oracle必须满足：semnavsucc8 == (d_min_to_gt < 8m)（等价关系）
3. Oracle与GS/Random使用完全相同的控制代码路径（只换目标id）
"""

import json
import csv
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import sys
from pathlib import Path

# Add scripts/analysis to path
_script_dir = Path(__file__).parent
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from unified_episode_evaluator import evaluate_episodes_from_jsonl


def check_oracle_correctness(
    oracle_results: List[Dict[str, Any]]
) -> Tuple[bool, Dict[str, Any]]:
    """
    检查1：Oracle必须满足 is_correct == True（100%）
    
    Returns:
        (passed, report_dict)
    """
    if not oracle_results:
        return False, {"error": "No Oracle results found"}
    
    total = len(oracle_results)
    correct_count = sum(1 for r in oracle_results if r.get("is_correct", False))
    incorrect_results = [r for r in oracle_results if not r.get("is_correct", False)]
    
    passed = (correct_count == total)
    
    report = {
        "check_name": "Oracle Correctness (100%)",
        "passed": passed,
        "total": total,
        "correct": correct_count,
        "incorrect": total - correct_count,
        "correct_rate": 100.0 * correct_count / total if total > 0 else 0.0,
        "incorrect_episodes": [
            {
                "episode": r.get("episode"),
                "scen_id": r.get("scen_id"),
                "target_idx_gt": r.get("target_idx_gt"),
                "chosen_idx_graph": r.get("chosen_idx_graph"),
            }
            for r in incorrect_results[:10]  # 只记录前10个
        ]
    }
    
    return passed, report


def check_oracle_semnavsucc_equivalence(
    oracle_results: List[Dict[str, Any]]
) -> Tuple[bool, Dict[str, Any]]:
    """
    检查2：Oracle必须满足 semnavsucc8 == (d_min_to_gt < 8m)（等价关系）
    
    因为Oracle总是选对（is_correct=True），所以：
    semnavsucc8 = is_correct AND (d_min_to_gt < 8m) = True AND (d_min_to_gt < 8m) = (d_min_to_gt < 8m)
    
    Returns:
        (passed, report_dict)
    """
    if not oracle_results:
        return False, {"error": "No Oracle results found"}
    
    violations = []
    
    for r in oracle_results:
        semnavsucc8 = r.get("semnavsucc8", False)
        d_min_to_gt = r.get("d_min_to_gt")
        is_correct = r.get("is_correct", False)
        
        # 如果d_min_to_gt是None，跳过
        if d_min_to_gt is None:
            continue
        
        # 计算期望值
        expected_semnavsucc8 = (d_min_to_gt < 8.0)
        
        # 检查等价关系
        if semnavsucc8 != expected_semnavsucc8:
            violations.append({
                "episode": r.get("episode"),
                "scen_id": r.get("scen_id"),
                "semnavsucc8": semnavsucc8,
                "d_min_to_gt": d_min_to_gt,
                "expected_semnavsucc8": expected_semnavsucc8,
                "is_correct": is_correct,
            })
    
    passed = (len(violations) == 0)
    
    report = {
        "check_name": "Oracle SemNavSucc Equivalence",
        "passed": passed,
        "total_checked": len([r for r in oracle_results if r.get("d_min_to_gt") is not None]),
        "violations": len(violations),
        "violation_details": violations[:10]  # 只记录前10个
    }
    
    return passed, report


def check_control_code_path_consistency(
    gs_results: List[Dict[str, Any]],
    random_results: List[Dict[str, Any]],
    oracle_results: List[Dict[str, Any]],
    jsonl_paths: Dict[str, str]
) -> Tuple[bool, Dict[str, Any]]:
    """
    检查3：Oracle与GS/Random使用完全相同的控制代码路径（只换目标id）
    
    这个检查需要：
    1. 检查代码中三种模式是否调用相同的控制函数
    2. 检查评估脚本中是否使用相同的控制器初始化参数
    
    由于这是代码层面的检查，我们只能做间接验证：
    - 检查三种模式的trajectory格式是否一致
    - 检查三种模式的字段是否一致
    - 检查是否有明显的代码路径差异
    
    Returns:
        (passed, report_dict)
    """
    # 检查字段一致性
    all_modes = {
        "gs": gs_results,
        "random": random_results,
        "oracle": oracle_results,
    }
    
    # 获取所有字段
    all_fields = set()
    for mode, results in all_modes.items():
        if results:
            all_fields.update(results[0].keys())
    
    # 检查每个模式是否有所有字段
    field_consistency = {}
    for mode, results in all_modes.items():
        if results:
            mode_fields = set(results[0].keys())
            missing_fields = all_fields - mode_fields
            extra_fields = mode_fields - all_fields
            field_consistency[mode] = {
                "has_all_fields": len(missing_fields) == 0,
                "missing_fields": list(missing_fields),
                "extra_fields": list(extra_fields),
            }
        else:
            field_consistency[mode] = {
                "has_all_fields": False,
                "missing_fields": list(all_fields),
                "extra_fields": [],
            }
    
    # 检查代码路径（通过检查评估脚本）
    code_path_check = {
        "gs_script": jsonl_paths.get("gs", "unknown"),
        "random_script": jsonl_paths.get("random", "unknown"),
        "oracle_script": jsonl_paths.get("oracle", "unknown"),
    }
    
    # 如果所有模式都有相同的字段，认为通过
    all_consistent = all(
        field_consistency[mode]["has_all_fields"]
        for mode in ["gs", "random", "oracle"]
        if all_modes[mode]
    )
    
    report = {
        "check_name": "Control Code Path Consistency",
        "passed": all_consistent,
        "field_consistency": field_consistency,
        "code_paths": code_path_check,
        "note": "This is an indirect check. Direct verification requires code inspection."
    }
    
    return all_consistent, report


def run_sanity_checks(
    gs_jsonl: str,
    random_jsonl: str,
    oracle_jsonl: str,
    output_report: Optional[str] = None
) -> Dict[str, Any]:
    """
    运行所有自洽性检查
    
    Args:
        gs_jsonl: GS模式JSONL文件路径
        random_jsonl: Random模式JSONL文件路径
        oracle_jsonl: Oracle模式JSONL文件路径
        output_report: 输出报告路径（可选）
    
    Returns:
        检查报告字典
    """
    print("[INFO] 开始自洽性检查...")
    
    # 评估所有episodes
    print("[INFO] 评估GS episodes...")
    gs_results, _ = evaluate_episodes_from_jsonl(gs_jsonl)
    
    print("[INFO] 评估Random episodes...")
    random_results, _ = evaluate_episodes_from_jsonl(random_jsonl)
    
    print("[INFO] 评估Oracle episodes...")
    oracle_results, _ = evaluate_episodes_from_jsonl(oracle_jsonl)
    
    # 运行检查
    print("[INFO] 运行检查1: Oracle Correctness...")
    check1_passed, check1_report = check_oracle_correctness(oracle_results)
    
    print("[INFO] 运行检查2: Oracle SemNavSucc Equivalence...")
    check2_passed, check2_report = check_oracle_semnavsucc_equivalence(oracle_results)
    
    print("[INFO] 运行检查3: Control Code Path Consistency...")
    check3_passed, check3_report = check_control_code_path_consistency(
        gs_results, random_results, oracle_results,
        {
            "gs": gs_jsonl,
            "random": random_jsonl,
            "oracle": oracle_jsonl,
        }
    )
    
    # 汇总报告
    all_passed = check1_passed and check2_passed and check3_passed
    
    report = {
        "all_passed": all_passed,
        "checks": {
            "oracle_correctness": check1_report,
            "oracle_semnavsucc_equivalence": check2_report,
            "control_code_path_consistency": check3_report,
        },
        "summary": {
            "total_checks": 3,
            "passed_checks": sum([check1_passed, check2_passed, check3_passed]),
            "failed_checks": 3 - sum([check1_passed, check2_passed, check3_passed]),
        }
    }
    
    # 输出报告
    if output_report:
        output_path = Path(output_report)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 同时生成Markdown报告
        md_path = output_path.with_suffix('.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# 评测自洽性审计报告\n\n")
            f.write(f"**状态**: {'[全部通过]' if all_passed else '[有检查失败]'}\n\n")
            f.write(f"**通过检查**: {report['summary']['passed_checks']}/{report['summary']['total_checks']}\n\n")
            
            f.write("## 检查1: Oracle Correctness (100%)\n\n")
            f.write(f"- **状态**: {'[通过]' if check1_passed else '[失败]'}\n")
            f.write(f"- **总episodes**: {check1_report['total']}\n")
            f.write(f"- **正确**: {check1_report['correct']} ({check1_report['correct_rate']:.1f}%)\n")
            if not check1_passed:
                f.write(f"- **错误episodes**: {len(check1_report['incorrect_episodes'])}\n")
            f.write("\n")
            
            f.write("## 检查2: Oracle SemNavSucc Equivalence\n\n")
            f.write(f"- **状态**: {'[通过]' if check2_passed else '[失败]'}\n")
            f.write(f"- **检查数量**: {check2_report['total_checked']}\n")
            f.write(f"- **违反数量**: {check2_report['violations']}\n")
            if not check2_passed:
                f.write(f"- **违反详情**: 见JSON报告\n")
            f.write("\n")
            
            f.write("## 检查3: Control Code Path Consistency\n\n")
            f.write(f"- **状态**: {'[通过]' if check3_passed else '[失败]'}\n")
            f.write(f"- **字段一致性**: 见JSON报告\n")
            f.write("\n")
    
    # 打印摘要
    print(f"\n[结果]")
    print(f"  检查1 (Oracle Correctness): {'[PASS]' if check1_passed else '[FAIL]'}")
    print(f"  检查2 (SemNavSucc Equivalence): {'[PASS]' if check2_passed else '[FAIL]'}")
    print(f"  检查3 (Code Path Consistency): {'[PASS]' if check3_passed else '[FAIL]'}")
    print(f"  总体: {'[全部通过]' if all_passed else '[有检查失败]'}")
    
    return report


def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="评测自洽性审计")
    parser.add_argument(
        "--gs-jsonl",
        type=str,
        required=True,
        help="GS模式JSONL文件路径"
    )
    parser.add_argument(
        "--random-jsonl",
        type=str,
        required=True,
        help="Random模式JSONL文件路径"
    )
    parser.add_argument(
        "--oracle-jsonl",
        type=str,
        required=True,
        help="Oracle模式JSONL文件路径"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/sanity_check_report.json",
        help="输出报告路径"
    )
    
    args = parser.parse_args()
    
    report = run_sanity_checks(
        args.gs_jsonl,
        args.random_jsonl,
        args.oracle_jsonl,
        args.output
    )
    
    if not report["all_passed"]:
        print("\n[WARNING] 有检查失败，请查看报告详情")
        exit(1)
    else:
        print("\n[SUCCESS] 所有检查通过！")


if __name__ == "__main__":
    main()

