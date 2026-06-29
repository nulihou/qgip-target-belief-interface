#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
行为层训练脚本

支持：
- Stage A: 只训 action_head + lane_head（冻结 GNN 主干）
- Stage B: 联合训练（解冻部分 backbone）
- Stage C: 全量对齐（可选）
"""

import sys
import os
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from tqdm import tqdm
import json
from typing import Dict, Any, Optional

# 添加项目根目录到路径
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from lc_org_nav.model import LCORGNet
from lc_org_nav.dataset import GoalSelectionDataset
from lc_org_nav.trainer_behavior import BehaviorLayerTrainer, create_behavior_policy_from_model
from lc_org_nav.online_nav.behavior_policy import BehaviorPolicy
from lc_org_nav.online_nav.lane_candidates import LaneCandidateProtocol
from lc_org_nav.online_nav.behavior_labels import BehaviorLabelGenerator


def load_or_create_schema_v2(sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 sample 加载或创建 schema_v2"""
    # 尝试从 sample 读取
    if "schema_v2" in sample:
        return sample["schema_v2"]
    
    # 尝试从其他字段重建（如果可能）
    # 这里简化：返回 None，实际应该根据数据格式重建
    return None


def load_or_create_route_context(sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 sample 加载或创建 route_context"""
    # 尝试从 sample 读取
    if "route_context" in sample:
        return sample["route_context"]
    
    # 返回默认值
    from lc_org_nav.query_schema import QuerySchema
    return QuerySchema._get_default_route_context()


def create_lane_candidates_offline(
    sample: Dict[str, Any],
    carla_map: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    """
    离线创建 lane candidates（训练时）
    
    注意：训练时可能没有 CARLA map，这里返回 mock 数据
    实际实现应该从 sample 中读取或使用保存的 lane_candidates
    """
    # 尝试从 sample 读取
    if "lane_candidates" in sample:
        return sample["lane_candidates"]
    
    # 如果没有，返回 None（训练时会跳过行为损失）
    return None


def train_epoch(
    model: LCORGNet,
    behavior_policy: BehaviorPolicy,
    train_loader: DataLoader,
    optimizer: optim.Optimizer,
    device: torch.device,
    trainer: BehaviorLayerTrainer,
    stage: str = "A",
    carla_map: Optional[Any] = None,
) -> Dict[str, float]:
    """
    训练一个 epoch
    
    Args:
        stage: "A" (只训行为头), "B" (联合训练), "C" (全量对齐)
    """
    model.train()
    behavior_policy.train()
    
    # 根据 stage 设置参数冻结
    if stage == "A":
        # Stage A: 冻结 GNN 主干
        for param in model.parameters():
            param.requires_grad = False
        for param in behavior_policy.parameters():
            param.requires_grad = True
    elif stage == "B":
        # Stage B: 解冻部分 backbone
        for param in model.parameters():
            param.requires_grad = True
        for param in behavior_policy.parameters():
            param.requires_grad = True
    else:  # Stage C
        # Stage C: 全量训练
        for param in model.parameters():
            param.requires_grad = True
        for param in behavior_policy.parameters():
            param.requires_grad = True
    
    total_loss = 0.0
    total_goal_loss = 0.0
    total_action_loss = 0.0
    total_lane_loss = 0.0
    num_batches = 0
    
    trainer.reset_stats()
    
    for batch_idx, sample in enumerate(tqdm(train_loader, desc=f"Training (Stage {stage})")):
        # 移动到设备
        sample = {k: v.to(device) if torch.is_tensor(v) else v for k, v in sample.items()}
        
        # 获取或创建必要数据
        schema_v2 = load_or_create_schema_v2(sample)
        route_context = load_or_create_route_context(sample)
        lane_candidates = create_lane_candidates_offline(sample, carla_map)
        
        # 模型前向传播
        outputs = model(
            node_feats=sample["node_feats"],
            edge_index=sample["edge_index"],
            edge_attr=sample["edge_attr"],
            lang_feat=sample["lang_feat"],
            candidate_mask=sample["candidate_mask"],
        )
        
        # 如果需要行为损失，需要节点 embedding
        # 这里简化：假设可以通过修改模型 forward 返回
        # 实际实现需要修改模型或使用 hook
        
        # 计算损失
        losses, stats = trainer.compute_losses(
            sample=sample,
            outputs=outputs,
            route_context=route_context,
            lane_candidates=lane_candidates,
            schema_v2=schema_v2,
        )
        
        # 反向传播
        optimizer.zero_grad()
        losses["total"].backward()
        optimizer.step()
        
        # 累计损失
        total_loss += losses["total"].item()
        total_goal_loss += losses["goal"].item()
        total_action_loss += losses["action"].item()
        total_lane_loss += losses["lane"].item()
        num_batches += 1
        
        # 定期打印
        if batch_idx % 100 == 0:
            print(f"\n  Batch {batch_idx}:")
            print(f"    Total loss: {losses['total'].item():.4f}")
            print(f"    Goal loss: {losses['goal'].item():.4f}")
            print(f"    Action loss: {losses['action'].item():.4f}")
            print(f"    Lane loss: {losses['lane'].item():.4f}")
            print(f"    Action enabled: {stats['action_loss_enabled']}")
            print(f"    Lane enabled: {stats['lane_loss_enabled']}")
    
    # 获取统计摘要
    stats_summary = trainer.get_stats_summary()
    
    return {
        "avg_loss": total_loss / num_batches if num_batches > 0 else 0.0,
        "avg_goal_loss": total_goal_loss / num_batches if num_batches > 0 else 0.0,
        "avg_action_loss": total_action_loss / num_batches if num_batches > 0 else 0.0,
        "avg_lane_loss": total_lane_loss / num_batches if num_batches > 0 else 0.0,
        **stats_summary,
    }


def evaluate(
    model: LCORGNet,
    behavior_policy: BehaviorPolicy,
    val_loader: DataLoader,
    device: torch.device,
    trainer: BehaviorLayerTrainer,
    carla_map: Optional[Any] = None,
) -> Dict[str, float]:
    """评估"""
    model.eval()
    behavior_policy.eval()
    
    total_loss = 0.0
    num_batches = 0
    
    action_correct = 0
    action_total = 0
    lane_correct = 0
    lane_total = 0
    
    trainer.reset_stats()
    
    with torch.no_grad():
        for sample in tqdm(val_loader, desc="Evaluating"):
            sample = {k: v.to(device) if torch.is_tensor(v) else v for k, v in sample.items()}
            
            schema_v2 = load_or_create_schema_v2(sample)
            route_context = load_or_create_route_context(sample)
            lane_candidates = create_lane_candidates_offline(sample, carla_map)
            
            outputs = model(
                node_feats=sample["node_feats"],
                edge_index=sample["edge_index"],
                edge_attr=sample["edge_attr"],
                lang_feat=sample["lang_feat"],
                candidate_mask=sample["candidate_mask"],
            )
            
            losses, stats = trainer.compute_losses(
                sample=sample,
                outputs=outputs,
                route_context=route_context,
                lane_candidates=lane_candidates,
                schema_v2=schema_v2,
            )
            
            total_loss += losses["total"].item()
            num_batches += 1
            
            # 计算准确率（如果有标签）
            # 这里简化，实际需要从 sample 读取 action_label 和 lane_label
    
    stats_summary = trainer.get_stats_summary()
    
    return {
        "avg_loss": total_loss / num_batches if num_batches > 0 else 0.0,
        **stats_summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Train Behavior Layer")
    parser.add_argument("--train-list", type=str, required=True, help="Training data list file")
    parser.add_argument("--val-list", type=str, help="Validation data list file")
    parser.add_argument("--stage", type=str, default="A", choices=["A", "B", "C"], help="Training stage")
    parser.add_argument("--num-epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=1, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--action-weight", type=float, default=1.0, help="Action loss weight")
    parser.add_argument("--lane-weight", type=float, default=0.5, help="Lane loss weight")
    parser.add_argument("--goal-weight", type=float, default=1.0, help="Goal loss weight")
    parser.add_argument("--device", type=str, default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--output-dir", type=str, default="./checkpoints/behavior_layer")
    
    args = parser.parse_args()
    
    device = torch.device(args.device)
    
    # 创建数据集
    train_dataset = GoalSelectionDataset(args.train_list)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    
    val_loader = None
    if args.val_list:
        val_dataset = GoalSelectionDataset(args.val_list)
        val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)
    
    # 创建模型
    # 假设从配置文件或检查点加载
    model = LCORGNet(
        node_feat_dim=32,  # 根据实际数据调整
        edge_feat_dim=16,
        lang_feat_dim=128,
        hidden_dim=128,
    ).to(device)
    
    # 创建 Behavior Policy
    behavior_policy = create_behavior_policy_from_model(model, hidden_dim=128).to(device)
    
    # 创建训练器
    trainer = BehaviorLayerTrainer(
        model=model,
        behavior_policy=behavior_policy,
        device=device,
        action_weight=args.action_weight,
        lane_weight=args.lane_weight,
        goal_weight=args.goal_weight,
    )
    
    # 创建优化器
    if args.stage == "A":
        # Stage A: 只优化 behavior_policy
        optimizer = optim.Adam(behavior_policy.parameters(), lr=args.lr)
    else:
        # Stage B/C: 优化所有参数
        optimizer = optim.Adam(
            list(model.parameters()) + list(behavior_policy.parameters()),
            lr=args.lr,
        )
    
    # 训练循环
    os.makedirs(args.output_dir, exist_ok=True)
    
    for epoch in range(1, args.num_epochs + 1):
        print(f"\n{'='*80}")
        print(f"Epoch {epoch}/{args.num_epochs} (Stage {args.stage})")
        print(f"{'='*80}")
        
        train_metrics = train_epoch(
            model=model,
            behavior_policy=behavior_policy,
            train_loader=train_loader,
            optimizer=optimizer,
            device=device,
            trainer=trainer,
            stage=args.stage,
        )
        
        print(f"\nTrain Metrics:")
        for k, v in train_metrics.items():
            print(f"  {k}: {v:.4f}")
        
        # 验证
        if val_loader:
            val_metrics = evaluate(
                model=model,
                behavior_policy=behavior_policy,
                val_loader=val_loader,
                device=device,
                trainer=trainer,
            )
            print(f"\nVal Metrics:")
            for k, v in val_metrics.items():
                print(f"  {k}: {v:.4f}")
        
        # 保存检查点
        checkpoint = {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "behavior_policy_state_dict": behavior_policy.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "train_metrics": train_metrics,
        }
        torch.save(checkpoint, os.path.join(args.output_dir, f"checkpoint_epoch_{epoch}.pt"))
    
    print("\nTraining completed!")


if __name__ == "__main__":
    main()

