#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行为层离线评估脚本

评估指标：
1. 行为头分类指标（Action/Lane accuracy）
2. Preference Flip（因果线迁移）
3. No-Route-Context / No-Behavior（必要性）
"""

import sys
import os
import argparse
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
from tqdm import tqdm
import numpy as np
from typing import Dict, Any, List
from collections import defaultdict

# 添加项目根目录到路径
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from lc_org_nav.model import LCORGNet
from lc_org_nav.dataset import GoalSelectionDataset
from lc_org_nav.online_nav.behavior_policy import BehaviorPolicy, ActionType, pool_graph_embedding
from lc_org_nav.online_nav.behavior_labels import BehaviorLabelGenerator
from lc_org_nav.online_nav.lane_candidates import LaneCandidateProtocol


def evaluate_action_accuracy(
    model: LCORGNet,
    behavior_policy: BehaviorPolicy,
    dataloader: DataLoader,
    device: torch.device,
) -> Dict[str, float]:
    """评估 Action 准确率"""
    model.eval()
    behavior_policy.eval()
    
    action_correct = 0
    action_total = 0
    action_confusion = defaultdict(int)  # {(pred, true): count}
    
    with torch.no_grad():
        for sample in tqdm(dataloader, desc="Evaluating Action"):
            sample = {k: v.to(device) if torch.is_tensor(v) else v for k, v in sample.items()}
            
            # 获取必要数据
            schema_v2 = sample.get("schema_v2")
            route_context = sample.get("route_context")
            lane_candidates = sample.get("lane_candidates")
            
            if schema_v2 is None or route_context is None or lane_candidates is None:
                continue
            
            mission = schema_v2.get("mission", "FOLLOW")
            if mission != "NAVIGATE_TO":
                continue
            
            # 模型前向传播（需要获取 node_embeddings）
            outputs = model(
                node_feats=sample["node_feats"],
                edge_index=sample["edge_index"],
                edge_attr=sample["edge_attr"],
                lang_feat=sample["lang_feat"],
                candidate_mask=sample["candidate_mask"],
            )
            
            # 获取节点 embedding（需要修改模型或使用 hook）
            # 这里简化：假设可以通过某种方式获取
            # 实际实现需要修改模型 forward 返回 h_nodes
            node_embeddings = outputs.get("node_embeddings")
            if node_embeddings is None:
                continue
            
            # 池化 graph embedding
            graph_embed = pool_graph_embedding(node_embeddings, sample["candidate_mask"])
            
            # Behavior Policy 前向传播
            behavior_pref = schema_v2.get("behavior", {})
            policy_output = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context,
                behavior_pref=behavior_pref,
                lane_candidates=lane_candidates,
            )
            
            # 生成标签
            label_gen = BehaviorLabelGenerator()
            action_label, _ = label_gen.generate_action_label(
                route_context=route_context,
                behavior_pref=behavior_pref,
                lane_candidates=lane_candidates,
            )
            
            # 预测
            action_pred = int(policy_output["action_logits"].argmax().item())
            
            # 统计
            action_total += 1
            if action_pred == action_label:
                action_correct += 1
            
            action_confusion[(action_pred, action_label)] += 1
    
    accuracy = action_correct / action_total if action_total > 0 else 0.0
    
    return {
        "action_accuracy": accuracy,
        "action_total": action_total,
        "action_confusion": dict(action_confusion),
    }


def evaluate_lane_accuracy(
    model: LCORGNet,
    behavior_policy: BehaviorPolicy,
    dataloader: DataLoader,
    device: torch.device,
) -> Dict[str, float]:
    """评估 Lane 准确率（仅在变道动作时）"""
    model.eval()
    behavior_policy.eval()
    
    lane_correct = 0
    lane_total = 0
    
    with torch.no_grad():
        for sample in tqdm(dataloader, desc="Evaluating Lane"):
            sample = {k: v.to(device) if torch.is_tensor(v) else v for k, v in sample.items()}
            
            schema_v2 = sample.get("schema_v2")
            route_context = sample.get("route_context")
            lane_candidates = sample.get("lane_candidates")
            
            if schema_v2 is None or route_context is None or lane_candidates is None:
                continue
            
            mission = schema_v2.get("mission", "FOLLOW")
            if mission != "NAVIGATE_TO":
                continue
            
            # 生成 action 标签
            label_gen = BehaviorLabelGenerator()
            action_label, _ = label_gen.generate_action_label(
                route_context=route_context,
                behavior_pref=schema_v2.get("behavior", {}),
                lane_candidates=lane_candidates,
            )
            
            # 只在变道动作时评估 lane
            if action_label not in [ActionType.CHANGE_LANE_LEFT, ActionType.CHANGE_LANE_RIGHT, ActionType.MERGE]:
                continue
            
            # 模型和 policy 前向传播
            outputs = model(
                node_feats=sample["node_feats"],
                edge_index=sample["edge_index"],
                edge_attr=sample["edge_attr"],
                lang_feat=sample["lang_feat"],
                candidate_mask=sample["candidate_mask"],
            )
            
            node_embeddings = outputs.get("node_embeddings")
            if node_embeddings is None:
                continue
            
            graph_embed = pool_graph_embedding(node_embeddings, sample["candidate_mask"])
            
            policy_output = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context,
                behavior_pref=schema_v2.get("behavior", {}),
                lane_candidates=lane_candidates,
            )
            
            # 生成 lane 标签
            lane_label, _ = label_gen.generate_lane_label(
                action_label=action_label,
                lane_candidates=lane_candidates,
                route_context=route_context,
            )
            
            # 预测
            lane_probs = policy_output["lane_probs"]
            lane_pred = int(lane_probs.argmax().item())
            
            # 统计
            lane_total += 1
            if lane_pred == lane_label:
                lane_correct += 1
    
    accuracy = lane_correct / lane_total if lane_total > 0 else 0.0
    
    return {
        "lane_accuracy": accuracy,
        "lane_total": lane_total,
    }


def evaluate_preference_flip(
    model: LCORGNet,
    behavior_policy: BehaviorPolicy,
    dataloader: DataLoader,
    device: torch.device,
) -> Dict[str, float]:
    """评估 Preference Flip（因果线迁移）"""
    model.eval()
    behavior_policy.eval()
    
    action_switched = 0
    lane_switched = 0
    total_samples = 0
    
    with torch.no_grad():
        for sample in tqdm(dataloader, desc="Evaluating Preference Flip"):
            sample = {k: v.to(device) if torch.is_tensor(v) else v for k, v in sample.items()}
            
            schema_v2 = sample.get("schema_v2")
            route_context = sample.get("route_context")
            lane_candidates = sample.get("lane_candidates")
            
            if schema_v2 is None or route_context is None or lane_candidates is None:
                continue
            
            mission = schema_v2.get("mission", "FOLLOW")
            if mission != "NAVIGATE_TO":
                continue
            
            # 模型前向传播
            outputs = model(
                node_feats=sample["node_feats"],
                edge_index=sample["edge_index"],
                edge_attr=sample["edge_attr"],
                lang_feat=sample["lang_feat"],
                candidate_mask=sample["candidate_mask"],
            )
            
            node_embeddings = outputs.get("node_embeddings")
            if node_embeddings is None:
                continue
            
            graph_embed = pool_graph_embedding(node_embeddings, sample["candidate_mask"])
            
            # 测试 leftmost
            schema_v2_leftmost = schema_v2.copy()
            schema_v2_leftmost["behavior"] = schema_v2_leftmost.get("behavior", {}).copy()
            schema_v2_leftmost["behavior"]["lane_pref"] = "leftmost"
            
            policy_output_leftmost = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context,
                behavior_pref=schema_v2_leftmost.get("behavior", {}),
                lane_candidates=lane_candidates,
            )
            
            action_leftmost = int(policy_output_leftmost["action_logits"].argmax().item())
            lane_leftmost = int(policy_output_leftmost["lane_probs"].argmax().item())
            
            # 测试 rightmost
            schema_v2_rightmost = schema_v2.copy()
            schema_v2_rightmost["behavior"] = schema_v2_rightmost.get("behavior", {}).copy()
            schema_v2_rightmost["behavior"]["lane_pref"] = "rightmost"
            
            policy_output_rightmost = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context,
                behavior_pref=schema_v2_rightmost.get("behavior", {}),
                lane_candidates=lane_candidates,
            )
            
            action_rightmost = int(policy_output_rightmost["action_logits"].argmax().item())
            lane_rightmost = int(policy_output_rightmost["lane_probs"].argmax().item())
            
            # 统计切换
            total_samples += 1
            if action_leftmost != action_rightmost:
                action_switched += 1
            if lane_leftmost != lane_rightmost:
                lane_switched += 1
    
    return {
        "preference_flip_action_switch_rate": action_switched / total_samples if total_samples > 0 else 0.0,
        "preference_flip_lane_switch_rate": lane_switched / total_samples if total_samples > 0 else 0.0,
        "total_samples": total_samples,
    }


def evaluate_no_route_context(
    model: LCORGNet,
    behavior_policy: BehaviorPolicy,
    dataloader: DataLoader,
    device: torch.device,
) -> Dict[str, float]:
    """评估 No-Route-Context（必要性）"""
    model.eval()
    behavior_policy.eval()
    
    normal_merge_count = 0
    none_merge_count = 0
    total_samples = 0
    
    with torch.no_grad():
        for sample in tqdm(dataloader, desc="Evaluating No-Route-Context"):
            sample = {k: v.to(device) if torch.is_tensor(v) else v for k, v in sample.items()}
            
            schema_v2 = sample.get("schema_v2")
            route_context = sample.get("route_context")
            lane_candidates = sample.get("lane_candidates")
            
            if schema_v2 is None or route_context is None or lane_candidates is None:
                continue
            
            mission = schema_v2.get("mission", "FOLLOW")
            if mission != "NAVIGATE_TO":
                continue
            
            # 只评估临近路口/merge 的样本
            if route_context.get("next_maneuver") not in ["MERGE", "EXIT"]:
                continue
            
            # 模型前向传播
            outputs = model(
                node_feats=sample["node_feats"],
                edge_index=sample["edge_index"],
                edge_attr=sample["edge_attr"],
                lang_feat=sample["lang_feat"],
                candidate_mask=sample["candidate_mask"],
            )
            
            node_embeddings = outputs.get("node_embeddings")
            if node_embeddings is None:
                continue
            
            graph_embed = pool_graph_embedding(node_embeddings, sample["candidate_mask"])
            behavior_pref = schema_v2.get("behavior", {})
            
            # 正常 route_context
            policy_output_normal = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context,
                behavior_pref=behavior_pref,
                lane_candidates=lane_candidates,
            )
            action_normal = int(policy_output_normal["action_logits"].argmax().item())
            
            # 无 route_context（默认值）
            from lc_org_nav.query_schema import QuerySchema
            route_context_none = QuerySchema._get_default_route_context()
            
            policy_output_none = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context_none,
                behavior_pref=behavior_pref,
                lane_candidates=lane_candidates,
            )
            action_none = int(policy_output_none["action_logits"].argmax().item())
            
            # 统计
            total_samples += 1
            if action_normal == ActionType.MERGE:
                normal_merge_count += 1
            if action_none == ActionType.MERGE:
                none_merge_count += 1
    
    return {
        "normal_merge_rate": normal_merge_count / total_samples if total_samples > 0 else 0.0,
        "none_merge_rate": none_merge_count / total_samples if total_samples > 0 else 0.0,
        "merge_reduction": (normal_merge_count - none_merge_count) / total_samples if total_samples > 0 else 0.0,
        "total_samples": total_samples,
    }


def evaluate_no_behavior(
    model: LCORGNet,
    behavior_policy: BehaviorPolicy,
    dataloader: DataLoader,
    device: torch.device,
) -> Dict[str, float]:
    """评估 No-Behavior（偏好必要性）"""
    model.eval()
    behavior_policy.eval()
    
    with_pref_switched = 0
    without_pref_switched = 0
    total_samples = 0
    
    with torch.no_grad():
        for sample in tqdm(dataloader, desc="Evaluating No-Behavior"):
            sample = {k: v.to(device) if torch.is_tensor(v) else v for k, v in sample.items()}
            
            schema_v2 = sample.get("schema_v2")
            route_context = sample.get("route_context")
            lane_candidates = sample.get("lane_candidates")
            
            if schema_v2 is None or route_context is None or lane_candidates is None:
                continue
            
            mission = schema_v2.get("mission", "FOLLOW")
            if mission != "NAVIGATE_TO":
                continue
            
            # 模型前向传播
            outputs = model(
                node_feats=sample["node_feats"],
                edge_index=sample["edge_index"],
                edge_attr=sample["edge_attr"],
                lang_feat=sample["lang_feat"],
                candidate_mask=sample["candidate_mask"],
            )
            
            node_embeddings = outputs.get("node_embeddings")
            if node_embeddings is None:
                continue
            
            graph_embed = pool_graph_embedding(node_embeddings, sample["candidate_mask"])
            
            # 有偏好（leftmost）
            behavior_pref_with = {"lane_pref": "leftmost", "overtake": "any", "yield_to": "any"}
            policy_output_with = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context,
                behavior_pref=behavior_pref_with,
                lane_candidates=lane_candidates,
            )
            lane_with_leftmost = int(policy_output_with["lane_probs"].argmax().item())
            
            # 有偏好（rightmost）
            behavior_pref_with_rightmost = {"lane_pref": "rightmost", "overtake": "any", "yield_to": "any"}
            policy_output_with_rightmost = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context,
                behavior_pref=behavior_pref_with_rightmost,
                lane_candidates=lane_candidates,
            )
            lane_with_rightmost = int(policy_output_with_rightmost["lane_probs"].argmax().item())
            
            # 无偏好（any）
            behavior_pref_without = {"lane_pref": "any", "overtake": "any", "yield_to": "any"}
            policy_output_without_leftmost = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context,
                behavior_pref=behavior_pref_without,
                lane_candidates=lane_candidates,
            )
            lane_without_leftmost = int(policy_output_without_leftmost["lane_probs"].argmax().item())
            
            policy_output_without_rightmost = behavior_policy(
                graph_embed=graph_embed,
                route_context=route_context,
                behavior_pref=behavior_pref_without,
                lane_candidates=lane_candidates,
            )
            lane_without_rightmost = int(policy_output_without_rightmost["lane_probs"].argmax().item())
            
            # 统计
            total_samples += 1
            if lane_with_leftmost != lane_with_rightmost:
                with_pref_switched += 1
            if lane_without_leftmost != lane_without_rightmost:
                without_pref_switched += 1
    
    return {
        "with_pref_switch_rate": with_pref_switched / total_samples if total_samples > 0 else 0.0,
        "without_pref_switch_rate": without_pref_switched / total_samples if total_samples > 0 else 0.0,
        "preference_necessity": (with_pref_switched - without_pref_switched) / total_samples if total_samples > 0 else 0.0,
        "total_samples": total_samples,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate Behavior Layer Offline")
    parser.add_argument("--data-list", type=str, required=True, help="Data list file")
    parser.add_argument("--model-checkpoint", type=str, required=True, help="Model checkpoint path")
    parser.add_argument("--behavior-checkpoint", type=str, help="Behavior policy checkpoint path")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--eval-mode", type=str, default="all", choices=["all", "action", "lane", "preference", "no_route", "no_behavior"])
    
    args = parser.parse_args()
    
    device = torch.device(args.device)
    
    # 加载数据集
    dataset = GoalSelectionDataset(args.data_list)
    dataloader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False)
    
    # 加载模型
    model = LCORGNet(
        node_feat_dim=32,
        edge_feat_dim=16,
        lang_feat_dim=128,
        hidden_dim=128,
    ).to(device)
    
    checkpoint = torch.load(args.model_checkpoint, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    
    # 加载 Behavior Policy
    behavior_policy = BehaviorPolicy(hidden_dim=128).to(device)
    if args.behavior_checkpoint:
        behavior_checkpoint = torch.load(args.behavior_checkpoint, map_location=device)
        behavior_policy.load_state_dict(behavior_checkpoint["behavior_policy_state_dict"])
    
    print("=" * 80)
    print("Behavior Layer Offline Evaluation")
    print("=" * 80)
    
    results = {}
    
    if args.eval_mode in ["all", "action"]:
        print("\n[1/5] Evaluating Action Accuracy...")
        results["action"] = evaluate_action_accuracy(model, behavior_policy, dataloader, device)
        print(f"  Action Accuracy: {results['action']['action_accuracy']:.4f}")
        print(f"  Total Samples: {results['action']['action_total']}")
    
    if args.eval_mode in ["all", "lane"]:
        print("\n[2/5] Evaluating Lane Accuracy...")
        results["lane"] = evaluate_lane_accuracy(model, behavior_policy, dataloader, device)
        print(f"  Lane Accuracy: {results['lane']['lane_accuracy']:.4f}")
        print(f"  Total Samples: {results['lane']['lane_total']}")
    
    if args.eval_mode in ["all", "preference"]:
        print("\n[3/5] Evaluating Preference Flip...")
        results["preference_flip"] = evaluate_preference_flip(model, behavior_policy, dataloader, device)
        print(f"  Action Switch Rate: {results['preference_flip']['preference_flip_action_switch_rate']:.4f}")
        print(f"  Lane Switch Rate: {results['preference_flip']['preference_flip_lane_switch_rate']:.4f}")
    
    if args.eval_mode in ["all", "no_route"]:
        print("\n[4/5] Evaluating No-Route-Context...")
        results["no_route_context"] = evaluate_no_route_context(model, behavior_policy, dataloader, device)
        print(f"  Normal MERGE Rate: {results['no_route_context']['normal_merge_rate']:.4f}")
        print(f"  None MERGE Rate: {results['no_route_context']['none_merge_rate']:.4f}")
        print(f"  MERGE Reduction: {results['no_route_context']['merge_reduction']:.4f}")
    
    if args.eval_mode in ["all", "no_behavior"]:
        print("\n[5/5] Evaluating No-Behavior...")
        results["no_behavior"] = evaluate_no_behavior(model, behavior_policy, dataloader, device)
        print(f"  With Preference Switch Rate: {results['no_behavior']['with_pref_switch_rate']:.4f}")
        print(f"  Without Preference Switch Rate: {results['no_behavior']['without_pref_switch_rate']:.4f}")
        print(f"  Preference Necessity: {results['no_behavior']['preference_necessity']:.4f}")
    
    # 保存结果
    output_file = "behavior_eval_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        import json
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to {output_file}")
    print("\nEvaluation completed!")


if __name__ == "__main__":
    main()

