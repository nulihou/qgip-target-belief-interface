#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评估关系重要性：在关系多样性子集上评估Full GS和No-Relation

实验：
1. Full GS评估（关系多样性子集）
2. No-Relation评估（关系多样性子集）
3. 关系翻转评估（反事实测试，可选）
"""

import os
import sys
import json
import argparse
import numpy as np
import torch
from pathlib import Path
from typing import List, Dict, Any, Optional
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

from lc_org_nav.online_nav.gs_loader import load_gs_model

# 常量：关系信息在lang_feat中（前5维是关系onehot）
NUM_REL_TYPES = 5
LANG_FEAT_DIM = 32  # lang_feat总维度
REL_ONEHOT_DIM = 5  # lang_feat的前5维是关系onehot


def perturb_no_relation(lang_feat: torch.Tensor) -> torch.Tensor:
    """
    扰动：No-Relation
    将lang_feat的前5维（关系onehot）全置0，保留其他语言特征
    """
    lang_feat_perturbed = lang_feat.clone()
    lang_feat_perturbed[:REL_ONEHOT_DIM] = 0.0
    return lang_feat_perturbed


def perturb_flipped_relation(lang_feat: torch.Tensor) -> torch.Tensor:
    """
    扰动：关系翻转（反事实测试）
    将关系类型翻转：front↔behind, left↔right, near保持不变
    """
    lang_feat_perturbed = lang_feat.clone()
    rel_onehot = lang_feat_perturbed[:REL_ONEHOT_DIM].clone()
    
    # 找到当前关系类型
    rel_type = int(torch.argmax(rel_onehot))
    
    # 翻转关系类型
    flip_map = {
        0: 0,  # near -> near (不变)
        1: 2,  # front -> behind
        2: 1,  # behind -> front
        3: 4,  # left -> right
        4: 3,  # right -> left
    }
    
    flipped_rel_type = flip_map.get(rel_type, 0)
    
    # 设置新的关系onehot
    lang_feat_perturbed[:REL_ONEHOT_DIM] = 0.0
    lang_feat_perturbed[flipped_rel_type] = 1.0
    
    return lang_feat_perturbed


def evaluate_protoacc(
    model,
    protocol_dir: str,
    device: torch.device,
    max_scen_id: int = 24,
    perturbation: Optional[str] = None,
) -> Dict[str, Any]:
    """
    评估ProtoAcc（协议级准确率）
    
    Args:
        model: 加载的模型
        protocol_dir: 协议图目录
        device: 设备
        max_scen_id: 最大场景ID
        perturbation: 扰动类型（None/'no_rel'/'flip_rel'）
    
    Returns:
        包含ProtoAcc和详细结果的字典
    """
    model.eval()
    correct_count = 0
    total_count = 0
    results = []
    
    for scen_id in range(max_scen_id + 1):
        npz_path = os.path.join(protocol_dir, f"scen_{scen_id:03d}.npz")
        
        if not os.path.exists(npz_path):
            print(f"[WARN] scen_{scen_id:03d}: Protocol graph not found, skipping")
            continue
        
        try:
            data = np.load(npz_path, allow_pickle=False)
            
            # Extract data
            node_feats = torch.from_numpy(data["node_feats"]).float().to(device)
            edge_index = torch.from_numpy(data["edge_index"]).long().to(device)
            edge_attr = torch.from_numpy(data["edge_attr"]).float().to(device)
            lang_feat = torch.from_numpy(data["lang_feat"]).float().to(device)
            cand_mask_np = data["candidate_mask"].astype(bool)
            candidate_mask = torch.from_numpy(cand_mask_np).bool().to(device)
            target_idx_gt = int(data["target_idx_gt"])
            
            # Apply perturbation
            original_lang_feat = lang_feat.clone()
            if perturbation == "no_rel":
                lang_feat = perturb_no_relation(lang_feat)
            elif perturbation == "flip_rel":
                lang_feat = perturb_flipped_relation(lang_feat)
            
            # Debug: check if perturbation actually changed lang_feat
            if perturbation and scen_id < 3:  # Debug first 3 scenes
                rel_original = original_lang_feat[:REL_ONEHOT_DIM].cpu().numpy()
                rel_perturbed = lang_feat[:REL_ONEHOT_DIM].cpu().numpy()
                if np.array_equal(rel_original, rel_perturbed):
                    print(f"[WARN] scen_{scen_id:03d}: Perturbation did not change lang_feat!")
                    print(f"  Original: {rel_original}")
                    print(f"  Perturbed: {rel_perturbed}")
            
            # Model inference
            with torch.no_grad():
                outputs = model.forward_single(
                    node_feats=node_feats,
                    edge_index=edge_index,
                    edge_attr=edge_attr,
                    lang_feat=lang_feat,
                    candidate_mask=candidate_mask,
                )
                goal_logits = outputs["goal_logits"]  # (N,)
            
            # 只在候选集合上取 argmax
            logits = goal_logits.view(-1)
            cand_indices = np.nonzero(cand_mask_np)[0]
            logits_cands = logits[candidate_mask]  # shape (K,)
            k_best = torch.argmax(logits_cands).item()
            chosen_idx = int(cand_indices[k_best])
            
            gs_correct = (chosen_idx == target_idx_gt)
            correct_count += int(gs_correct)
            total_count += 1
            
            results.append({
                "scen_id": scen_id,
                "chosen_idx": chosen_idx,
                "target_idx_gt": target_idx_gt,
                "gs_correct": gs_correct,
            })
            
        except Exception as e:
            print(f"[ERROR] scen_{scen_id:03d}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    protoacc = (correct_count / total_count * 100.0) if total_count > 0 else 0.0
    
    return {
        "protoacc": protoacc,
        "correct_count": correct_count,
        "total_count": total_count,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate relation importance on relation-diverse scenarios"
    )
    parser.add_argument(
        "--protocol-dir",
        type=str,
        default="scripts/online_multi/protocol_graphs_diverse",
        help="Directory containing relation-diverse protocol graphs"
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt",
        help="Path to GS model checkpoint"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/proto_main_eval/relation_importance_eval.json",
        help="Output JSON path"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
        help="Device (cuda/cpu)"
    )
    parser.add_argument(
        "--max-scen-id",
        type=int,
        default=24,
        help="Maximum scene ID to evaluate (default: 24 for 25 scenes)"
    )
    parser.add_argument(
        "--run-flip-test",
        action="store_true",
        help="Run relation flip test (counterfactual)"
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Relation Importance Evaluation")
    print("=" * 80)
    print(f"[Config] Protocol dir: {args.protocol_dir}")
    print(f"[Config] Checkpoint: {args.checkpoint}")
    print(f"[Config] Device: {args.device}")
    print(f"[Config] Max scen_id: {args.max_scen_id}")
    print(f"[Config] Run flip test: {args.run_flip_test}")
    
    # Load model
    device = torch.device(args.device)
    print(f"\n[Model] Loading GS model...")
    model = load_gs_model(args.checkpoint, device)
    print(f"[Model] Model loaded successfully")
    
    # 1. Full GS evaluation
    print("\n[1/3] Evaluating Full GS...")
    full_result = evaluate_protoacc(
        model,
        args.protocol_dir,
        device,
        max_scen_id=args.max_scen_id,
        perturbation=None,
    )
    print(f"  ProtoAcc: {full_result['protoacc']:.1f}% ({full_result['correct_count']}/{full_result['total_count']})")
    
    # 2. No-Relation evaluation
    print("\n[2/3] Evaluating No-Relation...")
    no_rel_result = evaluate_protoacc(
        model,
        args.protocol_dir,
        device,
        max_scen_id=args.max_scen_id,
        perturbation="no_rel",
    )
    print(f"  ProtoAcc: {no_rel_result['protoacc']:.1f}% ({no_rel_result['correct_count']}/{no_rel_result['total_count']})")
    
    # 3. Relation flip evaluation (optional)
    flip_result = None
    if args.run_flip_test:
        print("\n[3/3] Evaluating Relation Flip (Counterfactual)...")
        flip_result = evaluate_protoacc(
            model,
            args.protocol_dir,
            device,
            max_scen_id=args.max_scen_id,
            perturbation="flip_rel",
        )
        print(f"  ProtoAcc: {flip_result['protoacc']:.1f}% ({flip_result['correct_count']}/{flip_result['total_count']})")
    
    # Calculate drops
    drop_no_rel = full_result['protoacc'] - no_rel_result['protoacc']
    drop_flip = None
    if flip_result:
        drop_flip = full_result['protoacc'] - flip_result['protoacc']
    
    print("\n" + "=" * 80)
    print("Results Summary")
    print("=" * 80)
    print(f"Full GS:           {full_result['protoacc']:.1f}%")
    print(f"No-Relation:       {no_rel_result['protoacc']:.1f}% (drop: {drop_no_rel:.1f}%)")
    if flip_result:
        print(f"Relation Flip:     {flip_result['protoacc']:.1f}% (drop: {drop_flip:.1f}%)")
    
    # Save results (include detailed results for analysis)
    results = {
        "full_gs": {
            "protoacc": full_result["protoacc"],
            "correct_count": full_result["correct_count"],
            "total_count": full_result["total_count"],
            "results": full_result["results"],  # Include detailed results
        },
        "no_relation": {
            "protoacc": no_rel_result["protoacc"],
            "correct_count": no_rel_result["correct_count"],
            "total_count": no_rel_result["total_count"],
            "drop": float(drop_no_rel),
            "results": no_rel_result["results"],  # Include detailed results
        },
    }
    
    if flip_result:
        results["relation_flip"] = {
            "protoacc": flip_result["protoacc"],
            "correct_count": flip_result["correct_count"],
            "total_count": flip_result["total_count"],
            "drop": float(drop_flip),
            "results": flip_result["results"],  # Include detailed results
        }
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n[Done] Results saved to {args.output}")


if __name__ == "__main__":
    main()
