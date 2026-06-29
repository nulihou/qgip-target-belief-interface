#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析离线GS评估结果的分组统计

按候选数K分组（K=2 vs K=3）
按距离区间分组（30-40/40-50/50-60m）
"""

import os
import sys
import json
import argparse
import torch
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Tuple

# Add project root to path
sys.path.insert(0, os.getcwd())

try:
    from torch.utils.data import DataLoader
    from lc_org_nav.config import TrainConfig
    from lc_org_nav.dataset import GoalSelectionDataset
    from lc_org_nav.model import LCORGNet
except ImportError as e:
    print(f"[ERROR] Failed to import required modules: {e}")
    print("[INFO] Make sure you're in the project root directory")
    sys.exit(1)


def move_to_device(sample: Dict[str, Any], device: torch.device) -> Dict[str, Any]:
    """Move sample to device"""
    out = {}
    for k, v in sample.items():
        if isinstance(v, torch.Tensor):
            out[k] = v.to(device)
        else:
            out[k] = v
    return out


def bucket_dist(d: float) -> str:
    """按距离分桶"""
    if d < 40:
        return "30–40m"
    elif d < 50:
        return "40–50m"
    else:
        return "50–60m"


def load_model(checkpoint_path: str, device: torch.device) -> LCORGNet:
    """加载模型"""
    cfg = TrainConfig()
    model = LCORGNet(
        node_feat_dim=cfg.node_feat_dim,
        edge_feat_dim=cfg.edge_feat_dim,
        lang_feat_dim=cfg.lang_feat_dim,
        hidden_dim=cfg.hidden_dim,
        num_layers=cfg.num_layers,
        num_rel_types=cfg.num_rel_types,
        use_rel_gate=getattr(cfg, "use_rel_gate", False),
    ).to(device)
    
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    
    state = torch.load(checkpoint_path, map_location=device, weights_only=False)
    
    # 兼容几种常见保存格式
    if isinstance(state, dict) and "model_state_dict" in state:
        state = state["model_state_dict"]
    elif isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]
    elif isinstance(state, dict) and "model" in state and isinstance(state["model"], dict):
        state = state["model"]
    
    model.load_state_dict(state)
    model.eval()
    return model


def evaluate_offline_grouped(
    model: LCORGNet,
    test_list_path: str,
    device: torch.device,
    output_path: str = None,
) -> Dict[str, Any]:
    """
    评估离线GS性能，按候选数和距离分组
    """
    # 加载测试集
    if not os.path.exists(test_list_path):
        raise FileNotFoundError(f"Test list not found: {test_list_path}")
    
    with open(test_list_path, 'r', encoding='utf-8') as f:
        paths = [line.strip() for line in f if line.strip()]
    
    existing_paths = [p for p in paths if os.path.exists(p)]
    if not existing_paths:
        raise RuntimeError(f"No valid files found in test list: {test_list_path}")
    
    print(f"[INFO] Found {len(existing_paths)} test samples")
    
    dataset = GoalSelectionDataset(existing_paths)
    loader = DataLoader(dataset, batch_size=1, shuffle=False)
    
    # 分组统计
    by_k = defaultdict(lambda: {"total": 0, "correct": 0})
    by_dist = defaultdict(lambda: {"total": 0, "correct": 0})
    all_records = []
    
    with torch.no_grad():
        for batch_idx, sample in enumerate(loader, start=1):
            sample = move_to_device(sample, device)
            
            outputs = model(
                node_feats=sample["node_feats"],
                edge_index=sample["edge_index"],
                edge_attr=sample["edge_attr"],
                lang_feat=sample["lang_feat"],
                candidate_mask=sample["candidate_mask"],
            )
            goal_logits = outputs["goal_logits"]
            
            # 统一成 (B, N)
            if goal_logits.dim() == 1:
                goal_logits = goal_logits.unsqueeze(0)
            
            B = goal_logits.size(0)
            for b in range(B):
                logits_nodes = goal_logits[b]
                
                # candidate_mask
                cand_mask_tensor = sample["candidate_mask"]
                if isinstance(cand_mask_tensor, torch.Tensor) and cand_mask_tensor.dim() == 2:
                    cand_mask = cand_mask_tensor[b]
                else:
                    cand_mask = cand_mask_tensor
                
                # target_index
                if isinstance(sample["target_index"], torch.Tensor):
                    if sample["target_index"].dim() > 0:
                        target_index = int(sample["target_index"][b].item())
                    else:
                        target_index = int(sample["target_index"].item())
                else:
                    target_index = int(sample["target_index"])
                
                cand_indices = torch.nonzero(cand_mask, as_tuple=False).squeeze(-1)
                if cand_indices.numel() == 0:
                    continue
                
                logits_cand = logits_nodes[cand_indices]
                _, sorted_idx = torch.sort(logits_cand, descending=True)
                top1_cand_idx = cand_indices[sorted_idx[0]].item()
                
                # 判断是否正确
                correct = (top1_cand_idx == target_index)
                
                # 获取候选数
                k = int(cand_mask.sum().item())
                
                # 获取距离（从node_feats中提取）
                # node_feats的第7维（索引7）是d_a（anchor-relative距离）
                # 对于target节点，这就是ego到target的距离
                node_feats_b = sample["node_feats"]
                if isinstance(node_feats_b, torch.Tensor) and node_feats_b.dim() == 3:
                    node_feats_b = node_feats_b[b]  # (N, 32)
                elif isinstance(node_feats_b, torch.Tensor) and node_feats_b.dim() == 2:
                    pass  # 已经是(N, 32)
                else:
                    node_feats_b = torch.tensor(node_feats_b)
                
                # 提取target节点的d_a值（索引7）
                if target_index < node_feats_b.shape[0]:
                    start_dist = float(node_feats_b[target_index, 7].item())
                else:
                    # 如果target_index无效，尝试从所有候选节点中找到最小的d_a
                    if cand_indices.numel() > 0:
                        cand_d_a = node_feats_b[cand_indices, 7]
                        start_dist = float(cand_d_a.min().item())
                    else:
                        start_dist = 0.0
                
                dist_bucket = bucket_dist(start_dist)
                
                # 统计
                by_k[k]["total"] += 1
                by_k[k]["correct"] += int(correct)
                
                by_dist[dist_bucket]["total"] += 1
                by_dist[dist_bucket]["correct"] += int(correct)
                
                # 保存记录
                all_records.append({
                    "k": k,
                    "start_dist": start_dist,
                    "dist_bucket": dist_bucket,
                    "correct": correct,
                    "target_idx": target_index,
                    "chosen_idx": top1_cand_idx,
                })
                
                if batch_idx % 100 == 0:
                    print(f"  Processed {batch_idx}/{len(existing_paths)} samples")
    
    # 计算准确率
    results = {
        "by_k": {},
        "by_dist": {},
        "total": len(all_records),
        "overall_correct": sum(1 for r in all_records if r["correct"]),
    }
    
    for k in sorted(by_k.keys()):
        t = by_k[k]["total"]
        c = by_k[k]["correct"]
        acc = c / t * 100 if t > 0 else 0.0
        results["by_k"][k] = {
            "total": t,
            "correct": c,
            "accuracy": acc,
        }
    
    for b in sorted(by_dist.keys()):
        t = by_dist[b]["total"]
        c = by_dist[b]["correct"]
        acc = c / t * 100 if t > 0 else 0.0
        results["by_dist"][b] = {
            "total": t,
            "correct": c,
            "accuracy": acc,
        }
    
    results["overall_accuracy"] = results["overall_correct"] / results["total"] * 100 if results["total"] > 0 else 0.0
    
    # 保存结果
    if output_path:
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n[Save] Results saved to {output_path}")
    
    return results


def print_results(results: Dict[str, Any]):
    """打印结果"""
    print("\n" + "="*80)
    print("Offline GS Performance (Grouped Analysis)")
    print("="*80)
    
    print(f"\nOverall: {results['overall_correct']}/{results['total']} ({results['overall_accuracy']:.1f}%)")
    
    print("\n=== GS@1 by #candidates ===")
    for k in sorted(results["by_k"].keys()):
        r = results["by_k"][k]
        print(f"K={k}: {r['correct']}/{r['total']} ({r['accuracy']:.1f}%)")
    
    print("\n=== GS@1 by distance bucket ===")
    for b in sorted(results["by_dist"].keys()):
        r = results["by_dist"][b]
        print(f"{b}: {r['correct']}/{r['total']} ({r['accuracy']:.1f}%)")


def generate_table(results: Dict[str, Any]) -> str:
    """生成论文表格"""
    table = "\n" + "="*80 + "\n"
    table += "Table: Offline GS Performance (Grouped by #Candidates and Distance)\n"
    table += "="*80 + "\n\n"
    
    # 按候选数分组
    table += "| #Candidates | GS@1 | Samples |\n"
    table += "|-------------|------|----------|\n"
    for k in sorted(results["by_k"].keys()):
        r = results["by_k"][k]
        table += f"| K={k} | {r['accuracy']:.1f}% | {r['total']} |\n"
    
    table += "\n"
    
    # 按距离分组
    table += "| Distance Range | GS@1 | Samples |\n"
    table += "|----------------|------|----------|\n"
    for b in sorted(results["by_dist"].keys()):
        r = results["by_dist"][b]
        table += f"| {b} | {r['accuracy']:.1f}% | {r['total']} |\n"
    
    return table


def main():
    parser = argparse.ArgumentParser(description="Analyze Offline GS Performance (Grouped)")
    parser.add_argument(
        "--checkpoint",
        type=str,
        default="outputs_v2/multitask_mixed_v2_online_multi_rank/seed_42/best_lc_org_mtl_mixed.pt",
        help="Model checkpoint path"
    )
    parser.add_argument(
        "--test-list",
        type=str,
        default="data/lists/multi_test_list.txt",
        help="Test list path"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/proto_main_eval/offline_grouped_analysis.json",
        help="Output JSON file"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Device (cuda/cpu)"
    )
    
    args = parser.parse_args()
    
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    print(f"[INFO] Using device: {device}")
    
    # 加载模型
    print(f"[INFO] Loading model from: {args.checkpoint}")
    model = load_model(args.checkpoint, device)
    
    # 评估
    print(f"[INFO] Evaluating on: {args.test_list}")
    results = evaluate_offline_grouped(
        model=model,
        test_list_path=args.test_list,
        device=device,
        output_path=args.output,
    )
    
    # 打印结果
    print_results(results)
    
    # 生成表格
    table = generate_table(results)
    print(table)
    
    # 保存表格到markdown文件
    table_path = Path(args.output).with_suffix('.md')
    with open(table_path, 'w', encoding='utf-8') as f:
        f.write("# Offline GS Performance (Grouped Analysis)\n\n")
        f.write(f"**Analysis Date**: 2025-11-23\n\n")
        f.write(table)
    print(f"\n[Save] Table saved to {table_path}")


if __name__ == "__main__":
    main()

