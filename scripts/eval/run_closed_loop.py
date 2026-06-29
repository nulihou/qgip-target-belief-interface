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

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.train.model import QGIPNet

# Parse Args
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--blind-duration", type=float, default=1.0)
args, _ = parser.parse_known_args()

# Fault Injection Config
BLIND_DURATION = args.blind_duration
BLIND_INTERVAL = 5.0

# ==============================================================================
# Lightweight Leader Classifier
# ==============================================================================
class LeaderClassifier(nn.Module):
    def __init__(self, node_dim=32, edge_dim=16, hidden_dim=64):
        super().__init__()
        self.node_enc = nn.Sequential(nn.Linear(node_dim, hidden_dim), nn.ReLU())
        self.edge_enc = nn.Sequential(nn.Linear(edge_dim, hidden_dim), nn.ReLU())
        
        self.conv1 = GATv2Conv(hidden_dim, hidden_dim, edge_dim=hidden_dim, add_self_loops=False)
        self.conv2 = GATv2Conv(hidden_dim, hidden_dim, edge_dim=hidden_dim, add_self_loops=False)
        
        self.head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )

    def forward(self, x, edge_index, edge_attr):
        x = self.node_enc(x)
        edge_attr = self.edge_enc(edge_attr)
        x = x + self.conv1(x, edge_index, edge_attr)
        x = torch.relu(x)
        x = x + self.conv2(x, edge_index, edge_attr)
        x = torch.relu(x)
        scores = self.head(x).squeeze(-1)
        return scores

# ==============================================================================
# V6.4 Repair: Minimal SceneGraphBuilder (No External Dependencies)
# ==============================================================================
def build_node_features_minimal(ego_transform, vehicles, anchor_id):
    """
    Re-implementation of feature extraction to fix 'Graph Build Error'.
    Node dim: 32
    """
    ego_loc = ego_transform.location
    ego_yaw = math.radians(ego_transform.rotation.yaw)
    
    # Anchor transform
    anchor_tf = ego_transform
    for v in vehicles:
        if v.id == anchor_id:
            anchor_tf = v.get_transform()
            break
    
    ax = anchor_tf.location.x
    ay = anchor_tf.location.y
    ayaw = math.radians(anchor_tf.rotation.yaw)
    
    feats = []
    
    for v in vehicles:
        tf = v.get_transform()
        loc = tf.location
        vel = v.get_velocity()
        
        # 1. Ego-relative
        dx = loc.x - ego_loc.x
        dy = loc.y - ego_loc.y
        dist = math.sqrt(dx*dx + dy*dy)
        angle = math.atan2(dy, dx) - ego_yaw
        # Normalize angle
        angle = (angle + math.pi) % (2 * math.pi) - math.pi
        
        # 2. Anchor-relative
        dx_a = loc.x - ax
        dy_a = loc.y - ay
        dist_a = math.sqrt(dx_a*dx_a + dy_a*dy_a)
        angle_a = math.atan2(dy_a, dx_a) - ayaw
        angle_a = (angle_a + math.pi) % (2 * math.pi) - math.pi
        
        speed = math.sqrt(vel.x**2 + vel.y**2)
        
        # Construct feature vector (match training dim=32)
        f = np.zeros(32, dtype=np.float32)
        f[0] = dx
        f[1] = dy
        f[2] = dist
        f[3] = math.cos(angle)
        f[4] = math.sin(angle)
        
        f[5] = dx_a
        f[6] = dy_a
        f[7] = dist_a
        f[8] = math.cos(angle_a)
        f[9] = math.sin(angle_a)
        
        f[10] = speed
        f[11] = 1.0 if v.id == anchor_id else 0.0
        
        feats.append(f)
        
    return np.stack(feats), np.ones(len(vehicles))

