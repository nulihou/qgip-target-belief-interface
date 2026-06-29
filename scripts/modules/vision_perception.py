import numpy as np
try:
    import cv2
except ImportError:
    cv2 = None
import carla

class VisionPerception:
    def __init__(self, camera_config):
        self.cfg = camera_config
        self.width = self.cfg['res'][0]
        self.height = self.cfg['res'][1]
        self.fov = self.cfg['fov']
        self.cam_height = self.cfg['pos'][2] # 1.7m
        self.cam_x = self.cfg['pos'][0] # 0.8m forward from center
        self.pitch_deg = self.cfg['rot'][0] # Usually 0
        
        # IPM Parameters
        if cv2 is not None:
            self.ipm_matrix = self._compute_ipm_matrix()
        else:
            self.ipm_matrix = None
            print("Warning: VisionPerception disabled (cv2 not found)")
        
        # BEV Output Config
        self.bev_res = 0.1 # meters per pixel
        self.bev_w = 400 # 40m width
        self.bev_h = 400 # 40m forward
        # Ego is at (bev_w/2, bev_h) -> (200, 400) looking up
        
    def _compute_ipm_matrix(self):
        if cv2 is None: return None
        # 1. Camera Intrinsics
        f = (self.width / 2.0) / np.tan(np.deg2rad(self.fov / 2.0))
        cx = self.width / 2.0
        cy = self.height / 2.0
        K = np.array([[f, 0, cx],
                      [0, f, cy],
                      [0, 0, 1]])
        
        # 2. Camera Extrinsics (Camera to Ground)
        # We assume flat ground.
        # Camera is at (0, h, 0) relative to ground projection? 
        # No, in standard camera frame: Y is down, Z is forward, X is right.
        # Ground plane is at Y = height.
        
        # Let's define source points in Image and destination points on Ground (BEV)
        
        # Source Points (Trapezoid on Image)
        # Choose a region of interest on the road ahead
        src_h = self.height
        src_w = self.width
        
        # Horizon line is at cy (if pitch=0)
        horizon = cy
        
        # We take a trapezoid starting below horizon
        top_y = horizon + 20 # Just below horizon
        bot_y = src_h - 10
        
        # We need to map these to real world coordinates to find homography
        # Or we can compute projection matrix directly.
        
        # Let's use the homography method with known geometry.
        # We project 4 points from Image -> World (Z=0, Flat Earth)
        
        # Pitch rotation matrix (Camera X-axis rotation)
        theta = np.deg2rad(self.pitch_deg) 
        # Note: In CARLA/Unreal, Pitch is Y-rotation? No, let's stick to standard CV.
        # Camera Frame: Z forward, X right, Y down.
        # Pitch down means rotating around X.
        
        # However, manual homography is often brittle.
        # Let's use cv2.getPerspectiveTransform by mapping 4 points.
        
        # Defined Physical Region on Ground (Ego Frame, X forward, Y right)
        # We want to see:
        # Near: 3m ahead (blind spot)
        # Far: 30m ahead
        # Left: -10m
        # Right: 10m
        
        src_pts = []
        dst_pts = []
        
        # We project physical points to image to get src_pts
        # Ground Points (Forward, Right, Down=0) relative to Camera
        # Cam Pos in Ego: (0.8, 0, 1.7). 
        # Point P_ego(x, y, 0) -> P_cam(x-0.8, y, -1.7) (if axes aligned)
        # But Camera axes are: Z_c = X_e, X_c = Y_e, Y_c = -Z_e (Standard conversion)
        
        ground_pts_ego = [
            (5.0, -4.0),  # Near Left
            (5.0, 4.0),   # Near Right
            (30.0, 4.0),  # Far Right
            (30.0, -4.0)  # Far Left
        ]
        
        for x_e, y_e in ground_pts_ego:
            # Ego to Camera Standard (Z=Fwd, X=Right, Y=Down)
            # Cam is at x=0.8, z=1.7 relative to ego center.
            # Point relative to cam:
            pc_z = x_e - self.cam_x
            pc_x = y_e 
            pc_y = self.cam_height # Ground is 'down' by height
            
            # Project
            u = f * pc_x / pc_z + cx
            v = f * pc_y / pc_z + cy
            
            src_pts.append([u, v])
            
            # Destination on BEV Image (Top-Down)
            # Image: (0,0) is Top-Left. 
            # We want Ego at Bottom-Center.
            # Scale: 10 px/meter (bev_res = 0.1)
            # x_e is Up (negative v), y_e is Right (positive u)
            
            # Center of BEV image is (200, 400) which corresponds to Ego(0,0)
            # But wait, we want a fixed map size.
            # Let's say Image is 400x400 representing 40m x 40m area.
            # Ego is at (200, 350) (allowing 5m behind)
            
            scale = 10.0 # pixels per meter
            bev_cx = 200
            bev_cy = 350
            
            du = bev_cx + y_e * scale
            dv = bev_cy - x_e * scale
            
            dst_pts.append([du, dv])
            
        src_pts = np.float32(src_pts)
        dst_pts = np.float32(dst_pts)
        
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        return M

    def process(self, sem_image):
        """
        Input: Semantic Segmentation Image (H, W, 3) or (H, W) - CARLA format
        Output: Local Map dict
        """
        if cv2 is None or self.ipm_matrix is None:
            return {'lane_lines': [], 'junction': False, 'bev_raw': None}

        # CARLA Semantic Segmentation is encoded in Red channel
        if len(sem_image.shape) == 3:
            sem = sem_image[:, :, 2] # CARLA stores tag in Red (index 2 in BGR? No, usually index 2 is Red in RGB, but index 2 is Red in BGR too)
            # Wait, CARLA Python API 'raw_data' to array:
            # bgra = np.reshape(..., 4)
            # b, g, r, a. So Red is index 2.
            pass
        else:
            sem = sem_image
            
        # Extract Lane Markings
        # Tag 6: RoadLine
        # Tag 8: SideWalk (Curb) -> Optional, helps define road edge
        mask_lanes = (sem == 6).astype(np.uint8) * 255
        
        # Warp to BEV
        bev_lanes = cv2.warpPerspective(mask_lanes, self.ipm_matrix, (400, 400))
        
        # Extract Lines (Hough or Contours)
        # For simplicity and robustness, we find contours and sample points
        contours, _ = cv2.findContours(bev_lanes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        lane_lines = []
        
        for cnt in contours:
            if cv2.contourArea(cnt) < 2: continue # Noise (Lowered to 2 for thin poles)
            
            # Fit line or just take points
            # Simplify contour
            epsilon = 0.01 * cv2.arcLength(cnt, False) # Open arc?
            # Lanes are thin, contours might be loops.
            # Let's thin it to skeleton or just take centroids?
            
            # Better: Fit a line/curve through the contour points
            points = cnt.reshape(-1, 2)
            
            # Filter points to Ego Frame
            # BEV Image (u, v) -> Ego (x, y)
            # u = 200 + y*10 -> y = (u - 200)/10
            # v = 350 - x*10 -> x = (350 - v)/10
            
            ego_points = []
            for pt in points:
                u, v = pt
                y = (u - 200.0) / 10.0
                x = (350.0 - v) / 10.0
                ego_points.append((x, y))
                
            # Sort by x (distance)
            ego_points.sort(key=lambda p: p[0])
            
            # Downsample
            if len(ego_points) > 2:
                lane_lines.append({'points': ego_points, 'type': 'vision', 'side': 'unknown'})
                
        # Extract Obstacles (Static & Dynamic)
        # Safe: Road (7), RoadLine (6)
        # Obstacles: Building(1), Fence(2), Other(3), Ped(4), Pole(5), Sidewalk(8), Veg(9), Veh(10), Wall(11), Sign(12)
        obs_tags = [1, 2, 3, 4, 5, 8, 9, 10, 11, 12]
        mask_obs = np.isin(sem, obs_tags).astype(np.uint8) * 255
        
        # Warp to BEV
        bev_obs = cv2.warpPerspective(mask_obs, self.ipm_matrix, (400, 400))
        
        # Find blobs
        cnts, _ = cv2.findContours(bev_obs, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        vision_obstacles = []
        for c in cnts:
            area = cv2.contourArea(c)
            if area < 2: continue # Lowered threshold to 2 (0.02m^2) to detect thin poles/vegetation
            
            # Get center and radius
            (cx, cy), radius = cv2.minEnclosingCircle(c)
            
            # Convert to Ego Frame
            # Ego x (forward) = (350 - cy) / 10.0
            # Ego y (right)   = (cx - 200.0) / 10.0
            ex = (350.0 - cy) / 10.0
            ey = (cx - 200.0) / 10.0
            r_meter = radius / 10.0
            
            # Filter distant or invalid
            if ex < 0 or ex > 40.0: continue
            
            vision_obstacles.append({'pos': [ex, ey, 0], 'radius': r_meter, 'type': 'obstacle'})

        return {
            'lane_lines': lane_lines,
            'obstacles': vision_obstacles,
            'junction': False, # Vision-based junction detection is harder, skip for now
            'bev_raw': bev_lanes # For debug viz
        }
