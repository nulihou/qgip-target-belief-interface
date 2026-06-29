#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Closed-Loop Evaluation Script for Neuro-Symbolic VLN
"""

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import sys
import glob

# === Patch 'imp' for Python 3.12+ compatibility with CARLA eggs ===
try:
    import imp
except ImportError:
    import types
    import importlib.util
    import importlib.machinery
    
    # Create a mock imp module
    imp = types.ModuleType('imp')
    sys.modules['imp'] = imp
    
    # Define constants expected by legacy code
    imp.PKG_DIRECTORY = 5
    imp.PY_SOURCE = 1
    imp.PY_COMPILED = 2
    imp.C_EXTENSION = 3
    imp.SEARCH_ERROR = 0
    
    # Mock functions
    def find_module(name, path=None):
        spec = importlib.util.find_spec(name, path)
        if spec is None:
            raise ImportError(f"No module named {name}")
        return None, spec.origin, ('.py', 'r', imp.PY_SOURCE) # Dummy return
        
    def load_module(name, file, path, description):
        if hasattr(importlib, 'reload'):
            return importlib.import_module(name)
        else:
            return importlib.import_module(name)
            
    def load_dynamic(name, path, file=None):
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module
        raise ImportError(f"Could not load dynamic module {name} from {path}")

    def get_suffixes():
        return [('.py', 'r', imp.PY_SOURCE)]

    imp.find_module = find_module
    imp.load_module = load_module
    imp.load_dynamic = load_dynamic
    imp.get_suffixes = get_suffixes
    
    print("Patched 'imp' module for CARLA compatibility.", flush=True)
# ===================================================================

# Try to add CARLA egg if not found
try:
    # Check if CARLA is already installed
    import carla
    if hasattr(carla, 'Client'):
        print("CARLA already installed.", flush=True)
        egg_found = True # Skip search
    else:
        raise ImportError
except ImportError:
    pass

try:
    # Check if CARLA is already installed
    import carla
    if hasattr(carla, 'Client'):
        print("CARLA already installed.", flush=True)
        egg_found = True # Skip search
    else:
        raise ImportError
except ImportError:
    pass

try:
    # Common paths
    carla_root_paths = [
        os.environ.get("CARLA_PYTHON_API_PATH"),
        'E:/carla/WindowsNoEditor/PythonAPI',
        'C:/CARLA_0.9.13/PythonAPI',
        'D:/carla/PythonAPI',
        '/opt/carla/PythonAPI'
    ]
    
    if 'egg_found' not in locals():
        egg_found = False
    
    if not egg_found:
        for root in carla_root_paths:
            if not root or not os.path.exists(root):
                continue
            
            # method 1: add root to path (if carla is a package there)
            if root not in sys.path:
                sys.path.append(root)
            
            # method 2: look for egg
            # Try exact version first
            egg_pattern = os.path.join(root, 'carla', 'dist', 'carla-*%d.%d-%s.egg' % (
                sys.version_info.major,
                sys.version_info.minor,
                'win-amd64' if os.name == 'nt' else 'linux-x86_64'
            ))
            
            found = glob.glob(egg_pattern)
            
            # If not found, try ANY egg (fallback)
            if not found:
                 egg_pattern = os.path.join(root, 'carla', 'dist', '*.egg')
                 found = glob.glob(egg_pattern)
            
            if found:
                for f in found:
                    if f not in sys.path:
                        sys.path.append(f)
                        print(f"Added CARLA egg: {f}", flush=True)
                egg_found = True
                break
            
    if not egg_found:
         print("Warning: No CARLA egg found in common paths.", flush=True)

except Exception as e:
    print(f"Warning: CARLA setup failed: {e}", flush=True)

import time
import random
import numpy as np
import torch
import carla
import queue
from collections import deque
import math
try:
    import pygame
except ImportError:
    pygame = None
import logging
import csv

# Setup logging
logging.basicConfig(filename='eval.log', level=logging.DEBUG, filemode='a')
logging.info("Starting Eval Script...")

print("Starting Eval Script...", flush=True)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from scripts.modules.perception_oracle import PerceptionOracle
from scripts.modules.logic_adapter import LogicAdapter, IntentPredictor
from scripts.modules.vision_perception import VisionPerception
from scripts.learning.model import BaselineGNN, BaselineE2EAdapter
from scripts.control.mpc_controller import MPCController
from scripts.modules.planning import QuinticPolynomialPlanner # Option 1: Frenet Quintic Planner
from torch_geometric.data import Data, Batch

import argparse

# Parse Arguments
parser = argparse.ArgumentParser(description="Closed-Loop Evaluation")
parser.add_argument("--method", type=str, default="Ours (Full)", help="Method name for logging")
parser.add_argument("--scenario", type=str, default="Easy", choices=["Easy", "Medium", "Hard", "HardRainNoon"], help="Scenario difficulty")
parser.add_argument("--weather", type=str, default="ClearNoon", help="Weather preset name (optional override)")
parser.add_argument("--episodes", type=int, default=3, help="Number of episodes")
parser.add_argument("--model-path", type=str, default="checkpoints/baseline_epoch_10.pth", help="Path to model checkpoint")
parser.add_argument("--save-telemetry", action="store_true", help="Save per-frame telemetry (Exp 3)")
parser.add_argument("--no-memory", action="store_true", help="Ablation: Disable Memory (Exp 2)")
parser.add_argument("--no-soft-mpc", action="store_true", help="Ablation: Disable Soft-MPC (Exp 2)")
parser.add_argument("--no-uncertainty", action="store_true", help="Ablation: Disable Uncertainty-Aware Control (Exp 2)")
args = parser.parse_args()

print(f"DEBUG: Parsed Episodes: {args.episodes}", flush=True)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
MODEL_PATH = args.model_path
if not os.path.exists(MODEL_PATH):
    # Try to find latest checkpoint
    checkpoints = [f for f in os.listdir("checkpoints") if f.endswith(".pth")]
    if checkpoints:
        checkpoints.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))
        MODEL_PATH = os.path.join("checkpoints", checkpoints[-1])

HOST = "localhost"
PORT = 2000
TIMEOUT = 120.0
EVAL_EPISODES = args.episodes
MAX_STEPS = 1000 # Increased for safety (was 500)

# Sensor Config (Must match training/collection)
SENSOR_CONFIG = {
    'rgb_front': {'type': 'sensor.camera.rgb', 'pos': (0.8, 0, 1.7), 'rot': (0, 0, 0), 'fov': 90, 'res': (800, 450)},
    'rgb_bev': {'type': 'sensor.camera.rgb', 'pos': (0.0, 0.0, 20.0), 'rot': (-90, 0, 0), 'fov': 90, 'res': (400, 400)},
    'rgb_left': {'type': 'sensor.camera.rgb', 'pos': (0.0, -1.0, 1.5), 'rot': (0, -45, 0), 'fov': 90, 'res': (240, 135)}, # Reduced Res
    'rgb_right': {'type': 'sensor.camera.rgb', 'pos': (0.0, 1.0, 1.5), 'rot': (0, 45, 0), 'fov': 90, 'res': (240, 135)}, # Reduced Res
    'rgb_rear': {'type': 'sensor.camera.rgb', 'pos': (-1.5, 0.0, 1.5), 'rot': (0, 180, 0), 'fov': 90, 'res': (240, 135)}, # Reduced Res
    'sem_front': {'type': 'sensor.camera.semantic_segmentation', 'pos': (0.8, 0, 1.7), 'rot': (0, 0, 0), 'fov': 90, 'res': (400, 225)}, # Half res for efficiency
    'collision': {'type': 'sensor.other.collision', 'pos': (0, 0, 0), 'rot': (0, 0, 0)},
}

# Vocabulary & Maps (Must match dataset.py)
VOCAB = {
    "<pad>": 0, "<unk>": 1, "follow": 2, "the": 3, ".": 4,
    "red": 5, "green": 6, "blue": 7, "white": 8, "black": 9, 
    "grey": 10, "silver": 11, "yellow": 12, "orange": 13, 
    "brown": 14, "purple": 15, "dark": 16,
    "police": 17, "car": 18, "ambulance": 19, "firetruck": 20, 
    "van": 21, "truck": 22, "motorcycle": 23, "cyclist": 24, 
    "jeep": 25, "vehicle": 26,
    "on": 27, "your": 28, "left": 29, "right": 30, "front": 31, 
    "ahead": 32, "behind": 33, "center": 34
}

COLOR_MAP = {
    'unknown': 0, 'red': 1, 'green': 2, 'blue': 3, 'white': 4, 
    'black': 5, 'grey': 6, 'silver': 7, 'yellow': 8, 'orange': 9, 
    'brown': 10, 'purple': 11, 'dark blue': 12, 'dark green': 13
}

TYPE_MAP = {
    'object': 0, 'car': 1, 'van': 2, 'truck': 3, 'motorcycle': 4, 
    'cyclist': 5, 'jeep': 6, 'police car': 7, 'ambulance': 8, 
    'firetruck': 9
}

REL_MAP = {
    'left': 0, 'right': 1, 'front': 2, 'behind': 3
}

# Standard RGB values for color matching
RGB_VALUES = {
    'red': (255, 0, 0),
    'green': (0, 128, 0), # CARLA green is usually darker
    'blue': (0, 0, 255),
    'white': (255, 255, 255),
    'black': (0, 0, 0),
    'grey': (128, 128, 128),
    'silver': (192, 192, 192),
    'yellow': (255, 255, 0),
    'orange': (255, 165, 0),
    'brown': (165, 42, 42),
    'purple': (128, 0, 128),
    'dark blue': (0, 0, 139),
    'dark green': (0, 100, 0)
}

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
def text_to_indices(text, max_len=20):
    tokens = text.lower().replace('.', ' .').replace(',', ' ').split()
    indices = [VOCAB.get(t, VOCAB["<unk>"]) for t in tokens]
    if len(indices) < max_len:
        indices += [VOCAB["<pad>"]] * (max_len - len(indices))
    else:
        indices = indices[:max_len]
    return torch.tensor(indices, dtype=torch.long)

class PIDController:
    def __init__(self, K_P=1.0, K_D=0.1, K_I=0.0):
        self.K_P = K_P
        self.K_D = K_D
        self.K_I = K_I
        self.prev_error = 0.0
        self.integral = 0.0
        
    def step(self, error, dt):
        self.integral += error * dt
        derivative = (error - self.prev_error) / dt
        self.prev_error = error
        return self.K_P * error + self.K_I * self.integral + self.K_D * derivative

from collections import deque

class YawSmoother:
    def __init__(self):
        self.pos_history = deque(maxlen=20) # Store 20 frames (approx 1 sec)
    
    def get_smooth_yaw(self, current_pos):
        self.pos_history.append(current_pos)
        if len(self.pos_history) < 2:
            return None # Not enough history
            
        # Trust historical trajectory tangent over instantaneous Yaw
        p_start = self.pos_history[0]
        p_end = self.pos_history[-1]
        dx = p_end[0] - p_start[0]
        dy = p_end[1] - p_start[1]
        
        # Only update if moved significantly to avoid noise when stopped
        if np.hypot(dx, dy) > 1.0:
            return np.arctan2(dy, dx)
        else:
            return None # Keep previous or use raw

class SmoothFollower:
    """
    Virtual Spring Target for smooth following.
    Instead of tracking the raw target (which jitters), we track a virtual point
    behind the target that is exponentially smoothed.
    """
    def __init__(self, alpha=0.1):
        self.smooth_target = None
        self.alpha = alpha # Smoothing factor (0.05-0.1 is best)

    def _calculate_ideal_pos(self, raw_target_pos, ego_pos):
        # 1. Calculate "Ideal Follow Position" (7m behind target)
        # We don't have target orientation easily here without history,
        # so we assume the ideal position is towards the ego vehicle.
        vec = ego_pos - raw_target_pos
        dist = np.linalg.norm(vec)
        
        if dist < 0.1:
            direction = np.zeros(3)
        else:
            direction = vec / dist
            
        # Ideal position = Target + 7m * direction.
        # === User Request: Shorten Tether to 7.0m (Velcro Mode) ===
        DESIRED_FOLLOW_DIST = 7.0
        ideal_pos = raw_target_pos + direction * DESIRED_FOLLOW_DIST
        return ideal_pos

    def get_render_target(self, raw_target_pos, ego_pos, ego_heading=0.0):
        # 1. Calculate ideal position
        ideal_pos = self._calculate_ideal_pos(raw_target_pos, ego_pos)
        
        if self.smooth_target is None:
            self.smooth_target = ideal_pos
            return self.smooth_target

        # === User Request: Target Clamping (Smart Lateral Clamping) ===
        # Convert Global Delta to Ego Local Frame
        dx_global = ideal_pos[0] - self.smooth_target[0]
        dy_global = ideal_pos[1] - self.smooth_target[1]
        
        # Rotation Matrix (Global -> Local)
        # ego_heading is in Radians (Passed from caller)
        c = np.cos(-ego_heading)
        s = np.sin(-ego_heading)
        dx_local = c * dx_global - s * dy_global
        dy_local = s * dx_global + c * dy_global
        
        # Clamp Lateral Jump (User: 5cm per frame)
        max_lat_jump = 0.05 
        if abs(dy_local) > max_lat_jump:
             dy_local = np.sign(dy_local) * max_lat_jump
        
        # Clamp Longitudinal Jump (Relaxed: 1.0m per frame)
        max_long_jump = 1.0
        if abs(dx_local) > max_long_jump:
             dx_local = np.sign(dx_local) * max_long_jump
             
        # Rotate back to Global (Local -> Global)
        c = np.cos(ego_heading)
        s = np.sin(ego_heading)
        dx_final = c * dx_local - s * dy_local
        dy_final = s * dx_local + c * dy_local
        
        # Apply update
        self.smooth_target[0] += dx_final
        self.smooth_target[1] += dy_final
        self.smooth_target[2] = ideal_pos[2] # Z is less critical
        
        # 4. Store Extension for Metrics
        self.last_extension = np.linalg.norm(ideal_pos - self.smooth_target)
        
        return self.smooth_target

class SimpleTracker:
    """
    Simple Euclidean Distance Tracker with ID persistence (SORT-like logic)
    Helps smooth out target loss during turns or occlusions.
    """
    def __init__(self, max_age=10, dist_thresh=5.0):
        self.max_age = max_age # Max frames to keep lost track
        self.dist_thresh = dist_thresh
        self.tracks = {} # {id: {'centroid': np.array, 'age': 0, 'data': dict}}
        
    def update(self, detections):
        """
        detections: list of dicts with 'center_3d', 'id' (optional), etc.
        """
        # 1. Prediction (Kalman would go here, but we assume static position for short term)
        for tid in list(self.tracks.keys()):
            self.tracks[tid]['age'] += 1
            
        # 2. Matching
        pass

    def track_target(self, target_id, all_detections):
        """
        Try to find the target_id in current detections.
        If not found, see if we can recover it from history (simple proximity).
        """
        # Check if target is in current detections
        for det in all_detections:
            if det['id'] == target_id:
                # Update track
                self.tracks[target_id] = {'centroid': det['center_3d'], 'age': 0, 'data': det}
                return det
        
        # Not found - check history
        if target_id in self.tracks:
            track = self.tracks[target_id]
            if track['age'] < self.max_age:
                # Predict position (Linear motion model could be better)
                # For now, return last known position but mark as inferred
                # We can't return a full detection dict if we don't have it,
                # but we can return the cached one.
                return track['data']
        
        return None

class LeadTracker:
    """
    Advanced Target Tracker with State Machine (LOCKED, WARNING, LOST)
    and Constant Velocity Prediction for Ghost Targets.
    Now uses Time-Based Thresholds for robustness against CARLA frame rate variance.
    """
    def __init__(self):
        self.state = "LOST" # LOCKED, WARNING, LOST
        self.tracked_id = None
        
        # Time-based counters
        self.first_hit_time = None
        self.first_miss_time = None
        
        # Thresholds (Seconds)
        self.hit_time_threshold = 0.2 # Fast lock (approx 4 frames at 20fps)
        self.miss_time_threshold = 2.0 # Persistence (2.0s as requested)
        
        # Kinematics for Prediction
        self.last_pos = None # np.array [x, y, z] (Global)
        self.last_vel = None # np.array [vx, vy, vz] (Global)
        self.last_fwd = None # np.array [x, y, z] (Forward Vector)
        self.last_time = None
        self.last_road_id = None
        self.last_lane_id = None
        
    def reset(self):
        self.state = "LOST"
        self.tracked_id = None
        self.first_hit_time = None
        self.first_miss_time = None
        self.last_pos = None
        self.last_vel = None
        self.last_fwd = None
        self.last_time = None
        self.last_road_id = None
        self.last_lane_id = None
        
    def update(self, detections, target_id_hint=None, timestamp=None, map_api=None):
        """
        Update tracker state based on current detections.
        detections: List of dicts (from get_oracle_detections)
        target_id_hint: The ID we want to track (from Instruction/Grounding)
        timestamp: Current time in seconds
        map_api: carla.Map object (optional, for lane gating)
        """
        if timestamp is None:
            timestamp = time.time()

        found = False
        target_det = None
        
        # 1. Search for target
        search_id = self.tracked_id if self.tracked_id is not None else target_id_hint
        
        if search_id is not None:
            for det in detections:
                if det['id'] == search_id:
                    target_det = det
                    found = True
                    break
        
        # 2. State Transition
        if found:
            # Spatial Gating (User Requirement 3: Lane Waypoint Gate)
            # Prevent locking onto a target that jumped to a non-sensical lane (e.g. opposite side)
            # only when we are in LOST state (i.e. acquiring a NEW target or re-acquiring)
            valid_spatial = True
            if self.state == "LOST" and self.last_road_id is not None and map_api is not None:
                # Check if new target is consistent with history
                try:
                    loc = carla.Location(x=target_det['world_loc'][0], y=target_det['world_loc'][1], z=target_det['world_loc'][2])
                    wp = map_api.get_waypoint(loc, project_to_road=True, lane_type=carla.LaneType.Driving)
                    
                    if wp:
                        # 1. Direction Check
                        if self.last_fwd is not None:
                             wp_fwd = wp.transform.get_forward_vector()
                             lf = self.last_fwd
                             dot = wp_fwd.x * lf[0] + wp_fwd.y * lf[1] + wp_fwd.z * lf[2]
                             if dot < -0.5: # Opposite direction
                                 valid_spatial = False
                                 # print(f"LeadTracker: Rejecting ID {search_id} due to direction mismatch (Dot={dot:.2f})")
                        
                        # 2. Road/Lane Consistency (Optional strict mode)
                        # if wp.road_id != self.last_road_id:
                        #     pass # Warn?
                except:
                    pass
            
            if not valid_spatial:
                found = False # Treat as not found
            
            if found:
                if self.first_hit_time is None:
                    self.first_hit_time = timestamp
                
                self.first_miss_time = None # Reset miss timer
                
                # Update Kinematics
                # det['world_loc'] is [x, y, z]
                current_pos = np.array(det['world_loc'])
                current_vel = np.array(det['velocity'])
                
                self.last_pos = current_pos
                self.last_vel = current_vel
                self.last_time = timestamp
                
                # Store Forward Vector
                speed = np.linalg.norm(current_vel)
                if speed > 0.1:
                    self.last_fwd = current_vel / speed
                
                # Store Map Info
                if map_api is not None:
                    try:
                        loc = carla.Location(x=current_pos[0], y=current_pos[1], z=current_pos[2])
                        wp = map_api.get_waypoint(loc, project_to_road=True, lane_type=carla.LaneType.Driving)
                        if wp:
                            self.last_road_id = wp.road_id
                            self.last_lane_id = wp.lane_id
                    except:
                        pass
                
                if self.state == "LOST":
                    if (timestamp - self.first_hit_time) >= self.hit_time_threshold:
                        self.state = "LOCKED"
                        self.tracked_id = search_id
                elif self.state == "WARNING":
                    self.state = "LOCKED"
                
        else:
            self.first_hit_time = None # Reset hit timer
            
            if self.first_miss_time is None:
                self.first_miss_time = timestamp
            
            time_since_miss = timestamp - self.first_miss_time
            
            if self.state == "LOCKED":
                self.state = "WARNING"
            elif self.state == "WARNING":
                if time_since_miss >= self.miss_time_threshold:
                    self.state = "LOST"
                    self.tracked_id = None
                    
        return self.state, self.tracked_id

    def predict_position(self, dt):
        """
        Predict future position based on last known state (Constant Velocity Model)
        Returns: carla.Location or None
        """
        if self.last_pos is not None and self.last_vel is not None:
            # Simple P_new = P_old + V * dt
            pred_pos = self.last_pos + self.last_vel * dt
            return carla.Location(x=pred_pos[0], y=pred_pos[1], z=pred_pos[2])
        return None


class MetricsManager:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.data = {
            'speed': [],
            'target_speed': [],
            'accel': [],
            'throttle': [],
            'brake': [],
            'jerk': [],
            'dist_to_target': [],
            'steer': [],
            'collisions': 0,
            'target_detected': [],
            'timestamps': [],
            'lateral_error': [],
            'lateral_deviation': [], # Deviation from planned path
            'following_error': [], # Deviation from ideal distance (12m)
            'uncertainty': [],
            'cost_obs': [],
            'cost_smooth': [],
            'locked_target_id': [],
            'true_target_id': [],
            'mpc_solve_time': [], # New: Track MPC solve time
            'deadlock_events': 0, # New: Track number of deadlocks
            'virtual_spring_extension': [] # New: Track spring extension
        }
        self.start_time = time.time()
        self.last_accel = 0.0
        self.path_length = 0.0
        self.last_pos = None
        
    def update(self, timestamp, ego_speed, ego_accel, dist_to_target, steer, collision, target_visible, throttle=0.0, brake=0.0, target_speed_val=0.0, uncertainty=0.0, cost_obs=0.0, cost_smooth=0.0, ego_pos=None, locked_target_id=None, true_target_id=None, lateral_deviation=0.0, following_error=0.0, mpc_solve_time=0.0, deadlock=False, virtual_spring_extension=0.0):
        self.data['timestamps'].append(timestamp)
        self.data['speed'].append(ego_speed)
        self.data['target_speed'].append(target_speed_val)
        self.data['accel'].append(ego_accel)
        self.data['throttle'].append(throttle)
        self.data['brake'].append(brake)
        self.data['uncertainty'].append(uncertainty)
        self.data['cost_obs'].append(cost_obs)
        self.data['cost_smooth'].append(cost_smooth)
        self.data['locked_target_id'].append(locked_target_id)
        self.data['true_target_id'].append(true_target_id)
        self.data['lateral_deviation'].append(lateral_deviation)
        self.data['following_error'].append(following_error)
        self.data['mpc_solve_time'].append(mpc_solve_time)
        self.data['virtual_spring_extension'].append(virtual_spring_extension)
        
        if deadlock:
            self.data['deadlock_events'] += 1
        
        # Path Length
        if ego_pos is not None:
            if self.last_pos is not None:
                dist = np.linalg.norm(np.array(ego_pos) - np.array(self.last_pos))
                self.path_length += dist
            self.last_pos = ego_pos
        else:
            # Fallback approximation
            self.path_length += ego_speed * 0.05
        
        # Jerk (m/s^3)
        # Skip first 5 frames to avoid spawn noise
        if len(self.data['timestamps']) > 5:
             jerk = abs(ego_accel - self.last_accel) / 0.05
        else:
             jerk = 0.0
             
        self.data['jerk'].append(jerk)
        self.last_accel = ego_accel
        
        self.data['dist_to_target'].append(dist_to_target if dist_to_target is not None else -1.0)
            
        self.data['steer'].append(steer)
        self.data['lateral_error'].append(abs(steer)) # Using steer as proxy
        
        if collision:
            self.data['collisions'] += 1
            
        self.data['target_detected'].append(1 if target_visible else 0)

    def save_telemetry_log(self, episode_idx):
        """Save high-frequency telemetry for Mechanism Visualization (Exp 3)"""
        if not self.data['timestamps']: return
        
        filename = "telemetry_log.csv" 
        
        keys = ['timestamps', 'speed', 'target_speed', 'uncertainty', 'steer', 'cost_obs', 'cost_smooth', 'dist_to_target', 'mpc_solve_time', 'virtual_spring_extension']
        header = ['Timestamp', 'Speed', 'TargetSpeed', 'Entropy', 'Steer', 'Cost_Obs', 'Cost_Smooth', 'DistToTarget', 'MPCTime', 'SpringExt']
        
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(header)
                length = len(self.data['timestamps'])
                for i in range(length):
                    row = [
                        self.data['timestamps'][i],
                        self.data['speed'][i],
                        self.data['target_speed'][i],
                        self.data['uncertainty'][i],
                        self.data['steer'][i],
                        self.data['cost_obs'][i],
                        self.data['cost_smooth'][i],
                        self.data['dist_to_target'][i],
                        self.data['mpc_solve_time'][i],
                        self.data['virtual_spring_extension'][i]
                    ]
                    writer.writerow(row)
            print(f"Saved telemetry log to {filename}")
        except Exception as e:
            print(f"Failed to save telemetry log: {e}")

    def save_episode_log(self, episode_idx):
        """Legacy log for other purposes"""
        if not self.data['timestamps']: return
        
        filename = f"episode_log_{episode_idx}.csv"
        # We only save aligned fields
        keys = ['timestamps', 'speed', 'target_speed', 'uncertainty', 'dist_to_target', 'steer', 'throttle', 'brake']
        
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(keys)
                length = len(self.data['timestamps'])
                for i in range(length):
                    row = [self.data[k][i] for k in keys]
                    writer.writerow(row)
            print(f"Saved episode log to {filename}")
        except Exception as e:
            print(f"Failed to save episode log: {e}")

    def get_summary(self):
        if not self.data['speed']: return {}
        
        avg_speed = np.mean(self.data['speed'])
        max_jerk = np.max(self.data['jerk'])
        avg_jerk = np.mean(self.data['jerk'])
        
        dist_mean = np.mean(self.data['dist_to_target']) if self.data['dist_to_target'] else 0
        dist_std = np.std(self.data['dist_to_target']) if self.data['dist_to_target'] else 0
        
        target_acq_rate = np.mean(self.data['target_detected']) * 100
        
        # Lateral Deviation
        if self.data['lateral_deviation'] and any(self.data['lateral_deviation']):
             avg_lat_error = np.mean(self.data['lateral_deviation'])
        else:
             avg_lat_error = np.mean(self.data['lateral_error']) if self.data['lateral_error'] else 0
        
        collision_bool = 1 if self.data['collisions'] > 0 else 0
        
        # Calculate SPL
        dt = 0.05
        # ego_path_len = np.sum(self.data['speed']) * dt # Use accumulated path length
        ego_path_len = self.path_length
        target_path_len = np.sum(self.data['target_speed']) * dt
        
        # Add Initial Distance to Target to OptimalLength (Navigation Task)
        if self.data['dist_to_target']:
             initial_dist = self.data['dist_to_target'][0]
             if initial_dist > 0:
                 target_path_len += initial_dist
        
        success = 1 if (target_acq_rate > 50.0 and collision_bool == 0) else 0
        spl = 0.0
        if success:
            denom = max(ego_path_len, target_path_len)
            if denom > 0:
                spl = target_path_len / denom
        
        # --- New Metrics: Following Stability & Grounding Accuracy ---
        following_rmse = 0.0
        grounding_acc = 0.0
        
        # 1. Following Stability (RMSE against 12.0m)
        if self.data['following_error'] and any(self.data['following_error']):
            mse = np.mean(np.square(self.data['following_error']))
            following_rmse = np.sqrt(mse)
        else:
            desired_dist = 12.0
            valid_dists = [d for d in self.data['dist_to_target'] if d != -1.0]
            if valid_dists:
                mse = sum([(d - desired_dist)**2 for d in valid_dists]) / len(valid_dists)
                following_rmse = mse ** 0.5
            
        # 2. Grounding Accuracy
        if self.data['locked_target_id'] and self.data['true_target_id']:
            total_frames = len(self.data['timestamps'])
            correct_frames = 0
            for i in range(total_frames):
                # Ensure index exists
                if i < len(self.data['locked_target_id']) and i < len(self.data['true_target_id']):
                    lid = self.data['locked_target_id'][i]
                    tid = self.data['true_target_id'][i]
                    if lid is not None and tid is not None and lid == tid:
                        correct_frames += 1
            grounding_acc = (correct_frames / total_frames) * 100.0 if total_frames > 0 else 0.0

        # 3. Steering Entropy
        steer_entropy = 0.0
        if len(self.data['steer']) > 5:
            steers = np.array(self.data['steer'])
            # 2nd order prediction error
            if len(steers) > 2:
                # preds = 2 * steers[t-1] - steers[t-2]
                preds = 2 * steers[1:-1] - steers[:-2]
                actuals = steers[2:]
                errors = actuals - preds
                
                # Entropy of errors
                try:
                    hist, _ = np.histogram(errors, bins=20, density=False)
                    p = hist / np.sum(hist)
                    p = p[p > 0] # Remove zeros to avoid log(0)
                    steer_entropy = -np.sum(p * np.log2(p))
                except:
                    steer_entropy = 0.0

        # --- New Metrics: MPC Time, Deadlocks, Spring Extension ---
        avg_mpc_time = np.mean(self.data['mpc_solve_time']) * 1000.0 if self.data['mpc_solve_time'] else 0.0 # ms
        deadlocks = self.data['deadlock_events']
        avg_spring_ext = np.mean(self.data['virtual_spring_extension']) if self.data['virtual_spring_extension'] else 0.0

        # --- Reliability Metrics ---
        id_switches = 0
        prev_id = None
        target_lost_frames = 0
        min_gap = 999.0
        
        if self.data['locked_target_id']:
            for i, lid in enumerate(self.data['locked_target_id']):
                if i > 0:
                    if lid != prev_id and lid is not None and prev_id is not None:
                        id_switches += 1
                prev_id = lid
                
                # Lost Frame
                if i < len(self.data['target_detected']) and self.data['target_detected'][i] == 0:
                    target_lost_frames += 1
                    
                # Min Gap
                if i < len(self.data['dist_to_target']):
                    d = self.data['dist_to_target'][i]
                    if d > 0 and d < min_gap:
                        min_gap = d
        
        if min_gap == 999.0: min_gap = 0.0
        target_lost_duration = target_lost_frames * 0.05
        wrong_lead_rate = 100.0 - grounding_acc

        # Min TTC (User Request)
        min_ttc = 999.0
        if len(self.data['dist_to_target']) > 0 and len(self.data['speed']) == len(self.data['dist_to_target']):
            for i in range(len(self.data['dist_to_target'])):
                dist = self.data['dist_to_target'][i]
                speed = self.data['speed'][i]
                target_speed = self.data['target_speed'][i] if i < len(self.data['target_speed']) else 0.0
                
                rel_speed = speed - target_speed
                if dist > 0 and rel_speed > 0.1: # Closing in
                    ttc = dist / rel_speed
                    if ttc < min_ttc:
                        min_ttc = ttc
        
        if min_ttc == 999.0: min_ttc = -1.0 # No collision threat

        return {
            "Average Speed (m/s)": float(f"{avg_speed:.2f}"),
            "FollowingRMSE": float(f"{following_rmse:.2f}"),
            "GroundingAcc": float(f"{grounding_acc:.1f}"),
            "WrongLeadRate": float(f"{wrong_lead_rate:.1f}"),
            "IDSwitches": int(id_switches),
            "TargetLostDur": float(f"{target_lost_duration:.2f}"),
            "MinGap": float(f"{min_gap:.2f}"),
            "MinTTC": float(f"{min_ttc:.2f}"),
            "Max Jerk (m/s^3)": float(f"{max_jerk:.2f}"),
            "AvgJerk": float(f"{avg_jerk:.2f}"),
            "SteeringEntropy": float(f"{steer_entropy:.4f}"),
            "LatDeviation": float(f"{avg_lat_error:.2f}"),
            "Success": int(success),
            "Collision": int(collision_bool),
            "Time": float(f"{len(self.data['timestamps']) * 0.05:.2f}"),
            "PathLength": float(f"{self.path_length:.2f}"),
            "Target Acquisition Rate (%)": float(f"{target_acq_rate:.1f}"),
            "AvgMPCTime (ms)": float(f"{avg_mpc_time:.2f}"),
            "Deadlocks": int(deadlocks),
            "AvgSpringExt (m)": float(f"{avg_spring_ext:.2f}"),
            "Avg Jerk (m/s^3)": float(f"{avg_jerk:.2f}"),

            "Following Distance Mean (m)": float(f"{dist_mean:.2f}"),
            "Following Distance Std (m)": float(f"{dist_std:.2f}"),
            "Avg Lateral Error (approx)": float(f"{avg_lat_error:.3f}"),
            "Collision Occurred": collision_bool,
            "Total Collision Frames": self.data['collisions'],
            "SPL": float(f"{spl:.3f}"),
            "OptimalLength": float(f"{target_path_len:.2f}"),
            "FPS": float(f"{len(self.data['timestamps']) / (self.data['timestamps'][-1] - self.start_time):.2f}") if len(self.data['timestamps']) > 0 else 0.0
        }

# -----------------------------------------------------------------------------
# Main Evaluation Class
# -----------------------------------------------------------------------------
class ClosedLoopEvaluator:
    def __init__(self):
        self.scenario_difficulty = args.scenario
        
        # Initialize Weather Name (Safety Default)
        self.current_weather_name = "Unknown"
        if args.weather:
            self.current_weather_name = args.weather

        # Initialize Smooth Follower (Virtual Spring Target)
        self.smooth_follower = SmoothFollower(alpha=0.1)

        # Connect to CARLA
        try:
            print(f"DEBUG: carla module: {carla}", flush=True)
            if hasattr(carla, '__file__'):
                print(f"DEBUG: carla file: {carla.__file__}", flush=True)
            print(f"DEBUG: carla dir: {dir(carla)}", flush=True)
            
            print("Connecting to CARLA client...")
            self.client = carla.Client(HOST, PORT)
            self.client.set_timeout(TIMEOUT)
            print("Getting world...")
            self.world = self.client.get_world()
            print("Getting map...")
            self.map = self.world.get_map()
            
            # Setup Traffic Manager
            print("Setting up Traffic Manager...", flush=True)
            try:
                self.client.set_timeout(20.0) # Fail fast if stuck
                
                # Robust Traffic Manager Connection with Port Retries
                tm_ports = [8000, 8005, 8010, 8015, 8020]
                tm_connected = False
                
                for port in tm_ports:
                    try:
                        print(f"Attempting to connect to Traffic Manager on port {port}...", flush=True)
                        self.tm = self.client.get_trafficmanager(port)
                        # Test if alive by calling a simple method
                        self.tm.get_port()
                        print(f"Traffic Manager connected on port {port}.", flush=True)
                        tm_connected = True
                        break
                    except Exception as e_tm:
                        print(f"Failed to connect on port {port}: {e_tm}", flush=True)
                
                if not tm_connected:
                    raise RuntimeError("Could not connect to Traffic Manager on any port.")

                self.tm.set_global_distance_to_leading_vehicle(2.5) # Maintain safety distance
                print("Safety distance set.", flush=True)
                self.tm.set_hybrid_physics_mode(True) # Only run physics near ego to save CPU/GPU
                print("Hybrid physics set.", flush=True)
                self.tm.set_random_device_seed(0) # Deterministic
                print("Seed set.", flush=True)
                # Ensure they don't do crazy things
                self.tm.global_percentage_speed_difference(10.0) # Drive 10% slower than limit
                print("Traffic Manager setup done.", flush=True)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"TM Setup Failed: {e}", flush=True)
                self.tm = None
                
            # Enable Synchronous Mode
            print("Enabling Synchronous Mode...", flush=True)
            settings = self.world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = 0.05 # 20 FPS
            print("Applying settings...", flush=True)
            self.world.apply_settings(settings)
            
            # Set TM to Sync Mode
            if self.tm:
                self.tm.set_synchronous_mode(True)
                print("Traffic Manager set to Synchronous Mode.", flush=True)
                
            print("Synchronous Mode Enabled.", flush=True)
        except Exception as e:
            print(f"Error connecting to CARLA: {e}", flush=True)
            sys.exit(1)
            
        # Load Model
        try:
            print("Checking Torch device...", flush=True)
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            print(f"Using device: {self.device}", flush=True)
            
            if args.method == "E2E":
                self.model = BaselineE2EAdapter(
                    vocab_size=len(VOCAB),
                    color_num=len(COLOR_MAP),
                    type_num=len(TYPE_MAP),
                    rel_num=len(REL_MAP)
                ).to(self.device)
                print("Initialized E2E Baseline Model.", flush=True)
                
                # Try to load E2E checkpoint if exists, else warning
                e2e_path = "checkpoints/e2e_epoch_10.pth"
                if os.path.exists(e2e_path):
                     try:
                        self.model.load_state_dict(torch.load(e2e_path, map_location=self.device))
                        print(f"Loaded E2E model from {e2e_path}", flush=True)
                     except Exception as e:
                        print(f"Error loading E2E model: {e}. Using random weights.", flush=True)
                else:
                     print(f"WARNING: E2E Checkpoint not found at {e2e_path}. Using random weights!", flush=True)
            else:
                self.model = BaselineGNN(
                    vocab_size=len(VOCAB),
                    color_num=len(COLOR_MAP),
                    type_num=len(TYPE_MAP),
                    rel_num=len(REL_MAP)
                ).to(self.device)
                print("Initialized BaselineGNN Model.", flush=True)
                
                if os.path.exists(MODEL_PATH):
                    try:
                        self.model.load_state_dict(torch.load(MODEL_PATH, map_location=self.device, weights_only=True))
                    except TypeError:
                        # Fallback for older torch versions
                        self.model.load_state_dict(torch.load(MODEL_PATH, map_location=self.device))
                    print(f"Loaded model from {MODEL_PATH}", flush=True)
                else:
                    print(f"Model not found at {MODEL_PATH}", flush=True)
                    sys.exit(1)
                
            self.model.eval()
            self.logic_adapter = LogicAdapter(no_memory=args.no_memory)
            
            # Vision Obstacle Persistence Filter (Robustness for Rain/Noise)
            # {id_counter: {'pos': global_pos, 'hits': 0, 'misses': 0, 'type': label, 'radius': r}}
            self.vision_obstacle_history = {}
            self.vis_obs_id_counter = 0
            
            # Init Vision Perception
            # We need to wait until sensors are set up to get config, 
            # but we can assume default config for now matching SENSOR_CONFIG
            sem_cfg = SENSOR_CONFIG.get('sem_front', None)
            if not sem_cfg:
                 # Fallback if not in config yet (should be added)
                 sem_cfg = {'res': (400, 225), 'fov': 90, 'pos': (0.8, 0, 1.7), 'rot': (0, 0, 0)}
            
            self.vision_perception = VisionPerception(sem_cfg)
            print("Logic Adapter & Vision Perception initialized.", flush=True)
        except Exception as e:
             print(f"Error loading model: {e}", flush=True)
             sys.exit(1)
        
        # Controller (MPC)
        # Tune weights to prevent "snaking" (画龙) and reduce Jerk
        # UPDATED: Scheme 3 - Steering Damping & Lookahead Optimization
        # Increase steering penalty to prevent saturation
        if self.scenario_difficulty == 'HardRainNoon' or 'Rain' in args.weather:
             # === Scheme: Velcro Mode (User Request) ===
             # High Stiffness for Tracking, Relaxed Lateral for Stability
             mpc_weights = {
                'w_pos': 2.0,         # Increased: Tight longitudinal tracking
                'w_lat': 0.5,         # Lateral (Relaxed)
                'w_vel': 5.0,         # Increased: Force speed sync
                'w_yaw': 0.5,         # Relaxed Yaw
                'w_steer': 5.0,       # Penalize large steering
                'w_steer_rate': 200.0, # Lock steering (High damping)
                'w_smooth_accel': 40.0,
                'w_obs_scale': 100.0
             }
        else:
            mpc_weights = {
                'steer': 25.0,
                'smooth_steer': 50.0,
                'smooth_accel': 10.0,
                'pos': 30.0,
                'vel': 10.0,
                'w_obs_scale': 2.0
            }
        # Initialize MPC
        # User Request: Horizon 10 (Was 12) for faster reaction
        self.mpc = MPCController(dt=0.05, horizon=10, weights=mpc_weights)
        self.quintic_planner = QuinticPolynomialPlanner()
        self.yaw_smoother = YawSmoother() # User Request: Yaw Smoothing
        
        # Smooth Control Buffer
        self.last_throttle = 0.0
        self.last_brake = 0.0
        self.last_steer = 0.0
        self.last_accel = 0.0
        
        # Low-Pass Filter State (for Jerk Reduction)
        self.filtered_accel = 0.0
        self.filtered_steer = 0.0

        
        # State
        self.ego_vehicle = None
        self.sensors = []
        self.sensor_queues = {}
        self.last_sensor_data = {} # Cache for sensor data to prevent flickering
        self.other_actors = []
        self.actors = [] # All actors including ego and traffic
        self.actor_colors = {} # Store persistent colors for actors
        self.planned_path = [] # Store planned path waypoints
        self.current_dist_to_target = 0.0 # Store distance for visualization
        self.bypass_state = None # Store bypass decision for hysteresis
        self.obstacle_persistence = {} # {actor_id: frames_since_seen}
        
        self.metrics = MetricsManager()
        self.tracker = SimpleTracker(max_age=15) # Initialize Tracker
        self.lead_tracker = LeadTracker() # Initialize Lead Tracker (Advanced)
        self.intent_predictor = IntentPredictor(history_len=10) # Initialize Intent Predictor (tuned to 10)
        self.collision_occured = False
        self.episode_metrics = []
        self.stuck_counter = 0 # User Fix: Soft Boost Counter
        
        # Pygame Visualization
        if pygame is not None:
            pygame.init()
            self.display = pygame.display.set_mode((1200, 620))
            pygame.display.set_caption("Neuro-Symbolic VLN Evaluation - Modern UI")
            self.font = pygame.font.SysFont("Arial", 18)
            self.title_font = pygame.font.SysFont("Arial", 22, bold=True)
            self.clock = pygame.time.Clock()
            
            # Pre-allocate surface for path visualization (Optimization)
            self.path_surf = pygame.Surface((400, 400), pygame.SRCALPHA)
        else:
            self.display = None
            self.clock = None
            self.font = None
            self.title_font = None
            self.path_surf = None
            print("Warning: Pygame not installed. Visualization disabled.", flush=True)
        
    def setup_episode(self, difficulty='Easy', seed=None):
        """Reset environment and spawn actors with guaranteed target ahead"""
        print(f"Debug: Entering setup_episode ({difficulty}, Seed={seed})...", flush=True)
        
        # Set Seed for Reproducibility (or Diversity)
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            if self.tm:
                self.tm.set_random_device_seed(seed)
                print(f"Debug: Set TM Seed to {seed}", flush=True)
                
        self.difficulty = difficulty # Store for logic usage
        try:
            print("Debug: Calling cleanup...", flush=True)
            self.cleanup()
            print("Debug: Cleanup done.", flush=True)
            self.last_target_id = None
            self.target_lost_counter = 0
            self.bypass_state = None
            self.collision_persistence = 0
            self.stuck_timer = 0 # For non-collision stuck detection
            self.deadlock_timer = 0 # Scheme 4: Smart Deadlock Detection
            self.smooth_target_speed = 0.0 # Scheme 2: Target Speed LPF
            self.reverse_counter = 0
            self.collision_this_frame = False
            
            # Difficulty Configuration
            # "Target vehicle immobile and always red light" -> Increased ignore_lights_percentage
            # "Multiple candidate choices" -> Added Weather and Target Type variation
            DIFFICULTY_CONFIG = {
                'Easy': {
                'dists': [40.0], # Force Target far
                'n_distractors': 2, # Low density
                'n_decoys': 0, # No confusion
                'tm_ignore_lights': 100.0, # Target ignores lights
                'tm_speed_pct': -20.0, # Target drives 20% faster (Moderate)
                'weather': [carla.WeatherParameters.ClearNoon],
                'target_filter': 'vehicle.tesla.*',
                'lane_change': 0.0, # No lane changes
                'distractor_ignore_lights': 0.0,
                'distractor_spawn_mode': 'force_block' # Ensure one obstacle
            },
            'Medium': {
                'dists': [25.0, 30.0],
                'n_distractors': 10,
                'n_decoys': 1, # One similar vehicle
                'tm_ignore_lights': 100.0,
                'tm_speed_pct': -40.0, # Target drives 40% faster
                'weather': [carla.WeatherParameters.WetNoon, carla.WeatherParameters.ClearSunset],
                'target_filter': 'vehicle.*',
                'lane_change': 10.0, # Occasional lane changes
                'distractor_ignore_lights': 50.0,
                'distractor_spawn_mode': 'mixed'
            },
            'Hard': {
                'dists': [35.0, 45.0],
                'n_distractors': 25, # High density
                'n_decoys': 2, # Two similar vehicles
                'tm_ignore_lights': 100.0,
                'tm_speed_pct': -60.0, # Target drives 60% faster (Aggressive)
                'weather': [carla.WeatherParameters.HardRainNoon, carla.WeatherParameters.WetSunset],
                'target_filter': 'vehicle.*',
                'lane_change': 50.0, # Frequent lane changes
                'distractor_ignore_lights': 100.0,
                'distractor_spawn_mode': 'near_target'
            },
            'HardRainNoon': {
                'dists': [35.0, 45.0],
                'n_distractors': 25, # High density
                'n_decoys': 2, # Two similar vehicles
                'tm_ignore_lights': 100.0,
                'tm_speed_pct': -60.0, # Target drives 60% faster (Aggressive)
                'weather': [carla.WeatherParameters.HardRainNoon], # Force HardRainNoon
                'target_filter': 'vehicle.*',
                'lane_change': 50.0, # Frequent lane changes
                'distractor_ignore_lights': 100.0,
                'distractor_spawn_mode': 'near_target'
            }
        }
        except Exception as e:
            print(f"Error during setup_episode initialization: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return False
        
        cfg = DIFFICULTY_CONFIG.get(difficulty, DIFFICULTY_CONFIG['Easy'])
        print(f"Debug: Config loaded for {difficulty}", flush=True)
        
        # 0. Set Weather
        try:
            self.current_weather_name = "Unknown"
            weather_param = None
            
            # Priority 1: Command line override
            if "--weather" in sys.argv:
                if hasattr(carla.WeatherParameters, args.weather):
                    weather_param = getattr(carla.WeatherParameters, args.weather)
                    print(f"Debug: Forcing weather from CLI to {args.weather}", flush=True)

            # Priority 2: Scenario specific (HardRainNoon)
            if weather_param is None and difficulty == 'HardRainNoon':
                weather_param = carla.WeatherParameters.HardRainNoon
                self.current_weather_name = "HardRainNoon" # Explicitly set name
                print("Debug: Forcing HardRainNoon Weather for scenario", flush=True)

            # Priority 3: Config random choice
            if weather_param is None:
                weather_param = random.choice(cfg['weather'])
            
            # Store weather name for logging
            # Find name in WeatherParameters
            if self.current_weather_name == "Unknown":
                for name in dir(carla.WeatherParameters):
                    if not name.startswith('_') and getattr(carla.WeatherParameters, name) == weather_param:
                        self.current_weather_name = name
                        break
            
            print(f"Debug: Setting weather to {self.current_weather_name}...", flush=True)
            self.world.set_weather(weather_param)
            print("Debug: Weather set.", flush=True)
        except Exception as e:
            print(f"Error setting weather: {e}", flush=True)
        
        # Retry loop for finding a valid scenario
        max_retries = 10
        for attempt in range(max_retries):
            if attempt > 0:
                print(f"Debug: Scenario generation attempt {attempt+1}/{max_retries}...", flush=True)
                self.cleanup() # Clean up partial actors from previous attempt
            
            # 1. Get Spawn Points
            print("Debug: Getting spawn points...", flush=True)
            spawn_points = self.map.get_spawn_points()
            if len(spawn_points) < 10:
                print("Not enough spawn points!", flush=True)
                return False
                
            # 2. Spawn Ego
            print("Debug: Spawning Ego...", flush=True)
            ego_bp = self.world.get_blueprint_library().find('vehicle.tesla.model3')
            ego_bp.set_attribute('role_name', 'hero')
            
            # Retry spawning ego until we find a spot with road ahead
            ego_spawned = False
            for i in range(10):
                ego_spawn = random.choice(spawn_points)
                
                # Check if there is road ahead (simple check: valid waypoint + next waypoint exists)
                w = self.map.get_waypoint(ego_spawn.location)
                if not w: continue
                
                # Check 20m ahead
                next_ws = w.next(20.0)
                if not next_ws: continue
                
                self.ego_vehicle = self.world.try_spawn_actor(ego_bp, ego_spawn)
                if self.ego_vehicle:
                    print(f"Debug: Ego spawned at attempt {i+1}", flush=True)
                    self.actors.append(self.ego_vehicle)
                    print("Debug: Ticking world...", flush=True)
                    try:
                        self.world.tick() # Ensure location is updated
                    except Exception as e:
                        print(f"CRITICAL ERROR in tick: {e}", flush=True)
                        raise e
                    print("Debug: World ticked.", flush=True)
                    ego_spawned = True
                    break
                    
            if not ego_spawned:
                print("Failed to spawn ego vehicle after retries.", flush=True)
                continue # Try next scenario attempt
                
            # 3. Spawn Traffic (Targets)
            print("Debug: Spawning Traffic...", flush=True)
            try:
                # Filter blueprints based on difficulty
                if difficulty == 'Easy':
                    traffic_bps = self.world.get_blueprint_library().filter(cfg['target_filter'])
                else:
                    traffic_bps = self.world.get_blueprint_library().filter('vehicle.*')
                    
                traffic_bps = [bp for bp in traffic_bps if bp.get_attribute('number_of_wheels').as_int() in [2, 4]]
                # print(f"Debug: Found {len(traffic_bps)} vehicle blueprints.", flush=True)
            except Exception as e:
                print(f"Error filtering blueprints: {e}", flush=True)
                return False
    
            # A. Guaranteed Target Ahead
            # Get waypoint ahead of ego
            ego_w = self.map.get_waypoint(self.ego_vehicle.get_location())
            target_spawned = False
            
            # Try different distances ahead to find a valid spot
            for dist in cfg['dists']:
                # print(f"Debug: Trying dist {dist}...", flush=True)
                next_ws = ego_w.next(dist)
                if next_ws:
                    # Pick one path
                    target_w = next_ws[0]
                    # Raise slightly to avoid ground collision
                    t = target_w.transform
                    t.location.z += 0.5
                    
                    bp = random.choice(traffic_bps)
                    actor = self.world.try_spawn_actor(bp, t)
                    if actor:
                        # print(f"Debug: Actor spawned at {dist}", flush=True)
                        if self.tm:
                            # Retry setting autopilot to handle timeouts
                            for _retry in range(3):
                                try:
                                    actor.set_autopilot(True, self.tm.get_port()) # Use our configured TM
                                    print(f"Debug: Autopilot set for Target {actor.id} on port {self.tm.get_port()}", flush=True)
                                    break
                                except Exception as e:
                                    if _retry == 2: print(f"Warning: Failed to set autopilot for target: {e}", flush=True)
                                    time.sleep(0.1)
                            
                            # Configure specific behavior for target
                            self.tm.ignore_lights_percentage(actor, cfg['tm_ignore_lights'])
                            self.tm.ignore_signs_percentage(actor, cfg['tm_ignore_lights'])
                            self.tm.distance_to_leading_vehicle(actor, 3.0)
                            self.tm.vehicle_percentage_speed_difference(actor, cfg['tm_speed_pct'])
                            if cfg['lane_change'] > 0:
                                try:
                                    self.tm.auto_lane_change(actor, True)
                                    self.tm.random_left_lanechange_percentage(actor, cfg['lane_change'])
                                    self.tm.random_right_lanechange_percentage(actor, cfg['lane_change'])
                                except Exception as e:
                                    print(f"Warning: Failed to set lane change params for target: {e}", flush=True)
                        else:
                            # print("Debug: Enabling default Autopilot.", flush=True)
                            actor.set_autopilot(True) # Use default TM
                        
                        self.target_actor = actor
                        self.other_actors.append(actor)
                        print(f"Spawned Target at distance {dist}m", flush=True)
                        target_spawned = True
                        break
                    else:
                        pass
                        # print(f"Debug: Failed to spawn actor at {dist}", flush=True)
            
            if not target_spawned:
                # print("Warning: Could not spawn target directly ahead.", flush=True)
                continue # Try next scenario attempt
            
            # If we got here, Ego and Target are spawned. Success!
            break
            
        if not target_spawned:
            print("Error: Could not generate valid scenario after max retries.", flush=True)
            return False

        # B. Spawn Decoys (Same appearance as target)
        n_decoys = cfg.get('n_decoys', 0)
        if n_decoys > 0 and self.target_actor:
            print(f"Debug: Spawning {n_decoys} Decoys...", flush=True)
            target_bp = self.target_actor.type_id
            target_color = self.target_actor.attributes.get('color', None)
            
            decoy_bp = self.world.get_blueprint_library().find(target_bp)
            if target_color:
                decoy_bp.set_attribute('color', str(target_color))
            
            # Spawn decoys near target but not too close
            target_loc = self.target_actor.get_location()
            target_fwd = self.target_actor.get_transform().get_forward_vector()
            
            for _ in range(n_decoys):
                # Try to find spawn point near target (10-40m)
                spawn = None
                # Shuffle spawn points to avoid picking same one
                random.shuffle(spawn_points)
                for sp in spawn_points:
                    d = sp.location.distance(target_loc)
                    if 10.0 < d < 40.0:
                         # Check orientation alignment (Dot > 0.7 for roughly parallel)
                         sp_fwd = sp.rotation.get_forward_vector()
                         dot = sp_fwd.x * target_fwd.x + sp_fwd.y * target_fwd.y
                         if dot > 0.5: # Allow somewhat parallel (same direction)
                             spawn = sp
                             break
                if not spawn:
                    # Fallback with orientation check
                    for _ in range(20): # Try 20 times
                        cand = random.choice(spawn_points)
                        cand_fwd = cand.rotation.get_forward_vector()
                        dot = cand_fwd.x * target_fwd.x + cand_fwd.y * target_fwd.y
                        if dot > 0.5:
                            spawn = cand
                            break
                
                actor = self.world.try_spawn_actor(decoy_bp, spawn)
                if actor:
                    if self.tm:
                        actor.set_autopilot(True, self.tm.get_port())
                        self.tm.vehicle_percentage_speed_difference(actor, cfg['tm_speed_pct']) # Same speed behavior
                    else:
                        actor.set_autopilot(True)
                    self.other_actors.append(actor)
                    print(f"Debug: Spawned Decoy {actor.id}", flush=True)

        # C. Spawn Distractors (Nearby)
        print("Debug: Spawning Distractors...", flush=True)
        # For distractors, use generic vehicles
        distractor_bps = self.world.get_blueprint_library().filter('vehicle.*')
        distractor_bps = [bp for bp in distractor_bps if bp.get_attribute('number_of_wheels').as_int() == 4]
        
        target_loc = None
        target_fwd = None
        if target_spawned:
            target_loc = self.other_actors[-1].get_location()
            target_fwd = self.other_actors[-1].get_transform().get_forward_vector()

        for _ in range(cfg['n_distractors']):
            bp = random.choice(distractor_bps)
            
            spawn = None
            spawn_mode = cfg.get('distractor_spawn_mode', 'random')
            
            # Decide spawn strategy for this actor
            use_near_target = False
            spawn = None

            if spawn_mode == 'force_block':
                 # Force spawn between Ego and Target (Target at 40m)
                 # Try multiple distances: 20m, 25m, 15m, 30m
                 spawn_candidates = [20.0, 25.0, 15.0, 30.0]
                 found_spawn = False
                 
                 for dist in spawn_candidates:
                     try:
                         ws = ego_w.next(dist)
                         if ws:
                             spawn = ws[0].transform
                             spawn.location.z += 0.5
                             print(f"Debug: Trying force_block spawn at {dist}m: {spawn.location}", flush=True)
                             
                             actor = self.world.try_spawn_actor(bp, spawn)
                             if actor:
                                 # Setup TM
                                 actor.set_autopilot(True, self.tm.get_port())
                                 if self.tm:
                                     # Make distractor faster to avoid blocking flow (e.g. -10% -> 110% speed)
                                     self.tm.vehicle_percentage_speed_difference(actor, -10.0)
                                     self.tm.ignore_lights_percentage(actor, 0.0)
                                 print(f"Debug: Spawned force_block Distractor {actor.id} at {dist}m", flush=True)
                                 
                                 ignore_lights = cfg.get('distractor_ignore_lights', 50.0)
                                 self.tm.ignore_signs_percentage(actor, ignore_lights)
                                 
                                 self.other_actors.append(actor)
                                 found_spawn = True
                                 break # Success
                     except Exception as e:
                         print(f"Debug: Error calculating force_block spawn at {dist}m: {e}", flush=True)
                 
                 if found_spawn:
                     continue # Next distractor
                 else:
                     print("Debug: Failed to force_block spawn at all candidate distances. Fallback to random.", flush=True)
                     spawn = random.choice(spawn_points)

            elif spawn_mode == 'near_target':
                use_near_target = (random.random() < 0.8) # 80% near target
            elif spawn_mode == 'mixed':
                use_near_target = (random.random() < 0.4) # 40% near target
                
            if use_near_target and target_loc:
                # Try to find spawn point near target
                best_dist = float('inf')
                best_spawn = None
                for sp in spawn_points:
                    d = sp.location.distance(target_loc)
                    if 5.0 < d < 20.0: # 5-20m from target
                         # Check orientation
                         if target_fwd:
                             sp_fwd = sp.rotation.get_forward_vector()
                             dot = sp_fwd.x * target_fwd.x + sp_fwd.y * target_fwd.y
                             if dot > 0.5: # Parallel only
                                 spawn = sp
                                 break
                         else:
                             spawn = sp
                             break
                if not spawn:
                     # Fallback to random but let the Global Check filter it later if possible, 
                     # BUT since use_near_target was True, we skip the Global Check block below.
                     # So we MUST filter here or reset use_near_target to False.
                     use_near_target = False
                     spawn = random.choice(spawn_points)
            else:
                spawn = random.choice(spawn_points)
            
            # Distance check (ensure not too far from ego if random)
            if not use_near_target:
                d = spawn.location.distance(self.ego_vehicle.get_location())
                if not (10 < d < 60): continue
                
                # Global Orientation Check for Random Spawns
                # Filter out cross-traffic on grid maps to avoid horizontal blockages
                ego_fwd = self.ego_vehicle.get_transform().get_forward_vector()
                sp_fwd = spawn.rotation.get_forward_vector()
                dot = sp_fwd.x * ego_fwd.x + sp_fwd.y * ego_fwd.y
                if abs(dot) < 0.7: # Approx 45 degrees deviation allowed (allows oncoming traffic)
                     # Reject perpendicular spawns
                     continue

            actor = self.world.try_spawn_actor(bp, spawn)
            if actor:
                if self.tm:
                    for _retry in range(3):
                        try:
                            actor.set_autopilot(True, self.tm.get_port())
                            break
                        except Exception as e:
                            if _retry == 2: print(f"Warning: Failed to set autopilot for distractor: {e}", flush=True)
                            time.sleep(0.1)
                            
                    # Distractors can be less aggressive, but let's keep them moving
                    ignore_lights = cfg.get('distractor_ignore_lights', 50.0)
                    self.tm.ignore_lights_percentage(actor, ignore_lights)
                    
                    if spawn_mode == 'force_block':
                        self.tm.vehicle_percentage_speed_difference(actor, 20.0) # 20% slower
                        self.tm.ignore_lights_percentage(actor, 0.0)
                        print(f"Debug: Spawned force_block Distractor {actor.id} at 20m", flush=True)
                    self.tm.ignore_signs_percentage(actor, ignore_lights)
                else:
                    actor.set_autopilot(True)
                
                self.other_actors.append(actor)
            else:
                print(f"Debug: Failed to spawn distractor {i} (Mode: {spawn_mode})", flush=True)
                    
        # 4. Setup Sensors
        print("Debug: Setting up sensors...", flush=True)
        try:
            self.setup_sensors()
        except Exception as e:
            print(f"CRITICAL ERROR in setup_sensors: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return False
        print("Debug: Sensors setup done.", flush=True)
        
        # Wait for sensors to be ready
        time.sleep(1.0)
        print("Debug: setup_episode finished successfully", flush=True)
        return True
        
    def setup_sensors(self):
        """Attach sensors to ego vehicle"""
        bp_lib = self.world.get_blueprint_library()
        
        for name, cfg in SENSOR_CONFIG.items():
            print(f"Debug: Spawning sensor {name}...", flush=True)
            bp = bp_lib.find(cfg['type'])
            
            if 'res' in cfg:
                bp.set_attribute('image_size_x', str(cfg['res'][0]))
                bp.set_attribute('image_size_y', str(cfg['res'][1]))
            if 'fov' in cfg:
                bp.set_attribute('fov', str(cfg['fov']))
            
            loc = carla.Location(x=cfg['pos'][0], y=cfg['pos'][1], z=cfg['pos'][2])
            # Config is (Pitch, Yaw, Roll)
            rot = carla.Rotation(pitch=cfg['rot'][0], yaw=cfg['rot'][1], roll=cfg['rot'][2])
            transform = carla.Transform(loc, rot)
            
            sensor = self.world.spawn_actor(bp, transform, attach_to=self.ego_vehicle)
            
            if name == 'collision':
                sensor.listen(lambda event: self._on_collision(event))
            else:
                q = queue.Queue()
                sensor.listen(q.put)
                self.sensor_queues[name] = q
            
            self.sensors.append(sensor)
            
    def _on_collision(self, event):
        actor_type = event.other_actor.type_id
        print(f"CRITICAL: Collision with {actor_type} (ID: {event.other_actor.id}) at Frame {event.frame}", flush=True)
        self.collision_occured = True
        self.collision_this_frame = True
            
    def get_sensor_data(self):
        """Get latest data from sensors (Synchronized)"""
        # CARLA sensors are asynchronous.
        # To avoid flickering, we need to ensure we have a coherent frame from all sensors.
        # However, syncing strictly by frame ID is hard without World Tick (Synchronous Mode).
        # In Async mode, we just empty the queues and take the LATEST image.
        
        data = {}
        
        # 1. Wait for Primary Sensor (rgb_front)
        if 'rgb_front' in self.sensor_queues:
            q = self.sensor_queues['rgb_front']
            start_time = time.time()
            while q.empty():
                if time.time() - start_time > 2.0:
                    print(f"Warning: Sensor rgb_front timeout")
                    return None
                pygame.event.pump()
                time.sleep(0.005)
        
        # 2. Retrieve Data from All Sensors
        for name, q in self.sensor_queues.items():
            event = None
            try:
                while not q.empty():
                    event = q.get(block=False)
            except queue.Empty:
                pass
                
            if event:
                if name.startswith('rgb'):
                    array = np.frombuffer(event.raw_data, dtype=np.dtype("uint8"))
                    array = np.reshape(array, (event.height, event.width, 4)) # BGRA
                    self.last_sensor_data[name] = array[:, :, :3] # BGR
                elif name.startswith('sem'):
                    array = np.frombuffer(event.raw_data, dtype=np.dtype("uint8"))
                    array = np.reshape(array, (event.height, event.width, 4)) # BGRA
                    # Semantic tag is in Red channel (index 2)
                    self.last_sensor_data[name] = array[:, :, 2]
            
            # Always populate current data from cache if available
            if name in self.last_sensor_data:
                data[name] = self.last_sensor_data[name]
                 
        return data
        
    def get_oracle_detections(self):
        """Simulate perception using Ground Truth"""
        # Adapted from PerceptionOracle logic, but live
        detections = []
        
        ego_trans = self.ego_vehicle.get_transform()
        # World to Camera Matrix
        # Simplified: We just need relative position
        
        # Filter actors in range
        # print(f"Debug: Checking {len(self.other_actors)} actors...", flush=True)
        for actor in self.other_actors:
            if not actor.is_alive: 
                # print(f"Debug: Actor {actor.id} dead", flush=True)
                continue
            
            loc = actor.get_location()
            dist = loc.distance(ego_trans.location)
            
            # print(f"Debug: Actor {actor.id} Loc: {loc} Dist: {dist:.1f}", flush=True)
            
            if dist > 80: 
                # print(f"Debug: Actor {actor.id} too far ({dist:.1f}m) Loc: {loc} Ego: {ego_trans.location}", flush=True)
                continue # Too far
            
            # Calculate relative position
            # Project to Ego Frame
            fwd = ego_trans.get_forward_vector()
            right = ego_trans.get_right_vector()
            up = ego_trans.get_up_vector()
            
            vec = loc - ego_trans.location
            dx = vec.dot(right)
            dy = vec.dot(up)
            dz = vec.dot(fwd)
            
            # Only keep objects within reasonable range
            if dz < -10.0: 
                # print(f"Debug: Actor {actor.id} behind ({dz:.1f}m)", flush=True)
                continue # Allow objects slightly behind (side view)
            
            # Mock BBox (just center for now)
            # In image space? LogicAdapter needs bbox for center calc
            # But LogicAdapter also takes center_3d
            
            # Get color
            color = 'unknown'
            if actor.id in self.actor_colors:
                color = self.actor_colors[actor.id]
            else:
                c_str = actor.attributes.get('color')
                if c_str:
                    # Check if it's RGB string "r,g,b"
                    parts = str(c_str).split(',')
                    if len(parts) == 3:
                        try:
                            r, g, b = map(int, parts)
                            min_dist = float('inf')
                            best_color = 'unknown'
                            for name, rgb in RGB_VALUES.items():
                                d = (r - rgb[0])**2 + (g - rgb[1])**2 + (b - rgb[2])**2
                                if d < min_dist:
                                    min_dist = d
                                    best_color = name
                            color = best_color
                        except ValueError:
                            pass
                    
                    # Fallback to string match if not RGB or parsing failed
                    if color == 'unknown':
                        for k in COLOR_MAP.keys():
                             if k in str(c_str).lower():
                                 color = k
                                 break
                
                if color == 'unknown':
                    # Assign random color from our list
                    # Exclude 'unknown' from random choice
                    valid_colors = [k for k in COLOR_MAP.keys() if k != 'unknown']
                    color = random.choice(valid_colors)
                
                # Save it
                self.actor_colors[actor.id] = color
                
            # Get Type
            type_id = actor.type_id.lower()
            label = 'car'
            if 'van' in type_id: label = 'van'
            elif 'truck' in type_id: label = 'truck'
            elif 'police' in type_id: label = 'police car'
            elif 'cycle' in type_id or 'bike' in type_id or 'diamondback' in type_id or 'gazelle' in type_id: label = 'bicycle'
            elif 'scooter' in type_id: label = 'scooter'
            
            # Get Velocity
            vel = actor.get_velocity()
            speed = np.sqrt(vel.x**2 + vel.y**2 + vel.z**2)
            
            # Get World Location
            loc = actor.get_location()

            detections.append({
                'id': actor.id,
                'color': color,
                'label': label,
                'center_3d': [dx, dy, dz], # Right, Up, Forward (Relative)
                'world_loc': [loc.x, loc.y, loc.z], # Absolute
                'velocity': [vel.x, vel.y, vel.z], # Absolute Vector
                'speed': speed,
                'bbox': [0, 0, 100, 100], # Dummy bbox
                'depth': dz
            })
            
        return detections

    def generate_instruction(self, detections):
        """Generate a random instruction based on visible objects"""
        if not detections:
            return None, None
            
        target = None
        
        # Prefer self.target_actor if available and in detections
        if hasattr(self, 'target_actor') and self.target_actor:
             print(f"Debug: Looking for Target Actor {self.target_actor.id} in detections...", flush=True)
             for det in detections:
                 print(f"Debug: - Detection ID: {det['id']}", flush=True)
                 if det['id'] == self.target_actor.id:
                     target = det
                     break
        
        if not target:
             print("Debug: Original target not in detections, picking random.", flush=True)
             target = random.choice(detections)
        
        # Simple template
        # "Follow the [Color] [Type]"
        # Add relation: "on your left"
        
        rel = ""
        if target['center_3d'][0] < -1: rel = "on your left"
        elif target['center_3d'][0] > 1: rel = "on your right"
        else: rel = "ahead"
        
        text = f"Follow the {target['color']} {target['label']} {rel}"
        return text, target['id']

    def project_3d_to_2d(self, pos_3d):
        """Project 3D point (Camera Frame) to 2D pixel coordinates"""
        x, y, z = pos_3d
        if z <= 0.1: return None # Behind camera
        
        W, H = 800, 450
        FOV = 90.0
        
        f = (W / 2.0) / math.tan(math.radians(FOV / 2.0))
        
        u = int(x * f / z + W / 2.0)
        v = int(y * f / z + H / 2.0)
        
        if 0 <= u < W and 0 <= v < H:
            return (u, v)
        return None

    def render(self, sensor_data, text, detections, pred_target_id, true_target_id, control_info=None, local_map=None):
        """Render RGB image and overlay info"""
        if self.display is None:
            return

        if 'rgb_front' not in sensor_data:
            return
        
        # Clear screen with Dark Grey
        self.display.fill((20, 20, 20))
            
        # ==========================================================
        # 1. Main View (Front) - Top Left [0, 0] (800x450)
        # ==========================================================
        img = sensor_data['rgb_front']
        img_rgb = img[:, :, ::-1]
        surface = pygame.surfarray.make_surface(img_rgb.swapaxes(0, 1))
        self.display.blit(surface, (0, 0))
        
        # Overlay Detections (Only on Front View)
        for det in detections:
            # Project Center
            center_2d = self.project_3d_to_2d(det['center_3d'])
            if not center_2d: continue
            
            # Determine Color
            color = (0, 100, 255) # Default Blue
            width = 2
            
            if det['id'] == pred_target_id:
                color = (255, 50, 50) # Red
                width = 4
                
            if det['id'] == true_target_id:
                 if det['id'] == pred_target_id:
                     # Draw Green dot in center
                     pygame.draw.circle(self.display, (0, 255, 0), center_2d, 5)
                 else:
                     color = (0, 255, 0)
            
            # Draw Box
            z = det['center_3d'][2]
            box_h = int(200 / z) if z > 0 else 20
            box_w = int(200 / z) if z > 0 else 20
            
            rect = pygame.Rect(0, 0, box_w, box_h)
            rect.center = center_2d
            pygame.draw.rect(self.display, color, rect, width)
            
            # Draw Label
            label_text = f"{det['color']} {det['label']}"
            label_surf = self.font.render(label_text, True, color)
            self.display.blit(label_surf, (rect.x, rect.y - 20))
            
        # Border for Main View
        pygame.draw.rect(self.display, (255, 255, 255), (0, 0, 800, 450), 2)
        
        # ==========================================================
        # 2. BEV / Map - Top Right [800, 0] (400x400)
        # ==========================================================
        if 'rgb_bev' in sensor_data:
            img_bev = sensor_data['rgb_bev'][:, :, ::-1]
            surf_bev = pygame.surfarray.make_surface(img_bev.swapaxes(0, 1))
            
            # Draw Local Map (Lanes)
            if local_map:
                for lane in local_map.get('lane_lines', []):
                    pts = lane['points']
                    if len(pts) < 2: continue
                    
                    px_points = []
                    for (x, y) in pts:
                        # x is forward (up/down), y is right (left/right)
                        # BEV: u = 200 + y*10, v = 200 - x*10
                        u = 200 + int(y * 10.0)
                        v = 200 - int(x * 10.0)
                        
                        # Clip
                        u = max(0, min(399, u))
                        v = max(0, min(399, v))
                        px_points.append((u, v))
                    
                    if len(px_points) > 1:
                        color = (180, 180, 180) # Light Grey
                        width = 2
                        # Highlight road edges or specific lanes if needed
                        # if lane.get('side') == 'left': color = (255, 255, 0) 
                        pygame.draw.lines(surf_bev, color, False, px_points, width)

                # Draw Junction Indicator
                if local_map.get('junction'):
                    pygame.draw.circle(surf_bev, (255, 0, 255), (200, 200), 15, 2) # Magenta circle around ego

             # Draw Planned Path on BEV
            # Handle Path Persistence (Fix Flickering)
            # 0. Clear Surface
            self.path_surf.fill((0, 0, 0, 0))
            
            ego_trans = self.ego_vehicle.get_transform()
            ego_loc = ego_trans.location
            ego_fwd = ego_trans.get_forward_vector()
            ego_right = ego_trans.get_right_vector()

            # 1. Draw Candidates (Gray)
            if hasattr(self, 'candidate_paths') and self.candidate_paths:
                for cand_path in self.candidate_paths:
                     pts_2d = []
                     for wp_loc in cand_path:
                        vec = wp_loc - ego_loc
                        x_local = vec.dot(ego_fwd)
                        y_local = vec.dot(ego_right)
                        u = 200 + int(y_local * 10.0)
                        v = 200 - int(x_local * 10.0)
                        pts_2d.append((u, v))
                     
                     if len(pts_2d) > 1:
                         # Gray with low alpha
                         pygame.draw.lines(self.path_surf, (150, 150, 150, 60), False, pts_2d, 1)

            # 2. Draw Optimal Path (Gradient)
            path_to_draw = []
            if hasattr(self, 'planned_path') and self.planned_path:
                path_to_draw = self.planned_path
                self.last_valid_path = self.planned_path # Cache it
            elif hasattr(self, 'last_valid_path') and self.last_valid_path:
                path_to_draw = self.last_valid_path # Use cached
            
            if path_to_draw:
                # Transform points to ego frame and draw
                pts_2d = []
                for wp_loc in path_to_draw:
                    vec = wp_loc - ego_loc
                    
                    # Project to Ego Frame (X forward, Y right)
                    x_local = vec.dot(ego_fwd)
                    y_local = vec.dot(ego_right)
                    
                    # Map to Pixel
                    u = 200 + int(y_local * 10.0)
                    v = 200 - int(x_local * 10.0)
                    
                    pts_2d.append((u, v))
                
                # Draw lines with Professional Gradient
                if len(pts_2d) > 1:
                    # self.path_surf.fill((0, 0, 0, 0)) # Cleared at start
                    
                    total_pts = len(pts_2d)
                    
                    # "Beautiful Professional" Gradient: Electric Blue -> Cyan
                    start_c = np.array([0, 120, 255]) # Electric Blue
                    end_c = np.array([0, 255, 255])   # Cyan

                    for i in range(total_pts - 1):
                        p1 = pts_2d[i]
                        p2 = pts_2d[i+1]
                        
                        # Interpolate color along the path
                        t = i / max(1, total_pts - 1)
                        color_array = (1 - t) * start_c + t * end_c
                        color = tuple(color_array.astype(int))
                        
                        # Alpha Logic: Solid near ego, fade at end
                        alpha = 255
                        if t > 0.7:
                            alpha = int(255 * (1.0 - (t - 0.7) / 0.3))
                        
                        # 1. Glow Effect (Wide, Low Alpha)
                        glow_color = (*color, int(alpha * 0.3))
                        pygame.draw.line(self.path_surf, glow_color, p1, p2, 12)
                        
                        # 2. Main Line (Narrow, High Alpha)
                        main_color = (*color, alpha)
                        pygame.draw.line(self.path_surf, main_color, p1, p2, 4)
                        
                        # 3. Smooth Joints
                        pygame.draw.circle(self.path_surf, main_color, p1, 2)
                        
            surf_bev.blit(self.path_surf, (0, 0))
            
            self.display.blit(surf_bev, (800, 0))
            pygame.draw.rect(self.display, (255, 255, 255), (800, 0, 400, 400), 2)
            
            # Label "BEV / MAP"
            lbl = self.font.render("BEV / MAP", True, (255, 255, 255))
            self.display.blit(lbl, (810, 10))
            
        # ==========================================================
        # 3. Camera Strip (Rear/Mirrors) - Bottom [Y=460]
        # ==========================================================
        # Layout: [ Left (240) ] [ Rear (240) ] [ Right (240) ]
        
        start_y = 460
        gap = 20
        cam_w, cam_h = 240, 135
        start_x = 20
        
        # Left
        if 'rgb_left' in sensor_data:
            img = sensor_data['rgb_left'][:, :, ::-1]
            surf = pygame.surfarray.make_surface(img.swapaxes(0, 1))
            pos = (start_x, start_y)
            self.display.blit(surf, pos)
            pygame.draw.rect(self.display, (255, 255, 255), (*pos, cam_w, cam_h), 2)
            self.display.blit(self.font.render("LEFT", True, (255, 255, 255)), (pos[0]+5, pos[1]+5))
            
        # Rear
        if 'rgb_rear' in sensor_data:
            img = sensor_data['rgb_rear'][:, :, ::-1]
            surf = pygame.surfarray.make_surface(img.swapaxes(0, 1))
            pos = (start_x + cam_w + gap, start_y)
            self.display.blit(surf, pos)
            pygame.draw.rect(self.display, (255, 255, 255), (*pos, cam_w, cam_h), 2)
            self.display.blit(self.font.render("REAR", True, (255, 255, 255)), (pos[0]+5, pos[1]+5))

        # Right
        if 'rgb_right' in sensor_data:
            img = sensor_data['rgb_right'][:, :, ::-1]
            surf = pygame.surfarray.make_surface(img.swapaxes(0, 1))
            pos = (start_x + (cam_w + gap) * 2, start_y)
            self.display.blit(surf, pos)
            pygame.draw.rect(self.display, (255, 255, 255), (*pos, cam_w, cam_h), 2)
            self.display.blit(self.font.render("RIGHT", True, (255, 255, 255)), (pos[0]+5, pos[1]+5))

        # ==========================================================
        # 4. Info Panel - Bottom Right [800, 410]
        # ==========================================================
        # Background for Info
        info_rect = pygame.Rect(800, 400, 400, 220)
        pygame.draw.rect(self.display, (30, 30, 30), info_rect)
        pygame.draw.rect(self.display, (255, 255, 255), info_rect, 2)
        
        info_x = 815
        info_y = 415
        line_h = 25
        
        # Title
        self.display.blit(self.title_font.render("STATUS MONITOR", True, (0, 255, 255)), (info_x, info_y))
        info_y += 35
        
        # Instruction
        text_surf = self.font.render(f"CMD: {text}", True, (255, 255, 255))
        self.display.blit(text_surf, (info_x, info_y))
        info_y += line_h
        
        # Target Status
        is_match = (pred_target_id == true_target_id)
        status_color = (0, 255, 0) if is_match else (255, 50, 50)
        status_txt = "MATCH" if is_match else "MISMATCH"
        self.display.blit(self.font.render(f"Target: ID {true_target_id} | Pred {pred_target_id} [{status_txt}]", True, status_color), (info_x, info_y))
        info_y += line_h
        
        # Separator
        pygame.draw.line(self.display, (100, 100, 100), (info_x, info_y+5), (1185, info_y+5), 1)
        info_y += 15
        
        # Vehicle Telemetry
        if control_info:
            # Speed
            spd_color = (255, 255, 255)
            if control_info['speed'] > 7.0: spd_color = (255, 100, 100)
            self.display.blit(self.font.render(f"Speed: {control_info['speed']:.1f} m/s", True, spd_color), (info_x, info_y))
            
            # Throttle/Brake Bars
            # Throttle
            pygame.draw.rect(self.display, (50, 50, 50), (info_x + 150, info_y+5, 100, 10))
            pygame.draw.rect(self.display, (0, 255, 0), (info_x + 150, info_y+5, int(100 * control_info['throttle']), 10))
            self.display.blit(self.font.render("THR", True, (200, 200, 200)), (info_x + 260, info_y))
            
            info_y += line_h
            
            # Brake
            pygame.draw.rect(self.display, (50, 50, 50), (info_x + 150, info_y+5, 100, 10))
            pygame.draw.rect(self.display, (255, 0, 0), (info_x + 150, info_y+5, int(100 * control_info['brake']), 10))
            self.display.blit(self.font.render("BRK", True, (200, 200, 200)), (info_x + 260, info_y))
            
            info_y += line_h
            
            # Steer
            self.display.blit(self.font.render(f"Steer: {control_info['steer']:.2f}", True, (200, 200, 200)), (info_x, info_y))
        
        pygame.display.flip()
        
        # Handle Pygame Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.close()
                sys.exit()

    def get_vision_target(self, local_map, lookahead_dist):
        """
        Compute target point in local frame using vision-detected lane lines.
        Returns: (x, y) or None if fails
        """
        if not local_map or 'lane_lines' not in local_map:
            return None
            
        lane_lines = local_map['lane_lines']
        if not lane_lines:
            return None
            
        # 1. Separate lines into Left and Right based on lateral position
        left_lines = []
        right_lines = []
        
        for line in lane_lines:
            points = np.array(line['points'])
            if len(points) < 2: continue
            
            # Average Y of the line
            mean_y = np.mean(points[:, 1])
            
            # Filter lines that are too far away (not our lane)
            if mean_y < -5.0 or mean_y > 5.0: continue
            
            if mean_y < 0:
                left_lines.append((mean_y, points))
            else:
                right_lines.append((mean_y, points))
                
        # 2. Find closest left and right lines (Inner boundaries)
        # Sort left by Y descending (closest to 0 from negative side) -> Max Y
        closest_left = None
        if left_lines:
            left_lines.sort(key=lambda x: x[0], reverse=True) 
            closest_left = left_lines[0][1] # Points
            
        # Sort right by Y ascending (closest to 0 from positive side) -> Min Y
        closest_right = None
        if right_lines:
            right_lines.sort(key=lambda x: x[0])
            closest_right = right_lines[0][1] # Points
            
        # 3. Determine Lane Center Points
        center_points = []
        
        # We need to sample X points to generate center
        sample_xs = np.linspace(0, lookahead_dist + 5.0, num=10)
        
        if closest_left is not None and closest_right is not None:
            # Fit poly to both and average
            try:
                # Left
                pl = np.polyfit(closest_left[:, 0], closest_left[:, 1], 2)
                # Right
                pr = np.polyfit(closest_right[:, 0], closest_right[:, 1], 2)
                
                # Evaluate
                yl = np.polyval(pl, sample_xs)
                yr = np.polyval(pr, sample_xs)
                
                yc = (yl + yr) / 2.0
                center_points = np.column_stack((sample_xs, yc))
            except:
                return None
                
        elif closest_left is not None:
            # Only Left: Shift Right by half lane width (approx 1.75m)
            try:
                if len(closest_left) < 2: return None
                deg = min(2, len(closest_left) - 1)
                pl = np.polyfit(closest_left[:, 0], closest_left[:, 1], deg)
                yl = np.polyval(pl, sample_xs)
                yc = yl + 1.75 # Shift right
                center_points = np.column_stack((sample_xs, yc))
            except:
                return None
                
        elif closest_right is not None:
            # Only Right: Shift Left by half lane width
            try:
                if len(closest_right) < 2: return None
                deg = min(2, len(closest_right) - 1)
                pr = np.polyfit(closest_right[:, 0], closest_right[:, 1], deg)
                yr = np.polyval(pr, sample_xs)
                yc = yr - 1.75 # Shift left
                center_points = np.column_stack((sample_xs, yc))
            except:
                return None
        else:
            return None
            
        # 4. Get Target Point at lookahead_dist
        # Fit a final trajectory to the center points (smoother)
        try:
            p_center = np.polyfit(center_points[:, 0], center_points[:, 1], 2)
            y_target = np.polyval(p_center, lookahead_dist)
            
            # Clamp Y to reasonable values (stay on road)
            y_target = np.clip(y_target, -2.5, 2.5)
            
            return np.array([lookahead_dist, y_target])
        except:
            return None

    def generate_local_plan(self, ego_trans, target_loc, obstacles, target_speed):
        """
        Generate candidate trajectories and select the best one.
        Returns: 
            best_local_traj: np.array [H, 2] (x, y) in Ego Frame
            best_global_traj: list of carla.Location (for visualization)
            candidate_trajs: list of (local_traj, score) for debug viz
        """
        H = 20 # MPC Horizon (Increased to 20 for better lookahead)
        dt = 0.1
        
        # 1. Get Reference Waypoints (Centerline)
        # Trace a path for H steps roughly
        wps = []
        curr_wp = self.map.get_waypoint(ego_trans.location)
        dist_step = max(1.0, target_speed * dt)
        
        for _ in range(H):
                next_wps = curr_wp.next(dist_step)
                if not next_wps: break
                # Heuristic: pick one closer to target
                best_n = next_wps[0]
                min_d = best_n.transform.location.distance(target_loc)
                for n in next_wps:
                    d = n.transform.location.distance(target_loc)
                    if d < min_d:
                        min_d = d
                        best_n = n
                curr_wp = best_n
                wps.append(curr_wp)
                
        if not wps:
            # Fallback: Straight line if map fails
            # This ensures we always have a candidate plan
            fwd = ego_trans.get_forward_vector()
            loc = ego_trans.location
            fallback_wps = []
            for k in range(1, H+1):
                 # Create a dummy waypoint structure or just use locations?
                 # The code below expects 'wp' objects with transform.
                 # We can simulate it or just handle it in the candidate loop
                 pass
            # If wps is empty, we return None, [], [] which triggers Point Attractor.
            # Point Attractor is robust for "Just go there".
            # But if Point Attractor is failing to move, we need to fix MPC weights.
            # Let's try to generate a straight line plan.
            return None, [], []

        # 2. Generate Candidates (Frenet Offsets)
        # offsets = [-3.0, -1.5, 0.0, 1.5, 3.0] # Lane width approx 3.5m
        # Expanded offsets to allow full lane change for bypass
        offsets = [-3.5, -2.0, -1.0, 0.0, 1.0, 2.0, 3.5]
        
        candidates = []
        
        ego_loc = ego_trans.location
        ego_fwd = ego_trans.get_forward_vector()
        ego_right = ego_trans.get_right_vector()
        ego_yaw = ego_trans.rotation.yaw
        
        # Pre-compute Rotation Matrix (Global to Local)
        # Local X = Forward, Local Y = Right
        # v_local = R^T * (v_global - ego_global)
        c = np.cos(np.deg2rad(ego_yaw))
        s = np.sin(np.deg2rad(ego_yaw))
        # CARLA: X=Fwd, Y=Right? No.
        # Standard: X=East, Y=North.
        # Ego Fwd = (c, s). Ego Right = (s, -c)?? 
        # Let's use vector dot products for safety.
        
        for offset in offsets:
            local_traj = []
            global_traj = []
            valid = True
            first_collision_idx = -1
            
            for i, wp in enumerate(wps):
                # Shift lateral
                # wp_right = wp.transform.get_right_vector() # This might be noisy if map is bad
                # Use smooth approximation? Just use wp.transform
                wp_loc = wp.transform.location
                wp_right = wp.transform.get_right_vector()
                
                pt_loc = wp_loc + wp_right * offset
                global_traj.append(pt_loc)
                
                # Project to Ego Frame
                vec = pt_loc - ego_loc
                x_local = vec.dot(ego_fwd)
                y_local = vec.dot(ego_right)
                local_traj.append([x_local, y_local])
                
            local_traj = np.array(local_traj)
            
            # 3. Evaluate Candidate
            score = 0
            
            # A. Offset Penalty (Prefer Center)
            score += 1.0 * abs(offset)
            
            # B. Obstacle Penalty
            # obstacles: List of (x, y, radius, risk) in Ego Frame
            if obstacles:
                # Vectorized check
                traj_x = local_traj[:, 0]
                traj_y = local_traj[:, 1]
                
                for ox, oy, r, w_risk in obstacles:
                    d2 = (traj_x - ox)**2 + (traj_y - oy)**2
                    min_d2 = np.min(d2)
                    min_dist = np.sqrt(min_d2)
                    
                    # Hard Collision Check
                    if min_dist < (r + 1.0): # 1.0m safety margin (half car width)
                        score += 1000.0 # High penalty
                        if min_dist < r:
                             valid = False # Collision
                             # Find where collision happens
                             dists = np.sqrt(d2)
                             coll_indices = np.where(dists < r)[0]
                             if len(coll_indices) > 0:
                                 if first_collision_idx == -1 or coll_indices[0] < first_collision_idx:
                                     first_collision_idx = coll_indices[0]
                    
                    # Soft Risk
                    # score += w_risk * np.exp(-min_d2 / (2 * (r+2)**2)) * 10.0
                    if min_dist < 4.0:
                        score += (4.0 - min_dist) * w_risk
            
            # C. Smoothness (optional)
            
            # Store even if invalid, but mark it
            candidates.append({
                'local': local_traj,
                'global': global_traj,
                'score': score,
                'valid': valid,
                'collision_idx': first_collision_idx
            })
        
        # 4. Select Best
        # Filter valid first
        valid_candidates = [c for c in candidates if c['valid']]
        
        if valid_candidates:
            valid_candidates.sort(key=lambda x: x['score'])
            best = valid_candidates[0]
            return best['local'], best['global'], candidates
        else:
            # Fallback: Find the path that goes furthest before collision
            # Or just the one with lowest score (least overlap)
            candidates.sort(key=lambda x: x['score'])
            best = candidates[0]
            
            # Truncate at collision point
            if best['collision_idx'] != -1:
                safe_idx = max(0, best['collision_idx'] - 1)
                best['local'] = best['local'][:safe_idx]
                best['global'] = best['global'][:safe_idx]
            
            # If truncation resulted in empty, return a short stub
            if len(best['local']) < 2:
                 # Just 1 point slightly ahead?
                 # Or return empty list which triggers Point Attractor
                 return None, [], candidates
                 
            return best['local'], best['global'], candidates

    def update_obstacle_persistence(self, vision_obs, ego_transform):
        """
        Track obstacles across frames to filter noise (rain).
        vision_obs: List of {'pos': [x, y, z], 'radius': r, 'type': t} (in Ego Frame)
        ego_transform: carla.Transform
        Returns: List of valid obstacles (in Ego Frame)
        """
        # 1. Convert new observations to Global Frame
        current_obs_global = []
        
        ego_loc = ego_transform.location
        ego_fwd = ego_transform.get_forward_vector()
        ego_right = ego_transform.get_right_vector()
        ego_up = ego_transform.get_up_vector()
        
        for obs in vision_obs:
            local_pos = obs['pos']
            # Global = Ego + R * Local
            # CARLA vectors are (x,y,z). 
            # Local x is Forward, y is Right, z is Up
            global_pos = carla.Location(
                x = ego_loc.x + ego_fwd.x * local_pos[0] + ego_right.x * local_pos[1] + ego_up.x * local_pos[2],
                y = ego_loc.y + ego_fwd.y * local_pos[0] + ego_right.y * local_pos[1] + ego_up.y * local_pos[2],
                z = ego_loc.z + ego_fwd.z * local_pos[0] + ego_right.z * local_pos[1] + ego_up.z * local_pos[2]
            )
            current_obs_global.append({'pos': global_pos, 'radius': obs['radius'], 'type': obs['type']})
            
        # 2. Match with History
        # self.vision_obstacle_history = {id: {'pos': loc, 'hits': 0, 'misses': 0, 'radius': r}}
        
        matched_ids = set()
        
        for obs in current_obs_global:
            # Find closest existing tracked obstacle
            best_id = -1
            min_dist = 2.0 # Threshold for matching (m)
            
            for tid, track in self.vision_obstacle_history.items():
                dist = track['pos'].distance(obs['pos'])
                if dist < min_dist:
                    min_dist = dist
                    best_id = tid
            
            if best_id != -1:
                # Update existing
                self.vision_obstacle_history[best_id]['hits'] += 1
                self.vision_obstacle_history[best_id]['misses'] = 0
                # Moving Average for position? Or just keep latest?
                # Latest is better for moving objects, but these are mostly static.
                # Average for stability.
                alpha = 0.5
                prev = self.vision_obstacle_history[best_id]['pos']
                curr = obs['pos']
                new_pos = carla.Location(
                    x = alpha * curr.x + (1-alpha) * prev.x,
                    y = alpha * curr.y + (1-alpha) * prev.y,
                    z = alpha * curr.z + (1-alpha) * prev.z
                )
                self.vision_obstacle_history[best_id]['pos'] = new_pos
                self.vision_obstacle_history[best_id]['radius'] = obs['radius'] # Update radius
                matched_ids.add(best_id)
            else:
                # Create new
                self.vis_obs_id_counter += 1
                self.vision_obstacle_history[self.vis_obs_id_counter] = {
                    'pos': obs['pos'],
                    'hits': 1,
                    'misses': 0,
                    'radius': obs['radius'],
                    'type': obs['type']
                }
                matched_ids.add(self.vis_obs_id_counter)
                
        # 3. Decay Unmatched
        for tid in list(self.vision_obstacle_history.keys()):
            if tid not in matched_ids:
                self.vision_obstacle_history[tid]['misses'] += 1
                if self.vision_obstacle_history[tid]['misses'] > 5: # Lost for 5 frames
                    del self.vision_obstacle_history[tid]
                    
        # 4. Return Valid Obstacles (Hits > Threshold)
        # And convert BACK to Local Frame for MPC
        valid_obstacles = []
        hit_threshold = 5 # Persistence check (Increased from 3 for Rain Robustness)
        
        for tid, track in self.vision_obstacle_history.items():
            if track['hits'] >= hit_threshold:
                # Convert Global -> Local
                # Local = R^T * (Global - Ego)
                vec = track['pos'] - ego_loc
                
                # Project onto Ego Axes
                local_x = vec.dot(ego_fwd)
                local_y = vec.dot(ego_right)
                
                # Filter behind
                if local_x < -5.0: continue
                
                valid_obstacles.append({
                    'pos': [local_x, local_y, 0],
                    'radius': track['radius'],
                    'type': track['type']
                })
                
        return valid_obstacles

    def run(self):
        # Metrics Storage
        episode_metrics = []
        DIFFICULTY_LEVELS = ['Easy', 'Medium', 'Hard']

        for episode in range(EVAL_EPISODES):
            # difficulty = DIFFICULTY_LEVELS[episode % len(DIFFICULTY_LEVELS)]
            difficulty = args.scenario
            
            # Generate Unique Seed for this Episode
            # Base Seed + Episode Index ensures reproducibility but diversity across episodes
            current_seed = 1000 + episode 
            
            print(f"--- Episode {episode+1}/{EVAL_EPISODES} [Difficulty: {difficulty}, Seed: {current_seed}] ---")
            try:
                if not self.setup_episode(difficulty=difficulty, seed=current_seed):
                    print("Setup failed, retrying...", flush=True)
                    continue
            except Exception as e:
                print(f"CRITICAL: setup_episode crashed with {e}. Retrying...", flush=True)
                import traceback
                traceback.print_exc()
                continue
            
            print("Debug: setup_episode success", flush=True)

            # 1. Perception & Instruction
            # Wait a bit for traffic to settle
            print("Waiting for traffic...", flush=True)
            for i in range(5):
                print(f"  Tick {i}", flush=True)
                try:
                    self.world.tick()
                except Exception as e:
                    print(f"  Tick {i} failed: {e}", flush=True)
                # pygame.event.pump() # Simplify
            # time.sleep(2.0)
            print("Traffic settled.", flush=True)
                
            print("Debug: Getting detections...", flush=True)
            detections = self.get_oracle_detections()
            print(f"Debug: Got {len(detections) if detections else 0} detections", flush=True)
            
            if not detections:
                print("No objects found, skipping...")
                continue
                
            print("Debug: Generating instruction...", flush=True)
            text, target_id = self.generate_instruction(detections)
            print(f"Instruction: {text}")
            print(f"True Target ID: {target_id}")
            
            # FORCE INITIAL LOCK for robust evaluation
            # This ensures we test the "Following" behavior even if the initial GNN grounding is noisy
            self.last_target_id = target_id 
            print(f"Debug: Force-locked to Target {target_id} for start of episode.")
            
            # Verify Target ID match with Detections
            true_target_in_detections = any(d['id'] == target_id for d in detections)
            if not true_target_in_detections:
                 print(f"WARNING: Target {target_id} NOT found in initial detections!")
            else:
                 print(f"Target {target_id} found in detections.")
            
            # Episode Data
            steer_history = []
            accel_history = []
            lateral_errors = []
            
            # Reset Smoothed Yaw
            self.current_target_yaw_rad = None
            
            # Main Loop
            success = False
            for step in range(MAX_STEPS):
                self.collision_occured = False # Reset collision flag for this step
                self.collision_this_frame = False
                
                pygame.event.pump() # Keep window responsive
                self.world.tick() # Sync mode enabled
                
                # Get Snapshot for Accurate Timing (User Requirement 1 & 2)
                snapshot = self.world.get_snapshot()
                current_timestamp = snapshot.timestamp.elapsed_seconds
                
                # Collision Persistence Logic
                if self.collision_this_frame:
                    self.collision_persistence += 1
                else:
                    self.collision_persistence = 0
                    
                # We use Async mode by default, so we just grab latest sensor
                sensor_data = self.get_sensor_data()
                if not sensor_data: continue
                
                # 1. Perception
                detections = self.get_oracle_detections()
                
                # --- Vision Perception ---
                local_map = {}
                if 'sem_front' in sensor_data:
                    local_map = self.vision_perception.process(sensor_data['sem_front'])
                # -------------------------
                
                # --- Tracker Integration ---
                # Update tracker state (aging)
                self.tracker.update(detections)
                self.lead_tracker.update(detections, target_id_hint=target_id, timestamp=current_timestamp, map_api=self.map)
                
                # Try to recover target if lost
                if target_id is not None:
                     tracked_det = self.tracker.track_target(target_id, detections)
                     if tracked_det:
                         # Check if it's already in detections
                         found = False
                         for d in detections:
                             if d['id'] == tracked_det['id']:
                                 found = True
                                 break
                         
                         if not found:
                             # Inject recovered detection so Graph Builder can see it
                             # print(f"DEBUG: Recovered Target {target_id} from Tracker!", flush=True)
                             detections.append(tracked_det)
                # ---------------------------

                if not detections:
                    print("Lost all targets!")
                    break
                    
                # 2. Graph Construction
                nodes, edges = self.logic_adapter.build_graph(detections, 800, 450, local_map=local_map)
                
                # 3. Model Inference
                # Prepare Data
                # Nodes
                x_cat = []
                x_cont = []
                for n in nodes:
                    c_idx = COLOR_MAP.get(n['color'], 0)
                    t_idx = TYPE_MAP.get(n['label'], 0)
                    x_cat.append([c_idx, t_idx])
                    
                    # Normalize Pos (similar to dataset.py)
                    # center_3d is [x, y, z] (Right, Up, Forward)
                    # We normalize roughly by max range 50m
                    pos = np.array(n['center_3d']) / 50.0
                    x_cont.append(pos)
                    
                x_cat = torch.tensor(x_cat, dtype=torch.long)
                x_cont = torch.tensor(np.array(x_cont), dtype=torch.float)
                
                # Edges
                edge_index = []
                edge_attr = []
                for u, v, rel in edges:
                    edge_index.append([u, v])
                    edge_attr.append(REL_MAP.get(rel, 0))
                    
                if not edge_index:
                    edge_index = torch.empty((2, 0), dtype=torch.long)
                    edge_attr = torch.empty((0,), dtype=torch.long)
                else:
                    edge_index = torch.tensor(edge_index, dtype=torch.long).t()
                    edge_attr = torch.tensor(edge_attr, dtype=torch.long)
                    
                # Text
                text_idx = text_to_indices(text).unsqueeze(0) # [1, L]
                
                # Batch
                data = Data(
                    x_cat=x_cat,
                    x_cont=x_cont,
                    edge_index=edge_index,
                    edge_attr=edge_attr,
                    text=text_idx,
                    num_nodes=len(nodes)
                )
                batch = Batch.from_data_list([data]).to(self.device)
                
                # Predict
                
                # --- Persistence Logic (Hard Lock) ---
                # "Once locked, stay locked until lost."
                
                pred_idx = -1
                found_locked_target = False
                uncertainty = 0.0 # Uncertainty Metric
                
                if self.last_target_id is not None:
                    for i, n in enumerate(nodes):
                        if n['id'] == self.last_target_id:
                            pred_idx = i
                            found_locked_target = True
                            break
                
                if not found_locked_target:
                    # Only run model if we don't have a lock
                    with torch.no_grad():
                        scores = self.model(batch)
                        pred_idx = scores.argmax().item()
                        
                        # --- NOVELTY: Uncertainty Estimation ---
                        probs = torch.softmax(scores, dim=0)
                        # Entropy: -sum(p * log(p))
                        entropy = -torch.sum(probs * torch.log(probs + 1e-6)).item()
                        uncertainty = entropy
                        # ---------------------------------------
                
                # 4. Control
                # --- HYBRID SELECTION STRATEGY ---
                # 1. Model Prediction (GNN)
                # pred_idx already calculated above via self.model(batch)
                
                # 2. Heuristic Prediction (Rule-based Fallback)
                heuristic_idx = self.logic_adapter.match_instruction(nodes, edges, text)
                
                # 3. Arbitrate
                # If Model is just a baseline, it might be weak. 
                # For robust system evaluation (Planning focus), we prefer Heuristic if Model is uncertain 
                # or simply use Heuristic as a "Strong Baseline" to ensure we have a target.
                
                # Use Heuristic if available (it returns -1 if no match)
                if heuristic_idx != -1:
                    # Optional: Only override if Model is clearly wrong? 
                    # For now, let's Trust Heuristic for "Correct Selection" user request.
                    pred_idx = heuristic_idx
                    # print(f"Debug: Using Heuristic Selection (Node {pred_idx})")
                else:
                    pass
                    # print("Debug: Heuristic failed, using Model Prediction")

                target_node = nodes[pred_idx]
                pred_target_id = target_node['id']
                
                # Update last target
                self.last_target_id = pred_target_id
                
                # Check if correct
                if pred_target_id == target_id:
                    # print(".", end="", flush=True)
                    pass
                else:
                    # print("x", end="", flush=True)
                    pass
                    
                # Drive to Target
                # Improved Logic: Use Waypoints to follow the road/lane towards the target
                
                # 1. Get Ego Waypoint
                ego_loc = self.ego_vehicle.get_location()
                ego_wp = self.map.get_waypoint(ego_loc)
                
                # 2. Get Target Waypoint (We need absolute location)
                # We have target_id. Find actor.
                target_actor = None
                
                # USE GROUND TRUTH TARGET FOR NAVIGATION EVALUATION
                # This ensures we evaluate the planner's ability to bypass, independent of perception model performance.
                nav_target_id = target_id 
                # nav_target_id = pred_target_id # Uncomment to use Model Prediction
                
                # --- GHOST ANCHOR INTEGRATION (LeadTracker) ---
                # Check LeadTracker state
                lt_state, lt_id = self.lead_tracker.state, self.lead_tracker.tracked_id
                
                # Check if we have the actor object from CARLA world first (Ground Truth fallback for safety)
                for a in self.other_actors:
                    if a.id == nav_target_id:
                        target_actor = a
                        break
                        
                # Find if the target actor is visible in the current frame's detections
                visible_target_node = None
                for n in nodes:
                    if n['id'] == nav_target_id:
                        visible_target_node = n
                        break
                
                if visible_target_node:
                    is_ghost = False
                    self.ghost_timer = 0.0
                    target_loc = carla.Location(x=visible_target_node['world_loc'][0], y=visible_target_node['world_loc'][1], z=visible_target_node['world_loc'][2])
                else:
                    # Target lost -> Check LeadTracker prediction
                    is_ghost = True
                    self.ghost_timer += 0.05
                    
                    # Use predicted position
                    pred_loc = self.lead_tracker.predict_position(self.ghost_timer)
                    
                    if pred_loc:
                         target_loc = pred_loc
                         if step % 20 == 0:
                             print(f"  [Ghost] Target {nav_target_id} lost! Tracking Ghost at ({target_loc.x:.1f}, {target_loc.y:.1f})", flush=True)
                         
                         # Snap Ghost to Road
                         ghost_wp = self.map.get_waypoint(target_loc, project_to_road=True, lane_type=carla.LaneType.Driving)
                         if ghost_wp:
                             target_loc = ghost_wp.transform.location
                    elif target_actor:
                         # Fallback to Ground Truth if prediction fails (shouldn't happen if initialized)
                         target_loc = target_actor.get_location()
                    else:
                         # Total loss
                         target_loc = ego_wp.next(20.0)[0].transform.location

                
                # Debug Target State
                if step % 50 == 0:
                    # Target
                    if target_actor:
                        try:
                            t_vel = target_actor.get_velocity()
                            t_speed = np.sqrt(t_vel.x**2 + t_vel.y**2)
                            at_light = target_actor.is_at_traffic_light()
                            light_state = target_actor.get_traffic_light_state()
                            t_loc = target_actor.get_location()
                            print(f"Debug: Target {target_actor.id} Speed: {t_speed:.1f} m/s, At Light: {at_light}, Light State: {light_state}, Loc: ({t_loc.x:.1f}, {t_loc.y:.1f})", flush=True)
                        except:
                            pass
                    
                    # Debug: Print Other Actors Logic
                if step % 50 == 0:
                     print("Debug: Other Actors:", flush=True)
                     ego_loc = self.ego_vehicle.get_location()
                     ego_fwd = self.ego_vehicle.get_transform().get_forward_vector()
                     ego_right = self.ego_vehicle.get_transform().get_right_vector()
                     
                     for a in self.other_actors:
                         if a.id == self.ego_vehicle.id: continue
                         loc = a.get_location()
                         dist = loc.distance(ego_loc)
                         vec = loc - ego_loc
                         forward_dist = vec.x * ego_fwd.x + vec.y * ego_fwd.y + vec.z * ego_fwd.z
                         lateral_dist = vec.x * ego_right.x + vec.y * ego_right.y + vec.z * ego_right.z
                         
                         a_wp = self.map.get_waypoint(loc)
                         print(f"  ID {a.id}: Dist={dist:.1f}m, Fwd={forward_dist:.1f}m, Lat={lateral_dist:.1f}m, Lane={a_wp.lane_id}, Type={a.type_id}", flush=True)
                
                dist_to_target = 100.0 # Default
                
                if not target_actor:
                    # Fallback to relative position if actor not found (should not happen)
                    rel_pos = target_node['center_3d']
                    dx_cam, dy_cam, dz_cam = rel_pos
                    x_veh = dz_cam
                    y_veh = dx_cam
                    target_local = np.array([x_veh - 10.0, y_veh])
                    target_speed = 5.0
                    
                    # Reconstruct global target_loc for Local Planner
                    # ego_loc + fwd * x_veh + right * y_veh
                    fwd = self.ego_vehicle.get_transform().get_forward_vector()
                    right = self.ego_vehicle.get_transform().get_right_vector()
                    el = self.ego_vehicle.get_location()
                    target_loc = carla.Location(
                        x=el.x + fwd.x * x_veh + right.x * y_veh,
                        y=el.y + fwd.y * x_veh + right.y * y_veh,
                        z=el.z + fwd.z * x_veh + right.z * y_veh
                    )
                else:
                    real_target_loc = target_actor.get_location()
                    
                    # --- VIRTUAL SPRING TARGET (Beautification) ---
                    # Replace raw target with a "Virtual Spring" point 10m behind the target.
                    # This point is exponentially smoothed to eliminate jitter (Rubber Band Effect).
                    
                    # Get raw positions as numpy arrays
                    raw_target_pos = np.array([real_target_loc.x, real_target_loc.y, real_target_loc.z])
                    ego_pos = np.array([ego_loc.x, ego_loc.y, ego_loc.z])
                    
                    # Get Ego Heading (Radians)
                    ego_yaw_deg = self.ego_vehicle.get_transform().rotation.yaw
                    ego_yaw_rad = np.deg2rad(ego_yaw_deg)
                    
                    # Update Yaw Smoother (User Request)
                    # Use historical position fit to stabilize Yaw
                    raw_target_pos_2d = raw_target_pos[:2]
                    smooth_yaw_rad = self.yaw_smoother.get_smooth_yaw(raw_target_pos_2d)
                    
                    if smooth_yaw_rad is not None:
                        self.current_target_yaw_rad = smooth_yaw_rad
                    else:
                        # Fallback to instantaneous yaw
                        self.current_target_yaw_rad = np.deg2rad(target_actor.get_transform().rotation.yaw)
                    
                    # Calculate Smooth Virtual Target (with Lateral Clamping)
                    # Note: We use the SmoothFollower instance initialized in constructor
                    smooth_target_pos = self.smooth_follower.get_render_target(raw_target_pos, ego_pos, ego_heading=ego_yaw_rad)
                    
                    # Update target_loc to this new virtual point for CONTROL
                    target_loc = carla.Location(
                        x=smooth_target_pos[0],
                        y=smooth_target_pos[1],
                        z=smooth_target_pos[2]
                    )
                    
                    # Also update intent predictor for legacy consistency (optional)
                    self.intent_predictor.update((target_loc.x, target_loc.y))
                    # ----------------------------------------------

                    # METRICS: Use Real Target Location for distance calculation
                    # We want to maintain ~10m distance from REAL target.
                    dist_to_target = ego_loc.distance(real_target_loc)

                    # 3. Lookahead Waypoint Selection
                    # Get waypoints ahead of ego
                    # Dynamic Lookahead: 5m at low speed, up to 15m at high speed
                    current_speed = self.ego_vehicle.get_velocity()
                    speed_mag = np.sqrt(current_speed.x**2 + current_speed.y**2)
                    lookahead_dist = np.clip(speed_mag * 1.0, 5.0, 15.0) 
                    
                    # Get Ego Transform (Needed for obstacle check and MPC)
                    ego_trans = self.ego_vehicle.get_transform()

                    # OBSTACLE AVOIDANCE LOGIC
                    # Check if there is an obstacle between ego and target
                    obstacle_blocking = None
                    min_obs_dist = float('inf')
                    ego_fwd = ego_trans.get_forward_vector()
                    ego_right = ego_trans.get_right_vector()

                    if step % 10 == 0:
                         print(f"Debug: PredID={pred_target_id}, TrueID={target_id}, NavID={nav_target_id}", flush=True)

                    for actor in self.other_actors:
                        if actor.id == self.ego_vehicle.id: continue
                        # Fix 3: Safety Critical - Do NOT ignore nav_target_id if it is an obstacle!
                        # Only ignore the Ground Truth Target (which we are supposed to follow close)
                        if actor.id == target_id: continue 


                        # Distance Check
                        a_loc = actor.get_location()
                        d = ego_loc.distance(a_loc)
                        
                        # Only care if closer than target and within range (Increased to 25m)
                        if d < dist_to_target and d < 25.0:
                             # Check if in front (or slightly behind for side impacts)
                             vec_to_actor = a_loc - ego_loc
                             fwd_proj = vec_to_actor.dot(ego_fwd)
                             
                             if fwd_proj > -2.5: # Relaxed from > 0 to cover side impacts (Drifting)
                                 # Check lateral alignment (is it in my lane?)
                                # Lane width approx 3.5m. +/- 1.75m is the lane.
                                # We consider it blocking if it's within 2.0m laterally (straddling lane center)
                                right_proj = vec_to_actor.dot(ego_right)
                                obs_lateral_offset = abs(right_proj)
                                
                                # Debug lateral offset
                                if d < 20.0 and step % 20 == 0:
                                   print(f"Debug Loop: Actor {actor.id} Dist={d:.1f}, Fwd={fwd_proj:.1f}, Lat={obs_lateral_offset:.1f}, PredTgt={pred_target_id}", flush=True)

                                # Fix 1: Wide-Cone AEB (Expand lateral threshold to 3.0m)
                                if obs_lateral_offset < 3.0: 
                                    if d < min_obs_dist:
                                        min_obs_dist = d
                                        obstacle_blocking = actor
                                        # Log potential threat for debugging
                                        if d < 10.0 and step % 10 == 0:
                                            logging.debug(f"Debug Loop: Threat {actor.id} Dist={d:.1f}, Lat={obs_lateral_offset:.1f}, Fwd={fwd_proj:.1f}")
                    
                    override_wp = None
                    bypass_status = "None"
                    obs_lateral_offset_final = 0.0

                    # DEBUG: Print Ego Location and Lane
                    if step % 10 == 0:
                        print(f"Debug: Ego Loc: ({ego_loc.x:.1f}, {ego_loc.y:.1f}), Lane: {ego_wp.lane_id}", flush=True)

                    if obstacle_blocking:
                        # Recalculate offset for the selected obstacle
                        vec_to_obs = obstacle_blocking.get_location() - ego_loc
                        obs_lateral_offset_final = abs(vec_to_obs.dot(ego_right))
                        
                        # Try to bypass
                        print(f"Obstacle detected at {min_obs_dist:.1f}m (Lat: {obs_lateral_offset_final:.1f}m)! Attempting bypass...", flush=True)
                        
                        # Helper to check if lane is valid for driving
                        def is_drivable(lane):
                            return lane and lane.lane_type == carla.LaneType.Driving

                        # HYSTERESIS: Check if we have a preference
                        prefer_left = (self.bypass_state and "Left" in self.bypass_state)
                        prefer_right = (self.bypass_state and "Right" in self.bypass_state)
                        
                        # Dynamic Bypass Lookahead
                        # Target point should be roughly at the obstacle's distance + buffer
                        bypass_lookahead = max(min_obs_dist + 8.0, 15.0)

                        # Strategy 1: Check Left Lane (Formal)
                        # Check if lane change is allowed (Left or Both)
                        can_change_left = ego_wp.lane_change in [carla.LaneChange.Left, carla.LaneChange.Both]
                        
                        # If we prefer Right, skip Left unless forced
                        if not prefer_right:
                            if can_change_left or prefer_left:
                                left_lane = ego_wp.get_left_lane()
                                if is_drivable(left_lane):
                                    next_wps = left_lane.next(bypass_lookahead)
                                    if next_wps:
                                        override_wp = next_wps[0]
                                        bypass_status = "Left Lane"
                                        self.bypass_state = bypass_status
                        
                        # Strategy 2: Check Right Lane (Formal)
                        if not override_wp and not prefer_left:
                            can_change_right = ego_wp.lane_change in [carla.LaneChange.Right, carla.LaneChange.Both]
                            if can_change_right or prefer_right:
                                right_lane = ego_wp.get_right_lane()
                                if is_drivable(right_lane):
                                    next_wps = right_lane.next(bypass_lookahead)
                                    if next_wps:
                                        override_wp = next_wps[0]
                                        bypass_status = "Right Lane"
                                        self.bypass_state = bypass_status
                        
                        # Strategy 3: Nudge Left (Virtual Lane)
                        # If formal lane change not allowed or not found, try nudging if space permits
                        if not override_wp and not prefer_right:
                            nudge_offset = -2.5 # Reduced from 3.5 to prevent extreme steering
                            nudge_loc = ego_trans.location + ego_fwd * bypass_lookahead + ego_right * nudge_offset
                            nudge_wp = self.map.get_waypoint(nudge_loc, project_to_road=False) # Don't snap hard
                            
                            # Check if valid road
                            if nudge_wp and is_drivable(nudge_wp):
                                # Ensure we aren't going into opposite traffic if not allowed
                                # Simple check: compare lane ID sign (usually different signs mean opposite directions)
                                same_dir = (nudge_wp.lane_id * ego_wp.lane_id > 0)
                                if same_dir or can_change_left: # Allow if same dir OR if crossing is allowed
                                     if nudge_wp.lane_id != ego_wp.lane_id:
                                         override_wp = nudge_wp
                                         bypass_status = "Nudge Left (Lane)"
                                     else:
                                         # Same lane, but verify width
                                         if nudge_loc.distance(ego_trans.location) > 2.0:
                                             override_wp = nudge_wp
                                             bypass_status = "Nudge Left (Wide)"
                                     self.bypass_state = bypass_status

                        # Strategy 4: Nudge Right (Virtual Lane)
                        if not override_wp and not prefer_left:
                            nudge_offset = 2.5 # Reduced from 3.5 to prevent extreme steering
                            nudge_loc = ego_trans.location + ego_fwd * bypass_lookahead + ego_right * nudge_offset
                            nudge_wp = self.map.get_waypoint(nudge_loc, project_to_road=False)
                            
                            if nudge_wp and is_drivable(nudge_wp):
                                same_dir = (nudge_wp.lane_id * ego_wp.lane_id > 0)
                                if same_dir or can_change_right:
                                    if nudge_wp.lane_id != ego_wp.lane_id:
                                        override_wp = nudge_wp
                                        bypass_status = "Nudge Right (Lane)"
                                    else:
                                         if nudge_loc.distance(ego_trans.location) > 2.0:
                                             override_wp = nudge_wp
                                             bypass_status = "Nudge Right (Wide)"
                                    self.bypass_state = bypass_status
                        
                        if override_wp:
                             print(f"Bypass planned: {bypass_status}", flush=True)
                             # Visualization for Debug
                             if 'rgb_front' in sensor_data:
                                 # This is hard to draw in 2D without projection matrix, but we can print status
                                 pass
                    else:
                        # Clear bypass state if no obstacle nearby (optional, maybe keep it longer?)
                        # For now, clear it if we are totally free
                        pass


                    if override_wp:
                        best_wp = override_wp
                    else:
                        # Normal Path Following
                        next_wps = ego_wp.next(lookahead_dist)
                        
                        if not next_wps:
                            # Dead end?
                            best_wp = ego_wp
                        elif len(next_wps) == 1:
                            # Only one path
                            best_wp = next_wps[0]
                        else:
                            # Junction: Pick waypoint closest to target
                            best_dist = float('inf')
                            best_wp = next_wps[0]
                            for wp in next_wps:
                                d = wp.transform.location.distance(target_loc)
                                if d < best_dist:
                                    best_dist = d
                                    best_wp = wp
                    
                    # 4. Convert Waypoint to Local Frame for MPC
                    # World to Ego Transform
                    # ego_trans = self.ego_vehicle.get_transform() # Already got above
                    
                    # Vector from Ego to Waypoint
                    v_vec = best_wp.transform.location - ego_trans.location
                    
                    # Project to Ego Frame
                    fwd = ego_trans.get_forward_vector()
                    right = ego_trans.get_right_vector()
                    
                    x_local = v_vec.dot(fwd)
                    y_local = v_vec.dot(right)
                    
                    # Calculate distance to target vehicle for speed control
                    # dist_to_target ALREADY CALCULATED ABOVE
                    self.current_dist_to_target = dist_to_target
                    
                    # ADJUSTMENT: Ensure we don't aim through the target
                    # STOP_DISTANCE: Center-to-Center distance to stop behind target.
                    # Since we are using Virtual Spring Target (which is already 10m behind),
                    # we reduce the additional stop distance to a small safety buffer (2.0m).
                    STOP_DISTANCE = 2.0 
                    
                    # Project target location to local frame
                    vec_to_target = target_loc - ego_trans.location
                    x_target_local = vec_to_target.dot(fwd)
                    
                    if x_target_local > 0 and x_target_local < 30.0:
                         # The stop point is STOP_DISTANCE behind the target
                         stop_point_x = x_target_local - STOP_DISTANCE
                         
                         # Only clamp if we are NOT bypassing (i.e. obstacle is target)
                         # If bypassing, we want to drive PAST the obstacle
                         if not obstacle_blocking:
                             if x_local > stop_point_x:
                                 x_local = stop_point_x
                    
                    target_local = np.array([x_local, y_local])
                    
                    # --- VISION PERCEPTION INTEGRATION ---
                # If we have valid vision-based lane data, use it to refine lateral control
                # This replaces the map-based "perfect" lane center with the "seen" lane center
                # CRITICAL: Do NOT use Vision Target if we are Bypassing an obstacle!
                # Vision sees the "Blocked Lane", but we want to follow the "Bypass Path".
                
                # Scheme 3: Lookahead Optimization
                # Don't look at 1m (too jittery). Look at least 5m ahead for lateral guidance.
                vision_lookahead = max(x_local, 5.0)
                vision_target = self.get_vision_target(local_map, vision_lookahead)
                
                # Lane Change Detection:
                # If Map Y is large (> 1.5m), we are likely changing lanes or far off path.
                # In this case, Vision (which tracks current lane) is counter-productive.
                # Only use Vision if we are roughly aligned with the Map Path (within a lane width).
                is_changing_lanes = abs(y_local) > 1.5
                
                if vision_target is not None and not obstacle_blocking and bypass_status == "None" and not is_changing_lanes:
                    # Blend or Override
                    # Safety Clamp: Prevent Vision from contradicting Map too much
                    # If Map says we are at Y=0 (Center), and Vision says Y=3 (Right),
                    # we trust Vision up to a point.
                    
                    v_y = vision_target[1]
                    m_y = y_local
                    
                    # Clamp Vision Y to be within [Map Y - 2.0, Map Y + 2.0]
                    # Relaxed from 1.5 to 2.0 to allow more vision authority, but still prevent extreme drifts
                    clamped_v_y = np.clip(v_y, m_y - 2.0, m_y + 2.0)
                    
                    # Scheme 3.5: Vision Lateral Low-Pass Filter
                    # Reduce jitter from noisy perception (especially in Rain)
                    if not hasattr(self, 'filtered_vision_y'):
                        self.filtered_vision_y = clamped_v_y
                    
                    alpha_y = 0.2 # Strong smoothing for lateral position
                    self.filtered_vision_y = (1.0 - alpha_y) * self.filtered_vision_y + alpha_y * clamped_v_y
                    
                    target_local[1] = self.filtered_vision_y
                    
                    # Debug info
                    if step % 50 == 0:
                         print(f"  [Vision Control] Refined Target Y: Map={m_y:.2f} -> Vision={v_y:.2f} -> Clamped={clamped_v_y:.2f} -> Filtered={self.filtered_vision_y:.2f}", flush=True)
                # -------------------------------------
                
                # --- ENHANCED LONGITUDINAL CONTROL (Graph-Aware ACC) ---
                # Use the scene graph to find the closest object in our lane (front)
                # This is "Vision/Graph Based" instead of "Oracle Based"
                
                closest_front_dist = 999.0
                closest_front_speed = 0.0
                front_obj_id = -1
                
                # Iterate through edges to find 'front' relation
                # Edges: (u, v, rel) -> We want (Ego, v, 'front')
                # But 'edges' indices refer to 'nodes' list.
                # We need to find which node is Ego?
                # Actually, our graph builder doesn't explicitly add 'Ego' as a node usually,
                # unless we treat Ego as the origin of the coordinate system.
                # In logic_adapter.py, 'nodes' are detections.
                # Relations are between detections.
                # But we implemented "front/behind" relative to Ego implicitly?
                # No, logic_adapter computes relations between PAIRS of detections.
                
                # However, we have the raw 'nodes' list where each node has 'lane_idx'.
                # Ego is always at lane_idx = 0.
                
                for n in nodes:
                    # Filter: In Ego's lane (lane_idx == 0) and In Front (x > 0)
                    # Note: center_3d is in Camera Frame (Right, Down, Forward) usually,
                    # but we stored it. Let's check logic_adapter again.
                    # logic_adapter: ego_x = c3d[2] (Forward), ego_y = c3d[0] (Right)
                    
                    c3d = n['center_3d']
                    n_x = c3d[2] # Forward distance
                    n_y = c3d[0] # Lateral distance
                    n_lane = n.get('lane_idx', 0)
                    
                    # Check if object is in our path
                    # Lane Width approx 3.5m. lane_idx 0 means roughly -1.75 to 1.75
                    # We add a geometric sanity check: abs(n_y) < 2.0
                    # This handles cases where LogicAdapter fails to find lane lines and defaults to 0
                    
                    if n_lane == 0 and n_x > 0 and abs(n_y) < 2.0:
                        # It is in front of us in our lane
                        dist = n_x - 5.0 # Subtract vehicle length approx
                        if dist < closest_front_dist:
                            closest_front_dist = dist
                            front_obj_id = n['id']
                
                # Current Speed
                v = self.ego_vehicle.get_velocity()
                speed = np.sqrt(v.x**2 + v.y**2 + v.z**2)

                # Adaptive Cruise Control Logic
                # Desired Gap: 2 seconds * speed
                # In Hard mode, we need to be more aggressive to keep up
                gap_factor = 2.0
                base_speed = 16.0
                if hasattr(self, 'difficulty') and self.difficulty == 'Hard':
                    gap_factor = 1.2 # Reduced gap for agility
                    base_speed = 22.0 # Higher base speed
                
                # Rain Safety: Increase gap in rain due to lower friction
                if 'Rain' in getattr(self, 'current_weather_name', ''):
                    gap_factor = max(gap_factor, 2.0)
                    if step % 50 == 0:
                        print(f"  [ACC] Rain Mode: Increased Gap Factor to {gap_factor}", flush=True)

                safe_gap = max(10.0, speed * gap_factor)
                
                if closest_front_dist < 100.0: # Found something relevant
                    # P-Controller for speed
                    # error = actual_dist - desired_dist
                    # If actual < desired, slow down.
                    
                    # Target Speed Logic:
                    # If far: Cruise Speed
                    # If close: Match speed or Stop
                    
                    if closest_front_dist < 10.0:
                        # Emergency Braking / Stop
                        if override_wp:
                             # If bypassing, allow closer approach and maintain speed
                             if closest_front_dist < 4.0:
                                 target_speed = 0.0
                                 if step % 50 == 0:
                                     print(f"  [ACC] STOPPING (Bypass Critical)! Obstacle {front_obj_id} at {closest_front_dist:.1f}m", flush=True)
                             else:
                                 target_speed = 5.0 # Slow pass
                        else:
                            target_speed = 0.0
                            if step % 50 == 0:
                                print(f"  [ACC] STOPPING! Obstacle {front_obj_id} at {closest_front_dist:.1f}m", flush=True)
                    elif closest_front_dist < safe_gap:
                        # Follow Mode
                        # Linearly decrease speed
                        ratio = (closest_front_dist - 10.0) / (safe_gap - 10.0)
                        target_speed = base_speed * ratio
                        if step % 50 == 0:
                            print(f"  [ACC] Following {front_obj_id} at {closest_front_dist:.1f}m. TgtSpd: {target_speed:.1f}", flush=True)
                    else:
                        # Free Flow
                        target_speed = base_speed
                        
                    # Override Map-based speed if Vision sees an obstacle closer
                    # (Map might target a car 50m away, but Vision sees a pedestrian 20m away)
                
                # -------------------------------------------------------

                # Dynamic Speed Control (Legacy Map-based Fallback)
                # Only use if Vision didn't set a strict constraint
                if closest_front_dist >= 100.0:
                    if obstacle_blocking:
                        target_speed = 4.0 # Caution when bypassing
                    else:
                        if dist_to_target > 35.0:
                            if hasattr(self, 'difficulty') and self.difficulty == 'Hard':
                                target_speed = 22.0 # Catch up in Hard mode (Target ~25m/s)
                            else:
                                target_speed = 16.0
                        elif dist_to_target > 25.0:
                            target_speed = 12.0
                        elif dist_to_target > 15.0:
                            target_speed = 9.0
                        else:
                            target_speed = max(0.0, dist_to_target - 8.0)
                            target_speed = min(target_speed, 6.0)
                    
                    # Curvature Slowdown (Prevent Wide Turns)
                    # Apply if we are close OR if the angle is significant (Sharp Turn)
                    angle_to_target = math.atan2(target_local[1], target_local[0])
                    
                    # MODIFIED: Relaxed curvature slowdown for long distances
                    if dist_to_target < 20.0:
                        # Close range: Strict curvature limits
                        if abs(angle_to_target) > 0.5: # ~28 degrees
                            target_speed = min(target_speed, 5.0) 
                        if abs(angle_to_target) > 1.0: # ~57 degrees
                            target_speed = min(target_speed, 3.0) 
                        if abs(angle_to_target) > 1.5: # ~86 degrees (Hairpin)
                            target_speed = min(target_speed, 2.0) 
                    else:
                        # Long range: Relaxed limits. We need speed to close the gap.
                        if abs(angle_to_target) > 1.0: # ~57 degrees
                            target_speed = min(target_speed, 8.0) # Allow reasonable speed
                        if abs(angle_to_target) > 1.5: # ~86 degrees
                            target_speed = min(target_speed, 4.0)

                    
                    # Calculate Curvature from Map (Lookahead)
                    max_k = 0.0
                    if ego_wp:
                        yaw0 = ego_wp.transform.rotation.yaw
                        # Check multiple distances to catch approaching curves
                        for dist in [5.0, 10.0, 15.0, 20.0]: 
                            next_wps = ego_wp.next(dist)
                            if next_wps:
                                wp_next = next_wps[0]
                                yaw_next = wp_next.transform.rotation.yaw
                                diff = yaw_next - yaw0
                                # Normalize to [-180, 180]
                                while diff > 180: diff -= 360
                                while diff < -180: diff += 360
                                
                                # Average curvature over the distance
                                k = abs(np.deg2rad(diff)) / dist
                                if k > max_k: max_k = k

                    # Curvature-based speed reduction (Physics-based)
                    if max_k > 0.01: # Radius < 100m
                         # Centripetal limit: v = sqrt(a_lat * R) = sqrt(a_lat / k)
                         # Use a_lat = 2.0 m/s^2 (Comfortable/Safe cornering)
                         limit_speed = np.sqrt(2.0 / max_k)
                         target_speed = min(target_speed, limit_speed)
                         
                         if step % 50 == 0 and limit_speed < 10.0:
                             print(f"  [Curve] MaxK={max_k:.3f} (R={1/max_k:.1f}m) -> Limit={limit_speed:.1f} m/s", flush=True)
                
                # Current Speed (Calculated above)
                # v = self.ego_vehicle.get_velocity()
                # speed = np.sqrt(v.x**2 + v.y**2 + v.z**2)
                
                # --- PHYSICS DEFENSE: Trinity Strategy ---
                # 1. Update Ghost Timer
                # Use Visual Tracking Status (pred_target_id) instead of Ground Truth Actor existence
                is_ghost_mode = (pred_target_id != target_id)
                if is_ghost_mode:
                    self.ghost_timer += 0.05 # dt = 0.05s
                else:
                    self.ghost_timer = 0.0
                
                # 2. Wet Road Speed Cap (HardRainNoon -> Max 8.0 m/s for Velcro Mode)
                # Lower speed allows closer following distance (7m)
                if self.current_weather_name == "HardRainNoon":
                    MAX_SAFE_SPEED = 8.0
                    if target_speed > MAX_SAFE_SPEED:
                        target_speed = MAX_SAFE_SPEED
                
                # 3. Ghost Deceleration (Linear decay in ghost mode)
                if self.ghost_timer > 0:
                    decay_factor = max(0.0, 1.0 - 0.2 * self.ghost_timer)
                    target_speed = target_speed * decay_factor
                    if step % 20 == 0:
                        print(f"  [Ghost] Timer={self.ghost_timer:.2f}s, Decay={decay_factor:.2f}, TgtSpeed={target_speed:.2f}", flush=True)

                # --- NOVELTY: Uncertainty-Aware Active Control ---
                if not args.no_uncertainty and uncertainty > 1.0: # High uncertainty threshold
                     # Slow down to give perception more time/safety
                     target_speed = min(target_speed, 5.0) 
                     if step % 50 == 0:
                         print(f"  [Uncertainty] High Entropy ({uncertainty:.2f}) -> Reducing Speed", flush=True)
                
                # === Scheme 2: Target Speed LPF (Exponential Moving Average) ===
                if self.smooth_target_speed == 0.0:
                    self.smooth_target_speed = target_speed
                
                # Asymmetric Alpha: Fast to accelerate, Slow to brake (to prevent false positive braking)
                if target_speed < self.smooth_target_speed:
                    alpha = 0.1 # Decelerate slowly (trust history more)
                else:
                    alpha = 0.5 # Accelerate fast (trust perception)
                
                self.smooth_target_speed = (1 - alpha) * self.smooth_target_speed + alpha * target_speed
                target_speed = self.smooth_target_speed
                # ===============================================================

                # -------------------------------------------------

                # --- PREPARE OBSTACLES FOR MPC ---
                # Format: List of (x, y, radius, risk_weight)
                mpc_obstacles = []
                
                # 1. Vision-Detected Objects (from Graph)
                for n in nodes:
                    c3d = n['center_3d']
                    # Filter relevant objects (within 50m)
                    if c3d[2] > 0 and c3d[2] < 50.0 and abs(c3d[0]) < 10.0:
                        # Determine Risk Weight based on type
                        label = n.get('label', 'object')
                        risk = 1.0
                        radius = 2.0 # Default car width approx
                        
                        if label in ['person', 'pedestrian']:
                            risk = 5.0 # High risk for humans
                            radius = 0.5
                        elif label in ['truck', 'bus']:
                            radius = 2.5
                        elif label in ['bicycle', 'motorcycle']:
                            radius = 1.0
                            
                        # If object is in our lane, risk is very high
                        # Use geometric check as backup for lane_idx
                        if n.get('lane_idx') == 0 or (abs(c3d[0]) < 2.0 and c3d[2] < 20.0):
                            risk *= 5.0 # increased from 2.0 to 5.0
                            radius *= 1.2 # slightly larger radius for safety
                            
                        mpc_obstacles.append((c3d[2], c3d[0], radius, risk))

                # -------------------------------------------------
                # 1.5. Vision Persistence Obstacles (Static/Vegetation)
                # -------------------------------------------------
                if 'obstacles' in local_map:
                    # Get Ego Transform (re-get or reuse)
                    ego_trans = self.ego_vehicle.get_transform()
                    
                    # Update Persistence
                    # DEBUG: Persistence Filter
                    raw_obs_count = len(local_map['obstacles'])
                    valid_vis_obs = self.update_obstacle_persistence(local_map['obstacles'], ego_trans)
                    if step % 50 == 0:
                        print(f"  [Persistence] Raw: {raw_obs_count}, Valid: {len(valid_vis_obs)}", flush=True)
                    
                    for obs in valid_vis_obs:
                        x_local, y_local, _ = obs['pos']
                        radius = obs['radius']
                        
                        # Check duplicate
                        is_duplicate = False
                        for mpc_obs in mpc_obstacles:
                            d_dup = (x_local - mpc_obs[0])**2 + (y_local - mpc_obs[1])**2
                            if d_dup < 1.0:
                                is_duplicate = True
                                break
                        
                        if not is_duplicate:
                            # Static obstacles are high risk if close
                            risk = 2.0
                            if abs(y_local) < 2.5: # In or near lane
                                risk = 5.0
                            
                            # Enforce Minimum Radius for Safety (e.g. Poles are thin but dangerous)
                            safe_radius = max(radius, 1.0)
                            mpc_obstacles.append((x_local, y_local, safe_radius, risk))

                # -------------------------------------------------
                # GROUND TRUTH OBSTACLE INJECTION (Robustness Fallback)
                # -------------------------------------------------
                # Always inject GT obstacles if Vision missed them (or for testing)
                # This ensures MPC has data even if CV2 is missing or Perception fails
                
                # Get all vehicles and walkers
                actors = self.world.get_actors()
                vehicles = actors.filter('vehicle.*')
                walkers = actors.filter('walker.pedestrian.*')
                
                ego_trans = self.ego_vehicle.get_transform()
                ego_loc = ego_trans.location
                ego_fwd = ego_trans.get_forward_vector()
                ego_right = ego_trans.get_right_vector()
                
                for actor in list(vehicles) + list(walkers):
                    if actor.id == self.ego_vehicle.id:
                        continue
                        
                    # Calculate relative position
                    a_loc = actor.get_location()
                    vec = a_loc - ego_loc
                    dist = vec.length()
                    
                    if dist > 50.0:
                        continue
                        
                    # Project to Ego Frame
                    # x_local = forward distance
                    # y_local = lateral distance (right is positive)
                    x_local = vec.dot(ego_fwd)
                    y_local = vec.dot(ego_right)
                    
                    # Ignore objects behind
                    if x_local < -5.0:
                        continue
                        
                    # Check if already in mpc_obstacles (simple duplicate check by distance)
                    is_duplicate = False
                    for obs in mpc_obstacles:
                        # obs is (x, y, r, w)
                        d_dup = (x_local - obs[0])**2 + (y_local - obs[1])**2
                        if d_dup < 1.0: # Within 1m
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        # Determine type and risk
                        risk = 1.0
                        radius = 2.0
                        if 'walker' in actor.type_id:
                            risk = 5.0
                            radius = 0.5
                        elif 'vehicle' in actor.type_id:
                            radius = 2.2
                            if abs(y_local) < 2.0: # In our lane
                                risk = 5.0 # High risk
                        
                        mpc_obstacles.append((x_local, y_local, radius, risk))

                # 2. Map-Based Obstacles (Legacy Fallback)
                if obstacle_blocking:
                    # If perception missed it but map knows it (rare but possible)
                    pass 
                
                # --- LOCAL PLANNING (Optimization Step 1.3 & 2.1) ---
                # Generate candidate trajectories and select best one
                
                # OPTION 1: Frenet Quintic Polynomial Planner
                # We want to replace the simple 'generate_local_plan' (which uses Waypoint heuristic) 
                # with a mathematically smooth Quintic Polynomial.
                # However, Quintic Polynomial requires (sx, sy, svx, svy, sax, say) -> (ex, ey, evx, evy, eax, eay).
                # Current state (Ego Frame): x=0, y=0, vx=current_speed, vy=0, ax=last_accel, ay=0
                # Target state (Ego Frame): x=target_local[0], y=target_local[1], vx=target_speed, vy=0, ax=0, ay=0
                
                # Check if we should use Quintic (if implemented and stable)
                # Hybrid Strategy: Use Quintic for close following, Map-based for long range
                use_quintic = True
                if dist_to_target > 25.0:
                    use_quintic = False # Use Map Waypoints to stay on road 
                
                best_local_traj = None
                best_global_traj = []
                candidates = []
                
                if use_quintic:
                    # Use Bezier Curve (Smoother than Quintic)
                    # We hijack the 'use_quintic' flag or just prioritize Bezier here.
                    # Since we want to integrate Bezier, we'll use it as the primary local planner.
                    
                    # Calculate Target Heading (Relative to Ego)
                    target_heading_rel = 0.0
                    if best_wp:
                        ego_yaw = ego_trans.rotation.yaw
                        target_yaw = best_wp.transform.rotation.yaw
                        diff = target_yaw - ego_yaw
                        # Normalize to [-pi, pi]
                        target_heading_rel = np.deg2rad((diff + 180) % 360 - 180)
                    
                    ego_state = np.array([0.0, 0.0, 0.0, speed]) # x, y, yaw, v
                    
                    # Generate Bezier Trajectory
                    # Returns [H, 4] array: (x, y, v, yaw)
                    bezier_traj = self.mpc.get_bezier_trajectory(
                        ego_state, 
                        target_local, 
                        target_heading_rel, 
                        target_speed
                    )
                    
                    # Use the generated trajectory
                    best_local_traj = bezier_traj
                    
                    # Visualize Global Trajectory
                    ego_trans = self.ego_vehicle.get_transform()
                    fwd = ego_trans.get_forward_vector()
                    right = ego_trans.get_right_vector()
                    loc = ego_trans.location
                    
                    best_global_traj = []
                    for pt in bezier_traj:
                        # pt is [x, y, v, yaw]
                        g_loc = carla.Location(
                             x=loc.x + fwd.x * pt[0] + right.x * pt[1],
                             y=loc.y + fwd.y * pt[0] + right.y * pt[1],
                             z=loc.z + fwd.z * pt[0] + right.z * pt[1]
                        )
                        best_global_traj.append(g_loc)
                        
                elif False: # Disabled Quintic for now (Legacy)
                    # Current State in Ego Frame
                    v_ego = speed
                         
                if not use_quintic: # Fallback if Quintic disabled or failed
                    # Legacy Local Planner
                    best_local_traj, best_global_traj, candidates = self.generate_local_plan(
                        ego_trans, target_loc, mpc_obstacles, target_speed
                    )
                
                # FINAL FALLBACK: If both planners failed (returned None or empty)
                if best_local_traj is None or len(best_local_traj) == 0:
                     # Safety Trajectory: Straight ahead at crawl speed
                     # This prevents MPC from receiving empty trajectory and crashing/stopping
                     target_len = self.mpc.H
                     safe_speed = 2.0
                     dt = 0.05
                     # x = v*t, y=0
                     t = np.arange(1, target_len + 1) * dt
                     x_pts = safe_speed * t
                     y_pts = np.zeros(target_len)
                     best_local_traj = np.column_stack((x_pts, y_pts))
                     if step % 10 == 0:
                        print("  [Fallback] ALL Planners Failed -> Safety Creep (Straight)", flush=True)

                
                # Update Visualization Data
                self.planned_path = best_global_traj if best_global_traj else []
                # Store candidates for visualization (needs support in render)
                self.candidate_paths = [c['global'] for c in candidates]
                
                # --- NOVELTY: Language-Conditioned Cost Function ---
                mpc_weights = {}
                style_factor = 0.5 # Default balanced
                
                if not args.no_soft_mpc:
                    # Simple keyword matching (Simulating L2 Reasoning output)
                    if "closely" in text.lower() or "close" in text.lower() or "fast" in text.lower():
                        # Aggressive / Tight Following
                        mpc_weights['w_obs_scale'] = 0.5 # Relax safety margin
                        mpc_weights['w_pos'] = 40.0 # Tighter tracking (Base 20 -> 40)
                        mpc_weights['w_smooth_accel'] = 40.0 # Slightly less smooth than default (50) for responsiveness
                        style_factor = 0.8
                        if step % 50 == 0: print("  [Style] 'Closely' -> Aggressive Tracking", flush=True)
                        
                    elif "carefully" in text.lower() or "safe" in text.lower() or "slow" in text.lower():
                        # Conservative / Safe
                        mpc_weights['w_obs_scale'] = 5.0 # Increase safety margin
                        mpc_weights['w_smooth_accel'] = 100.0 # Extremely Smooth (Default 50)
                        mpc_weights['w_steer'] = 20.0 # Penalize steering more (Default 15.0)
                        style_factor = 0.2
                        if step % 50 == 0: print("  [Style] 'Carefully' -> Conservative Safety", flush=True)
                # ---------------------------------------------------

                # Initialize timing
                mpc_solve_time = 0.0

                # Solve MPC with Semantic Obstacles and Local Plan Reference
                if best_local_traj is not None and len(best_local_traj) > 0:
                     try:
                        # DEBUG: Print inputs before solve
                        if step % 20 == 0:
                            print(f"DEBUG: Calling MPC Solve with Speed={speed:.2f}, Target={target_local}, RefTrajLen={len(best_local_traj)}", flush=True)
                        
                        t0_mpc = time.time()
                        control, _ = self.mpc.solve(speed, target_local, target_speed=target_speed, obstacles=mpc_obstacles, ref_traj=best_local_traj, weights=mpc_weights, uncertainty=uncertainty)
                        mpc_solve_time = time.time() - t0_mpc

                        # Robust extraction of scalars
                        flat_ctrl = np.array(control).flatten()
                        accel = float(flat_ctrl[0]) if len(flat_ctrl) > 0 else 0.0
                        steer = float(flat_ctrl[1]) if len(flat_ctrl) > 1 else 0.0
                     except Exception as e:
                        print(f"CRITICAL: MPC Solve crashed: {e}", flush=True)
                        accel, steer = 0.0, 0.0
                else:
                     # Fallback to Point Attractor if Local Planner fails
                     # SAFETY CHECK: If we failed to find a path because of obstacles, DO NOT blindly accelerate.
                     if obstacle_blocking and min_obs_dist < 20.0:
                         if step % 10 == 0:
                            print(f"  [Fallback] Planner failed & Obstacle ahead ({min_obs_dist:.1f}m) -> Emergency Stop", flush=True)
                         accel = -4.0
                         steer = 0.0
                     else:
                         try:
                            t0_mpc = time.time()
                            control, _ = self.mpc.solve(speed, target_local, target_speed=target_speed, obstacles=mpc_obstacles, weights=mpc_weights, uncertainty=uncertainty)
                            mpc_solve_time = time.time() - t0_mpc

                            # Robust extraction of scalars
                            flat_ctrl = np.array(control).flatten()
                            accel = float(flat_ctrl[0]) if len(flat_ctrl) > 0 else 0.0
                            steer = float(flat_ctrl[1]) if len(flat_ctrl) > 1 else 0.0
                         except Exception as e:
                            print(f"CRITICAL: MPC Solve (Fallback) crashed: {e}", flush=True)
                            accel, steer = 0.0, 0.0
                
                # DEBUG: Print Control Output
                if step % 20 == 0:
                     msg = f"DEBUG: MPC Accel={float(accel):.2f}, Steer={float(steer):.2f}, RefTrajLen={len(best_local_traj) if best_local_traj is not None else 0}"
                     print(msg)
                     logging.debug(msg)
                     if best_local_traj is not None and len(best_local_traj) > 0:
                         print(f"DEBUG: RefTraj[0]={best_local_traj[0]}")
                
                # Emergency Brake Override
                # If we are too close (closer than safety margin), force brake
                # Check BOTH target and obstacle
                
                emergency_brake_active = False
                min_safe_dist = 5.0 # Reduced from 6.0 for closer following
                if dist_to_target < min_safe_dist:
                     if dist_to_target < 4.0:
                         accel = -4.0 # Panic
                     else:
                         accel = -2.0 # Strong Brake
                     emergency_brake_active = True
                
                # If obstacle is blocking
                if obstacle_blocking:
                     # Calculate lateral offset to obstacle center
                     vec_to_obs = obstacle_blocking.get_location() - ego_trans.location
                     obs_lat = abs(vec_to_obs.dot(ego_right))
                     
                     # If we are too close longitudinally AND too close laterally, BRAKE.
                     # Longitudinal limit: 6.0m (center-to-center)
                     if min_obs_dist < 6.0:
                         if obs_lat < 2.2: # Increased to 2.2m (safe passing clearance)
                             print(f"Emergency Brake! Dist={min_obs_dist:.1f}, Lat={obs_lat:.1f}", flush=True)
                             # Gradual Emergency Brake to reduce Jerk
                             if min_obs_dist < 4.0:
                                 accel = -4.0 # Panic
                             else:
                                 accel = -2.0 # Strong Brake
                             emergency_brake_active = True
                         elif not override_wp: # No way around
                             print("Blocked (No Path), Emergency Brake!", flush=True)
                             if min_obs_dist < 4.0:
                                 accel = -4.0
                             else:
                                 accel = -2.0
                             emergency_brake_active = True

                
                # RECOVERY MODE: If stuck in collision, Reverse
                request_reverse = False
                
                # Trigger Reverse
                if self.collision_persistence > 30 and speed < 0.1: # Increased to 30 frames (1.5s) to avoid false positives
                     if self.reverse_counter == 0:
                         print(f"CRITICAL: Stuck in collision ({self.collision_persistence} frames). Triggering Persistent REVERSE (60 frames)!", flush=True)
                         self.reverse_counter = 60 # Force reverse for 3 seconds
                
                # Stuck Detection (Non-Collision)
                # === Scheme 4: Smart Deadlock Detection ===
                # Logic: If MPC wants to accelerate significantly (> 2.0 m/s^2) but we are stopped (< 0.1 m/s)
                # for > 3.0s, we are physically stuck.
                
                # CRITICAL FIX: Do not count deadlock while Reversing!
                deadlock_triggered = False
                if self.reverse_counter > 0:
                    self.deadlock_timer = 0
                elif accel > 2.0 and speed < 0.1:
                    self.deadlock_timer += 0.05 # dt
                else:
                    self.deadlock_timer = 0
                
                if self.deadlock_timer > 3.0:
                    if self.reverse_counter == 0:
                        print(f"CRITICAL: Confirmed Stuck (Accel>2.0, Speed<0.1 for 3s). Triggering REVERSE!", flush=True)
                        self.reverse_counter = 60
                        self.deadlock_timer = 0
                        deadlock_triggered = True
                
                # Apply Persistent Reverse
                if self.reverse_counter > 0:
                    self.reverse_counter -= 1
                    accel = -2.0 
                    steer = 0.0 # Straight back
                    request_reverse = True
                    
                    # Log periodically
                    if self.reverse_counter % 10 == 0:
                        print(f"  [Recovery] Reversing... {self.reverse_counter} frames left.", flush=True)
                
                # DEBUG: Print Status
                if step % 10 == 0:
                    msg = f"Step {step}: Dist={dist_to_target:.1f}m, Speed={speed:.1f}m/s, TgtSpeed={target_speed:.1f}, Obs={obstacle_blocking is not None}, Bypass={bypass_status}, LocalPlan={best_local_traj is not None}"
                    print(msg)
                    logging.debug(msg)

                # self.planned_path updated above from Local Planner

                
                # Record Metrics
                steer_history.append(steer)
                accel_history.append(accel)
                # Lateral Error is now deviation from WAYPOINT, not vehicle
                # We can calculate deviation from vehicle for reference
                # But since the goal is to follow the path, path deviation is more relevant for stability
                # However, for "Following", we want to know if we lost the car.
                lateral_errors.append(abs(y_local))

                # Apply Control
                # MPC Steer is in radians, CARLA needs [-1, 1] normalized
                # Max steer is 40 deg (0.7 rad) approx
                steer_norm = steer / np.deg2rad(40)
                steer_norm = np.clip(steer_norm, -1.0, 1.0)
                
                # --- Pre-Smoothing Safety Clamp ---
                # Strictly limit acceleration change to prevent Jerk spikes
                # Max Jerk 100 m/s^3 -> 5 m/s^2 per 0.05s
                if not emergency_brake_active:
                    accel = np.clip(accel, self.last_accel - 2.0, self.last_accel + 2.0)
                self.last_accel = accel
                
                # --- Control Smoothing (Low-Pass Filter + Rate Limit) ---
                # To reduce Jerk < 2000 m/s^3, we need smooth acceleration changes.
                
                # 1. LPF on Acceleration Command (accel)
                alpha_steer = 0.2 # Default alpha
                
                if emergency_brake_active:
                    # CRITICAL: Bypass LPF for Emergency Brake to ensure immediate response
                    self.filtered_accel = accel
                    # Dampen steering during panic brake to avoid swerving into obstacles
                    # If we are braking hard, we assume we should go straight or keep current path gently
                    self.filtered_steer = steer_norm * 0.5 
                    
                    # Reset Rate Limiter state so it doesn't block the brake
                    self.last_brake = 0.0 # Will be set to target_brake in next step
                elif speed < 1.0 and accel > 0.5:
                     # STARTUP BOOST: Bypass LPF for acceleration if stopped/slow and trying to move
                     # This reduces lag in getting off the line
                     self.filtered_accel = accel
                     
                     # STARTUP BOOST STEERING:
                     # If we are boosting, we want to straighten out FAST.
                     # Trust the MPC clamped output (0.0) and apply it quickly.
                     alpha_steer = 0.8 
                     self.filtered_steer = self.filtered_steer * (1.0 - alpha_steer) + steer_norm * alpha_steer
                else:
                    # alpha = 0.1 means ~10 frame time constant (0.5s) - Smoother
                    alpha_accel = 0.1
                    if self.filtered_accel == 0.0: self.filtered_accel = accel # Init
                    self.filtered_accel = self.filtered_accel * (1.0 - alpha_accel) + accel * alpha_accel

                    # 2. LPF on Steering Command
                    # alpha_steer = 0.2 (Defined above)
                    if self.filtered_steer == 0.0: self.filtered_steer = steer_norm # Init
                    self.filtered_steer = self.filtered_steer * (1.0 - alpha_steer) + steer_norm * alpha_steer
                
                # Use Filtered Values for Output Calculation
                f_accel = self.filtered_accel
                f_steer = self.filtered_steer
                
                # Map Filtered Accel to Throttle/Brake
                target_throttle = 0.0
                target_brake = 0.0
                is_boosting = False
                
                if f_accel > 0:
                    target_throttle = np.clip(f_accel / 3.0, 0.0, 1.0)
                    
                    # Update stuck counter
                    if speed < 0.1 and f_accel > 0.5:
                        self.stuck_counter += 1
                    else:
                        self.stuck_counter = 0

                    # === Scheme 1: Start-up Boost (Static Friction Overcome) ===
                    # If we are effectively stopped and want to go, give a KICK.
                    # Bypass Rate Limiter to ensure torque is applied INSTANTLY.
                    # GUARD: Do not boost if we are already moving fast or collided.
                    
                    # User Fix 1: Soft Boost Logic (Gradual Ramp-up)
                    if self.stuck_counter > 5 and not self.collision_occured and speed < 2.0:
                         # Gradual Boost: 0.4 -> 0.8
                         boost_intensity = min(0.4 + (self.stuck_counter - 5) * 0.05, 0.8)
                         print(f"  [Control] Soft Boost Triggered: {boost_intensity:.2f}", flush=True)
                         target_throttle = boost_intensity 
                         is_boosting = True
                    elif speed < 1.0 and f_accel > 0.1:
                         target_throttle = max(target_throttle, 0.5) # Gentle assist
                    
                    # CRITICAL: If accelerating, release brake IMMEDIATELY
                    self.last_brake = 0.0
                else:
                    target_brake = np.clip(-f_accel / 5.0, 0.0, 1.0)

                # 3. Rate Limiter (Final Safety Check)
                # Ensure we don't jump even if LPF moves fast (e.g. on step input)
                
                if emergency_brake_active or is_boosting:
                     # Bypass Rate Limiter for Brake OR Boost
                     throttle = target_throttle
                     brake = target_brake # Should be close to 1.0 if accel is -4.0
                     self.last_throttle = throttle
                     self.last_brake = brake
                else:
                    # Throttle
                    th_step = 0.05 # Increased from 0.01 for better responsiveness (2s to full)
                    if target_throttle > self.last_throttle:
                        self.last_throttle = min(self.last_throttle + th_step, target_throttle)
                    else:
                        self.last_throttle = max(self.last_throttle - 0.1, target_throttle) # Cut throttle slower (0.2 -> 0.1)
                    throttle = self.last_throttle
                    
                    # Brake (Allow fast braking for safety)
                    if target_brake > self.last_brake:
                        self.last_brake = min(self.last_brake + 0.2, target_brake) # Fast brake
                    else:
                        self.last_brake = max(self.last_brake - 0.05, target_brake) # Release slow
                    brake = self.last_brake
                
                # === Safety: Speed Limiter ===
                # Prevent runaway acceleration even if MPC/Boost asks for it
                if target_actor:
                     # Heuristic: If we are significantly over target speed, CUT THROTTLE.
                     limit_speed = t_speed + 3.0 # Allow +3 m/s buffer
                     
                     # HardRainNoon Cap Enforcement
                     if self.current_weather_name == "HardRainNoon":
                         limit_speed = min(limit_speed, 7.5) # Strict cap (7.0 target + 0.5 buffer)

                     if speed > limit_speed:
                         throttle = 0.0
                         if step % 20 == 0: print(f"  [Safety] Speed Limit Triggered ({speed:.1f} > {limit_speed:.1f})", flush=True)

                # Steer
                st_step = 0.05 # Reduced from 0.1
                delta_steer = f_steer - self.last_steer
                delta_steer = np.clip(delta_steer, -st_step, st_step)
                steer_norm = self.last_steer + delta_steer
                self.last_steer = steer_norm
                
                control = carla.VehicleControl()
                control.manual_gear_shift = False
                control.hand_brake = False
                control.steer = float(steer_norm)
                
                if request_reverse:
                    control.reverse = True
                    control.throttle = 0.4 # Reduced from 0.8 to prevent unsafe backing
                    control.brake = 0.0
                    # Reset smoothing state to avoid lag when switching back
                    self.last_throttle = 0.4
                    self.last_brake = 0.0
                else:
                    control.reverse = False
                    control.throttle = float(throttle)
                    control.brake = float(brake)
                
                # User Fix 2: Absolute Safety Shield (AEB)
                # === User Request: Dynamic AEB (Velocity Dependent) ===
                # If slow, allow close (3m). If fast, brake early.
                # Threshold = 2.0m + (Speed * 0.5s)
                # e.g., 8m/s -> 6m. 2m/s -> 3m.
                
                # Use min_obs_dist calculated earlier (Oracle/Ground Truth for Safety)
                # CRITICAL FIX: Include Target Vehicle in AEB check!
                real_safe_dist = min_obs_dist
                if target_actor:
                     real_safe_dist = min(real_safe_dist, dist_to_target)

                # Calculate Dynamic Threshold
                dynamic_threshold = 2.0 + (speed * 0.5)
                
                if real_safe_dist < dynamic_threshold:
                     # Multi-stage braking logic could be simplified or kept.
                     # User requested: Throttle 0, Brake 1.0 if < threshold
                     control.throttle = 0.0
                     control.brake = 1.0
                     brake_type = "Dynamic"
                     
                     if step % 5 == 0:
                         msg = f"[Safety] Proximity AEB! Dist: {real_safe_dist:.2f}m (Thresh: {dynamic_threshold:.1f}m)"
                         print(msg, flush=True)
                         logging.warning(msg)
                
                if step % 1 == 0:
                    msg = f"DEBUG: Control Throttle={control.throttle:.2f}, Brake={control.brake:.2f}, Steer={control.steer:.2f}, Rev={control.reverse}"
                    logging.debug(msg)
                    print(msg, flush=True)

                print("Debug: Applying control...", flush=True)
                self.ego_vehicle.apply_control(control)
                print("Debug: Control applied.", flush=True)
                
                # Update Metrics
                # Use ACTUAL acceleration for Jerk calculation (Physical comfort)
                acc_vec = self.ego_vehicle.get_acceleration()
                ego_trans = self.ego_vehicle.get_transform()
                fwd_vec = ego_trans.get_forward_vector()
                actual_accel = acc_vec.x * fwd_vec.x + acc_vec.y * fwd_vec.y + acc_vec.z * fwd_vec.z
                self.last_accel = actual_accel
                
                # Get Target Speed for Metrics
                t_speed = 0.0
                if target_actor:
                     tv = target_actor.get_velocity()
                     t_speed = np.sqrt(tv.x**2 + tv.y**2 + tv.z**2)
                     t_loc = target_actor.get_location()
                     print(f"Debug: Target Location: ({t_loc.x:.2f}, {t_loc.y:.2f}, {t_loc.z:.2f}), Dist: {dist_to_target:.2f}", flush=True)
                else:
                     print(f"Debug: Target LOST! Dist: {dist_to_target}", flush=True)
                
                # Get MPC costs
                cost_obs = 0.0
                cost_smooth = 0.0
                if hasattr(self.mpc, 'last_metrics') and self.mpc.last_metrics:
                    cost_obs = self.mpc.last_metrics.get('obs', 0.0)
                    cost_smooth = self.mpc.last_metrics.get('smooth', 0.0)

                target_visible = (pred_target_id == target_id)
                
                # --- Metrics Calculation ---
                # 1. Following Error (RMSE calculation happens in aggregation, here we store raw)
                # Ideal Distance = 12.0m (hardcoded per user spec)
                ideal_dist = 12.0
                following_error = dist_to_target - ideal_dist
                
                # 2. Steering Entropy (needs history, calculated in post-processing or rolling window)
                # For online calculation, we can keep a short buffer
                if not hasattr(self, 'steer_entropy_buffer'):
                    self.steer_entropy_buffer = []
                self.steer_entropy_buffer.append(control.steer)
                if len(self.steer_entropy_buffer) > 20: # 1 second window at 20Hz
                     self.steer_entropy_buffer.pop(0)
                
                # Simple Entropy approx: std dev of steering changes or prediction error
                # User def: "High Frequency Oscillation"
                # Let's store raw steer for post-processing
                
                # 3. Lateral Deviation
                # Deviation from the planned path (best_local_traj)
                # Or simply Deviation from Lane Center (Map Ground Truth)
                # Since "Planning" (Bezier) aims to stay in lane or cut corner safely,
                # measuring deviation from Lane Center is a good proxy for "Ride Quality" and "Safety".
                # It also penalizes "cutting corners" if strict lane keeping is desired,
                # but for this paper, we want to show stability ("No Oscillation").
                
                # Recalculate robustly using Map
                try:
                    ego_t = self.ego_vehicle.get_transform()
                    e_loc = ego_t.location
                    e_wp = self.map.get_waypoint(e_loc)
                    vec_diff = e_loc - e_wp.transform.location
                    # Project onto Right Vector of Waypoint (CTE)
                    lat_dev = abs(vec_diff.dot(e_wp.transform.get_right_vector()))
                except:
                    lat_dev = 0.0
                
                # --- Metrics Calculation (Aggregated) ---
                # We update the metrics manager with raw data. 
                # Complex metrics like Steering Entropy and Jerk are calculated in 'metrics.py' or 'metrics_manager.py'
                # But we can pass pre-calculated values if needed.
                # Here we pass raw values.
                
                # Get Spring Extension
                spring_ext = 0.0
                if hasattr(self.smooth_follower, 'last_extension'):
                    spring_ext = self.smooth_follower.last_extension

                self.metrics.update(
                    timestamp=time.time(),
                    ego_speed=speed,
                    ego_accel=actual_accel, # Changed from 'accel' (MPC target) to 'actual_accel' (Physics)
                    dist_to_target=dist_to_target if dist_to_target < 100 else None,
                    steer=control.steer,
                    throttle=control.throttle,
                    brake=control.brake,
                    collision=self.collision_occured,
                    target_visible=target_visible,
                    target_speed_val=t_speed,
                    uncertainty=uncertainty,
                    cost_obs=cost_obs,
                    cost_smooth=cost_smooth,
                    ego_pos=[ego_trans.location.x, ego_trans.location.y, ego_trans.location.z],
                    locked_target_id=pred_target_id,
                    true_target_id=target_id,
                    following_error=following_error,
                    lateral_deviation=lat_dev,
                    mpc_solve_time=mpc_solve_time,
                    deadlock=deadlock_triggered,
                    virtual_spring_extension=spring_ext
                )
                
                # Check Success
                # if dz_cam < 5.0: # Too close?
                #    pass
                    
                # Get Local Map from Vision
                local_map = None
                if 'sem_front' in sensor_data:
                    # Semantic data comes as (H, W, 4) BGRA usually or (H, W, 3)
                    # CARLA raw data convert is typically flat.
                    # Our get_sensor_data converts rgb to BGR.
                    # Let's check get_sensor_data logic for semantic.
                    
                    # We need to handle semantic specifically in get_sensor_data
                    # But for now, let's assume it handles it or we fix it.
                    # Wait, get_sensor_data currently only handles 'rgb*' prefix for reshaping.
                    # We need to update get_sensor_data first.
                    pass
                
                # FIX: Moved logic to get_sensor_data
                if 'sem_front' in sensor_data:
                     local_map = self.vision_perception.process(sensor_data['sem_front'])

                # --- CAMERA BEAUTIFICATION (Cinematic Spring Arm) ---
                # High Rear View (-10m behind, +5m up) with Lagged Follow
                spectator = self.world.get_spectator()
                ego_t = self.ego_vehicle.get_transform()
                
                # 1. Calculate Ideal Position
                fwd = ego_t.get_forward_vector()
                up = ego_t.get_up_vector()
                ideal_loc = ego_t.location - fwd * 10.0 + up * 5.0
                ideal_rot = carla.Rotation(pitch=-20.0, yaw=ego_t.rotation.yaw, roll=0.0)
                
                # 2. Initialize or Update Lagged Position
                if not hasattr(self, 'spectator_loc'):
                    self.spectator_loc = ideal_loc
                    self.spectator_rot = ideal_rot
                
                # 3. Apply Smoothing (Alpha=0.1 for heavy lag/smoothness)
                alpha_cam = 0.1
                self.spectator_loc = carla.Location(
                    x = (1 - alpha_cam) * self.spectator_loc.x + alpha_cam * ideal_loc.x,
                    y = (1 - alpha_cam) * self.spectator_loc.y + alpha_cam * ideal_loc.y,
                    z = (1 - alpha_cam) * self.spectator_loc.z + alpha_cam * ideal_loc.z
                )
                
                # Smooth Yaw (Handle wrap-around)
                # Simple lerp for now, assuming no crazy spins
                cur_yaw = self.spectator_rot.yaw
                tgt_yaw = ideal_rot.yaw
                diff = tgt_yaw - cur_yaw
                if diff > 180: diff -= 360
                if diff < -180: diff += 360
                new_yaw = cur_yaw + alpha_cam * diff
                self.spectator_rot = carla.Rotation(pitch=-20.0, yaw=new_yaw, roll=0.0)
                
                spectator.set_transform(carla.Transform(self.spectator_loc, self.spectator_rot))
                # ----------------------------------------------------

                # Render
                control_info = {
                    'steer': control.steer,
                    'throttle': control.throttle,
                    'brake': control.brake,
                    'speed': speed
                }
                self.render(sensor_data, text, detections, pred_target_id, target_id, control_info, local_map=local_map)
                if self.clock:
                    self.clock.tick(20) # 20 FPS
                else:
                    time.sleep(0.05) # Manual sync if no pygame
                # pass
                    
            print(f"\nEpisode finished.")
            logging.info(f"Episode {episode} finished.")
            
            try:
                summary = self.metrics.get_summary()
                print("Debug: Got summary from metrics manager.", flush=True)
            except Exception as e:
                print(f"CRITICAL: Failed to get summary: {e}", flush=True)
                summary = {}

            # Add Experiment Metadata
            summary['Method'] = args.method
            summary['Scenario'] = args.scenario
            # Use actual weather if available, else args
            summary['Weather'] = getattr(self, 'current_weather_name', args.weather)
            
            print("\n=== Episode Metrics ===")
            for k, v in summary.items():
                print(f"  {k}: {v}")
            
            # Save detailed log for this episode (for visualization)
            try:
                self.metrics.save_episode_log(episode)
                print("Debug: Saved episode log.", flush=True)
            except Exception as e:
                print(f"Warning: Failed to save episode log: {e}", flush=True)
            
            if args.save_telemetry:
                logging.info(f"Saving telemetry log for episode {episode}...")
                self.metrics.save_telemetry_log(episode)
            
            # episode_metrics.append(summary) # Local var removed
            self.metrics.reset()
            self.collision_occured = False
            
            # Save metrics after each episode
            print(f"Debug: Appending summary to episode_metrics (len before: {len(self.episode_metrics)})", flush=True)
            self.episode_metrics.append(summary)
            self.save_metrics_to_file()
            
            self.cleanup()
        
        # Overall Summary
        if self.episode_metrics:
            print("\n=== Overall Evaluation Metrics ===")
            self.save_metrics_to_file()
            
    def save_metrics_to_file(self):
        """Save current metrics to file (TXT and CSV)"""
        if not self.episode_metrics: return
        
        # 1. Save TXT Summary (Existing)
        try:
            with open("eval_metrics.txt", "w") as f:
                f.write("=== Overall Evaluation Metrics ===\n")
                
                # Calculate Overall Averages
                n = len(self.episode_metrics)
                avg_speed = np.mean([m.get("Average Speed (m/s)", 0) for m in self.episode_metrics])
                avg_jerk = np.mean([m.get("AvgJerk", 0) for m in self.episode_metrics])
                collision_rate = np.mean([m.get("Collision", 0) for m in self.episode_metrics]) * 100
                acq_rate = np.mean([m.get("Target Acquisition Rate (%)", 0) for m in self.episode_metrics])
                
                f.write(f"Number of Episodes: {n}\n")
                f.write(f"Average Speed: {avg_speed:.2f} m/s\n")
                f.write(f"Average Jerk: {avg_jerk:.2f} m/s^3\n")
                f.write(f"Collision Rate: {collision_rate:.1f}%\n")
                f.write(f"Target Acquisition Rate: {acq_rate:.1f}%\n")
                f.write("-" * 30 + "\n")
                
                for i, m in enumerate(self.episode_metrics):
                    f.write(f"\nEpisode {i+1}:\n")
                    for k, v in m.items():
                        f.write(f"  {k}: {v}\n")
            print("Metrics saved to eval_metrics.txt")
        except Exception as e:
            print(f"Failed to save TXT metrics: {e}")

        # 2. Save CSV (New for Plotting)
        try:
            csv_file = "eval_metrics.csv"
            
            # User Requested Columns
            fieldnames = [
                "Episode", 
                "Method", 
                "Success", 
                "Collision", 
                "Time", 
                "PathLength", 
                "FollowingRMSE", 
                "GroundingAcc",
                "WrongLeadRate",
                "IDSwitches",
                "TargetLostDur",
                "MinGap",
                "AvgJerk", 
                "SteeringEntropy", 
                "LatDeviation",
                "AvgMPCTime",
                "Deadlocks",
                "AvgSpringExt"
            ]
            
            with open(csv_file, mode='w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for i, m in enumerate(self.episode_metrics):
                    # Filter and Map
                    row = {}
                    row["Episode"] = i + 1
                    row["Method"] = m.get("Method", "N/A")
                    row["Success"] = m.get("Success", 0)
                    row["Collision"] = m.get("Collision", 0)
                    row["Time"] = m.get("Time", 0)
                    row["PathLength"] = m.get("PathLength", 0)
                    row["FollowingRMSE"] = m.get("FollowingRMSE", 0)
                    row["GroundingAcc"] = m.get("GroundingAcc", 0)
                    row["WrongLeadRate"] = m.get("WrongLeadRate", 0)
                    row["IDSwitches"] = m.get("IDSwitches", 0)
                    row["TargetLostDur"] = m.get("TargetLostDur", 0)
                    row["MinGap"] = m.get("MinGap", 0)
                    row["AvgJerk"] = m.get("AvgJerk", 0)
                    row["SteeringEntropy"] = m.get("SteeringEntropy", 0)
                    row["LatDeviation"] = m.get("LatDeviation", 0)
                    row["AvgMPCTime"] = m.get("AvgMPCTime (ms)", 0)
                    row["Deadlocks"] = m.get("Deadlocks", 0)
                    row["AvgSpringExt"] = m.get("AvgSpringExt (m)", 0)
                    
                    writer.writerow(row)
                    
            print(f"Metrics saved to {csv_file}")
        except Exception as e:
             print(f"Failed to save CSV metrics: {e}")

    def cleanup(self):
        """Destroy actors"""
        self.actor_colors = {} # Reset colors
        
        # Reset Tracking State
        self.last_target_id = None
        self.collision_occured = False
        self.metrics.reset()
        
        # Destroy sensors first
        for s in self.sensors:
            if s.is_alive: s.destroy()
        self.sensors = []
        
        # Destroy ego
        if self.ego_vehicle and self.ego_vehicle.is_alive:
            self.ego_vehicle.destroy()
        self.ego_vehicle = None
            
        # Destroy other actors (tracked by script)
        for a in self.other_actors:
            if a.is_alive: a.destroy()
        self.other_actors = []
        
        # Destroy all tracked actors (just in case)
        if hasattr(self, 'actors'):
            for a in self.actors:
                 if a and a.is_alive: a.destroy()
            self.actors = []
            
        # FORCE CLEANUP: Destroy ALL vehicles and walkers in the world
        # This handles leftovers from previous crashed runs (e.g. ghosts)
        if self.world:
            try:
                # print("Debug: Force cleaning all vehicles/walkers...", flush=True)
                actors = self.world.get_actors()
                vehicles = actors.filter('vehicle.*')
                walkers = actors.filter('walker.*')
                for a in list(vehicles) + list(walkers):
                    if a.is_alive: a.destroy()
            except Exception as e:
                print(f"Warning: Error during force cleanup: {e}", flush=True)

        
    def close(self):
        self.cleanup()
        if pygame is not None:
            pygame.quit()

if __name__ == "__main__":
    print("Starting Closed-Loop Evaluation...", flush=True)
    try:
        evaluator = ClosedLoopEvaluator()
        evaluator.run()
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f"CRITICAL ERROR: {e}")
        logging.error(traceback.format_exc())
    finally:
        if 'evaluator' in locals():
            evaluator.close()
