import numpy as np
from scipy.optimize import minimize
import time

class MPCController:
    def __init__(self, dt=0.1, horizon=15, weights=None):
        self.dt = dt
        self.H = horizon # Horizon length
        
        # Vehicle Constraints (Tesla Model 3 approx)
        self.max_steer = np.deg2rad(40) # rad
        self.max_accel = 3.0 # m/s^2
        self.max_brake = 5.0 # m/s^2
        self.wheelbase = 2.8 # meters
        
        # Weights
        self.w_pos = 1.0  # Baseline (Longitudinal)
        self.w_lat = 0.5  # Lateral Error (Cross-track)
        self.w_vel = 40.0 # Prioritize speed tracking
        self.w_yaw = 2.5  # CRITICAL: Align with Bezier tangent
        self.w_steer = 0.1 # Relaxed steering
        self.w_accel = 1.0
        self.w_smooth_accel = 50.0 
        self.w_smooth_steer = 10.0 # w_steer_rate: Suppress high freq jitter
        
        if weights:
            self.w_pos = weights.get('w_pos', weights.get('pos', self.w_pos))
            self.w_lat = weights.get('w_lat', weights.get('lat', weights.get('w_pos', weights.get('pos', self.w_lat))))
            self.w_vel = weights.get('w_vel', weights.get('vel', self.w_vel))
            self.w_yaw = weights.get('w_yaw', weights.get('yaw', self.w_yaw))
            self.w_steer = weights.get('w_steer', weights.get('steer', self.w_steer))
            self.w_accel = weights.get('w_accel', weights.get('accel', self.w_accel))
            self.w_smooth_accel = weights.get('w_smooth_accel', weights.get('smooth_accel', self.w_smooth_accel))
            self.w_smooth_steer = weights.get('w_smooth_steer', weights.get('smooth_steer', weights.get('w_steer_rate', self.w_smooth_steer)))
        
        # Last solution for warm start
        self.last_u = np.zeros(2 * self.H)
        self.last_metrics = {}
        
        # Beautification State (Cinematic Control)
        self.last_steer = 0.0
        self.last_throttle = 0.0
        
        # Stuck Counter for Start-up Boost
        self.stuck_counter = 0
        
    def kinematic_bicycle_model(self, state, control):
        """
        State: [x, y, yaw, v]
        Control: [accel, steer]
        """
        x, y, yaw, v = state
        a, delta = control
        
        # Updates
        # x_next = x + v * cos(yaw) * dt
        # y_next = y + v * sin(yaw) * dt
        # yaw_next = yaw + v / L * tan(delta) * dt
        # v_next = v + a * dt
        
        beta = np.arctan(0.5 * np.tan(delta)) # Slip angle approx
        
        dx = v * np.cos(yaw + beta)
        dy = v * np.sin(yaw + beta)
        dyaw = v / self.wheelbase * np.sin(beta)
        dv = a
        
        new_state = np.array([
            x + dx * self.dt,
            y + dy * self.dt,
            yaw + dyaw * self.dt,
            v + dv * self.dt
        ])
        return new_state

    def predict_trajectory(self, x0, u_seq):
        """
        Predict trajectory given initial state and control sequence.
        u_seq: [a0, d0, a1, d1, ...]
        """
        traj = [x0]
        curr_x = x0
        
        u_seq = u_seq.reshape((self.H, 2))
        
        for i in range(self.H):
            u = u_seq[i]
            curr_x = self.kinematic_bicycle_model(curr_x, u)
            traj.append(curr_x)
            
        return np.array(traj)

    def get_bezier_trajectory(self, ego_state, target_pos, target_heading, target_speed):
        """
        Generate a cubic Bezier curve trajectory.
        ego_state: [x, y, yaw, v]
        target_pos: [x, y]
        target_heading: float (yaw in rad)
        target_speed: float
        """
        p0 = ego_state[:2]
        p3 = target_pos
        
        # Control point distance factor (1/3 of distance is standard for smooth curves)
        dist = np.linalg.norm(p3 - p0)
        # Avoid zero distance
        if dist < 0.1:
            dist = 0.1
            
        ctrl_len = dist * 0.35
        
        # P1: Ego tangent extension
        p1 = p0 + ctrl_len * np.array([np.cos(ego_state[2]), np.sin(ego_state[2])])
        
        # P2: Target tangent extension (backward from target)
        p2 = p3 - ctrl_len * np.array([np.cos(target_heading), np.sin(target_heading)])
        
        refs = []
        for i in range(self.H):
            t = (i + 1) / self.H
            # Cubic Bezier Formula
            # B(t) = (1-t)^3*P0 + 3*(1-t)^2*t*P1 + 3*(1-t)*t^2*P2 + t^3*P3
            point = (1-t)**3 * p0 + \
                    3 * (1-t)**2 * t * p1 + \
                    3 * (1-t) * t**2 * p2 + \
                    t**3 * p3
            
            # Calculate Tangent (Derivative) for Ref Yaw
            # B'(t) = 3(1-t)^2(P1-P0) + 6(1-t)t(P2-P1) + 3t^2(P3-P2)
            d1 = 3 * (1-t)**2 * (p1 - p0)
            d2 = 6 * (1-t) * t * (p2 - p1)
            d3 = 3 * t**2 * (p3 - p2)
            tangent = d1 + d2 + d3
            
            ref_yaw = np.arctan2(tangent[1], tangent[0])
            
            # [x, y, v, yaw] (User requested format: [x, y, speed, yaw])
            # But we need to be careful about what _compute_costs expects.
            # Usually we pass [x, y] or [x, y, v, yaw] if supported.
            # Let's standardize on [x, y, v, yaw]
            refs.append([point[0], point[1], target_speed, ref_yaw])
            
        return np.array(refs)
        
    def _compute_costs(self, u_flat, x0, target_pos, target_speed, obstacles=[], ref_traj=None, weights=None, uncertainty=0.0):
        """
        Helper to compute cost and its components.
        Returns: (total_cost, components_dict)
        """
        u_seq = u_flat.reshape((self.H, 2))
        traj = self.predict_trajectory(x0, u_flat) # [H+1, 4]
        
        # Default Weights
        w_pos = self.w_pos
        w_lat = self.w_lat
        w_vel = self.w_vel
        w_yaw = self.w_yaw
        w_accel = self.w_accel
        w_steer = self.w_steer
        w_smooth_accel = self.w_smooth_accel
        w_smooth_steer = self.w_smooth_steer
        w_obs_scale = 1.0
        
        if weights:
            w_pos = weights.get('w_pos', w_pos)
            w_lat = weights.get('w_lat', weights.get('w_pos', w_lat))
            w_vel = weights.get('w_vel', w_vel)
            w_yaw = weights.get('w_yaw', w_yaw)
            w_accel = weights.get('w_accel', w_accel)
            w_steer = weights.get('w_steer', w_steer)
            w_smooth_accel = weights.get('w_smooth_accel', w_smooth_accel)
            w_smooth_steer = weights.get('w_smooth_steer', w_smooth_steer)
            w_obs_scale = weights.get('w_obs_scale', 1.0)
        
        cost_pos = 0.0
        cost_vel = 0.0
        cost_yaw = 0.0
        cost_control = 0.0
        cost_smooth = 0.0
        cost_obs = 0.0
        
        # 1. Position Error (Tracking)
        if ref_traj is not None:
            # Handle variable length ref_traj
            ref_len = len(ref_traj)
            if ref_len < self.H:
                # Pad with last point
                if ref_len > 0:
                    last_pt = ref_traj[-1]
                    padding = np.tile(last_pt, (self.H - ref_len, 1))
                    ref_traj = np.vstack((ref_traj, padding))
                else:
                    # Empty ref_traj? Fallback to point attractor
                    ref_traj = None
            elif ref_len > self.H:
                 ref_traj = ref_traj[:self.H]
        
        if ref_traj is not None:
            # Track the reference trajectory
            # traj has H+1 points (0 to H). ref_traj has H points (1 to H).
            # We compare traj[1:] with ref_traj
            
            # Position Error [x, y]
            diff = traj[1:, :2] - ref_traj[:, :2]
            
            # Split into Longitudinal (X) and Lateral (Y)
            diff_x = diff[:, 0]
            diff_y = diff[:, 1]
            
            cost_pos = w_pos * np.sum(diff_x**2) + w_lat * np.sum(diff_y**2)
            
            # Yaw Error (If ref_traj has 4 columns: x, y, v, yaw)
            if ref_traj.shape[1] >= 4:
                yaw_diff = traj[1:, 2] - ref_traj[:, 3]
                # Normalize angle to [-pi, pi]
                yaw_diff = (yaw_diff + np.pi) % (2 * np.pi) - np.pi
                cost_yaw = w_yaw * np.sum(yaw_diff**2)
                
        else:
            # Fallback: Point Attractor (Original)
            dists = np.sqrt(np.sum((traj[1:, :2] - target_pos)**2, axis=1))
            cost_pos = w_pos * np.sum(dists)
        
        # 2. Velocity Error
        vels = traj[1:, 3]
        cost_vel = w_vel * np.sum((vels - target_speed)**2)
        
        # 3. Control Effort
        accels = u_seq[:, 0]
        steers = u_seq[:, 1]
        cost_control = w_accel * np.sum(accels**2) + w_steer * np.sum(steers**2)
        
        # 4. Smoothness (Jerk/Slew rate)
        if self.H > 1:
            d_acc = np.diff(accels)
            d_str = np.diff(steers)
            
            # --- DISTANCE-ADAPTIVE REGULARIZATION (OPTION 1) ---
            # Increase smoothness penalty when close to target to prevent chattering
            # Calculate distance to target (from current state x0 to target_pos)
            # x0 is usually [0,0,0,v] in local frame. target_pos is local coordinates.
            dist_to_target = np.linalg.norm(target_pos - x0[:2])
            
            # Alpha factor: 1.0 at long range, increases exponentially at close range (< 5m)
            # alpha = 1.0 + 10.0 * exp(-dist / 3.0)
            alpha_smooth = 1.0 + 10.0 * np.exp(-dist_to_target / 3.0)
            
            # Apply alpha to smoothness cost
            cost_smooth = w_smooth_accel * alpha_smooth * np.sum(d_acc**2) + \
                          w_smooth_steer * alpha_smooth * np.sum(d_str**2)
            
            # Also regularize control magnitude slightly more at close range to prevent aggressive inputs
            cost_control += (w_accel * 0.5 * (alpha_smooth - 1.0)) * np.sum(accels**2) + \
                            (w_steer * 0.5 * (alpha_smooth - 1.0)) * np.sum(steers**2)
            
        # 5. Semantic Obstacle Avoidance (Risk Potential Field)
        # Soft Constraint using Potential Field
        if obstacles:
            traj_x = traj[1:, 0] # [H]
            traj_y = traj[1:, 1] # [H]
            
            for obs in obstacles:
                ox, oy, r, w_risk = obs
                
                # Euclidean distance squared
                d2 = (traj_x - ox)**2 + (traj_y - oy)**2
                
                # Gaussian Potential Field
                # --- ENTROPY-REGULARIZED POTENTIAL FIELD ---
                # Inflate sigma based on uncertainty
                # sigma = base_sigma * (1 + alpha * H(P))
                base_sigma = max(r, 1.0) # Minimum sigma 1m
                dynamic_sigma = base_sigma * (1.0 + 2.0 * uncertainty)
                
                # [Fix A] Clamp sigma to prevent invisible walls in high uncertainty
                dynamic_sigma = min(dynamic_sigma, 3.0)

                risk = w_risk * np.exp(-d2 / (2 * dynamic_sigma**2))
                
                cost_obs += np.sum(risk) * 10.0 * w_obs_scale # Boost weight for safety
                
                # Add Inverse Barrier for very close range (Harder Soft Constraint)
                safe_dist_sq = (r + 0.5)**2
                danger_mask = d2 < safe_dist_sq
                if np.any(danger_mask):
                    # w / (d2 + eps)
                    cost_obs += w_risk * np.sum(1.0 / (d2[danger_mask] + 0.1)) * 10.0 * w_obs_scale
        
        total_cost = cost_pos + cost_vel + cost_yaw + cost_control + cost_smooth + cost_obs
        
        components = {
            'pos': cost_pos,
            'vel': cost_vel,
            'yaw': cost_yaw,
            'control': cost_control,
            'smooth': cost_smooth,
            'obs': cost_obs
        }
        return total_cost, components

    def cost_function(self, u_flat, x0, target_pos, target_speed, obstacles=[], ref_traj=None, weights=None, uncertainty=0.0):
        """
        u_flat: Flattened control sequence
        x0: Initial state [0, 0, 0, v_current] (Local frame)
        target_pos: [x_t, y_t] (Local frame) - used if ref_traj is None
        target_speed: Desired speed
        obstacles: List of (x, y, radius, risk_weight) in Local Frame
        ref_traj: Optional [H, 2] or [H, 4] array of reference points
        weights: Optional dict to override default weights
        uncertainty: Current perception uncertainty (Entropy)
        """
        total_cost, _ = self._compute_costs(u_flat, x0, target_pos, target_speed, obstacles, ref_traj, weights, uncertainty)
        return total_cost


    def solve(self, current_speed, target_rel_pos, target_speed=5.0, obstacles=[], ref_traj=None, weights=None, uncertainty=0.0):
        """
        Solve MPC for one step.
        current_speed: Scalar (m/s)
        target_rel_pos: [x, y] in Ego Frame
        obstacles: List of dicts or tuples representing obstacles
        ref_traj: Optional [H, 2] reference trajectory
        weights: Optional dict for dynamic cost function
        uncertainty: Current perception uncertainty (Entropy)
        """
        # Initial State (Local Frame): x=0, y=0, yaw=0, v=current
        x0 = np.array([0.0, 0.0, 0.0, current_speed])
        
        # Bounds
        # Accel: [-max_brake, max_accel]
        # Steer: [-max_steer, max_steer]
        bounds = []
        for _ in range(self.H):
            bounds.append((-self.max_brake, self.max_accel)) # Accel
            bounds.append((-self.max_steer, self.max_steer)) # Steer
            
        # Optimization
        # Warm start with previous solution shifted
        # u0 -> u1, u1 -> u2 ...
        # self.last_u is flat: [a0, d0, a1, d1, ...] (length 2*H)
        # Shift by 2 elements (one time step)
        u_init = np.roll(self.last_u, -2)
        
        # The last control (now at index -2 and -1) should be copied from the previous last control
        # instead of zero, to maintain continuity (constant acceleration/steer assumption at horizon end)
        u_init[-2] = u_init[-4] # Copy accel
        u_init[-1] = u_init[-3] # Copy steer
        
        # Clip u_init to bounds to avoid scipy warning/errors
        # Flatten bounds for checking
        min_b = np.array([b[0] for b in bounds])
        max_b = np.array([b[1] for b in bounds])
        u_init = np.clip(u_init, min_b, max_b)
        
        # Safe Boost Check (Beautification)
        # If we just reset the history (e.g. Safe Boost), we need to ensure the warm start doesn't fight it.
        # But Safe Boost logic is outside in the loop. 
        # Here we just apply the last_u as guess.
        
        try:
            res = minimize(
                self.cost_function,
                u_init,
                args=(x0, target_rel_pos, target_speed, obstacles, ref_traj, weights, uncertainty),
                method='SLSQP',
                bounds=bounds,
                options={'ftol': 1e-3, 'disp': False, 'maxiter': 50}
            )
            self.last_u = res.x
            first_u = res.x[:2]
            
            # Compute final metrics for the chosen solution
            _, self.last_metrics = self._compute_costs(
                res.x, x0, target_rel_pos, target_speed, obstacles, ref_traj, weights, uncertainty
            )
            
        except Exception as e:
            print(f"MPC Optimization Failed: {e}")
            # Fallback: maintain speed, zero steer? Or brake?
            # Safe fallback: Mild braking, zero steer
            first_u = [-1.0, 0.0]
            self.last_u = np.zeros(2 * self.H) # Reset
            self.last_metrics = {'pos': 0, 'vel': 0, 'control': 0, 'smooth': 0, 'obs': 0}
            
        return first_u, self.last_metrics
