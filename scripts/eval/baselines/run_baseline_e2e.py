import carla
import torch
import torch.nn as nn
from torch_geometric.nn import GATv2Conv
import numpy as np
import sys
import os
import math
import collections
from collections import deque
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from scripts.train.model import QGIPNet

# ==============================================================================
# Helpers (Shared)
# ==============================================================================

def build_node_features_minimal(ego_transform, vehicles, anchor_id):
    ego_loc = ego_transform.location
    ego_yaw = math.radians(ego_transform.rotation.yaw)
    anchor_tf = ego_transform
    for v in vehicles:
        if v.id == anchor_id: anchor_tf = v.get_transform(); break
    ax = anchor_tf.location.x; ay = anchor_tf.location.y; ayaw = math.radians(anchor_tf.rotation.yaw)
    feats = []
    for v in vehicles:
        tf = v.get_transform(); loc = tf.location; vel = v.get_velocity()
        dx = loc.x - ego_loc.x; dy = loc.y - ego_loc.y
        dist = math.sqrt(dx*dx + dy*dy)
        angle = math.atan2(dy, dx) - ego_yaw
        angle = (angle + math.pi) % (2 * math.pi) - math.pi
        dx_a = loc.x - ax; dy_a = loc.y - ay
        dist_a = math.sqrt(dx_a*dx_a + dy_a*dy_a)
        angle_a = math.atan2(dy_a, dx_a) - ayaw
        angle_a = (angle_a + math.pi) % (2 * math.pi) - math.pi
        speed = math.sqrt(vel.x**2 + vel.y**2)
        f = np.zeros(32, dtype=np.float32)
        f[0]=dx; f[1]=dy; f[2]=dist; f[3]=math.cos(angle); f[4]=math.sin(angle)
        f[5]=dx_a; f[6]=dy_a; f[7]=dist_a; f[8]=math.cos(angle_a); f[9]=math.sin(angle_a)
        f[10]=speed; f[11]=1.0 if v.id == anchor_id else 0.0
        feats.append(f)
    return np.stack(feats), np.ones(len(vehicles))

def build_edges_minimal(vehicles):
    N = len(vehicles)
    src_list = []; dst_list = []; attr_list = []
    for i in range(N):
        loc_i = vehicles[i].get_transform().location
        for j in range(N):
            if i == j: continue
            loc_j = vehicles[j].get_transform().location
            dx = loc_j.x - loc_i.x; dy = loc_j.y - loc_i.y
            dist = math.sqrt(dx*dx + dy*dy); angle = math.atan2(dy, dx)
            f = np.zeros(16, dtype=np.float32)
            f[0]=dx; f[1]=dy; f[2]=dist; f[3]=math.cos(angle); f[4]=math.sin(angle)
            f[5]=1.0 if dist < 30.0 else 0.0
            src_list.append(i); dst_list.append(j); attr_list.append(f)
    if not src_list: return np.zeros((2, 0), dtype=np.long), np.zeros((0, 16), dtype=np.float32)
    return np.stack([src_list, dst_list], axis=0), np.stack(attr_list, axis=0)

class SceneGraphBuilder:
    def __init__(self, radius=50.0): self.radius = radius
    def build_graph(self, ego_vehicle, candidates):
        try:
            if not candidates: return None
            vehicles = list(candidates)
            if len(vehicles) == 0: return None
            anchor_id = vehicles[0].id
            node_feats, candidate_mask = build_node_features_minimal(ego_vehicle.get_transform(), vehicles, anchor_id)
            edge_index, edge_attr = build_edges_minimal(vehicles)
            return {"node_feats": node_feats, "edge_index": edge_index, "edge_attr": edge_attr, "candidate_mask": candidate_mask, "actor_ids": [v.id for v in vehicles]}
        except: return None

