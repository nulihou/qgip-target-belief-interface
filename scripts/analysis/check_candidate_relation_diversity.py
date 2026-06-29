#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查每个场景中所有候选的关系类型多样性

关键问题：协议图只存储了anchor→target的关系
我们需要检查：每个场景中，anchor到所有候选的关系类型是否相同
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

# Import relation classification function
_script_data_dir = os.path.join(_project_root, "scripts", "data")
if _script_data_dir not in sys.path:
    sys.path.insert(0, _script_data_dir)

from scripts.data.carla_collect_data import classify_relation, NUM_REL_TYPES
import carla
import math

# Try to import carla
_carla_python_api_paths = [
    os.environ.get("CARLA_PYTHON_API_PATH"),
    "E:/carla/WindowsNoEditor/PythonAPI",
    "/opt/carla/PythonAPI",
    os.path.join(os.path.expanduser("~"), "CARLA_0.9.15", "PythonAPI"),
]

for path in _carla_python_api_paths:
    if path and os.path.exists(path):
        if path not in sys.path:
            sys.path.insert(0, path)
        break

try:
    import carla
except ImportError:
    print("[WARN] CARLA not available, will use geometry-based relation computation")


def compute_relation_from_transforms(anchor_tf: carla.Transform, target_tf: carla.Transform) -> int:
    """
    从两个Transform计算关系类型
    返回满足的关系类型（如果有多个，返回第一个）
    """
    for rel_type in range(NUM_REL_TYPES):
        if classify_relation(anchor_tf, target_tf, rel_type):
            return rel_type
    return 0  # 默认返回0（near）


def check_candidate_relations_in_scene(
    scen: Dict[str, Any],
    protocol_dir: str,
    client: Optional[carla.Client] = None,
) -> Dict[str, Any]:
    """
    检查一个场景中所有候选的关系类型
    """
    scen_id = scen.get("id", -1)
    if scen_id < 0:
        return {}
    
    # 加载协议图
    npz_path = os.path.join(protocol_dir, f"scen_{scen_id:03d}.npz")
    if not os.path.exists(npz_path):
        return {}
    
    data = np.load(npz_path, allow_pickle=False)
    candidate_indices = data["candidate_indices"].tolist() if "candidate_indices" in data else []
    ego_index = int(data["ego_index"]) if "ego_index" in data else 0
    node_spawn_indices = data["node_spawn_indices"].tolist() if "node_spawn_indices" in data else []
    
    # 获取anchor（ego）的spawn index
    if ego_index >= len(node_spawn_indices):
        return {}
    anchor_spawn_idx = node_spawn_indices[ego_index]
    
    # 获取场景信息
    town = scen.get("town", "Town10HD")
    spawn_points = None
    
    if client is not None:
        try:
            world = client.get_world()
            if world.get_map().name != town:
                world = client.load_world(town)
            spawn_points = world.get_map().get_spawn_points()
        except Exception as e:
            print(f"[WARN] Failed to load world {town}: {e}")
            return {}
    
    if spawn_points is None or anchor_spawn_idx >= len(spawn_points):
        return {}
    
    # 获取anchor的transform
    anchor_tf = spawn_points[anchor_spawn_idx]
    
    # 计算每个候选的关系类型
    candidate_relations = []
    for cand_idx in candidate_indices:
        if cand_idx >= len(node_spawn_indices):
            continue
        cand_spawn_idx = node_spawn_indices[cand_idx]
        if cand_spawn_idx >= len(spawn_points):
            continue
        
        cand_tf = spawn_points[cand_spawn_idx]
        rel_type = compute_relation_from_transforms(anchor_tf, cand_tf)
        candidate_relations.append({
            "cand_idx": int(cand_idx),
            "rel_type": rel_type,
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
        description="Check candidate relation diversity across scenes"
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        default="data/online_multi/multi_seen_v3.json",
        help="Path to scenarios JSON file"
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
        default="results/proto_main_eval/candidate_relation_diversity.json",
        help="Output JSON path"
    )
    parser.add_argument(
        "--max-scen-id",
        type=int,
        default=29,
        help="Maximum scene ID to check"
    )
    parser.add_argument(
        "--carla-host",
        type=str,
        default="localhost",
        help="CARLA host"
    )
    parser.add_argument(
        "--carla-port",
        type=int,
        default=2000,
        help="CARLA port"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Candidate Relation Diversity Check")
    print("=" * 80)
    print(f"[Config] Scenarios: {args.scenarios}")
    print(f"[Config] Protocol dir: {args.protocol_dir}")
    print(f"[Config] Max scen_id: {args.max_scen_id}")
    
    # Load scenarios
    with open(args.scenarios, "r", encoding="utf-8") as f:
        scenarios = json.load(f)
    
    # Try to connect to CARLA (optional)
    client = None
    try:
        client = carla.Client(args.carla_host, args.carla_port)
        client.set_timeout(10.0)
        print(f"[CARLA] Connected to {args.carla_host}:{args.carla_port}")
    except Exception as e:
        print(f"[WARN] Failed to connect to CARLA: {e}")
        print(f"[WARN] Will use geometry-based relation computation (may be less accurate)")
        client = None
    
    # Check each scene
    scene_results = []
    for scen in scenarios:
        scen_id = scen.get("id", -1)
        if scen_id < 0 or scen_id > args.max_scen_id:
            continue
        
        result = check_candidate_relations_in_scene(scen, args.protocol_dir, client)
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
        print(f"  Rel type {rel_type}: {count} candidates ({count/len(all_rel_types)*100:.1f}%)")
    
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

