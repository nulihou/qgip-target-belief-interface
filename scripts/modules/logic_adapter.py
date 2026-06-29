import numpy as np
import time
from collections import deque

class IntentPredictor:
    """
    Trajectory Regression based Predictor (Option 2)
    Fits a smooth curve to the history of positions to eliminate jitter.
    """
    def __init__(self, history_len=10):
        self.history = deque(maxlen=history_len)

    def update(self, pos):
        """
        pos: [x, y] or (x, y) - Global coordinates preferred
        """
        self.history.append(pos)

    def get_smoothed_target(self):
        """
        Returns the smoothed current position (x, y).
        """
        if len(self.history) < 3:
            if len(self.history) > 0:
                return self.history[-1]
            return None
            
        # Fit parametric curve x(t), y(t) against index
        steps = np.arange(len(self.history))
        pts = np.array(self.history)
        
        try:
            deg = 2
            coeff_x = np.polyfit(steps, pts[:, 0], deg)
            coeff_y = np.polyfit(steps, pts[:, 1], deg)
            
            # Evaluate at current time t (last index)
            current_t = steps[-1]
            smooth_x = np.poly1d(coeff_x)(current_t)
            smooth_y = np.poly1d(coeff_y)(current_t)
            
            return (smooth_x, smooth_y)
        except Exception:
            return self.history[-1]

    def predict_intent_path(self, predict_len=20):
        """
        Returns a list of (x, y) points representing the smoothed future path.
        """
        if len(self.history) < 5:
            return []
        
        steps = np.arange(len(self.history))
        pts = np.array(self.history) # [[x, y], ...]
        
        try:
            deg = 2
            coeff_x = np.polyfit(steps, pts[:, 0], deg)
            coeff_y = np.polyfit(steps, pts[:, 1], deg)
            
            poly_x = np.poly1d(coeff_x)
            poly_y = np.poly1d(coeff_y)
            
            # Predict future
            current_t = steps[-1]
            # Extend for predict_len steps (assuming 1 step = 1 frame ~ 0.05s)
            future_steps = np.arange(current_t, current_t + predict_len)
            
            future_x = poly_x(future_steps)
            future_y = poly_y(future_steps)
            
            return list(zip(future_x, future_y))
            
        except Exception:
            return []

class KalmanFilterLite:
    def __init__(self, dt=0.05):
        # State: [x, y, vx, vy]
        self.state = np.zeros(4)
        self.P = np.eye(4) * 1.0 # Initial Covariance
        self.dt = dt
        
        # State Transition Matrix (Constant Velocity Model)
        # x_k = x_{k-1} + vx * dt
        self.F = np.eye(4)
        self.F[0, 2] = dt
        self.F[1, 3] = dt
        
        # Process Noise Covariance (Q)
        # Model uncertainty (e.g., changes in acceleration)
        self.Q = np.eye(4) * 0.1
        
        # Measurement Matrix (H)
        # We observe [x, y]
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        
        # Measurement Noise Covariance (R)
        # Sensor noise
        self.R = np.eye(2) * 0.5 # Assume 0.5m noise
        
        self.initialized = False

    def predict(self):
        if not self.initialized: return
        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q
        
    def update(self, measurement):
        """
        measurement: [x, y]
        """
        if not self.initialized:
            self.state[:2] = measurement
            self.state[2:] = 0 # Assume zero initial velocity
            self.initialized = True
            return self.state[:2]
            
        # Standard KF Update
        z = np.array(measurement)
        y = z - self.H @ self.state # Innovation
        S = self.H @ self.P @ self.H.T + self.R # Innovation Covariance
        K = self.P @ self.H.T @ np.linalg.inv(S) # Kalman Gain
        
        self.state = self.state + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        
        return self.state[:2]
        
    def get_state(self):
        return self.state[:2] # [x, y]