def build_edges_minimal(vehicles):
    """
    Fully connected edges. Edge dim: 16
    """
    N = len(vehicles)
    src_list = []
    dst_list = []
    attr_list = []
    
    for i in range(N):
        loc_i = vehicles[i].get_transform().location
        for j in range(N):
            if i == j: continue
            
            loc_j = vehicles[j].get_transform().location
            dx = loc_j.x - loc_i.x
            dy = loc_j.y - loc_i.y
            dist = math.sqrt(dx*dx + dy*dy)
            angle = math.atan2(dy, dx)
            
            f = np.zeros(16, dtype=np.float32)
            f[0] = dx
            f[1] = dy
            f[2] = dist
            f[3] = math.cos(angle)
            f[4] = math.sin(angle)
            f[5] = 1.0 if dist < 30.0 else 0.0 # Near flag
            
            src_list.append(i)
            dst_list.append(j)
            attr_list.append(f)
            
    if not src_list: # Single node case
        return np.zeros((2, 0), dtype=np.long), np.zeros((0, 16), dtype=np.float32)
        
    edge_index = np.stack([src_list, dst_list], axis=0)
    edge_attr = np.stack(attr_list, axis=0)
    return edge_index, edge_attr

class AccelerationTracker:
    def __init__(self, alpha=0.1):
        self.alpha = alpha
        self.last_vel = None
        self.last_time = None
        self.filtered_acc = 0.0

    def update(self, current_vel, current_time):
        if self.last_vel is None:
            self.last_vel = current_vel
            self.last_time = current_time
            return 0.0
        
        dt = current_time - self.last_time
        if dt < 1e-3: return self.filtered_acc
        
        raw_acc = (current_vel - self.last_vel) / dt
        # 简单的限幅，防止计算异常
        raw_acc = np.clip(raw_acc, -10.0, 10.0)
        
        self.filtered_acc = self.alpha * raw_acc + (1 - self.alpha) * self.filtered_acc
        
        self.last_vel = current_vel
        self.last_time = current_time
        return self.filtered_acc

class KalmanTracker:
    """V7.2: Motion Prediction Module"""
    def __init__(self, dt=0.05):
        self.dt = dt
        # State: [x, y, vx, vy]
        self.x = np.zeros(4)
        self.P = np.eye(4) * 100.0 # Initial uncertainty
        
        # Process Model (Constant Velocity)
        self.F = np.eye(4)
        self.F[0, 2] = dt
        self.F[1, 3] = dt
        
        # Measurement Model
        self.H = np.eye(4)
        
        # Noise Covariances
        self.R = np.eye(4) * 0.1 # Measurement noise (Sensor is accurate)
        self.Q = np.eye(4) * 0.5 # Process noise (Driver can change accel)
        
        self.is_initialized = False
        self.lost_steps = 0
        self.last_nis = float("nan")
        self.last_update_mode = "uninitialized"
        self.disable_nis_gating = False
        self.disable_hard_recovery = False
        self.soft_gate_threshold = 12.0
        self.hard_gate_threshold = 20.0

    def update(self, measurement, confidence=1.0):
        # measurement: [x, y, vx, vy]
        if not self.is_initialized:
            self.x = measurement
            # Initial uncertainty: Pos small, Vel large
            self.P = np.diag([1.0, 1.0, 100.0, 100.0])
            self.is_initialized = True
            self.lost_steps = 0
            self.last_nis = 0.0
            self.last_update_mode = "init"
            return self.x
        
        # Adaptive Q/R based on confidence
        # High confidence -> Trust measurement more (Q stays same, R stays same)
        # Low confidence -> Trust model more (Increase R) + More Process Noise (Increase Q)
        current_R = self.R * (1.0 / (confidence + 1e-6))
        current_Q = self.Q * (1.0 + 5.0 * (1.0 - confidence))
        
        # Predict Phase
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + current_Q
        
        # Update Phase
        y = measurement - self.H @ self.x
        
        # NIS Gating (Outlier Rejection)
        # Chi-squared (df=2): 95%=5.99, 99%=9.21
        S = self.H @ self.P @ self.H.T + current_R
        nis = float(y.T @ np.linalg.inv(S) @ y)
        self.last_nis = nis

        if self.disable_nis_gating:
            K = self.P @ self.H.T @ np.linalg.inv(S)
            self.x = self.x + K @ y
            self.P = (np.eye(4) - K @ self.H) @ self.P
            self.lost_steps = 0
            self.last_update_mode = "normal"
            return self.x
        
        # Two-stage gating. Defaults are validation-set operating gates; the
        # batch runner can override them for threshold-sensitivity experiments.
        T_reject = float(getattr(self, "soft_gate_threshold", 12.0))
        T_reset = float(getattr(self, "hard_gate_threshold", 20.0))
        
        if nis > T_reset: 
             # Hard Reset if confident
             if self.disable_hard_recovery:
                 self.last_update_mode = "hard_reject"
             elif confidence > 0.8:
                 self.x = measurement
                 self.P = np.diag([1.0, 1.0, 100.0, 100.0]) # Reasonable re-init covariance
                 self.last_update_mode = "hard_reset"
             else:
                 pass # Ignore outlier
                 self.last_update_mode = "hard_reject"
                 
        elif nis > T_reject:
             # Soft Update (Inflate R significantly)
             inflated_R = current_R * 10.0
             S_soft = self.H @ self.P @ self.H.T + inflated_R
             K = self.P @ self.H.T @ np.linalg.inv(S_soft)
             self.x = self.x + K @ y
             self.P = (np.eye(4) - K @ self.H) @ self.P
             self.last_update_mode = "soft"
             
        else:
            # Normal Update
            K = self.P @ self.H.T @ np.linalg.inv(S)
            self.x = self.x + K @ y
            self.P = (np.eye(4) - K @ self.H) @ self.P
            self.last_update_mode = "normal"
        
        self.lost_steps = 0
        return self.x

    def predict(self):
        if not self.is_initialized: return None
        
        # Pure Prediction
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        self.lost_steps += 1
        self.last_nis = float("nan")
        self.last_update_mode = "predict"
        return self.x


