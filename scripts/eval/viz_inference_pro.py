import torch
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.cm as cm
import numpy as np
import os
import sys
import math

# Add path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.train.dataset import NavigationGraphDataset, graph_collate_fn
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
            path=item['path'] # Keep path
        )
        data_list.append(data)
        
    if len(data_list) == 0: return None
    return Batch.from_data_list(data_list)

from scripts.train.model import QGIPNet

# === 绘图辅助函数 ===
def draw_rotated_rect(ax, center, width, height, angle_rad, color, alpha=1.0, label=None, edge_color=None):
    """绘制旋转矩形代表车辆"""
    # 计算矩形左下角坐标 (before rotation)
    # Matplotlib 的 Rectangle 是从左下角开始定义的，Angle 是逆时针
    # 我们需要根据中心点反推
    ts = ax.transData
    tr = matplotlib.transforms.Affine2D().rotate_around(center[0], center[1], angle_rad)
    
    # 车辆尺寸 (假设一般轿车)
    # 左下角
    xy = (center[0] - width/2, center[1] - height/2)
    
    rect = patches.Rectangle(
        xy, width, height,
        linewidth=1, edgecolor=edge_color if edge_color else 'black',
        facecolor=color, alpha=alpha,
        transform=tr + ts
    )
    ax.add_patch(rect)
    return rect

def get_heading_from_vel(vx, vy):
    """从速度计算朝向，如果没有速度则默认朝上或保持"""
    speed = math.sqrt(vx**2 + vy**2)
    if speed < 0.1:
        return np.pi / 2 # 默认朝上 (y轴正向)
    return math.atan2(vy, vx)