class LogicAdapter:
    def __init__(self, no_memory=False):
        # Spatiotemporal Memory
        # id -> list of {'t': time, 'speed': speed}
        self.history = {} 
        self.max_history = 20 # Keep last 20 frames (~1-2 seconds)
        self.no_memory = no_memory
        
        # --- GHOST ANCHOR MEMORY (Option 2) ---
        self.target_memory = {
            'last_pos': None, # [x, y, z] (local)
            'last_vel': None, # [vx, vy, vz]
            'lost_frames': 0,
            'max_lost_frames': 100 # Extrapolate for 5.0s (Increased from 60 for HardRain)
        }
        
        # --- KALMAN FILTER (Option 3 - Perception Smoothing) ---
        self.kf = KalmanFilterLite(dt=0.05)
        self.last_target_id_seen = None

    def update_target_memory(self, target_node, dt=0.05):
        """
        Updates the memory of the tracked target using Kalman Filter.
        If target_node is None, extrapolates position (Ghost Anchor).
        Returns: (pos, is_ghost)
        """
        # Check if target ID changed, if so, reset KF
        if target_node is not None:
            tid = target_node['id']
            if self.last_target_id_seen != tid:
                self.kf = KalmanFilterLite(dt=dt) # Reset
                self.last_target_id_seen = tid
                
        if target_node is not None:
            # Target is visible
            raw_pos = np.array(target_node['center_3d'])
            # We only track X (Right) and Z (Forward) in Camera Frame for smoothing
            # center_3d is usually [x, y, z] -> check eval_closed_loop usage
            # Actually VisionPerception outputs [y, -z, x] relative to Ego? 
            # Let's assume raw_pos is [x, y, z] in some consistent local frame.
            # We filter x and z (horizontal plane).
            
            # KF Predict Step
            self.kf.predict()
            
            # KF Update Step
            # measurement: [x, z] (assuming y is height or similar, usually less critical for steering)
            # Actually let's just filter index 0 and 2.
            meas = [raw_pos[0], raw_pos[2]]
            smoothed_xz = self.kf.update(meas)
            
            # Reconstruct pos
            pos = raw_pos.copy()
            pos[0] = smoothed_xz[0]
            pos[2] = smoothed_xz[1]
            
            self.target_memory['last_pos'] = pos
            
            # Store estimated velocity from KF
            # state is [x, z, vx, vz]
            vx = self.kf.state[2]
            vz = self.kf.state[3]
            self.target_memory['last_vel'] = np.array([vx, 0, vz])
            
            self.target_memory['lost_frames'] = 0
            
            return pos, False
            
        else:
            # Target Lost
            if self.target_memory['last_pos'] is not None and \
               self.target_memory['lost_frames'] < self.target_memory['max_lost_frames']:
               
                self.target_memory['lost_frames'] += 1
                
                # FIX 3: Extended Ghost Memory Strategy
                # If lost for a short time (< 1.0s / 20 frames), continue predicting (Blind Mode)
                if self.target_memory['lost_frames'] < 20:
                    # Extrapolate using KF Prediction
                    self.kf.predict()
                    pred_xz = self.kf.get_state()
                    
                    ghost_pos = self.target_memory['last_pos'].copy()
                    ghost_pos[0] = pred_xz[0]
                    ghost_pos[2] = pred_xz[1]
                    
                    # Also update stored pos for next step continuity
                    self.target_memory['last_pos'] = ghost_pos
                    
                    return ghost_pos, True
                else:
                    # Lost for too long (> 1.0s). Don't blind accelerate.
                    # Return a "Stop Point" (virtual target close to ego to force braking)
                    # or allow drift but do not update position (let it lag behind).
                    
                    # Strategy: Return a static point 10m ahead.
                    # If vehicle moves, this point will become closer, eventually forcing a stop.
                    # We do NOT update last_pos, so the ghost stays put in world frame?
                    # No, last_pos is in Local Frame usually? 
                    # Wait, update_target_memory inputs/outputs seem to be used in Local Frame context in eval_closed_loop?
                    # Let's assume Local Frame.
                    
                    # If Local Frame, returning a fixed [0, 0, 10] means "Target is always 10m ahead".
                    # That would make the car maintain speed!
                    # We want the target to "Stop" in World Frame, i.e., move closer in Local Frame as we move.
                    
                    # Better Strategy: Return None to signal "No Target".
                    # But user said "Slowly decelerate/stop instead of emergency brake".
                    # If we return None, the system might emergency brake or search.
                    
                    # User instruction: "return stop_point"
                    # "Return a virtual point just in front of car, speed set to 0"
                    
                    # I will return a point very close to the car to force it to stop/slow down.
                    # ghost_pos = [0, 0, 5.0] (5m ahead).
                    # If desired following distance is 15m, this is "Too Close" -> Brake.
                    
                    ghost_pos = np.array([0.0, 0.0, 5.0]) 
                    return ghost_pos, True

            return None, False

    def build_graph(self, detections, img_width, img_height, local_map=None):
        """
        Builds a spatiotemporal scene graph from detections.
        Now includes 'action' state based on history.
        
        Args:
            detections: list of dicts with keys 'bbox', 'color', 'label', 'depth', 'center_3d', 'speed'
            img_width: image width
            img_height: image height
            local_map: optional dict with 'lane_lines' from VisionPerception
            
        Returns:
            nodes: list of node attributes
            edges: list of (source_idx, target_idx, relation_type)
        """
        nodes = []
        current_time = time.time()
        
        # Helper to get lane relative to ego (approximate)
        def get_lane_index(x_local, y_local, local_map):
            lanes = local_map.get('lane_lines', [])
            is_junction = local_map.get('junction', False)

            # Fallback if no map or junction
            if not lanes or is_junction:
                if y_local < -1.5: return -1 # Left
                if y_local > 1.5: return 1   # Right
                return 0 # Ego
            
            # Calculate Y position of each lane line at x_local
            lane_y_at_x = []
            for l in lanes:
                pts = np.array(l['points'])
                if len(pts) < 2: continue
                
                # Check valid range (avoid wild extrapolation)
                min_x, max_x = pts[0, 0], pts[-1, 0]
                if x_local < min_x - 5.0 or x_local > max_x + 5.0:
                    continue

                # Use linear interpolation for robustness
                # (Polyfit can oscillate at ends)
                y_at_x = np.interp(x_local, pts[:, 0], pts[:, 1])
                lane_y_at_x.append(y_at_x)
            
            lane_y_at_x.sort()
            
            # Count lines to left and right of the object
            lines_to_left = sum(1 for ly in lane_y_at_x if ly < y_local)
            
            # We also need to know where Ego is (y=0) relative to these lines
            # to determine the relative lane index.
            ego_lines_to_left = sum(1 for ly in lane_y_at_x if ly < 0)
            
            # Result:
            # If object has 2 lines to left, and Ego has 1 line to left
            # Object is in Lane +1 (Right)
            return lines_to_left - ego_lines_to_left

        for det in detections:
            cx = (det['bbox'][0] + det['bbox'][2]) / 2.0
            cy = (det['bbox'][1] + det['bbox'][3]) / 2.0
            
            c3d = det.get('center_3d', [0, 0, 0])
            ego_x = c3d[2] # Forward
            ego_y = c3d[0] # Right
            
            lane_idx = 0
            if local_map:
                lane_idx = get_lane_index(ego_x, ego_y, local_map)
            
            # --- Spatiotemporal State Update ---
            did = det.get('id', -1)
            speed = det.get('speed', 0.0)
            
            if did != -1 and not self.no_memory:
                if did not in self.history:
                    self.history[did] = []
                self.history[did].append({'t': current_time, 'speed': speed})
                
                # Trim history
                if len(self.history[did]) > self.max_history:
                    self.history[did].pop(0)
            
            # Compute Action State (FSM)
            action = 'unknown'
            if self.no_memory:
                action = 'static' # Force static state for ablation
            elif did != -1 and len(self.history.get(did, [])) > 0:
                hist = self.history[did]
                avg_speed = np.mean([h['speed'] for h in hist])
                
                if avg_speed < 0.1:
                    action = 'stopped'
                else:
                    # Check acceleration
                    if len(hist) >= 5:
                        s_start = hist[0]['speed']
                        s_end = hist[-1]['speed']
                        dt = hist[-1]['t'] - hist[0]['t']
                        if dt > 0.1:
                            accel = (s_end - s_start) / dt
                            if accel > 1.0:
                                action = 'accelerating'
                            elif accel < -1.0:
                                action = 'decelerating'
                            else:
                                action = 'moving'
                    else:
                        action = 'moving'
            
            nodes.append({
                'id': did,
                'color': det.get('color', 'unknown'),
                'label': det.get('label', 'object'),
                'center': (cx, cy),
                'depth': det.get('depth', 0.0),
                'center_3d': c3d,
                'bbox': det['bbox'],
                'lane_idx': lane_idx,
                'action': action, # New Attribute
                'speed': speed
            })
            
        edges = []
        num_nodes = len(nodes)
        
        for i in range(num_nodes):
            for j in range(num_nodes):
                if i == j: continue
                
                n1 = nodes[i]
                n2 = nodes[j]
                
                # Check spatial relations
                # "n2 is [REL] of n1"
                # Use 3D centers if available, else 2D
                
                p1 = n1['center_3d']
                p2 = n2['center_3d']
                
                # Relative vector from n1 to n2 in Camera Frame
                dx = p2[0] - p1[0] # Right
                dy = p2[1] - p1[1] # Down
                dz = p2[2] - p1[2] # Forward
                
                # Thresholds
                horizontal_thresh = 1.0 # meters
                depth_thresh = 2.0 # meters
                
                # Left/Right
                # ENHANCEMENT: Use Lane Index if available for more robust Left/Right
                is_left = False
                is_right = False
                
                if local_map:
                    # If lane indices differ, relation is strong
                    l1 = n1['lane_idx']
                    l2 = n2['lane_idx']
                    if l2 < l1: is_left = True
                    elif l2 > l1: is_right = True
                    else:
                        # Same lane, fall back to geometric offset
                        if abs(dx) > horizontal_thresh:
                            if dx < 0: is_left = True
                            else: is_right = True
                else:
                    # Original Logic
                    if abs(dx) > horizontal_thresh:
                        if dx > 0: is_right = True
                        else: is_left = True
                        
                if is_right:
                    edges.append((i, j, 'right'))
                elif is_left:
                    edges.append((i, j, 'left'))
                        
                # Front/Behind (based on depth)
                if abs(dz) > depth_thresh:
                    if dz > 0:
                        edges.append((i, j, 'behind')) # n2 is behind n1 (further away)
                    else:
                        edges.append((i, j, 'front'))  # n2 is in front of n1 (closer)
                        
        return nodes, edges

    def match_instruction(self, nodes, edges, instruction):
        """
        Heuristic matching for instruction: "Follow the [COLOR] [TYPE] [RELATION]"
        e.g. "Follow the dark green vehicle on your front-left"
        
        Returns:
            best_idx: index of best matching node
            debug_info: dict with scores
        """
        words = instruction.lower().replace('.', '').replace(',', '').split()
        
        # 1. Extract Target Attributes
        target_color = None
        target_type = None
        spatial_rel = []
        
        # Colors
        colors = ['red', 'green', 'blue', 'white', 'black', 'grey', 'silver', 'yellow', 'orange', 'brown', 'purple', 'dark blue', 'dark green']
        # Sort by length desc to match "dark green" before "green"
        colors.sort(key=len, reverse=True)
        
        for c in colors:
            if c in instruction.lower(): # Check full string for multi-word colors
                target_color = c
                break
                
        # Types
        types = ['police car', 'ambulance', 'firetruck', 'van', 'truck', 'motorcycle', 'cyclist', 'jeep', 'car', 'vehicle']
        for t in types:
            if t in instruction.lower():
                target_type = t
                break
                
        # Spatial Relations keywords
        if 'left' in words: spatial_rel.append('left')
        if 'right' in words: spatial_rel.append('right')
        if 'front' in words or 'ahead' in words: spatial_rel.append('front')
        # "behind" in instruction usually refers to relation to ego, but sometimes to other objects.
        # "Follow the car behind the truck"
        
        # For now, handle "on your [REL]" which means relative to EGO.
        # "Follow the X on your left" -> X is left of Ego.
        
        best_idx = -1
        best_score = -1.0
        
        for i, node in enumerate(nodes):
            score = 0.0
            
            # Color match
            if target_color:
                if node['color'] == target_color:
                    score += 2.0
                elif target_color in node['color'] or node['color'] in target_color:
                    score += 1.0
                    
            # Type match
            if target_type:
                # "vehicle" matches "car", "truck", etc.
                if target_type == 'vehicle':
                    if node['label'] in ['car', 'truck', 'van', 'jeep', 'police car', 'ambulance', 'firetruck']:
                        score += 1.0
                elif target_type in node['label']:
                    score += 2.0
                    
            # Spatial match (Relative to Ego)
            # Ego is effectively at (0,0,0) in Camera Frame (ignoring small offset)
            # Node center_3d: [x, y, z]
            # x > 0: Right, x < 0: Left
            # z > 0: Front
            
            p = node['center_3d']
            
            if 'left' in spatial_rel:
                if p[0] < -1.0: # Left
                    score += 1.0
                else:
                    score -= 0.5
            
            if 'right' in spatial_rel:
                if p[0] > 1.0: # Right
                    score += 1.0
                else:
                    score -= 0.5
                    
            if 'front' in spatial_rel:
                if p[2] > 0: # Front
                    score += 0.5 # Trivial for front camera
                    
            # Distance penalty (prefer closer if ambiguous?)
            # score -= node['depth'] * 0.01
            
            if score > best_score:
                best_score = score
                best_idx = i
                
        if best_score < 0.5: # Threshold
            return -1
            
        return best_idx