class SceneGraphBuilder:
    def __init__(self, radius=50.0):
        self.radius = radius

    def build_graph(self, ego_vehicle, candidates):
        try:
            if not candidates:
                return None
                
            ego_transform = ego_vehicle.get_transform()
            vehicles = list(candidates)
            if len(vehicles) == 0: return None
            
            # 使用本地的 Minimal Builder
            anchor_id = vehicles[0].id
            
            node_feats, candidate_mask = build_node_features_minimal(ego_transform, vehicles, anchor_id)
            edge_index, edge_attr = build_edges_minimal(vehicles)
            
            actor_ids = [v.id for v in vehicles]
            
            return {
                "node_feats": node_feats,
                "edge_index": edge_index,
                "edge_attr": edge_attr,
                "candidate_mask": candidate_mask,
                "actor_ids": actor_ids
            }
        except Exception as e:
            print(f"Graph Build Error: {e}")
            return None

class LateralPID:
    """仅用于横向控制的 PID"""
    def __init__(self, K_P=1.95, K_D=0.2, K_I=0.07, dt=0.05):
        self.K_P = K_P
        self.K_D = K_D
        self.K_I = K_I
        self.dt = dt
        self._e_buffer = deque(maxlen=10)

    def run_step(self, target_y_offset):
        """
        target_y_offset: 目标在 Ego 坐标系下的横向偏移 (左负右正? 需根据坐标系确认)
        CARLA 右手坐标系: Y 是右。所以 target_y > 0 在右边。
        如果 target_y_offset 是我们希望去的地方（比如 0），
        error = target - current. current 在 ego frame 是 0.
        所以 error = target_y_offset.
        """
        error = target_y_offset
        
        self._e_buffer.append(error)
        if len(self._e_buffer) >= 2:
            _de = (self._e_buffer[-1] - self._e_buffer[-2]) / self.dt
            _ie = sum(self._e_buffer) * self.dt
        else:
            _de = 0.0
            _ie = 0.0
            
        return np.clip(self.K_P * error + self.K_D * _de + self.K_I * _ie, -1.0, 1.0)