class LongitudinalPID:
    """Simple PID for speed control"""
    def __init__(self, K_P=1.0, K_D=0.0, K_I=0.0, dt=0.05):
        self.K_P = K_P; self.K_D = K_D; self.K_I = K_I; self.dt = dt
        self._e_buffer = deque(maxlen=10)

    def run_step(self, target_speed, current_speed):
        error = target_speed - current_speed
        self._e_buffer.append(error)
        if len(self._e_buffer) >= 2: _de = (self._e_buffer[-1] - self._e_buffer[-2]) / self.dt; _ie = sum(self._e_buffer) * self.dt
        else: _de = 0.0; _ie = 0.0
        return np.clip(self.K_P * error + self.K_D * _de + self.K_I * _ie, -1.0, 1.0)

class LateralPID:
    def __init__(self, K_P=1.95, K_D=0.2, K_I=0.07, dt=0.05):
        self.K_P = K_P; self.K_D = K_D; self.K_I = K_I; self.dt = dt; self._e_buffer = deque(maxlen=10)
    def run_step(self, target_y_offset):
        error = target_y_offset; self._e_buffer.append(error)
        if len(self._e_buffer) >= 2: _de = (self._e_buffer[-1] - self._e_buffer[-2]) / self.dt; _ie = sum(self._e_buffer) * self.dt
        else: _de = 0.0; _ie = 0.0
        return np.clip(self.K_P * error + self.K_D * _de + self.K_I * _ie, -1.0, 1.0)

class LeaderClassifier(nn.Module):
    def __init__(self, node_dim=32, edge_dim=16, hidden_dim=64):
        super().__init__()
        self.node_enc = nn.Sequential(nn.Linear(node_dim, hidden_dim), nn.ReLU())
        self.edge_enc = nn.Sequential(nn.Linear(edge_dim, hidden_dim), nn.ReLU())
        self.conv1 = GATv2Conv(hidden_dim, hidden_dim, edge_dim=hidden_dim, add_self_loops=False)
        self.conv2 = GATv2Conv(hidden_dim, hidden_dim, edge_dim=hidden_dim, add_self_loops=False)
        self.head = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ReLU(), nn.Linear(hidden_dim, 1))
    def forward(self, x, edge_index, edge_attr):
        x = self.node_enc(x); edge_attr = self.edge_enc(edge_attr)
        x = x + self.conv1(x, edge_index, edge_attr); x = torch.relu(x)
        x = x + self.conv2(x, edge_index, edge_attr); x = torch.relu(x)
        return self.head(x).squeeze(-1)

