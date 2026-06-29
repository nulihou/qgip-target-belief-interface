import carla
import torch
import numpy as np
import sys
import os
import math
import collections
from collections import deque

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from scripts.train.model import QGIPNet

# ==============================================================================
# Helpers
# ==============================================================================

def build_node_features_minimal(ego_transform, vehicles, anchor_id):
    ego_loc = ego_transform.location
    ego_yaw = math.radians(ego_transform.rotation.yaw)
    
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
        
        dx = loc.x - ego_loc.x
        dy = loc.y - ego_loc.y
        dist = math.sqrt(dx*dx + dy*dy)
        angle = math.atan2(dy, dx) - ego_yaw
        angle = (angle + math.pi) % (2 * math.pi) - math.pi
        
        dx_a = loc.x - ax
        dy_a = loc.y - ay
        dist_a = math.sqrt(dx_a*dx_a + dy_a*dy_a)
        angle_a = math.atan2(dy_a, dx_a) - ayaw
        angle_a = (angle_a + math.pi) % (2 * math.pi) - math.pi
        
        speed = math.sqrt(vel.x**2 + vel.y**2)
        
        f = np.zeros(32, dtype=np.float32)
        f[0] = dx; f[1] = dy; f[2] = dist; f[3] = math.cos(angle); f[4] = math.sin(angle)
        f[5] = dx_a; f[6] = dy_a; f[7] = dist_a; f[8] = math.cos(angle_a); f[9] = math.sin(angle_a)
        f[10] = speed
        f[11] = 1.0 if v.id == anchor_id else 0.0
        
        feats.append(f)
        
    return np.stack(feats), np.ones(len(vehicles))

def build_edges_minimal(vehicles):
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
            f[0] = dx; f[1] = dy; f[2] = dist; f[3] = math.cos(angle); f[4] = math.sin(angle)
            f[5] = 1.0 if dist < 30.0 else 0.0
            
            src_list.append(i); dst_list.append(j); attr_list.append(f)
            
    if not src_list:
        return np.zeros((2, 0), dtype=np.long), np.zeros((0, 16), dtype=np.float32)
        
    edge_index = np.stack([src_list, dst_list], axis=0)
    edge_attr = np.stack(attr_list, axis=0)
    return edge_index, edge_attr

class SceneGraphBuilder:
    def __init__(self, radius=50.0):
        self.radius = radius

    def build_graph(self, ego_vehicle, candidates):
        try:
            if not candidates: return None
            ego_transform = ego_vehicle.get_transform()
            vehicles = list(candidates)
            if len(vehicles) == 0: return None
            
            anchor_id = vehicles[0].id
            node_feats, candidate_mask = build_node_features_minimal(ego_transform, vehicles, anchor_id)
            edge_index, edge_attr = build_edges_minimal(vehicles)
            actor_ids = [v.id for v in vehicles]
            
            return {
                "node_feats": node_feats, "edge_index": edge_index, "edge_attr": edge_attr,
                "candidate_mask": candidate_mask, "actor_ids": actor_ids
            }
        except Exception as e:
            print(f"Graph Build Error: {e}")
            return None

class LateralPID:
    def __init__(self, K_P=1.95, K_D=0.2, K_I=0.07, dt=0.05):
        self.K_P = K_P; self.K_D = K_D; self.K_I = K_I; self.dt = dt
        self._e_buffer = deque(maxlen=10)

    def run_step(self, target_y_offset):
        error = target_y_offset
        self._e_buffer.append(error)
        if len(self._e_buffer) >= 2:
            _de = (self._e_buffer[-1] - self._e_buffer[-2]) / self.dt
            _ie = sum(self._e_buffer) * self.dt
        else:
            _de = 0.0; _ie = 0.0
        return np.clip(self.K_P * error + self.K_D * _de + self.K_I * _ie, -1.0, 1.0)

