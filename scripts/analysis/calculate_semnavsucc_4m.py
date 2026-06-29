#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算 SemNavSucc@4m 指标

定义：
SemNavSucc@4m = (# 既选对目标 ∧ 导航成功@4m 的 episodes) / (总 episodes 数)

即：(chosen_idx == target_idx_gt) AND success_4m == True
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple


def load_jsonl(path: Path) -> Dict[int, Dict[str, Any]]:
    """加载JSONL文件，返回以scen_id为key的字典"""
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
                scen_id = rec.get("scen_id", rec.get("episode"))
                if scen_id is not None:
                    episodes[scen_id] = rec
            except json.JSONDecodeError as e:
                print(f"[WARNING] Failed to parse line: {e}")
                continue
    
    return episodes


def compute_semantic_navsucc_4m(log_path: Path) -> Tuple[int, float]:
    """
    计算语义感知导航成功率@4m
    
    返回: (total, sem_rate_4m)
    """
    recs = load_jsonl(log_path)
    total = len(recs)
    
    if total == 0:
        print(f"[ERROR] No valid records found in {log_path}")
        return 0, 0.0
    
    sem_success_4m = 0  # 语义成功@4m（选对目标且几何成功@4m）
    
    for sid, r in recs.items():
        # 获取字段（兼容不同字段名）
        chosen = r.get("chosen_idx_graph") or r.get("chosen_idx")
        tgt = r.get("target_idx_gt")
        succ4 = bool(r.get("success_4m", False))
        
        # 语义成功@4m：选对目标且几何成功@4m
        if (chosen is not None) and (tgt is not None) and (chosen == tgt) and succ4:
            sem_success_4m += 1
    
    sem_rate_4m = sem_success_4m / total * 100 if total > 0 else 0.0
    
    return total, sem_rate_4m


def main():
    base_dir = Path("logs_v2/proto_main_eval/trajectory_eval")
    
    # 三个方法的日志文件
    files = {
        "Random": base_dir / "random_proto_driven.jsonl",
        "GS (LCORGNet)": base_dir / "gs_proto_driven.jsonl",
        "Oracle": base_dir / "oracle_proto_driven.jsonl",
    }
    
    results = {}
    for method_name, log_path in files.items():
        total, sem_rate_4m = compute_semantic_navsucc_4m(log_path)
        results[method_name] = {
            "total": total,
            "sem_navsucc_4m": sem_rate_4m
        }
        print(f"{method_name}:")
        print(f"  Total Episodes: {total}")
        print(f"  SemNavSucc@4m: {sem_rate_4m:.1f}%")
        print()
    
    # 输出表格格式
    print("="*80)
    print("SemNavSucc@4m Results for Table:")
    print("="*80)
    for method_name in ["Random", "GS (LCORGNet)", "Oracle"]:
        if method_name in results:
            rate = results[method_name]["sem_navsucc_4m"]
            print(f"{method_name:20s}: {rate:.1f}%")


if __name__ == "__main__":
    main()

