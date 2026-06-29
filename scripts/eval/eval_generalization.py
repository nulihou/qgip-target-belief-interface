"""
Eval Generalization Script
==========================
Evaluates the trained QGIP-Net on the "Unseen" Test Set (Town05).
Metrics:
  1. Selection Accuracy (Top-1)
  2. ADE (Average Displacement Error) - 轨迹平均误差
  3. FDE (Final Displacement Error) - 终点误差 (8s处)
"""

import torch
from torch.utils.data import DataLoader
import numpy as np
import os
import sys

# Add project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.train.dataset import NavigationGraphDataset, graph_collate_fn
# PyG Collate Function
from torch_geometric.data import Data, Batch

def pyg_collate_fn(batch):
    data_list = []
    for item in batch:
        if item is None: continue
        
        # Convert dict to PyG Data object
        data = Data(
            x=item['x'],
            edge_index=item['edge_index'],
            edge_attr=item['edge_attr'],
            y=item['y'], # target_index
            query=item['query'].unsqueeze(0), # [1, D] for batching
            mask=item['mask'],
            gt_traj=item['gt_traj'].unsqueeze(0), # [1, T, 2]
            traj_mask=item['traj_mask'].unsqueeze(0) # [1, T]
        )
        data_list.append(data)
        
    if len(data_list) == 0: return None
    return Batch.from_data_list(data_list)

from scripts.train.model import QGIPNet 

def evaluate():
    # === 配置 ===
    # 注意：我们这里直接加载训练好的模型权重
    # 如果你在训练脚本中没有保存模型，我们需要先保存一下
    # 为了演示，我们假设你刚刚运行完 train.py，模型还在内存里或者你可以手动保存
    # 但为了标准化，我们应该在 train.py 里保存模型。
    # 由于我无法修改之前的内存状态，我假设你已经在 train.py 运行后得到一个 model.pth
    # 如果没有，请先在 train.py 最后加一行 torch.save(model.state_dict(), 'checkpoints/best_model.pth')
    # 或者我们直接在这个脚本里实例化一个新模型（但这没用，因为是随机初始化的）
    
    # *** 关键修正 ***
    # 鉴于你的 train.py 刚刚运行完但没有保存模型代码，
    # 我无法直接加载训练好的权重。
    # 为了不浪费你刚才跑的 100 epoch，我建议：
    # 1. 修改 train.py 加入保存逻辑
    # 2. 重新跑几个 epoch (或者 100 epoch 如果你愿意)
    # 3. 然后再跑这个 eval 脚本
    
    # 但是，为了演示流程，我先写好这个脚本。
    # 请务必先去 train.py 加入保存代码并运行！
    
    MODEL_PATH = "checkpoints/best_model.pth" 
    TEST_DATA_PATH = "data/final_dataset/test_unseen.json" # Town05
    BATCH_SIZE = 32
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 1. 加载数据
    print(f"Loading Test Set: {TEST_DATA_PATH}")
    test_ds = NavigationGraphDataset(TEST_DATA_PATH)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, collate_fn=pyg_collate_fn)
    
    # 2. 加载模型
    model = QGIPNet(node_dim=32, edge_dim=16, query_dim=5).to(DEVICE)
    
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Error: Model file not found at {MODEL_PATH}")
        print("Please modify train.py to save the model and run it first!")
        return

    try:
        model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
        print("✅ Model loaded successfully.")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return
        
    model.eval()
    
    # 3. 指标统计
    total_samples = 0
    correct_selections = 0
    
    total_ade = 0.0
    total_fde = 0.0
    valid_traj_count = 0
    
    print("🚀 Starting Evaluation on Town05 (Unseen)...")
    
    with torch.no_grad():
        for batch in test_loader:
            if batch is None: continue
            
            batch = batch.to(DEVICE)
            
            # Forward
            # logits: [Total_N, 1] -> Need to handle batch
            scores, pred_traj, aux = model(
                batch.x, batch.edge_index, batch.edge_attr, 
                batch.query, batch.batch, batch.ptr
            )
            
            # --- Metric 1: Selection Accuracy ---
            # QGIPNet outputs scores for ALL nodes [Total_N, 1]
            # We need to find argmax within each graph
            
            # Global target indices
            global_targets = batch.ptr[:-1] + batch.y
            
            # Argmax per graph
            from torch_geometric.utils import scatter
            # scatter_max returns (max_vals, argmax_indices)
            # but argmax_indices is relative to the source tensor dimension?
            # No, scatter_max returns index in source.
            
            # Let's use a simpler loop for eval safety if scatter is complex
            # Or use ptr
            
            pred_indices = []
            for i in range(len(batch.ptr) - 1):
                start = batch.ptr[i]
                end = batch.ptr[i+1]
                graph_scores = scores[start:end]
                local_argmax = torch.argmax(graph_scores)
                global_argmax = start + local_argmax
                pred_indices.append(global_argmax)
            
            pred_indices = torch.tensor(pred_indices, device=DEVICE)
            
            correct = (pred_indices == global_targets).sum().item()
            correct_selections += correct
            total_samples += (len(batch.ptr) - 1)
            
            # --- Metric 2: Trajectory Error (ADE / FDE) ---
            # batch.gt_traj: [B, T, 2]
            # pred_traj: [B, T, 2]
            
            # Calculate L2 distance
            error = torch.norm(pred_traj - batch.gt_traj, dim=-1) # [B, T]
            
            # Mask invalid steps
            masked_error = error * batch.traj_mask
            
            # ADE
            sample_valid_steps = batch.traj_mask.sum(dim=1)
            sample_ade = masked_error.sum(dim=1) / (sample_valid_steps + 1e-6)
            
            # FDE
            last_step_idx = sample_valid_steps.long() - 1
            last_step_idx = torch.clamp(last_step_idx, min=0)
            fde_val = error.gather(1, last_step_idx.unsqueeze(1)).squeeze(1)
            
            valid_rows = (sample_valid_steps > 0)
            
            total_ade += sample_ade[valid_rows].sum().item()
            total_fde += fde_val[valid_rows].sum().item()
            valid_traj_count += valid_rows.sum().item()

    # --- 4. 最终报告 ---
    acc = 100 * correct_selections / total_samples
    avg_ade = total_ade / (valid_traj_count + 1e-6)
    avg_fde = total_fde / (valid_traj_count + 1e-6)
    
    print("\n" + "="*40)
    print("       OOD EVALUATION REPORT (Town05)")
    print("="*40)
    print(f"Samples: {total_samples}")
    print(f"🎯 Selection Accuracy: {acc:.2f}%")
    print(f"📉 Planning ADE:       {avg_ade:.4f} m") 
    print(f"🏁 Planning FDE:       {avg_fde:.4f} m")
    print("="*40)
    
    if acc > 80.0:
        print("✅ RESULT: EXCELLENT GENERALIZATION (SOTA Level)")
    elif acc > 60.0:
        print("⚠️ RESULT: GOOD, BUT ROOM FOR IMPROVEMENT")
    else:
        print("❌ RESULT: OVERFITTING DETECTED")

if __name__ == "__main__":
    evaluate()
