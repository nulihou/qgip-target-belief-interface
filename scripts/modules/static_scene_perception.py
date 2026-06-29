import carla
import numpy as np
import math

class StaticScenePerception:
    def __init__(self, carla_map):
        self.map = carla_map

    def get_local_map(self, ego_vehicle, radius=40.0, sampling_resolution=2.0):
        """
        Extracts local map features around the ego vehicle.
        Returns a dictionary containing:
        - lanes: List of lane boundaries (ego-centric coordinates)
        - road_edges: List of road edges (curbs)
        - junction: Boolean (is inside or near junction)
        """
        ego_trans = ego_vehicle.get_transform()
        ego_loc = ego_trans.location
        ego_wp = self.map.get_waypoint(ego_loc, project_to_road=True, lane_type=(carla.LaneType.Driving | carla.LaneType.Sidewalk))
        
        local_map = {
            'lane_lines': [], # List of {'points': [(x,y)], 'type': str, 'color': str}
            'road_edges': [],
            'junction': ego_wp.is_junction
        }

        # We will scan the road topology by traversing waypoints
        # 1. Get current lane waypoints (forward and backward)
        # 2. Get adjacent lanes
        
        scanned_lanes = []
        
        # Helper to traverse lane
        def traverse_lane(start_wp, dist):
            points = []
            # Forward
            current = start_wp
            d = 0
            while d < dist:
                points.append(current)
                next_wps = current.next(sampling_resolution)
                if not next_wps:
                    break
                current = next_wps[0] # Take the first path
                d += sampling_resolution
                
            # Backward (add to front)
            current = start_wp
            d = 0
            backward_points = []
            while d < dist/2.0: # Look back a bit less
                prev_wps = current.previous(sampling_resolution)
                if not prev_wps:
                    break
                current = prev_wps[0]
                backward_points.append(current)
                d += sampling_resolution
            
            return backward_points[::-1] + points

        # Get relevant waypoints
        # Current Lane
        center_lane_wps = traverse_lane(ego_wp, radius)
        scanned_lanes.append(center_lane_wps)
        
        # Left Lane
        if ego_wp.lane_change in [carla.LaneChange.Left, carla.LaneChange.Both]:
            left_wp = ego_wp.get_left_lane()
            if left_wp and left_wp.lane_type == carla.LaneType.Driving:
                scanned_lanes.append(traverse_lane(left_wp, radius))
        
        # Right Lane
        if ego_wp.lane_change in [carla.LaneChange.Right, carla.LaneChange.Both]:
            right_wp = ego_wp.get_right_lane()
            if right_wp and right_wp.lane_type == carla.LaneType.Driving:
                scanned_lanes.append(traverse_lane(right_wp, radius))

        # Process Waypoints to Lines
        for lane_wps in scanned_lanes:
            if not lane_wps: continue
            
            # Left Boundary
            left_boundary = []
            right_boundary = []
            
            for wp in lane_wps:
                # Transform to Ego Frame
                # Lane width/2 offset
                half_width = wp.lane_width / 2.0
                
                # Get local coordinates of the waypoint center
                local_center = self._world_to_ego(wp.transform.location, ego_trans)
                
                # We need the perpendicular vector to the lane direction at this waypoint
                # But simply, we can transform the world-coordinates of the boundaries
                
                # Carla logic:
                # Right vector is (sin(yaw), -cos(yaw), 0) ?? No, Carla is Left-Handed?
                # Let's trust transforms.
                
                # Better approach:
                # wp.transform.get_right_vector() points to the right of the lane
                r_vec = wp.transform.get_right_vector()
                
                # Left Point
                l_pt_world = wp.transform.location - r_vec * half_width
                r_pt_world = wp.transform.location + r_vec * half_width
                
                left_boundary.append(self._world_to_ego(l_pt_world, ego_trans))
                right_boundary.append(self._world_to_ego(r_pt_world, ego_trans))
            
            # Add to map
            local_map['lane_lines'].append({'points': left_boundary, 'type': 'unknown', 'side': 'left'})
            local_map['lane_lines'].append({'points': right_boundary, 'type': 'unknown', 'side': 'right'})

        return local_map

    def _world_to_ego(self, location, ego_trans):
        """
        Transforms a world location to ego-centric coordinate system (X-forward, Y-right).
        """
        # Vector from Ego to Point
        vec = location - ego_trans.location
        
        # Ego Forward and Right vectors
        ego_fwd = ego_trans.get_forward_vector()
        ego_right = ego_trans.get_right_vector()
        
        # Project
        x = vec.dot(ego_fwd)
        y = vec.dot(ego_right)
        
        return (x, y)