# ==============================================================================
# E2E Agent (No MPC, Direct Trajectory Following)
# ==============================================================================
class QGIPAgent:
    def __init__(self, vehicle, model_path, device='cuda'):
        self.vehicle = vehicle
        self.device = device
        
        self.model = QGIPNet(node_dim=32, edge_dim=16, hidden_dim=128).to(device)
        state_dict = torch.load(model_path, map_location=device)
        if 'state_dict' in state_dict: state_dict = state_dict['state_dict']
        new_state_dict = {}
        for k, v in state_dict.items(): new_state_dict[k.replace('module.', '')] = v
        self.model.load_state_dict(new_state_dict, strict=False)
        self.model.eval()
        
        self.graph_builder = SceneGraphBuilder()
        self.lat_pid = LateralPID()
        self.lon_pid = LongitudinalPID(K_P=1.0, K_D=0.05, K_I=0.1) # PID for E2E
        self.prev_traj = None
        
        # V7.0 Classifier (Optional, but E2E typically relies on its own selection or simple logic)
        # We use V7.0 selection to be fair on "Perception", but E2E on "Control"
        self.v7_model = LeaderClassifier().to(device)
        v7_ckpt = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "checkpoints/v7/llc_epoch_20.pth")
        if os.path.exists(v7_ckpt):
            self.v7_model.load_state_dict(torch.load(v7_ckpt, map_location=device))
            self.v7_model.eval()
            self.use_v7 = True
        else:
            self.use_v7 = False

    def process_model_output(self, raw_deltas):
        curr_traj = torch.cumsum(raw_deltas, dim=1).cpu().numpy()[0]
        if self.prev_traj is not None:
            alpha = 0.7
            len_min = min(len(curr_traj)-1, len(self.prev_traj[1:]))
            smooth = alpha * curr_traj[:-1][:len_min] + (1-alpha) * self.prev_traj[1:][:len_min]
            final_traj = np.vstack([smooth, curr_traj[-1]])
        else: final_traj = curr_traj
        self.prev_traj = final_traj
        return final_traj

    def run_step(self, query_vec, candidates):
        # 1. Perception
        snapshot = self.graph_builder.build_graph(self.vehicle, candidates)
        if snapshot is None: return carla.VehicleControl()

        x = torch.from_numpy(snapshot['node_feats']).float().to(self.device)
        edge_index = torch.from_numpy(snapshot['edge_index']).long().to(self.device)
        edge_attr = torch.from_numpy(snapshot['edge_attr']).float().to(self.device)
        q = torch.tensor(query_vec).float().to(self.device).unsqueeze(0)
        v = self.vehicle.get_velocity()
        speed = np.sqrt(v.x**2 + v.y**2)
        ego_vel = torch.tensor([[speed, 0.0]]).float().to(self.device)

        with torch.no_grad():
            if self.use_v7:
                scores = self.v7_model(x, edge_index, edge_attr)
                target_idx = torch.argmax(scores).item()
            else:
                target_idx = 0
            
            logits, pred_deltas, _ = self.model(
                x, edge_index, edge_attr, q, 
                batch=torch.zeros(x.size(0), dtype=torch.long).to(self.device),
                ptr=torch.tensor([0, x.size(0)], dtype=torch.long).to(self.device),
                ego_velocity=ego_vel
            )

        if target_idx < pred_deltas.size(0):
            selected_deltas = pred_deltas[target_idx:target_idx+1]
        else:
            selected_deltas = pred_deltas[0:1]
            
        raw_traj = self.process_model_output(selected_deltas)
        
        # 2. Geometric Adaptation (Standard)
        real_dist = 100.0
        if candidates and target_idx < len(candidates):
            target_actor = candidates[target_idx]
            real_dist = self.vehicle.get_location().distance(target_actor.get_location())
        
        model_dist = np.linalg.norm(raw_traj[-1]) + 1e-6
        scaling_factor = np.clip(real_dist / model_dist, 1.0, 5.0)
        adaptive_traj = raw_traj * scaling_factor
        
        # 3. Control (E2E Baseline: PID following trajectory)
        # NO MPC, NO SAFETY CONSTRAINTS
        
        # Lateral
        look_ahead_idx = min(int(10 + speed), len(adaptive_traj)-1)
        target_point = adaptive_traj[look_ahead_idx]
        steer = self.lat_pid.run_step(target_point[1])
        
        # Longitudinal (Follow trajectory speed implicitly or distance)
        # The trajectory is spatial.
        # We can try to maintain the distance implied by the trajectory end point?
        # Or simpler: Target Speed = Distance / Time?
        # Let's assume the trajectory implies a desired speed.
        # Length of trajectory ~ distance to cover in T=2.0s?
        # V_target = Length / 2.0
        traj_len = np.linalg.norm(adaptive_traj[-1])
        target_speed = traj_len / 2.0 # 2.0s horizon
        
        # Clip target speed to safe limits
        target_speed = np.clip(target_speed, 0.0, 30.0)
        
        acc_cmd = self.lon_pid.run_step(target_speed, speed)
        
        throttle = 0.0; brake = 0.0
        if acc_cmd > 0: throttle = acc_cmd
        else: brake = abs(acc_cmd)
        
        return carla.VehicleControl(throttle=float(throttle), steer=float(steer), brake=float(brake))