class AccelerationTracker:
    def __init__(self, alpha=0.1):
        self.alpha = alpha
        self.last_vel = None; self.last_time = None; self.filtered_acc = 0.0

    def update(self, current_vel, current_time):
        if self.last_vel is None:
            self.last_vel = current_vel; self.last_time = current_time
            return 0.0
        dt = current_time - self.last_time
        if dt < 1e-3: return self.filtered_acc
        raw_acc = (current_vel - self.last_vel) / dt
        raw_acc = np.clip(raw_acc, -10.0, 10.0)
        self.filtered_acc = self.alpha * raw_acc + (1 - self.alpha) * self.filtered_acc
        self.last_vel = current_vel; self.last_time = current_time
        return self.filtered_acc

# ==============================================================================
# Baseline-Rule Agent (V6.4)
# ==============================================================================
class QGIPAgent:
    def __init__(self, vehicle, model_path, device='cuda'):
        self.vehicle = vehicle
        self.device = device
        
        self.model = QGIPNet(node_dim=32, edge_dim=16, hidden_dim=128).to(device)
        state_dict = torch.load(model_path, map_location=device)
        if 'state_dict' in state_dict: state_dict = state_dict['state_dict']
        new_state_dict = {}
        for k, v in state_dict.items():
            new_state_dict[k.replace('module.', '')] = v
        self.model.load_state_dict(new_state_dict, strict=False)
        self.model.eval()
        
        self.graph_builder = SceneGraphBuilder()
        self.lat_pid = LateralPID()
        self.tracker = AccelerationTracker()
        self.prev_traj = None
        self.last_selected_actor_id = None
        self.last_selected_source_actor_id = None

    def process_model_output(self, raw_deltas):
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

    def _get_rule_based_target(self, candidates):
        """Baseline Logic: Select closest vehicle in front"""
        if not candidates: return 0
        ego_loc = self.vehicle.get_location()
        min_dist = 9999.0
        best_idx = 0
        for i, actor in enumerate(candidates):
            dist = ego_loc.distance(actor.get_location())
            if dist < min_dist:
                min_dist = dist
                best_idx = i
        return best_idx

    def run_step(self, query_vec, candidates):
        # 1. Perception
        snapshot = self.graph_builder.build_graph(self.vehicle, candidates)
        if snapshot is None:
            self.last_selected_actor_id = None
            self.last_selected_source_actor_id = None
            return carla.VehicleControl()

        x = torch.from_numpy(snapshot['node_feats']).float().to(self.device)
        edge_index = torch.from_numpy(snapshot['edge_index']).long().to(self.device)
        edge_attr = torch.from_numpy(snapshot['edge_attr']).float().to(self.device)
        q = torch.tensor(query_vec).float().to(self.device).unsqueeze(0)
        v = self.vehicle.get_velocity()
        speed = np.sqrt(v.x**2 + v.y**2)
        ego_vel = torch.tensor([[speed, 0.0]]).float().to(self.device)

        with torch.no_grad():
            logits, pred_deltas, _ = self.model(
                x, edge_index, edge_attr, q, 
                batch=torch.zeros(x.size(0), dtype=torch.long).to(self.device),
                ptr=torch.tensor([0, x.size(0)], dtype=torch.long).to(self.device),
                ego_velocity=ego_vel
            )

        # 2. Rule-based Selection (BASELINE CORE)
        target_idx = self._get_rule_based_target(candidates)
        if candidates and target_idx < len(candidates):
            selected_actor = candidates[target_idx]
            self.last_selected_actor_id = getattr(selected_actor, "id", None)
            self.last_selected_source_actor_id = getattr(selected_actor, "source_actor_id", self.last_selected_actor_id)
        else:
            self.last_selected_actor_id = None
            self.last_selected_source_actor_id = None
        
        if target_idx < pred_deltas.size(0):
            selected_deltas = pred_deltas[target_idx:target_idx+1]
        else:
            selected_deltas = pred_deltas[0:1]
            
        raw_traj = self.process_model_output(selected_deltas)
        
        # 3. Control (Standard)
        real_dist = 100.0
        target_vel = 0.0
        target_acc_est = 0.0
        timestamp = self.vehicle.get_world().get_snapshot().timestamp.elapsed_seconds
        
        if candidates and target_idx < len(candidates):
            target_actor = candidates[target_idx]
            real_dist = self.vehicle.get_location().distance(target_actor.get_location())
            vt = target_actor.get_velocity()
            target_vel = np.sqrt(vt.x**2 + vt.y**2)
            target_acc_est = self.tracker.update(target_vel, timestamp)

        model_dist = np.linalg.norm(raw_traj[-1]) + 1e-6
        scaling_factor = np.clip(real_dist / model_dist, 1.0, 5.0)
        adaptive_traj = raw_traj * scaling_factor
        
        look_ahead_idx = min(int(10 + speed), len(adaptive_traj)-1)
        steer = self.lat_pid.run_step(adaptive_traj[look_ahead_idx][1])
        
        # MPC Logic (Simplified for Baseline)
        throttle = 0.0; brake = 0.0
        # ... (Assuming simple PID for baseline to match V6.4 exact behavior or reuse MPC)
        # To be strictly fair, we should reuse the EXACT MPC code from run_closed_loop.py
        # For brevity, I will use a simple PID for longitudinal here, or I can copy the MPC code.
        # Let's copy the MPC code to be fair.
        
        SYSTEM_DELAY = 0.15 
        input_dist = real_dist - (speed * SYSTEM_DELAY)
        dt_mpc = 0.1; horizon = 15
        lat_candidates = [-3.0, 0.0, 3.0] 
        acc_candidates = [-8.0, -4.5, -2.0, 0.0, 1.5, 3.0]
        best_cost = float('inf'); best_acc = -4.5; best_lat = 0.0 
        desired_gap = 10.0 + 1.5 * speed 

        for lat_offset in lat_candidates:
            lane_change_cost = abs(lat_offset) * 200.0 
            for acc in acc_candidates: 
                cost = lane_change_cost 
                sim_v_ego = speed; sim_rel_dist_x = input_dist; sim_rel_y = 0.0             
                is_collision = False; has_overtaken = False 
                for t in range(horizon): 
                    sim_v_ego += acc * dt_mpc; sim_v_ego = max(0.0, sim_v_ego) 
                    pred_target_vel = max(0.0, target_vel + target_acc_est * (t * dt_mpc)) 
                    sim_rel_dist_x += (pred_target_vel - sim_v_ego) * dt_mpc 
                    traj_ratio = min(1.0, (t * dt_mpc) / 1.0) 
                    current_lat_pos = lat_offset * traj_ratio 
                    sim_rel_y = 0.0 - current_lat_pos 
                    if sim_rel_dist_x > -2.0 and sim_rel_dist_x < 5.0: 
                        if abs(sim_rel_y) < 1.8: is_collision = True; break 
                    if sim_rel_dist_x < -2.0: has_overtaken = True 
                if is_collision: cost = float('inf') 
                else: 
                    if not has_overtaken: 
                        if sim_rel_dist_x < 10.0: cost += (10.0 - sim_rel_dist_x) ** 2 * 50.0 
                        cost += abs(sim_rel_dist_x - desired_gap) * 2.0 
                        cost += abs(acc) * 5.0 
                    else: 
                        cost -= 5000.0 
                        cost += abs(sim_v_ego - 30.0) * 1.0 
                        if sim_rel_dist_x < -10.0: cost += abs(lat_offset) * 50.0 
                if cost < best_cost: best_cost = cost; best_acc = acc; best_lat = lat_offset 

        if best_acc > 0: throttle = np.clip(best_acc / 3.0, 0, 1) 
        else: brake = np.clip(abs(best_acc) / 8.0, 0, 1) 

        look_ahead_idx = min(int(10 + speed), len(adaptive_traj)-1) 
        base_target = adaptive_traj[look_ahead_idx] 
        final_target_y = base_target[1] + best_lat 
        steer = self.lat_pid.run_step(final_target_y)

        if abs(best_lat) < 0.1 and real_dist < 4.0: 
             return carla.VehicleControl(throttle=0.0, steer=float(steer), brake=1.0) 
        
        return carla.VehicleControl(throttle=float(throttle), steer=float(steer), brake=float(brake))
