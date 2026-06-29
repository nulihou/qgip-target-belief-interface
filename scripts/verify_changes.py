import sys
import unittest
import numpy as np
from unittest.mock import MagicMock
import os

# Set path to include project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

# Mock carla
mock_carla = MagicMock()
sys.modules['carla'] = mock_carla

# Import MPCController
from scripts.control.mpc_controller import MPCController

class SmoothFollowerTest:
    def __init__(self):
        self.smooth_target = None
        
    def _calculate_ideal_pos(self, raw_target_pos, ego_pos):
        vec = ego_pos - raw_target_pos
        dist = np.linalg.norm(vec)
        if dist < 0.1:
            direction = np.zeros(3)
        else:
            direction = vec / dist
        ideal_pos = raw_target_pos + direction * 10.0
        return ideal_pos

    def get_render_target(self, raw_target_pos, ego_pos):
        ideal_pos = self._calculate_ideal_pos(raw_target_pos, ego_pos)
        if self.smooth_target is None:
            self.smooth_target = ideal_pos
            return self.smooth_target
        
        error = np.linalg.norm(ideal_pos - self.smooth_target)
        # Sigmoid: 0.05 + 0.55 * (1 / (1 + np.exp(-2.0 * (error - 1.5))))
        dynamic_alpha = 0.05 + 0.55 * (1 / (1 + np.exp(-2.0 * (error - 1.5))))
        
        self.smooth_target = (1 - dynamic_alpha) * self.smooth_target + dynamic_alpha * ideal_pos
        return self.smooth_target

class TestLogic(unittest.TestCase):
    def test_smooth_follower_sigmoid(self):
        print("\nTesting SmoothFollower Sigmoid...")
        sf = SmoothFollowerTest()
        raw = np.array([100.0, 0.0, 0.0])
        ego = np.array([0.0, 0.0, 0.0])
        
        # First call sets smooth_target
        res = sf.get_render_target(raw, ego)
        np.testing.assert_array_almost_equal(res, np.array([90.0, 0.0, 0.0]))
        print("Initial target set correctly.")
        
        # Second call with small error
        raw2 = np.array([100.1, 0.0, 0.0])
        res2 = sf.get_render_target(raw2, ego)
        ideal2 = sf._calculate_ideal_pos(raw2, ego)
        error = np.linalg.norm(ideal2 - res) # Error between NEW ideal and OLD smooth
        alpha = 0.05 + 0.55 * (1 / (1 + np.exp(-2.0 * (error - 1.5))))
        print(f"Small error ({error:.4f}) alpha: {alpha:.4f}")
        self.assertTrue(alpha < 0.2, "Alpha should be small for small error")

        # Third call with LARGE error
        raw3 = np.array([120.0, 0.0, 0.0])
        # Force previous smooth target to be far
        sf.smooth_target = np.array([90.0, 0.0, 0.0])
        ideal3 = sf._calculate_ideal_pos(raw3, ego) # [110, 0, 0]
        error3 = np.linalg.norm(ideal3 - sf.smooth_target) # 20.0
        
        res3 = sf.get_render_target(raw3, ego)
        alpha3 = 0.05 + 0.55 * (1 / (1 + np.exp(-2.0 * (error3 - 1.5))))
        print(f"Large error ({error3:.4f}) alpha: {alpha3:.4f}")
        self.assertTrue(alpha3 > 0.5, "Alpha should be large for large error")

    def test_mpc_bezier(self):
        print("\nTesting MPC Bezier Trajectory...")
        mpc = MPCController()
        ego_state = np.array([0.0, 0.0, 0.0, 10.0]) # x, y, yaw, v
        target_pos = np.array([10.0, 10.0])
        target_heading = np.pi/2 # 90 deg
        target_speed = 5.0
        
        traj = mpc.get_bezier_trajectory(ego_state, target_pos, target_heading, target_speed)
        
        self.assertEqual(len(traj), mpc.H)
        self.assertEqual(traj.shape[1], 4) # x, y, v, yaw
        
        last_pt = traj[-1]
        print(f"Last point: {last_pt}")
        np.testing.assert_array_almost_equal(last_pt[:2], target_pos)
        self.assertEqual(last_pt[2], target_speed)
        
        # Check tangent roughly
        # P0(0,0), P3(10,10)
        # P1 = P0 + 0.35*dist*dir(0) = (0,0) + 0.35*14.14*(1,0) = (4.95, 0)
        # P2 = P3 - 0.35*dist*dir(90) = (10,10) - 4.95*(0,1) = (10, 5.05)
        # Trajectory should start flat (yaw~0) and end vertical (yaw~90)
        first_yaw = traj[0][3]
        last_yaw = traj[-1][3]
        print(f"First yaw: {np.rad2deg(first_yaw):.2f} deg")
        print(f"Last yaw: {np.rad2deg(last_yaw):.2f} deg")
        
        self.assertTrue(abs(first_yaw) < 0.5)
        self.assertTrue(abs(last_yaw - np.pi/2) < 0.1)

    def test_mpc_yaw_cost(self):
        print("\nTesting MPC Yaw Cost...")
        mpc = MPCController()
        mpc.w_yaw = 10.0
        
        # Case 1: Perfect match
        ref_traj = np.zeros((mpc.H, 4))
        traj = np.zeros((mpc.H+1, 4))
        mpc.predict_trajectory = MagicMock(return_value=traj)
        
        u_flat = np.zeros(mpc.H * 2)
        cost, components = mpc._compute_costs(u_flat, np.zeros(4), np.zeros(2), 0.0, ref_traj=ref_traj)
        self.assertEqual(components['yaw'], 0.0)
        print("Zero cost for perfect match verified.")
        
        # Case 2: Yaw error pi/2
        traj_bad = np.zeros((mpc.H+1, 4))
        traj_bad[:, 2] = np.pi/2 # Yaw = 90 deg in column 2 (index 2 is yaw? Wait)
        # In kinematic_bicycle_model: [x, y, yaw, v]
        # In predict_trajectory: returns [x, y, yaw, v]
        # In _compute_costs: traj[1:, 2] IS yaw. Correct.
        
        mpc.predict_trajectory = MagicMock(return_value=traj_bad)
        
        cost, components = mpc._compute_costs(u_flat, np.zeros(4), np.zeros(2), 0.0, ref_traj=ref_traj)
        
        # Error calc: (traj_yaw - ref_yaw + pi) % 2pi - pi
        # (pi/2 - 0 + pi) % 2pi - pi = (1.5pi) % 2pi - pi = 1.5pi - pi = 0.5pi ? No.
        # 1.5pi is 3pi/2. 
        # (3pi/2) % 2pi = 3pi/2.
        # 3pi/2 - pi = pi/2. Correct.
        
        expected_yaw_cost = (np.pi/2)**2 * mpc.H * mpc.w_yaw
        print(f"Yaw cost: {components['yaw']}, Expected: {expected_yaw_cost}")
        np.testing.assert_almost_equal(components['yaw'], expected_yaw_cost)

if __name__ == '__main__':
    unittest.main()
