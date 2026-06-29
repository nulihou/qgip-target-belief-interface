import numpy as np
import json
import math
import os

class PerceptionOracle:
    def __init__(self, seq_dir):
        self.seq_dir = seq_dir
        meta_path = os.path.join(seq_dir, "meta.json")
        trace_path = os.path.join(seq_dir, "trace.npz")
        
        with open(meta_path, 'r') as f:
            self.meta = json.load(f)
        self.trace = np.load(trace_path)
        
        # Camera Intrinsics (RGB Front)
        self.sensor_cfg = self.meta['cam_intrinsics']['rgb_front']
        self.width = self.sensor_cfg['res'][0]
        self.height = self.sensor_cfg['res'][1]
        self.fov = self.sensor_cfg['fov']
        
        # K matrix
        # f = w / (2 * tan(fov/2))
        self.focal = self.width / (2.0 * math.tan(math.radians(self.fov) / 2.0))
        self.cx = self.width / 2.0
        self.cy = self.height / 2.0
        
        # Camera Extrinsics (Relative to Ego)
        # CARLA: x=fwd, y=right, z=up
        self.cam_rel_pos = np.array(self.sensor_cfg['pos'])
        
        # Actor Details
        self.actor_details = self.meta['actor_details'] # id -> details

    def _get_color_name(self, rgb_str):
        # simple euclidean distance to known colors
        try:
            r, g, b = map(int, rgb_str.split(','))
        except:
            return "black" # Default
            
        colors = {
            'red': (200, 0, 0),
            'green': (0, 200, 0),
            'blue': (0, 0, 200),
            'white': (240, 240, 240),
            'black': (10, 10, 10),
            'grey': (128, 128, 128),
            'silver': (192, 192, 192),
            'yellow': (255, 255, 0),
            'orange': (255, 165, 0),
            'brown': (165, 42, 42),
            'purple': (128, 0, 128),
            'dark blue': (21, 38, 98),
            'dark green': (16, 44, 21)
        }
        best_color = 'unknown'
        min_dist = float('inf')
        for name, c in colors.items():
            dist = (r-c[0])**2 + (g-c[1])**2 + (b-c[2])**2
            if dist < min_dist:
                min_dist = dist
                best_color = name
        return best_color

    def _get_label(self, type_id):
        if 'police' in type_id: return 'police car'
        if 'ambulance' in type_id: return 'ambulance'
        if 'firetruck' in type_id: return 'firetruck'
        if 'van' in type_id: return 'van'
        if 'truck' in type_id: return 'truck'
        if 'motorcycle' in type_id or 'harley' in type_id: return 'motorcycle'
        if 'cyclist' in type_id: return 'cyclist'
        if 'jeep' in type_id: return 'jeep'
        if 'vehicle' in type_id: return 'car'
        return 'unknown'

    def _world_to_camera_norm(self, point_world, ego_pos, ego_yaw):
        """
        Transforms world point to camera coordinate system (CV convention).
        Returns (x_cv, y_cv, z_cv)
        """
        # 1. World to Ego
        dx = point_world[0] - ego_pos[0]
        dy = point_world[1] - ego_pos[1]
        dz = point_world[2] - ego_pos[2]
        
        # Rotate by -yaw to align with Ego Forward (X)
        yaw_rad = math.radians(ego_yaw)
        cos_y = math.cos(-yaw_rad)
        sin_y = math.sin(-yaw_rad)
        
        x_ego = dx * cos_y - dy * sin_y
        y_ego = dx * sin_y + dy * cos_y
        z_ego = dz
        
        # 2. Ego to Sensor (CARLA Coords)
        x_sensor = x_ego - self.cam_rel_pos[0]
        y_sensor = y_ego - self.cam_rel_pos[1]
        z_sensor = z_ego - self.cam_rel_pos[2]
        
        # 3. Sensor to CV Camera Coords
        # CV_X (Right) = Sensor_Y
        # CV_Y (Down) = -Sensor_Z
        # CV_Z (Forward) = Sensor_X
        
        x_cv = y_sensor
        y_cv = -z_sensor
        z_cv = x_sensor
        
        return np.array([x_cv, y_cv, z_cv])

    def get_detections(self, frame_idx):
        """
        Returns list of dict:
        {
            'id': actor_id,
            'bbox': [x1, y1, x2, y2],
            'label': 'car',
            'color': 'black',
            'depth': dist,
            'center_3d': [x, y, z] (in CV camera frame)
        }
        """
        if frame_idx >= len(self.trace['frame_ids']):
            return []
            
        ego_state = self.trace['ego_state'][frame_idx] # [x, y, z, yaw, vel]
        ego_pos = ego_state[:3]
        ego_yaw = ego_state[3]
        
        nearby_ids = self.trace['nearby_id'][frame_idx]
        nearby_states = self.trace['nearby_state'][frame_idx] # [N, 5]
        
        detections = []
        
        for i, aid in enumerate(nearby_ids):
            if aid == 0: continue # Invalid
            
            # Get details
            details = self.actor_details.get(str(aid))
            if not details: continue
            
            pos = nearby_states[i][:3]
            
            # Project center
            p_cam = self._world_to_camera_norm(pos, ego_pos, ego_yaw)
            
            if p_cam[2] <= 0:
                # print(f"DEBUG: ID {aid} rejected: Behind cam (z={p_cam[2]:.2f})")
                continue # Behind camera
            
            # Project to image
            u = (p_cam[0] * self.focal / p_cam[2]) + self.cx
            v = (p_cam[1] * self.focal / p_cam[2]) + self.cy
            
            if 0 <= u < self.width and 0 <= v < self.height:
                # Approximate bbox based on distance
                # Assume car width ~2m, height ~1.5m
                # w_px = (2 * f) / z
                w_px = (2.0 * self.focal) / p_cam[2]
                h_px = (1.5 * self.focal) / p_cam[2]
                
                x1 = max(0, u - w_px/2)
                y1 = max(0, v - h_px/2)
                x2 = min(self.width, u + w_px/2)
                y2 = min(self.height, v + h_px/2)
                
                detections.append({
                    'id': int(aid),
                    'bbox': [x1, y1, x2, y2],
                    'label': self._get_label(details['type_id']),
                    'color': self._get_color_name(details['color']),
                    'depth': float(p_cam[2]),
                    'center_3d': p_cam.tolist()
                })
            # else:
            #     print(f"DEBUG: ID {aid} rejected: Out of bounds (u={u:.1f}, v={v:.1f})")
                
        return detections
