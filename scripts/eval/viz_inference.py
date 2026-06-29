import torch
import matplotlib.pyplot as plt
import numpy as np
import os
import sys
import math

# Add path
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
            traj_mask=item['traj_mask'].unsqueeze(0), # [1, T]
            ego_vel=item['ego_vel'].unsqueeze(0), # [1, 2]
            path=item['path'] # Keep path for visualization
        )
        data_list.append(data)
        
    if len(data_list) == 0: return None
    return Batch.from_data_list(data_list)

from scripts.train.model import QGIPNet

def visualize_inference():
    # 配置
    MODEL_PATH = "checkpoints/best_model.pth"
    # 挑一个 OOD 的数据来看
    TEST_DATA = "data/final_dataset/test_unseen.json"
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # 加载
    ds = NavigationGraphDataset(TEST_DATA)
    # Use standard DataLoader with custom collate
    loader = torch.utils.data.DataLoader(ds, batch_size=1, shuffle=True, collate_fn=pyg_collate_fn)
    
    model = QGIPNet(node_dim=32, edge_dim=16, query_dim=5).to(DEVICE)
    
    if not os.path.exists(MODEL_PATH):
        print(f"Model not found at {MODEL_PATH}")
        return

    try:
        model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    except Exception as e:
        print(f"Failed to load model: {e}")
        return
        
    model.eval()
    
    print("🎨 Generating visualizations...")
    
    # 只需要画几个典型 Case
    num_viz = 5
    
    with torch.no_grad():
        for i, batch in enumerate(loader):
            if i >= num_viz: break
            if batch is None: continue
            
            batch = batch.to(DEVICE)
            
            # Forward
            # pred_deltas: [1, T, 2]
            scores, pred_deltas, aux = model(
                batch.x, batch.edge_index, batch.edge_attr, 
                batch.query, batch.batch, batch.ptr,
                ego_velocity=batch.ego_vel
            )
            
            # 还原轨迹 (相对于 t=0 的 Ego)
            pred_traj = torch.cumsum(pred_deltas, dim=1).cpu().numpy()[0]
            # gt_traj from dataset is absolute position (local frame)
            gt_traj = batch.gt_traj.cpu().numpy()[0]
            
            # 获取选择结果
            # scores is [Total_N, 1]. For batch=1, Total_N is nodes in this graph.
            probs = torch.softmax(scores, dim=0).cpu().numpy().flatten()
            pred_idx = np.argmax(probs)
            gt_idx = batch.y.item()
            is_correct = (pred_idx == gt_idx)
            
            # --- 绘图 ---
            plt.figure(figsize=(10, 10))
            
            # 1. 画车辆节点 (t=0)
            # node_feats: [N, D]. 假设前两维是 relative x, y (dataset.py confirms this)
            nodes = batch.x.cpu().numpy()
            
            # Ego (Node 0)
            plt.scatter(nodes[0, 0], nodes[0, 1], c='black', marker='^', s=200, label='Ego')
            
            # Candidates
            # 用 Attention/Prob 颜色编码
            cmap = plt.get_cmap('Reds')
            
            for n in range(1, nodes.shape[0]):
                # 区分是否是 Target
                edge_color = 'green' if n == gt_idx else 'gray'
                # 预测概率颜色
                p = probs[n] if n < len(probs) else 0
                fill_color = cmap(p)
                
                # Check candidate mask
                is_candidate = batch.mask[n].item()
                if not is_candidate:
                     edge_color = 'blue' # non-candidate vehicles (obstacles)
                     
                plt.scatter(nodes[n, 0], nodes[n, 1], 
                            facecolors=fill_color, edgecolors=edge_color, 
                            s=150, linewidth=2)
                plt.text(nodes[n, 0]+0.5, nodes[n, 1]+0.5, f"{p:.2f}", fontsize=8)

            # 2. 画轨迹
            # GT (Solid Green)
            # Mask valid GT steps
            traj_mask = batch.traj_mask.cpu().numpy()[0]
            valid_gt = gt_traj[traj_mask]
            if len(valid_gt) > 0:
                plt.plot(valid_gt[:, 0], valid_gt[:, 1], 'g-', linewidth=2, label='Expert Traj')
            
            # Pred (Dashed Blue)
            plt.plot(pred_traj[:, 0], pred_traj[:, 1], 'b--', linewidth=2, label='QGIP Traj')
            
            # 3. 装饰
            # Query info
            q_vec = batch.query.cpu().numpy()[0]
            # 0: near, 1: front, 2: behind, 3: left, 4: right
            q_str = "Unknown"
            if q_vec[3] == 1: q_str = "Left"
            elif q_vec[4] == 1: q_str = "Right"
            elif q_vec[1] == 1: q_str = "Front"
            
            plt.title(f"Case {i}: {batch.path[0][-20:]}\nSelect Acc: {is_correct} | Query: {q_str}")
            plt.legend()
            plt.grid(True)
            plt.axis('equal')
            
            # 保存
            os.makedirs("docs/viz", exist_ok=True)
            save_path = f"docs/viz/case_{i}.png"
            plt.savefig(save_path)
            plt.close()
            print(f"Saved {save_path}")

if __name__ == "__main__":
    visualize_inference()
