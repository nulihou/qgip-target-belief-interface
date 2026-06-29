import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from dataset import NavigationGraphDataset
from model import QGIPNet
from torch_geometric.data import Data, Batch
import os
import time

# PyG Collate Function
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
            traj_mask=item['traj_mask'].unsqueeze(0), # [1, T]
            ego_vel=item['ego_vel'].unsqueeze(0), # [1, 2]
            path=item['path'] # Keep path for visualization
        )
        data_list.append(data)
        
    if len(data_list) == 0: return None
    return Batch.from_data_list(data_list)

import torch.nn.functional as F

def compute_physics_loss(pred_deltas, gt_traj_pos, traj_mask):
    """
    pred_deltas: [B, T, 2] (预测的每一步位移)
    gt_traj_pos: [B, T, 2] (Ground Truth 绝对位置) - 注意这里 dataset 返回的是绝对位置
    traj_mask:   [B, T]    (有效位掩码)
    """
    # 1. Position Loss (位置准确性)
    # 累加 Delta 得到绝对轨迹 (假设起始点是 0,0)
    # 注意：我们的 dataset 返回的 gt_traj 已经是局部坐标系下的绝对位置 (相对于 t=0)
    # 所以 pred_deltas 需要 cumsum
    pred_traj = torch.cumsum(pred_deltas, dim=1)
    
    # Masking logic needs to be careful
    # We flatten or mask before loss
    
    loss_pos = F.smooth_l1_loss(pred_traj[traj_mask], gt_traj_pos[traj_mask])
    
    # 2. Smoothness Loss (平滑性 - 惩罚急加速/锯齿)
    # 计算二阶差分 (加速度变化率 / Jerk)
    # acc = delta_t - delta_{t-1}
    # pred_deltas is [B, T, 2]
    
    if pred_deltas.size(1) > 2:
        pred_acc = pred_deltas[:, 1:] - pred_deltas[:, :-1]
        pred_jerk = pred_acc[:, 1:] - pred_acc[:, :-1]
        loss_smooth = torch.mean(pred_jerk ** 2)
    else:
        loss_smooth = torch.tensor(0.0, device=pred_deltas.device)
    
    # 3. Kinematics Loss (动力学约束 - 防止横向漂移)
    # 车辆不能像螃蟹一样横着走。
    # 简单约束：dx 应该远大于 dy (在局部坐标系下，x是车头方向)
    # 如果 dy 很大，说明在漂移 (Lateral velocity penalty)
    # pred_deltas[:, :, 1] is dy
    loss_kine = torch.mean(torch.abs(pred_deltas[:, :, 1])) * 0.1
    
    return loss_pos, loss_smooth, loss_kine

def train():
    # --- 1. Config ---
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    BATCH_SIZE = 32
    LR = 1e-4
    EPOCHS = 100
    
    # --- 2. Data ---
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    train_path = os.path.join(root_dir, 'data', 'final_dataset', 'train.json')
    val_path = os.path.join(root_dir, 'data', 'final_dataset', 'val.json')
    
    print("⏳ Loading datasets...", flush=True)
    train_ds = NavigationGraphDataset(train_path)
    val_ds = NavigationGraphDataset(val_path)
    print("✅ Datasets loaded.", flush=True)
    
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, collate_fn=pyg_collate_fn)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, collate_fn=pyg_collate_fn)
    
    # --- 3. Model ---
    print("⏳ Initializing model...", flush=True)
    model = QGIPNet(node_dim=32, edge_dim=16, query_dim=5).to(device)
    optimizer = optim.Adam(model.parameters(), lr=LR)
    print("✅ Model initialized.", flush=True)
    
    # Losses
    cls_criterion = nn.CrossEntropyLoss()
    # reg_criterion = nn.SmoothL1Loss(reduction='none') # Replaced by physics loss
    
    # Physics Loss Weights
    W_CLS = 1.0
    W_POS = 10.0
    W_SMT = 2.0
    W_KIN = 0.5
    
    print("🚀 Training Started...")
    
    best_loss = float('inf')
    
    for epoch in range(EPOCHS):
        model.train()
        total_cls_loss = 0
        total_reg_loss = 0
        total_loss = 0
        steps = 0
        
        for batch in train_loader:
            if batch is None: continue
            batch = batch.to(device)
            
            # Forward
            # Note: PyG Batch object has .batch and .ptr attributes automatically
            # Also pass ego_velocity
            scores, pred_deltas, aux = model(
                batch.x, batch.edge_index, batch.edge_attr, 
                batch.query, batch.batch, batch.ptr,
                ego_velocity=batch.ego_vel
            )
            
            # --- Loss Calculation ---
            # 1. Selection Loss (Classification)
            global_target_indices = batch.ptr[:-1] + batch.y
            
            from torch_geometric.utils import softmax
            probs = softmax(scores, batch.batch)
            log_probs = torch.log(probs + 1e-9)
            
            cls_loss = -log_probs[global_target_indices].mean()
            
            # 2. Physics-Informed Planning Loss
            # pred_deltas: [Batch, T, 2]
            # batch.gt_traj: [Batch, T, 2] (Absolute positions)
            l_pos, l_smt, l_kin = compute_physics_loss(pred_deltas, batch.gt_traj, batch.traj_mask)
            
            # 3. Total Loss
            loss = W_CLS*cls_loss + W_POS*l_pos + W_SMT*l_smt + W_KIN*l_kin
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            total_cls_loss += cls_loss.item()
            total_reg_loss += l_pos.item() # Tracking pos loss as main reg metric
            total_loss += loss.item()
            steps += 1
            
        avg_loss = total_loss / steps
        avg_cls = total_cls_loss / steps
        avg_reg = total_reg_loss / steps
        print(f"Epoch {epoch+1}/{EPOCHS} | Total: {avg_loss:.4f} (Cls: {avg_cls:.4f}, Reg: {avg_reg:.4f})")
        
        # Save Best Model
        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save(model.state_dict(), 'checkpoints/best_model.pth')
            # print(f"✅ Model saved (Loss: {best_loss:.4f})")

if __name__ == "__main__":
    train()