class QGIPAgent:
    def __init__(self, vehicle, model_path, device='cuda'):
        self.vehicle = vehicle
        self.device = device
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        self.qgip_model_path = os.environ.get("QGIP_MODEL_PATH", model_path)
        if not os.path.isabs(self.qgip_model_path):
            self.qgip_model_path = os.path.join(project_root, self.qgip_model_path)

        self.leader_ckpt_path = os.environ.get(
            "QGIP_LEADER_CKPT",
            os.path.join(project_root, "checkpoints/v7/llc_epoch_20.pth"),
        )
        if not os.path.isabs(self.leader_ckpt_path):
            self.leader_ckpt_path = os.path.join(project_root, self.leader_ckpt_path)

        self.debug_log_path = os.environ.get("QGIP_CLOSED_LOOP_DEBUG_LOG", "final_results_closed_loop.txt")
        
        # 加载模型
        # EDGE_FEAT_DIM 应该是 16 (参考 collect_multi_candidate_advanced.py)
        self.model = QGIPNet(node_dim=32, edge_dim=16, hidden_dim=128).to(device)
        
        # Apply Ablation Flag if set on class
        if getattr(self, 'ABLATION_NO_QUERY', False):
             self.model.ablation_no_query = True
        if getattr(self, 'ABLATION_QUERY_ZERO', False):
             self.model.ablation_query_zero = True
        if getattr(self, 'ABLATION_FILM_OFF', False):
             self.model.ablation_film_off = True
        if getattr(self, 'ABLATION_EDGE_OFF', False):
             self.model.ablation_edge_off = True
        
        # 加载权重 (处理可能的 DistributedDataParallel 前缀)
        print(f"[INFO] Loading QGIP model checkpoint from {self.qgip_model_path}")
        state_dict = torch.load(self.qgip_model_path, map_location=device)
        if 'state_dict' in state_dict: state_dict = state_dict['state_dict']
        new_state_dict = {}
        for k, v in state_dict.items():
            new_state_dict[k.replace('module.', '')] = v
        self.model.load_state_dict(new_state_dict, strict=False)
        self.model.eval()
        
        self.graph_builder = SceneGraphBuilder()
        self.lat_pid = LateralPID()
        self.tracker = AccelerationTracker()
        
        # 轨迹平滑缓存
        self.prev_traj = None
        
        # V6.4: 时序逻辑平滑 (Temporal Logit Smoothing)
        self.historical_logits = None
        self.logit_alpha = 0.7
        self.v7_score_ema = None
        self.v7_score_alpha = 0.65
        self.v7_hysteresis_margin = 0.05
        self.sticky_target_idx = None
        
        # V7.2: Kalman Tracker
        self.kf = KalmanTracker(dt=0.05)
        self.kf.disable_nis_gating = bool(getattr(self, 'ABLATION_NIS_OFF', False))
        self.kf.disable_hard_recovery = bool(getattr(self, 'ABLATION_HARD_RECOVERY_OFF', False))
        self.kf.soft_gate_threshold = float(os.environ.get("QGIP_NIS_SOFT_GATE", getattr(self, 'NIS_SOFT_GATE', 12.0)))
        self.kf.hard_gate_threshold = float(os.environ.get("QGIP_NIS_HARD_GATE", getattr(self, 'NIS_HARD_GATE', 20.0)))
        if self.kf.hard_gate_threshold <= self.kf.soft_gate_threshold:
            self.kf.hard_gate_threshold = self.kf.soft_gate_threshold + 1e-6
        self.last_selected_actor_id = None
        self.last_selected_source_actor_id = None
        
        # Lightweight leader classifier checkpoint. The historical folder name
        # `v7` is a model-artifact label, not the paper/submission version.
        self.v7_model = LeaderClassifier().to(device)
        
        if os.path.exists(self.leader_ckpt_path):
            print(f"[INFO] Loading leader classifier checkpoint from {self.leader_ckpt_path}")
            self.v7_model.load_state_dict(torch.load(self.leader_ckpt_path, map_location=device))
            self.v7_model.eval()
            self.use_v7 = True
        else:
            print(f"[WARN] Leader classifier checkpoint not found at {self.leader_ckpt_path}; using QGIP selector.")
            self.use_v7 = False

    def process_model_output(self, raw_deltas):
        """轨迹积分与平滑 (V6.2 Stable Logic)"""
        curr_traj = torch.cumsum(raw_deltas, dim=1).cpu().numpy()[0]
        if self.prev_traj is not None:
            alpha = 0.7
            len_min = min(len(curr_traj)-1, len(self.prev_traj[1:]))
            smooth = alpha * curr_traj[:-1][:len_min] + (1-alpha) * self.prev_traj[1:][:len_min]
            final_traj = np.vstack([smooth, curr_traj[-1]])
        else:
            final_traj = curr_traj
        self.prev_traj = final_traj
        return final_traj

    def run_step(self, query_vec, candidates):
        try:
            # ------------------------------------------------------------------
            # 1. 感知与推理 (Perception & Inference)
            # ------------------------------------------------------------------
            snapshot = self.graph_builder.build_graph(self.vehicle, candidates)
            if snapshot is None:
                self.last_selected_actor_id = None
                self.last_selected_source_actor_id = None
                return carla.VehicleControl()
    
            x = torch.from_numpy(snapshot['node_feats']).float().to(self.device)
            edge_index = torch.from_numpy(snapshot['edge_index']).long().to(self.device)
            edge_attr = torch.from_numpy(snapshot['edge_attr']).float().to(self.device)
            if getattr(self, 'ABLATION_EDGE_OFF', False):
                edge_attr = torch.zeros_like(edge_attr)
            q = torch.tensor(query_vec).float().to(self.device).unsqueeze(0)
            v = self.vehicle.get_velocity()
            speed = np.sqrt(v.x**2 + v.y**2)
            ego_vel = torch.tensor([[speed, 0.0]]).float().to(self.device)
    
            with torch.no_grad():
                # 1. V7.0 Inference (Priority)
                target_idx = 0
                if self.use_v7 and not getattr(self, 'FORCE_GNN_SELECTOR', False):
                    scores = self.v7_model(x, edge_index, edge_attr)
                    score_probs = torch.softmax(scores, dim=0)
                    if self.v7_score_ema is not None and self.v7_score_ema.shape == score_probs.shape:
                        self.v7_score_ema = self.v7_score_alpha * score_probs + (1.0 - self.v7_score_alpha) * self.v7_score_ema
                    else:
                        self.v7_score_ema = score_probs
                        self.sticky_target_idx = None

                    candidate_idx = torch.argmax(self.v7_score_ema).item()
                    if (
                        self.sticky_target_idx is not None
                        and self.sticky_target_idx < self.v7_score_ema.numel()
                        and self.v7_score_ema[self.sticky_target_idx] + self.v7_hysteresis_margin >= self.v7_score_ema[candidate_idx]
                    ):
                        target_idx = self.sticky_target_idx
                    else:
                        target_idx = candidate_idx
                    self.sticky_target_idx = target_idx
                
                # 2. V6.4 Inference (Legacy & Trajectory)
                logits, pred_deltas, _ = self.model(
                    x, edge_index, edge_attr, q, 
                    batch=torch.zeros(x.size(0), dtype=torch.long).to(self.device),
                    ptr=torch.tensor([0, x.size(0)], dtype=torch.long).to(self.device),
                    ego_velocity=ego_vel
                )
                
                # 如果没有 V7，使用 V6.4 逻辑
                if (not self.use_v7) or getattr(self, 'FORCE_GNN_SELECTOR', False):
                    # V6.4: Stage 1 - 时序逻辑平滑
                    current_probs = torch.softmax(logits.squeeze(-1), dim=0)
                    
                    if self.historical_logits is None:
                        self.historical_logits = current_probs
                    else:
                        if self.historical_logits.shape == current_probs.shape:
                            self.historical_logits = self.logit_alpha * current_probs + (1 - self.logit_alpha) * self.historical_logits
                        else:
                            self.historical_logits = current_probs 
                    
                    final_probs = self.historical_logits
                    target_idx = torch.argmax(final_probs).item()
            
            # ------------------------------------------------------------------
            # 2. 几何域适应 (Geometric Domain Adaptation) & V7.2 Tracking
            # ------------------------------------------------------------------
            # Correctly select the trajectory for the target
            if target_idx < pred_deltas.size(0):
                selected_deltas = pred_deltas[target_idx:target_idx+1]
            else:
                selected_deltas = pred_deltas[0:1] # Fallback
            if candidates and target_idx < len(candidates):
                selected_actor = candidates[target_idx]
                self.last_selected_actor_id = getattr(selected_actor, "id", None)
                self.last_selected_source_actor_id = getattr(selected_actor, "source_actor_id", self.last_selected_actor_id)
            else:
                self.last_selected_actor_id = None
                self.last_selected_source_actor_id = None
                
            raw_traj = self.process_model_output(selected_deltas)
            
            # 获取真实感知数据
            real_dist = 100.0
            target_vel = 0.0
            target_acc_est = 0.0
            
            timestamp = self.vehicle.get_world().get_snapshot().timestamp.elapsed_seconds
            
            # V7.2: Kalman Filter Logic
            # -------------------------
            
            # Hysteresis Logic
            # V7.0 score (0~1) can be used as confidence
            # But here we assume ID match is 1.0 confidence
            
            if candidates and target_idx < len(candidates):
                target_actor = candidates[target_idx]
                loc_target = target_actor.get_location()
                vt = target_actor.get_velocity()
                
                # Update KF
                measurement = np.array([loc_target.x, loc_target.y, vt.x, vt.y])
                kf_state = self.kf.update(measurement, confidence=1.0)
                
                # Use raw measurement for immediate control (more responsive)
                loc_ego = self.vehicle.get_location()
                real_dist = loc_ego.distance(loc_target)
                target_vel = np.sqrt(vt.x**2 + vt.y**2)
                
                target_acc_est = self.tracker.update(target_vel, timestamp)
                
            elif self.kf.is_initialized and self.kf.lost_steps < int(getattr(self, 'GHOST_HORIZON', 30)): # Increase to 1.5s (30 steps) for robustness
                # Ghost Target Logic
                if getattr(self, 'ABLATION_LAST_OBS_HOLD', False):
                    kf_state = self.kf.x.copy()
                    self.kf.lost_steps += 1
                    self.kf.last_nis = float("nan")
                    self.kf.last_update_mode = "hold"
                else:
                    kf_state = self.kf.predict()
                
                # Calculate dist to ghost
                loc_ego = self.vehicle.get_location()
                dx = kf_state[0] - loc_ego.x
                dy = kf_state[1] - loc_ego.y
                real_dist = math.sqrt(dx*dx + dy*dy)
                
                target_vel = math.sqrt(kf_state[2]**2 + kf_state[3]**2)
                target_acc_est = 0.0 # Assume constant velocity when lost
                
                with open(self.debug_log_path, "a", encoding="utf-8") as f:
                    f.write(f"👻 Ghost Tracking: Dist={real_dist:.1f}m\n")
            
            else:
                # Completely Lost
                real_dist = 100.0
                target_vel = 0.0
                target_acc_est = 0.0
    
            # 计算 Scaling Factor (Rubber Band)
            model_dist = np.linalg.norm(raw_traj[-1]) + 1e-6
            scaling_factor = np.clip(real_dist / model_dist, 1.0, 5.0)
            adaptive_traj = raw_traj * scaling_factor
            
            # ------------------------------------------------------------------
            # 3. 横向控制
            # ------------------------------------------------------------------
            look_ahead_idx = min(int(10 + speed), len(adaptive_traj)-1)
            steer = self.lat_pid.run_step(adaptive_traj[look_ahead_idx][1])
    
            # ------------------------------------------------------------------
            # 4. 纵向+横向联合控制: V6.2 - Hard Constraint MPC
            # ------------------------------------------------------------------
            
            # --- A. 参数 ---
            SYSTEM_DELAY = 0.15 
            input_dist = real_dist - (speed * SYSTEM_DELAY)
            
            dt_mpc = 0.1 
            horizon = 15
            
            lat_candidates = [-3.0, 0.0, 3.0] 
            acc_candidates = [-8.0, -4.5, -2.0, 0.0, 1.5, 3.0]
    
            best_cost = float('inf') 
            best_acc = -4.5 
            best_lat = 0.0 
            
            desired_gap = 10.0 + 1.5 * speed 
            
            current_target_acc = target_acc_est
    
            # --- B. 采样循环 ---
            for lat_offset in lat_candidates:
                lane_change_cost = abs(lat_offset) * 200.0 
                
                for acc in acc_candidates: 
                    cost = lane_change_cost 
                    
                    sim_v_ego = speed 
                    sim_rel_dist_x = input_dist 
                    sim_rel_y = 0.0             
                    
                    is_collision = False 
                    has_overtaken = False 
                    
                    for t in range(horizon): 
                        # 动力学推演
                        sim_v_ego += acc * dt_mpc 
                        sim_v_ego = max(0.0, sim_v_ego) 
                        
                        pred_target_vel = max(0.0, target_vel + current_target_acc * (t * dt_mpc)) 
                        
                        sim_rel_dist_x += (pred_target_vel - sim_v_ego) * dt_mpc 
                        
                        traj_ratio = min(1.0, (t * dt_mpc) / 1.0) 
                        current_lat_pos = lat_offset * traj_ratio 
                        sim_rel_y = 0.0 - current_lat_pos 
    
                        # 碰撞检测 (Hard Constraint)
                        if sim_rel_dist_x > -2.0 and sim_rel_dist_x < 5.0: 
                            if abs(sim_rel_y) < 1.8: 
                                is_collision = True 
                                break 
                        
                        if sim_rel_dist_x < -2.0: 
                            has_overtaken = True 
    
                    # Cost 计算
                    if is_collision and not getattr(self, 'ABLATION_MPC_FILTER_OFF', False): 
                        cost = float('inf') 
                    else: 
                        if not has_overtaken: 
                            if sim_rel_dist_x < 10.0: 
                                cost += (10.0 - sim_rel_dist_x) ** 2 * 50.0 
                            
                            cost += abs(sim_rel_dist_x - desired_gap) * 2.0 
                            cost += abs(acc) * 5.0 
                        else: 
                            cost -= 5000.0 
                            cost += abs(sim_v_ego - 30.0) * 1.0 
                            if sim_rel_dist_x < -10.0:
                                cost += abs(lat_offset) * 50.0 
    
                    if cost < best_cost: 
                        best_cost = cost 
                        best_acc = acc 
                        best_lat = lat_offset 
    
            # --- C. 执行 --- 
            throttle = 0.0 
            brake = 0.0 
            
            if best_acc > 0: 
                throttle = np.clip(best_acc / 3.0, 0, 1) 
            else: 
                brake = np.clip(abs(best_acc) / 8.0, 0, 1) 
    
            look_ahead_idx = min(int(10 + speed), len(adaptive_traj)-1) 
            base_target = adaptive_traj[look_ahead_idx] 
            final_target_y = base_target[1] + best_lat 
            
            steer = self.lat_pid.run_step(final_target_y)
    
            # AEB
            if (not getattr(self, 'ABLATION_MPC_FILTER_OFF', False)) and abs(best_lat) < 0.1 and real_dist < 4.0: 
                 print("[WARN] AEB Triggered") 
                 return carla.VehicleControl(throttle=0.0, steer=float(steer), brake=1.0) 
            
            return carla.VehicleControl(throttle=float(throttle), steer=float(steer), brake=float(brake))
        
        except Exception as e:
            with open(getattr(self, "debug_log_path", "final_results_closed_loop.txt"), "a", encoding="utf-8") as f:
                f.write(f"ERROR in run_step: {e}\n")
            print(f"ERROR in run_step: {e}")
            return carla.VehicleControl()