def visualize_pro():
    # 设置论文风格字体
    # plt.rcParams['font.family'] = 'serif'
    # plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']
    
    # 配置
    MODEL_PATH = "checkpoints/best_model.pth"
    TEST_DATA = "data/final_dataset/test_unseen.json"
    DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    OUTPUT_DIR = "docs/viz_paper"
    
    # 加载
    ds = NavigationGraphDataset(TEST_DATA)
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
    
    print("🎨 Generating Professional Visualizations...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 颜色定义 (Paper Safe Colors)
    COLOR_EGO = '#333333'      # 深灰 Ego
    COLOR_TARGET = '#2ca02c'   # 绿色 Target (GT)
    COLOR_OTHER = '#d62728'    # 红色 Other Candidates
    COLOR_TRAJ_GT = '#2ca02c'
    COLOR_TRAJ_PRED = '#1f77b4' # 蓝色 Prediction
    
    num_viz = 10 # 画10张
    
    with torch.no_grad():
        for i, batch in enumerate(loader):
            if i >= num_viz: break
            if batch is None: continue
            
            batch = batch.to(DEVICE)
            scores, pred_deltas, aux = model(
                batch.x, batch.edge_index, batch.edge_attr, 
                batch.query, batch.batch, batch.ptr,
                ego_velocity=batch.ego_vel
            )
            
            # 数据还原
            pred_traj = torch.cumsum(pred_deltas, dim=1).cpu().numpy()[0]
            gt_traj = batch.gt_traj.cpu().numpy()[0] # gt_traj is already absolute
            probs = torch.softmax(scores, dim=0).cpu().numpy().flatten()
            
            nodes = batch.x.cpu().numpy() # [N, D] (x, y, vx, vy, ...)
            gt_idx = batch.y.item()
            pred_idx = np.argmax(probs)
            
            # === 创建画布 ===
            # 使用正方形画布，显得紧凑
            fig, ax = plt.subplots(figsize=(8, 8), dpi=150)
            
            # 1. 绘制车辆 (Oriented Boxes)
            # 假设 nodes 前4维是: x, y, vx, vy
            # 如果你的特征格式不同，请调整这里的索引
            
            # Ego
            draw_rotated_rect(ax, (0,0), 4.5, 2.0, np.pi/2, COLOR_EGO, alpha=1.0, edge_color='black')
            ax.text(0, -3, "Ego", ha='center', fontsize=10, fontweight='bold')
            
            # Candidates
            for n in range(1, nodes.shape[0]):
                cx, cy = nodes[n, 0], nodes[n, 1]
                # Note: node features might vary. Based on graph_builder.py/dataset.py:
                # [rel_x, rel_y, vx, vy, heading_cos, heading_sin]
                # But dataset.py said ego_vel = x[0, 2:4]
                # Let's assume index 2,3 is vx, vy
                vx, vy = nodes[n, 2], nodes[n, 3] 
                
                # 过滤掉太远的车辆 (只画 50m 以内的)
                if abs(cx) > 50 or abs(cy) > 50: continue
                
                heading = get_heading_from_vel(vx, vy)
                prob = probs[n]
                
                # 颜色逻辑
                is_target = (n == gt_idx)
                base_color = COLOR_TARGET if is_target else COLOR_OTHER
                
                # 透明度逻辑：概率越低越透明，但最低保留 0.2
                # alpha = max(0.2, min(1.0, prob * 2.0))
                # 简单点: 选中/GT 不透明，其他的根据 prob
                alpha = 1.0 if (is_target or prob > 0.1) else 0.3
                
                # 绘制车身
                rect = draw_rotated_rect(ax, (cx, cy), 4.5, 2.0, heading, base_color, alpha=alpha)
                
                # 绘制 Attention 连线 (仅针对高概率或Target)
                if prob > 0.1 or is_target:
                    ax.plot([0, cx], [0, cy], color=base_color, linestyle=':', alpha=0.5, linewidth=1)
                    # 标签
                    ax.text(cx, cy+2, f"{prob:.2f}", fontsize=8, color=base_color, fontweight='bold', ha='center')

            # 2. 绘制轨迹
            # GT Trajectory (实线)
            # Mask valid
            traj_mask = batch.traj_mask.cpu().numpy()[0]
            valid_gt = gt_traj[traj_mask]
            
            if len(valid_gt) > 0:
                ax.plot(valid_gt[:, 0], valid_gt[:, 1], color=COLOR_TRAJ_GT, linewidth=3, label='Expert (GT)', alpha=0.7)
                # End point marker
                ax.scatter(valid_gt[-1, 0], valid_gt[-1, 1], color=COLOR_TRAJ_GT, marker='x', s=50)

            # Pred Trajectory (虚线)
            ax.plot(pred_traj[:, 0], pred_traj[:, 1], color=COLOR_TRAJ_PRED, linewidth=2.5, linestyle='--', label='QGIP (Ours)')
            # End point marker
            ax.scatter(pred_traj[-1, 0], pred_traj[-1, 1], color=COLOR_TRAJ_PRED, marker='o', s=30)

            # 3. 设置视口 (Smart ROI)
            # 自动计算包围盒：包含 Ego, Target 和 Pred Trajectory
            roi_x = [0, pred_traj[-1, 0]]
            roi_y = [0, pred_traj[-1, 1]]
            
            if len(valid_gt) > 0:
                 roi_x.append(valid_gt[-1, 0])
                 roi_y.append(valid_gt[-1, 1])
                 
            # Add target pos
            roi_x.append(nodes[gt_idx, 0])
            roi_y.append(nodes[gt_idx, 1])
            
            min_x, max_x = min(roi_x)-10, max(roi_x)+10
            min_y, max_y = min(roi_y)-10, max(roi_y)+10
            
            # 强制最小视口 30x30，防止太小
            if max_x - min_x < 30:
                mid = (max_x + min_x)/2
                min_x, max_x = mid-15, mid+15
            if max_y - min_y < 30:
                mid = (max_y + min_y)/2
                min_y, max_y = mid-15, mid+15

            ax.set_xlim(min_x, max_x)
            ax.set_ylim(min_y, max_y)
            
            # 4. 装饰
            ax.set_aspect('equal')
            ax.grid(True, linestyle='--', alpha=0.3)
            ax.set_xlabel("Lateral Distance (m)")
            ax.set_ylabel("Longitudinal Distance (m)")
            
            # 标题包含 Query 信息
            # 0: near, 1: front, 2: behind, 3: left, 4: right
            q_vec = batch.query[0].cpu().numpy()
            q_str = "Keep Forward"
            if q_vec[3] == 1: q_str = "Turn Left"
            elif q_vec[4] == 1: q_str = "Turn Right"
            
            title_color = 'green' if pred_idx == gt_idx else 'red'
            ax.set_title(f"Query: {q_str} | Success: {pred_idx == gt_idx}", color=title_color, fontsize=12, fontweight='bold')
            
            ax.legend(loc='upper right')
            
            # 保存
            save_path = os.path.join(OUTPUT_DIR, f"paper_viz_{i}.png")
            plt.savefig(save_path, bbox_inches='tight', pad_inches=0.1)
            plt.close()
            print(f"Saved {save_path}")

if __name__ == "__main__":
    visualize_pro()
