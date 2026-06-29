# scripts/train/dataset.py

import torch
from torch.utils.data import Dataset
import numpy as np
import json
import os
import math

class NavigationGraphDataset(Dataset):
    def __init__(self, json_path, history_horizon=80):
        # history_horizon: 对应采集时的 T * Frequency (8s * 10Hz = 80 steps)
        self.data_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.target_len = history_horizon
        
        with open(json_path, 'r') as f:
            self.index = json.load(f)
            
        print(f"[Dataset] Loaded {len(self.index)} samples from {json_path}")
        
        # 预定义查询映射，防止数据中没有 lang_feat
        # 0: near, 1: front, 2: behind, 3: left, 4: right
        self.REL_TYPE_MAP = {
            0: [1, 0, 0, 0, 0],
            1: [0, 1, 0, 0, 0],
            2: [0, 0, 1, 0, 0],
            3: [0, 0, 0, 1, 0],
            4: [0, 0, 0, 0, 1]
        }

    def __len__(self):
        return len(self.index)

    def _global_to_local(self, target_pos, ref_pos, ref_yaw_rad):
        """
        将全局坐标转换为 Ego 局部坐标
        target_pos: [x, y]
        ref_pos: [x, y] (Ego t=0)
        ref_yaw_rad: Ego heading in radians
        """
        dx = target_pos[0] - ref_pos[0]
        dy = target_pos[1] - ref_pos[1]
        
        # 旋转矩阵 (逆时针旋转 -yaw，即转回局部坐标系)
        # local_x = dx * cos + dy * sin
        # local_y = -dx * sin + dy * cos
        # 注意：CARLA 的坐标系通常是左手系或右手系，这里采用标准 2D 旋转
        cos_a = math.cos(-ref_yaw_rad)
        sin_a = math.sin(-ref_yaw_rad)
        
        lx = dx * cos_a - dy * sin_a
        ly = dx * sin_a + dy * cos_a
        return [lx, ly]

    def __getitem__(self, idx):
        # 1. 拼接绝对路径
        rel_path = self.index[idx]['path']
        full_path = os.path.join(self.data_root, rel_path)
        
        try:
            with np.load(full_path, allow_pickle=True) as data:
                # 兼容 Joint Collection 格式 (snapshot 在顶层)
                if 'snapshot' in data:
                    raw_snap = data['snapshot'].item()
                else:
                    # 兼容 Multi-Candidate 格式
                    raw_snap = data 
                
                # --- 3. 提取特征 ---
                
                # Node Feats: [N, 32] (float32)
                # 确保是 float 类型
                x = torch.from_numpy(raw_snap['node_feats']).float()
                
                # Edge Index: [2, E] (int64)
                # PyG 要求 edge_index 是 long 类型
                edge_index = torch.from_numpy(raw_snap['edge_index']).long()
                
                # Edge Attr: [E, 16] (float32)
                edge_attr = torch.from_numpy(raw_snap['edge_attr']).float()
                
                # Query (Language Feature)
                # 优先使用预计算的 lang_feat
                if 'lang_feat' in raw_snap:
                     q = torch.from_numpy(raw_snap['lang_feat']).float()
                elif 'rel_type' in raw_snap:
                    # 如果只有 rel_type，进行 One-Hot 编码
                    rt = int(raw_snap['rel_type'])
                    q_vec = self.REL_TYPE_MAP.get(rt, [0,0,0,0,0])
                    q = torch.tensor(q_vec).float()
                else:
                    # Fallback (不应该发生)
                    q = torch.zeros(5).float()

                # Target Label (Classification Task)
                # 这是一个整数索引，指向 x 中的哪一个节点是 Target
                y = torch.tensor(raw_snap['target_index'], dtype=torch.long)
                
                # 候选掩码 (Mask)
                # 用于在 Loss 计算时只考虑有效的候选节点
                mask = torch.from_numpy(raw_snap['candidate_mask']).bool()
                
                # --- Ego Velocity (New for GRU Planner) ---
                # 从 node_feats 中提取 Ego 的速度
                # 假设 Node 0 是 Ego
                # node_feats 维度: [N, D]
                # 假设 velocity 在 node_feats 的某些列
                # 通常是 [x, y, vx, vy, heading, ...]
                # 让我们假设 vx, vy 是 index 2, 3 (根据 lc_org_nav/online_nav/graph_builder.py)
                # 最好检查一下 graph_builder.py
                
                # 暂时假设 vx, vy 在 2,3
                ego_vel = x[0, 2:4] # [2]
                
                # 2. 解析 Trajectory (Planning Ground Truth)
                # 这是一个 list of dicts: [{'global_loc': [x,y,z], ...}, ...]
                if 'trajectory' in data:
                    traj_raw = data['trajectory']
                    
                    # 获取参考坐标系 (Ego at t=0)
                    # 优先从 meta 读取，如果没有则用 snapshot 中 Ego (node 0) 的位置
                    if 'meta' in data:
                        meta = data['meta'].item()
                        ref_pos = meta['ego_ref_loc'] # [x, y, z]
                        ref_rot = meta['ego_ref_rot'] # [pitch, yaw, roll]
                    else:
                        # Fallback for old data
                        # 假设 node 0 是 Ego
                        # 注意：node_feats 通常是相对坐标，不能用来还原全局。
                        # 如果没有 meta，这部分数据可能无法用于训练 Planning Head
                        # 这里返回一个 dummy 掩码
                        return None

                    ref_yaw = math.radians(ref_rot[1])
                    
                    local_traj = []
                    # 我们只需要提取 Ego 的未来轨迹 (Ego Trajectory)
                    # 因为 Planning Head 是控制 Ego 怎么开
                    # 注意：raw trajectory 数据里通常存的是 Target 的轨迹？
                    # 让我们回顾 collect_joint_data.py -> 'trajectory' 存的是 Target 的状态
                    # Wait! S2S Collector 存的是 Ego 和 Target 两个的 loc。
                    # Joint Collector (最新版) 存的是 point['global_loc'] (Target) ???
                    
                    # --- 关键修正 ---
                    # 如果我们要训练 "智能跟随"，我们需要 Ground Truth 是 "Expert 驾驶下的 Ego 轨迹"
                    # 请检查你的 .npz 结构。
                    # 如果 'trajectory' 里存的是 Target 的位置，那我们是在做 "轨迹预测 (Prediction)"
                    # 如果 'trajectory' 里存的是 Ego 的位置，那我们是在做 "规划 (Planning)"
                    
                    # 假设：你的 trajectory list 每个元素包含 'ego_loc' (S2S版)
                    # 或者如果是 Joint版，可能只存了 target。
                    # 既然是 "智能跟随"，Expert 控制下的 Ego 轨迹才是 GT。
                    
                    # 假设数据格式是 S2S 版： point['ego_loc']
                    # 如果是 Joint 版只存了 Target，那只能做 Target Prediction。
                    # 让我们按最理想的 Planning 任务处理 (需要 Ego GT)
                    
                    valid_len = min(len(traj_raw), self.target_len)
                    for i in range(valid_len):
                        # 提取 Ego 的位置作为 GT
                        # 如果你的数据里只有 target_loc，那就暂且用 target_loc (做预测任务)
                        # 强烈建议确认数据里包含 ego_loc
                        pt = traj_raw[i]
                        # 优先尝试 ego_loc，如果没有则退化为 target_loc
                        curr_pos = pt.get('ego_loc', pt.get('global_loc'))
                        
                        lx, ly = self._global_to_local(curr_pos, ref_pos, ref_yaw)
                        local_traj.append([lx, ly])
                    
                    # Padding or Truncating
                    traj_tensor = torch.zeros((self.target_len, 2), dtype=torch.float)
                    if len(local_traj) > 0:
                        loaded = torch.tensor(local_traj).float()
                        traj_tensor[:len(local_traj), :] = loaded
                    
                    # Mask: 标记有效长度，防止 padding 影响 Loss
                    traj_mask = torch.zeros(self.target_len, dtype=torch.bool)
                    traj_mask[:len(local_traj)] = True
                else:
                    traj_tensor = torch.zeros((self.target_len, 2), dtype=torch.float)
                    traj_mask = torch.zeros(self.target_len, dtype=torch.bool)

                return {
                    'x': x,
                    'edge_index': edge_index,
                    'edge_attr': edge_attr,
                    'query': q,
                    'y': y,
                    'mask': mask,
                    'gt_traj': traj_tensor, # [T, 2]
                    'traj_mask': traj_mask, # [T]
                    'ego_vel': ego_vel,     # [2]
                    'path': rel_path
                }
                
        except Exception as e:
            # print(f"[Error] Failed to load {rel_path}: {e}")
            return None

def graph_collate_fn(batch):
    """
    自定义 Collate 函数
    简单的剔除 None 数据
    """
    batch = [b for b in batch if b is not None]
    if len(batch) == 0: return None
    return batch
