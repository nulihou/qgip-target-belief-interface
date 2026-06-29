#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查每个场景中所有候选的关系类型多样性（不依赖CARLA版本）

直接从协议图的edge_attr几何特征计算关系类型，不需要CARLA连接
"""

import os
import sys
import json
import argparse
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import Counter
import io
import math

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
_script_dir = os.path.dirname(os.path.abspath(__file__))  # scripts/analysis
_analysis_dir = os.path.dirname(_script_dir)  # scripts
_project_root = os.path.dirname(_analysis_dir)  # 项目根目录
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

NUM_REL_TYPES = 5

# 关系分类阈值（从carla_collect_data.py复制）
NEAR_THRESHOLD = 50.0  # meters
FRONT_DIST_MIN = 5.0
FRONT_DIST_MAX = 40.0
FRONT_ANGLE_THRESHOLD = math.pi / 6  # 30 degrees


def classify_relation_from_geometry(dx: float, dy: float, d: float, angle: float) -> int:
    """
    从几何特征（dx, dy, d, angle）计算关系类型
    
    Args:
        dx: x方向距离
        dy: y方向距离
        d: 欧氏距离
        angle: 角度（atan2(dy, dx)）
    
    Returns:
        关系类型: 0=near, 1=front, 2=behind, 3=left, 4=right
    """
    # 0: near (d < 50m)
    if d < NEAR_THRESHOLD:
        return 0
    
    # 1: front (5m < d < 40m, -30° < angle < 30°)
    if FRONT_DIST_MIN < d < FRONT_DIST_MAX:
        if -FRONT_ANGLE_THRESHOLD < angle < FRONT_ANGLE_THRESHOLD:
            return 1
    
    # 2: behind (5m < d < 40m, 150° < angle < 210° 或 -210° < angle < -150°)
    if FRONT_DIST_MIN < d < FRONT_DIST_MAX:
        abs_angle = abs(angle)
        if abs_angle > math.pi - FRONT_ANGLE_THRESHOLD or abs_angle < math.pi + FRONT_ANGLE_THRESHOLD:
            # 归一化到[0, 2π]
            if angle < 0:
                angle_norm = angle + 2 * math.pi
            else:
                angle_norm = angle
            if math.pi - FRONT_ANGLE_THRESHOLD < angle_norm < math.pi + FRONT_ANGLE_THRESHOLD:
                return 2
    
    # 3: left (5m < d < 40m, 60° < angle < 120°)
    if FRONT_DIST_MIN < d < FRONT_DIST_MAX:
        if math.pi / 3 < angle < 2 * math.pi / 3:
            return 3
    
    # 4: right (5m < d < 40m, -120° < angle < -60°)
    if FRONT_DIST_MIN < d < FRONT_DIST_MAX:
        if -2 * math.pi / 3 < angle < -math.pi / 3:
            return 4
    
    # 默认返回near
    return 0


def check_candidate_relations_from_protocol_graph(
    protocol_dir: str,
    scen_id: int,
) -> Dict[str, Any]:
    """
    从协议图检查一个场景中所有候选的关系类型
    直接从edge_attr的几何特征计算，不需要CARLA
    """
    npz_path = os.path.join(protocol_dir, f"scen_{scen_id:03d}.npz")
    if not os.path.exists(npz_path):
        return {}
    
    data = np.load(npz_path, allow_pickle=False)
    
    # 获取基本信息
    candidate_indices = data["candidate_indices"].tolist() if "candidate_indices" in data else []
    ego_index = int(data["ego_index"]) if "ego_index" in data else 0
    edge_index = data["edge_index"]  # (2, E)
    edge_attr = data["edge_attr"]  # (E, 8)
    
    # 从edge_attr提取几何特征
    # edge_attr格式: [dx, dy, d, cos_a, sin_a, near_flag, ...]
    # 我们需要找到从ego到每个候选的边
    
    candidate_relations = []
    
    for cand_idx in candidate_indices:
        # 找到从ego_index到cand_idx的边
        edge_mask = (edge_index[0] == ego_index) & (edge_index[1] == cand_idx)
        if not np.any(edge_mask):
            continue
        
        edge_idx = np.where(edge_mask)[0][0]
        edge_features = edge_attr[edge_idx]
        
        # 提取几何特征
        dx = float(edge_features[0])
        dy = float(edge_features[1])
        d = float(edge_features[2])
        cos_a = float(edge_features[3])
        sin_a = float(edge_features[4])
        
        # 计算角度
        angle = math.atan2(dy, dx)
        
        # 计算关系类型
        rel_type = classify_relation_from_geometry(dx, dy, d, angle)
        
        candidate_relations.append({
            "cand_idx": int(cand_idx),
            "rel_type": rel_type,
            "distance": d,
            "angle_deg": math.degrees(angle),
        })
    
    # 统计关系类型
    rel_types = [r["rel_type"] for r in candidate_relations]
    unique_rel_types = set(rel_types)
    rel_type_counter = Counter(rel_types)
    
    return {
        "scene_id": scen_id,
        "num_candidates": len(candidate_relations),
        "candidate_relations": candidate_relations,
        "unique_rel_types": sorted(list(unique_rel_types)),
        "unique_rel_count": len(unique_rel_types),
        "rel_type_distribution": dict(rel_type_counter),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Check candidate relation diversity across scenes (no CARLA required)"
    )
    parser.add_argument(
        "--protocol-dir",
        type=str,
        default="scripts/online_multi/protocol_graphs",
        help="Directory containing protocol graphs"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/proto_main_eval/candidate_relation_diversity_full.json",
        help="Output JSON path"
    )
    parser.add_argument(
        "--max-scen-id",
        type=int,
        default=29,
        help="Maximum scene ID to check"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Candidate Relation Diversity Check (No CARLA Required)")
    print("=" * 80)
    print(f"[Config] Protocol dir: {args.protocol_dir}")
    print(f"[Config] Max scen_id: {args.max_scen_id}")
    
    # Check each scene
    scene_results = []
    for scen_id in range(args.max_scen_id + 1):
        result = check_candidate_relations_from_protocol_graph(
            args.protocol_dir,
            scen_id
        )
        if result:
            scene_results.append(result)
            print(f"  Scene {scen_id:03d}: {result['unique_rel_count']} unique relations "
                  f"({result['rel_type_distribution']})")
    
    # Statistics
    unique_rel_counts = [r["unique_rel_count"] for r in scene_results]
    avg_unique_rel = np.mean(unique_rel_counts) if unique_rel_counts else 0.0
    
    scenes_with_single_rel = sum(1 for c in unique_rel_counts if c == 1)
    scenes_with_multiple_rel = sum(1 for c in unique_rel_counts if c > 1)
    
    # Overall relation type distribution
    all_rel_types = []
    for r in scene_results:
        all_rel_types.extend([rel["rel_type"] for rel in r["candidate_relations"]])
    overall_rel_dist = Counter(all_rel_types)
    
    print("\n" + "=" * 80)
    print("Summary Statistics")
    print("=" * 80)
    print(f"Total scenes checked: {len(scene_results)}")
    print(f"Average unique relations per scene: {avg_unique_rel:.2f}")
    print(f"Scenes with unique_rel_count=1: {scenes_with_single_rel} ({scenes_with_single_rel/len(scene_results)*100:.1f}%)")
    print(f"Scenes with unique_rel_count>1: {scenes_with_multiple_rel} ({scenes_with_multiple_rel/len(scene_results)*100:.1f}%)")
    print(f"\nOverall relation type distribution (across all candidates):")
    for rel_type in range(NUM_REL_TYPES):
        count = overall_rel_dist.get(rel_type, 0)
        pct = count / len(all_rel_types) * 100 if all_rel_types else 0.0
        print(f"  Rel type {rel_type}: {count} candidates ({pct:.1f}%)")
    
    # Save results
    results = {
        "summary": {
            "total_scenes": len(scene_results),
            "avg_unique_rel": float(avg_unique_rel),
            "scenes_with_single_rel": scenes_with_single_rel,
            "scenes_with_multiple_rel": scenes_with_multiple_rel,
            "overall_rel_distribution": dict(overall_rel_dist),
        },
        "scene_results": scene_results,
    }
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n[Done] Results saved to {args.output}")
    
    # Diagnosis
    print("\n" + "=" * 80)
    print("Diagnosis")
    print("=" * 80)
    if scenes_with_single_rel == len(scene_results):
        print("❌ **CRITICAL**: All scenes have only 1 unique relation type!")
        print("   This explains why Shuffled-Relation doesn't drop:")
        print("   - If all candidates have the same relation type, shuffling won't change the selection")
        print("   - The model can rely on geometric features alone to select the target")
    elif scenes_with_single_rel > len(scene_results) * 0.8:
        print("⚠️  **WARNING**: Most scenes (>80%) have only 1 unique relation type")
        print("   This may explain why Shuffled-Relation has limited effect")
    else:
        print("✅ Scenes have diverse relation types")
        print("   The issue with Shuffled-Relation may be elsewhere")


if __name__ == "__main__":
    main()
