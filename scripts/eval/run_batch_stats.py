import carla
import torch
import numpy as np
import random
import time
import sys
import os
import csv
from collections import deque

# Path setup
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from scripts.train.model import QGIPNet
from scripts.eval.run_closed_loop import QGIPAgent, SceneGraphBuilder

EPISODE_CSV_FIELDS = [
    "Episode",
    "Result",
    "StrictSR",
    "LooseSR",
    "Jerk",
    "JerkP95",
    "MinDistance",
    "MinTTC",
    "MinHeadway",
    "NearMiss",
    "DropoutFrames",
    "RecoveryTime",
    "LeaderAcc",
    "LeaderFrames",
    "WrongLeaderFrames",
    "IDSwitches",
    "CandidateFrames",
    "FaultedCandidateFrames",
    "FalsePositiveFrames",
    "FalseNegativeFrames",
    "NISFrames",
    "NISMean",
    "NISP95",
    "NISSoftViolations",
    "NISHardViolations",
    "KFInitUpdates",
    "KFNormalUpdates",
    "KFSoftUpdates",
    "KFHardResets",
    "KFHardRejects",
    "KFPredictFrames",
    "KFHoldFrames",
]


class ActorSnapshot:
    """Frozen actor-like object used for detector-level fault injection."""

    def __init__(self, actor_id, transform, velocity, source_actor_id=None):
        self.id = actor_id
        self.source_actor_id = actor_id if source_actor_id is None else source_actor_id
        self._transform = transform
        self._velocity = velocity

    def get_transform(self):
        return self._transform

    def get_location(self):
        return self._transform.location

    def get_velocity(self):
        return self._velocity


class BatchEvaluator:
    def __init__(self, town='Town05', model_path='checkpoints/best_model.pth', agent_class=QGIPAgent):
        print(f"[DEBUG] Initializing Evaluator on {town}...", flush=True)
        self.agent_class = agent_class
        self.client = carla.Client('localhost', 2000)
        self.client.set_timeout(float(os.environ.get("CARLA_TIMEOUT_S", "60.0")))

        self.world = self._load_world_with_retry(town)

        self.settings = self._get_settings_with_retry()
        self.settings.synchronous_mode = True
        self.settings.fixed_delta_seconds = 0.05
        self._apply_settings_with_retry(self.settings)
        
        self.tm = self.client.get_trafficmanager(8000)
        self.tm.set_synchronous_mode(True)
        self.tm.set_global_distance_to_leading_vehicle(2.0)
        
        self.bp_lib = self.world.get_blueprint_library()
        self.map = self.world.get_map()
        
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model_path = model_path
        self._candidate_delay_queue = deque()
        self._rng = None
        self._rng_seed = None
        print(f"[DEBUG] QGIP Model Path: {self.model_path}", flush=True)
        print(f"[DEBUG] Leader Checkpoint: {os.environ.get('QGIP_LEADER_CKPT', 'checkpoints/v7/llc_epoch_20.pth')}", flush=True)

    def _load_world_with_retry(self, town):
        attempts = int(os.environ.get("CARLA_WORLD_RETRIES", "3"))
        settle_s = float(os.environ.get("CARLA_WORLD_SETTLE_S", "2.0"))
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                print(f"[DEBUG] Loading world {town} (attempt {attempt}/{attempts})...", flush=True)
                world = self.client.load_world(town)
                time.sleep(settle_s)
                print("[DEBUG] World Loaded.", flush=True)
                return world
            except RuntimeError as exc:
                last_exc = exc
                print(f"[WARN] load_world failed: {exc}", flush=True)
                time.sleep(2.0 * attempt)
        raise last_exc

    def _apply_settings_with_retry(self, settings):
        attempts = int(os.environ.get("CARLA_SETTINGS_RETRIES", "3"))
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                self.world.apply_settings(settings)
                return
            except RuntimeError as exc:
                last_exc = exc
                print(f"[WARN] apply_settings failed (attempt {attempt}/{attempts}): {exc}", flush=True)
                time.sleep(2.0 * attempt)
                try:
                    self.world = self.client.get_world()
                except RuntimeError:
                    pass
        raise last_exc

    def _get_settings_with_retry(self):
        attempts = int(os.environ.get("CARLA_SETTINGS_RETRIES", "3"))
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                return self.world.get_settings()
            except RuntimeError as exc:
                last_exc = exc
                print(f"[WARN] get_settings failed (attempt {attempt}/{attempts}): {exc}", flush=True)
                time.sleep(2.0 * attempt)
                try:
                    self.world = self.client.get_world()
                except RuntimeError:
                    pass
        raise last_exc

    def close(self):
        try:
            if hasattr(self, "tm"):
                self.tm.set_synchronous_mode(False)
        except RuntimeError as exc:
            print(f"[WARN] Failed to release TrafficManager sync mode: {exc}", flush=True)
        try:
            if hasattr(self, "world"):
                settings = self.world.get_settings()
                settings.synchronous_mode = False
                settings.fixed_delta_seconds = None
                self.world.apply_settings(settings)
                print("[DEBUG] CARLA synchronous mode released.", flush=True)
        except RuntimeError as exc:
            print(f"[WARN] Failed to release world sync mode: {exc}", flush=True)

    def _get_rng(self):
        seed = int(getattr(self, "random_seed", 7))
        if self._rng is None or self._rng_seed != seed:
            self._rng = np.random.default_rng(seed)
            self._rng_seed = seed
        return self._rng

    def _clone_transform(self, transform):
        return carla.Transform(
            carla.Location(transform.location.x, transform.location.y, transform.location.z),
            carla.Rotation(transform.rotation.pitch, transform.rotation.yaw, transform.rotation.roll),
        )

    def _clone_velocity(self, velocity):
        return carla.Vector3D(velocity.x, velocity.y, velocity.z)

    def _actor_snapshot(self, actor, actor_id=None, position_noise_m=0.0, velocity_noise_mps=0.0):
        transform = self._clone_transform(actor.get_transform())
        velocity = self._clone_velocity(actor.get_velocity())
        rng = self._get_rng()
        if position_noise_m > 0.0:
            transform.location.x += float(rng.normal(0.0, position_noise_m))
            transform.location.y += float(rng.normal(0.0, position_noise_m))
        if velocity_noise_mps > 0.0:
            velocity.x += float(rng.normal(0.0, velocity_noise_mps))
            velocity.y += float(rng.normal(0.0, velocity_noise_mps))
        return ActorSnapshot(actor.id if actor_id is None else actor_id, transform, velocity, source_actor_id=actor.id)

    def _false_positive_snapshot(self, ego, frame):
        rng = self._get_rng()
        ego_tf = ego.get_transform()
        forward = ego_tf.get_forward_vector()
        right = ego_tf.get_right_vector()
        rel_x = float(rng.uniform(8.0, 25.0))
        rel_y = float(rng.uniform(-3.0, 3.0))
        loc = carla.Location(
            ego_tf.location.x + forward.x * rel_x + right.x * rel_y,
            ego_tf.location.y + forward.y * rel_x + right.y * rel_y,
            ego_tf.location.z + 0.2,
        )
        transform = carla.Transform(loc, carla.Rotation(yaw=ego_tf.rotation.yaw))
        velocity = carla.Vector3D(0.0, 0.0, 0.0)
        return ActorSnapshot(900000 + frame, transform, velocity, source_actor_id=None)

    def _apply_detector_faults(self, candidates, ego, frame):
        rng = self._get_rng()
        fn_rate = float(getattr(self, "false_negative_rate", 0.0))
        fp_rate = float(getattr(self, "false_positive_rate", 0.0))
        id_switch_prob = float(getattr(self, "id_switch_probability", 0.0))
        position_noise_m = float(getattr(self, "observation_noise_m", 0.0))
        velocity_noise_mps = float(getattr(self, "velocity_noise_mps", 0.0))

        out = []
        dropped = 0
        for cand in candidates:
            if fn_rate > 0.0 and rng.random() < fn_rate:
                dropped += 1
                continue
            out.append(self._actor_snapshot(cand, position_noise_m=position_noise_m, velocity_noise_mps=velocity_noise_mps))

        false_positive_added = False
        if fp_rate > 0.0 and rng.random() < fp_rate:
            out.append(self._false_positive_snapshot(ego, frame))
            false_positive_added = True

        if len(out) >= 2 and id_switch_prob > 0.0 and rng.random() < id_switch_prob:
            out[0].id, out[1].id = out[1].id, out[0].id

        return out, dropped, false_positive_added

    def _apply_detection_delay(self, candidates):
        delay_ms = float(getattr(self, "delay_ms", 0.0))
        delay_frames = int(round(delay_ms / 50.0))
        if delay_frames <= 0:
            self._candidate_delay_queue.clear()
            return candidates
        self._candidate_delay_queue.append(list(candidates))
        if len(self._candidate_delay_queue) <= delay_frames:
            return []
        return self._candidate_delay_queue.popleft()

    def _mean_and_p95_jerk(self, acc_history):
        if len(acc_history) <= 1:
            return 0.0, 0.0
        acc_np = np.array(acc_history)
        jerk = np.diff(acc_np, axis=0) / 0.05
        jerk_mag = np.linalg.norm(jerk, axis=1)
        return float(np.mean(jerk_mag)), float(np.percentile(jerk_mag, 95))

    def _empty_metrics(self):
        return {
            "min_distance_m": float("inf"),
            "min_ttc_s": float("inf"),
            "min_headway_s": float("inf"),
            "near_miss": False,
            "dropout_frames": 0,
            "candidate_frames": 0,
            "faulted_candidate_frames": 0,
            "false_positive_frames": 0,
            "false_negative_frames": 0,
            "leader_frames": 0,
            "correct_leader_frames": 0,
            "wrong_leader_frames": 0,
            "selection_id_switches": 0,
            "prev_selected_actor_id": None,
            "recovery_times": [],
            "nis_values": [],
            "nis_soft_violations": 0,
            "nis_hard_violations": 0,
            "kf_mode_counts": {
                "init": 0,
                "normal": 0,
                "soft": 0,
                "hard_reset": 0,
                "hard_reject": 0,
                "predict": 0,
                "hold": 0,
            },
        }

    def _finish_episode(self, result, acc_history, metrics):
        mean_jerk, p95_jerk = self._mean_and_p95_jerk(acc_history)
        min_distance = metrics["min_distance_m"]
        min_ttc = metrics["min_ttc_s"]
        min_headway = metrics["min_headway_s"]
        recovery_times = metrics["recovery_times"]
        nis_values = metrics["nis_values"]
        kf_mode_counts = metrics["kf_mode_counts"]
        return {
            "Result": result,
            "Jerk": mean_jerk,
            "JerkP95": p95_jerk,
            "MinDistance": "" if np.isinf(min_distance) else min_distance,
            "MinTTC": "" if np.isinf(min_ttc) else min_ttc,
            "MinHeadway": "" if np.isinf(min_headway) else min_headway,
            "NearMiss": int(metrics["near_miss"]),
            "DropoutFrames": metrics["dropout_frames"],
            "RecoveryTime": "" if not recovery_times else float(np.mean(recovery_times)),
            "LeaderAcc": "" if metrics["leader_frames"] == 0 else metrics["correct_leader_frames"] / metrics["leader_frames"],
            "LeaderFrames": metrics["leader_frames"],
            "WrongLeaderFrames": metrics["wrong_leader_frames"],
            "IDSwitches": metrics["selection_id_switches"],
            "CandidateFrames": metrics["candidate_frames"],
            "FaultedCandidateFrames": metrics["faulted_candidate_frames"],
            "FalsePositiveFrames": metrics["false_positive_frames"],
            "FalseNegativeFrames": metrics["false_negative_frames"],
            "NISFrames": len(nis_values),
            "NISMean": "" if not nis_values else float(np.mean(nis_values)),
            "NISP95": "" if not nis_values else float(np.percentile(nis_values, 95)),
            "NISSoftViolations": metrics["nis_soft_violations"],
            "NISHardViolations": metrics["nis_hard_violations"],
            "KFInitUpdates": kf_mode_counts["init"],
            "KFNormalUpdates": kf_mode_counts["normal"],
            "KFSoftUpdates": kf_mode_counts["soft"],
            "KFHardResets": kf_mode_counts["hard_reset"],
            "KFHardRejects": kf_mode_counts["hard_reject"],
            "KFPredictFrames": kf_mode_counts["predict"],
            "KFHoldFrames": kf_mode_counts["hold"],
        }

    def _scenario_profile(self):
        return str(getattr(self, "scenario_profile", "following") or "following").strip().lower()

    def _query_vector(self, frame):
        profile = str(getattr(self, "query_profile", "follow") or "follow").strip().lower()
        delay = int(getattr(self, "query_delay_frames", 0) or 0)
        if delay > 0 and frame < delay:
            profile = "follow"
        if profile in {"follow", "leader", "default"}:
            return [0, 1, 0, 0, 0]
        if profile in {"left", "lane_left", "change_left"}:
            return [0, 0, 1, 0, 0]
        if profile in {"right", "lane_right", "change_right", "wrong_right"}:
            return [0, 0, 0, 1, 0]
        if profile in {"stop", "brake"}:
            return [0, 0, 0, 0, 1]
        if profile in {"zero", "none"}:
            return [0, 0, 0, 0, 0]
        return [0, 1, 0, 0, 0]

    def _query_metric_target(self, target, distractor):
        profile = self._scenario_profile()
        query_profile = str(getattr(self, "query_profile", "follow") or "follow").strip().lower()
        adjacent_query = query_profile in {
            "left",
            "lane_left",
            "change_left",
            "right",
            "lane_right",
            "change_right",
            "wrong_right",
        }
        if distractor is not None and profile in {"query_sensitive", "query_left", "query_right"} and adjacent_query:
            return distractor
        return target

    def _apply_weather_profile(self):
        profile = str(getattr(self, "weather_profile", "clear") or "clear").strip().lower()
        if profile in {"", "none", "clear"}:
            return
        presets = {
            "glare": carla.WeatherParameters(
                cloudiness=5.0,
                precipitation=0.0,
                sun_altitude_angle=15.0,
                sun_azimuth_angle=20.0,
                fog_density=0.0,
            ),
            "low_light": carla.WeatherParameters(
                cloudiness=30.0,
                precipitation=0.0,
                sun_altitude_angle=-5.0,
                fog_density=10.0,
            ),
            "rain": carla.WeatherParameters(
                cloudiness=80.0,
                precipitation=65.0,
                precipitation_deposits=40.0,
                wetness=80.0,
                sun_altitude_angle=35.0,
            ),
            "fog": carla.WeatherParameters(
                cloudiness=70.0,
                precipitation=0.0,
                fog_density=55.0,
                fog_distance=25.0,
                sun_altitude_angle=20.0,
            ),
        }
        weather = presets.get(profile)
        if weather is not None:
            self.world.set_weather(weather)

    def _sensor_profile_defaults(self):
        profile = str(getattr(self, "sensor_profile", "none") or "none").strip().lower()
        if profile == "camera_glare":
            self.observation_noise_m = max(float(getattr(self, "observation_noise_m", 0.0)), 0.30)
            self.false_negative_rate = max(float(getattr(self, "false_negative_rate", 0.0)), 0.35)
            self.false_positive_rate = max(float(getattr(self, "false_positive_rate", 0.0)), 0.05)
        elif profile == "lidar_dropout":
            self.observation_noise_m = max(float(getattr(self, "observation_noise_m", 0.0)), 0.20)
            self.false_negative_rate = max(float(getattr(self, "false_negative_rate", 0.0)), 0.30)
        elif profile == "motion_blur":
            self.observation_noise_m = max(float(getattr(self, "observation_noise_m", 0.0)), 0.50)
            self.delay_ms = max(float(getattr(self, "delay_ms", 0.0)), 100.0)
        elif profile == "low_light":
            self.observation_noise_m = max(float(getattr(self, "observation_noise_m", 0.0)), 0.35)
            self.false_negative_rate = max(float(getattr(self, "false_negative_rate", 0.0)), 0.25)

    def try_spawn_scenario(self, max_retries=50):
        spawn_points = self.map.get_spawn_points()
        for i in range(max_retries):
            ego_spawn = random.choice(spawn_points)
            ego_waypoint = self.map.get_waypoint(ego_spawn.location)
            profile = self._scenario_profile()
            if profile == "curve_following":
                future = ego_waypoint.next(45.0)
                if not future:
                    continue
                yaw_delta = abs((future[0].transform.rotation.yaw - ego_waypoint.transform.rotation.yaw + 180.0) % 360.0 - 180.0)
                if yaw_delta < 12.0:
                    continue
            
            # --- Two-Leader Ambiguity Logic ---
            
            # 1. Spawn Target (Same Lane)
            next_wps = ego_waypoint.next(15.0)
            if not next_wps: continue
            target_waypoint = next_wps[0]
            target_spawn = target_waypoint.transform
            target_spawn.location.z += 0.5
            
            # 2. Spawn Distractor (Adjacent Lane or Nearby)
            # Try get left or right lane
            distractor_spawn = None
            left_lane = target_waypoint.get_left_lane()
            right_lane = target_waypoint.get_right_lane()
            query_profile = str(getattr(self, "query_profile", "follow") or "follow").strip().lower()
            wants_left = profile in {"query_left"} or query_profile in {"left", "lane_left", "change_left"}
            wants_right = profile in {"query_right"} or query_profile in {"right", "lane_right", "change_right", "wrong_right"}
            if profile in {"query_sensitive", "query_left", "query_right"}:
                if wants_left and left_lane:
                    distractor_spawn = left_lane.transform
                elif wants_right and right_lane:
                    distractor_spawn = right_lane.transform
                elif left_lane:
                    distractor_spawn = left_lane.transform
                elif right_lane:
                    distractor_spawn = right_lane.transform
            elif left_lane:
                distractor_spawn = left_lane.transform
            elif right_lane:
                distractor_spawn = right_lane.transform
            
            # Ambiguity V2: Target is ALWAYS Center. Distractor is Side.
            # If no side lane, skip.
            needs_distractor = getattr(self, 'ambiguity_test', False) or profile in {
                "adjacent_lane_distractor",
                "cut_in",
                "cut_out",
                "merge",
                "two_leader_similar",
                "wrong_query",
                "delayed_query",
                "query_sensitive",
                "query_left",
                "query_right",
            }
            if needs_distractor:
                 if not distractor_spawn: continue
                 # Distractor slightly AHEAD to be annoying (Hard Mode)
                 # target is at 15m. distractor at 15m.
                 # Let's push distractor to 18m? Or just same.
                 # User said "slightly ahead".
                 # Let's move distractor forward by 3m along its lane.
                 # But we only have the waypoint transform.
                 # We can just use the transform and rely on speed diff.
                 distractor_spawn.location.z += 0.5
            
            ego_bp = self.bp_lib.find('vehicle.tesla.model3')
            target_bp = self.bp_lib.find('vehicle.audi.tt')
            distractor_bp = self.bp_lib.find('vehicle.ford.mustang')
            
            # Ambiguity V2: Randomize Spawn Order Only
            # Target is ALWAYS at target_spawn (Center)
            # Distractor is ALWAYS at distractor_spawn (Side)
            # BUT we shuffle the order of spawning to kill ID bias.
            
            if needs_distractor:
                spawn_list = [
                    (target_bp, target_spawn, 'target'),
                    (distractor_bp, distractor_spawn, 'distractor')
                ]
                random.shuffle(spawn_list)
                
                target_actor = None
                distractor_actor = None
                
                for bp, transform, role in spawn_list:
                    actor = self.world.try_spawn_actor(bp, transform)
                    if not actor: break
                    if role == 'target': target_actor = actor
                    else: distractor_actor = actor
                
                if not target_actor or not distractor_actor:
                    if target_actor: target_actor.destroy()
                    if distractor_actor: distractor_actor.destroy()
                    continue
                    
                target = target_actor
                distractor = distractor_actor
                
            else:
                # Standard Spawn Logic
                target = self.world.try_spawn_actor(target_bp, target_spawn)
                if not target: continue
                distractor = None

            ego = self.world.try_spawn_actor(ego_bp, ego_spawn)
            if not ego:
                target.destroy()
                if distractor: distractor.destroy()
                continue
            
            return ego, target, distractor
        return None, None, None

    def get_lateral_offset(self, actor, lane_wp):
        """Calculates lateral offset of actor from lane center."""
        actor_loc = actor.get_location()
        
        # Project actor location onto lane centerline
        # Simple approximation: Distance to waypoint
        # Better: Use vector projection
        
        wp_loc = lane_wp.transform.location
        wp_vec = lane_wp.transform.get_forward_vector()
        
        vec_actor = carla.Vector3D(
            actor_loc.x - wp_loc.x,
            actor_loc.y - wp_loc.y,
            0
        )
        
        # Cross product to get lateral distance
        # 2D cross product: x1*y2 - x2*y1
        cross = vec_actor.x * wp_vec.y - vec_actor.y * wp_vec.x
        return abs(cross)

    def run_episode(self, episode_id):
        actors = []
        collision_event = []
        self._candidate_delay_queue.clear()
        episode_seed = int(getattr(self, "random_seed", 7)) + int(episode_id) * 1009
        random.seed(episode_seed)
        np.random.seed(episode_seed % (2**32 - 1))
        self._rng = np.random.default_rng(episode_seed)
        self._rng_seed = episode_seed
        try:
            self.tm.set_random_device_seed(episode_seed)
        except RuntimeError as exc:
            print(f"[WARN] Failed to set TrafficManager seed: {exc}", flush=True)

        self._sensor_profile_defaults()
        self._apply_weather_profile()
        scenario_profile = self._scenario_profile()
        
        try:
            print(f"[DEBUG] Ep {episode_id}: Spawning...", flush=True)
            ego, target, distractor = self.try_spawn_scenario()
            if not ego or not target:
                print(f"[ERROR] Ep {episode_id}: Spawn Failed.", flush=True)
                return self._finish_episode("SetupFail", [], self._empty_metrics())
            
            actors.extend([ego, target])
            target.set_autopilot(True, self.tm.get_port())
            
            if distractor:
                actors.append(distractor)
                distractor.set_autopilot(True, self.tm.get_port())
                # Distractor slightly faster or same speed to be annoying
                self.tm.vehicle_percentage_speed_difference(distractor, 55.0) # Faster than target (60.0)
            
            # Limit Target Speed to ~30 km/h (Urban Speed)
            self.tm.vehicle_percentage_speed_difference(target, 60.0)
            
            # Warmup
            for _ in range(10): self.world.tick()
            
            # Sensors
            col_bp = self.bp_lib.find('sensor.other.collision')
            col_sensor = self.world.spawn_actor(col_bp, carla.Transform(), attach_to=ego)
            actors.append(col_sensor)
            col_sensor.listen(lambda event: collision_event.append(event))
            
            # Agent
            agent = self.agent_class(ego, self.model_path, self.device)
            
            # Apply Ablation
            if getattr(agent, 'ABLATION_NO_QUERY', False):
                agent.model.ablation_no_query = True
            
            max_frames = 500
            print(f"[DEBUG] Ep {episode_id}: Running...", flush=True)
            metric_target = self._query_metric_target(target, distractor)
            
            # Metric: Target-Hold Accuracy
            correct_target_frames = 0
            total_valid_frames = 0
            id_switches = 0
            last_selected_id = None
            
            # Jerk Calculation
            acc_history = []
            metrics = self._empty_metrics()
            blackout_prev = False
            recovery_start_frame = None
            
            for frame in range(max_frames):
                if scenario_profile == "hard_brake":
                    if 130 <= frame < 190:
                        target.set_autopilot(False)
                        target.apply_control(carla.VehicleControl(throttle=0.0, brake=0.75))
                    elif frame == 190:
                        target.set_autopilot(True, self.tm.get_port())
                elif scenario_profile == "cut_in" and distractor:
                    if 125 <= frame < 210:
                        distractor.set_autopilot(False)
                        distractor.apply_control(carla.VehicleControl(throttle=0.15, steer=-0.25, brake=0.0))
                    elif frame == 210:
                        distractor.set_autopilot(True, self.tm.get_port())

                # Collect Acceleration for Jerk
                v_acc = ego.get_acceleration()
                acc_history.append([v_acc.x, v_acc.y, v_acc.z])
                
                if len(collision_event) > 0:
                    # Calculate partial jerk
                    mean_jerk = 0.0
                    if len(acc_history) > 1:
                        acc_np = np.array(acc_history)
                        jerk = np.diff(acc_np, axis=0) / 0.05
                        jerk_mag = np.linalg.norm(jerk, axis=1)
                        mean_jerk = np.mean(jerk_mag)
                        
                    print(f"[RESULT] Ep {episode_id}: Collision! Jerk={mean_jerk:.2f}", flush=True)
                    return self._finish_episode("Collision", acc_history, metrics)
                
                ego_loc = ego.get_location()
                target_loc = metric_target.get_location()
                dist = ego_loc.distance(target_loc)
                
                # Check Lost
                ego_vel = ego.get_velocity()
                ego_speed = np.sqrt(ego_vel.x**2 + ego_vel.y**2)
                target_vel_now = metric_target.get_velocity()
                target_speed_now = np.sqrt(target_vel_now.x**2 + target_vel_now.y**2)
                thw = dist / ego_speed if ego_speed > 0.2 else float("inf")
                closing_speed = ego_speed - target_speed_now
                ttc = dist / closing_speed if closing_speed > 0.2 else float("inf")
                metrics["min_distance_m"] = min(metrics["min_distance_m"], float(dist))
                if not np.isinf(thw):
                    metrics["min_headway_s"] = min(metrics["min_headway_s"], float(thw))
                if not np.isinf(ttc):
                    metrics["min_ttc_s"] = min(metrics["min_ttc_s"], float(ttc))
                if (
                    dist < float(getattr(self, "near_miss_distance_m", 5.0))
                    or (not np.isinf(thw) and thw < float(getattr(self, "near_miss_headway_s", 0.8)))
                    or (not np.isinf(ttc) and ttc < float(getattr(self, "near_miss_ttc_s", 1.0)))
                ):
                    metrics["near_miss"] = True

                if thw > 3.5 and dist > 80.0:
                    target_vel = metric_target.get_velocity()
                    target_speed = np.sqrt(target_vel.x**2 + target_vel.y**2)
                    
                    # Calculate partial jerk before returning
                    mean_jerk = 0.0
                    if len(acc_history) > 1:
                        acc_np = np.array(acc_history)
                        jerk = np.diff(acc_np, axis=0) / 0.05
                        jerk_mag = np.linalg.norm(jerk, axis=1)
                        mean_jerk = np.mean(jerk_mag)
                        
                    if target_speed < 1.0: return self._finish_episode("Success", acc_history, metrics)
                    if ego_speed > 20.0: return self._finish_episode("ValidDegradation", acc_history, metrics)
                    print(f"[RESULT] Ep {episode_id}: Lost! Jerk={mean_jerk:.2f}", flush=True)
                    return self._finish_episode("Lost", acc_history, metrics)
                
                # Control
                # Simulate Perception Failure (Occlusion) every 100 frames for 20 frames
                # This forces Ghost Tracking to activate
                blind_frames = int(getattr(self, 'blind_duration', 1.0) * 20)
                blind_interval_frames = max(1, int(float(getattr(self, "blind_interval_s", 5.0)) / 0.05))
                blackout_active = blind_frames > 0 and frame % blind_interval_frames < blind_frames and frame > 50
                if blackout_active:
                    candidates = []
                    metrics["dropout_frames"] += 1
                else:
                    if distractor:
                         # Ambiguity Test: Both vehicles are candidates
                         if scenario_profile == "cut_in" and frame < 125:
                             candidates = [target]
                         elif scenario_profile == "cut_out" and 130 <= frame < 210:
                             candidates = []
                             metrics["dropout_frames"] += 1
                         else:
                             candidates = [target, distractor]
                         # Shuffle to prevent "always pick first" bias if model is dumb
                         random.shuffle(candidates)
                         
                         # --- Lane Gating (Symbolic Prior) ---
                         # If enabled, filter candidates based on lane offset
                         if getattr(self, 'lane_gating', False):
                             # Get Ego Lane
                             ego_wp = self.map.get_waypoint(ego.get_location())
                             
                             filtered_candidates = []
                             for cand in candidates:
                                 # Check lateral offset from Ego's lane center
                                 # We assume Ego is roughly in lane center
                                 d_lat = self.get_lateral_offset(cand, ego_wp)
                                 
                                 # Threshold: 1.5m (Standard Lane Width ~3.5m, so half is 1.75m)
                                 if d_lat < 1.5:
                                     filtered_candidates.append(cand)
                             
                             # If all filtered out (e.g. changing lanes), fallback to all
                             if len(filtered_candidates) > 0:
                                 candidates = filtered_candidates
                             # Else: Keep original candidates (soft fallback)
                             
                    else:
                        candidates = [target]

                    if candidates:
                        metrics["candidate_frames"] += 1
                    candidates, dropped_count, false_positive_added = self._apply_detector_faults(candidates, ego, frame)
                    candidates = self._apply_detection_delay(candidates)
                    if dropped_count > 0:
                        metrics["false_negative_frames"] += 1
                    if false_positive_added:
                        metrics["false_positive_frames"] += 1
                    if dropped_count > 0 or false_positive_added or float(getattr(self, "observation_noise_m", 0.0)) > 0.0:
                        metrics["faulted_candidate_frames"] += 1

                query = self._query_vector(frame)
                control = agent.run_step(query, candidates)
                kf = getattr(agent, "kf", None)
                if kf is not None:
                    nis = getattr(kf, "last_nis", None)
                    if nis is not None and np.isfinite(nis):
                        nis = float(nis)
                        metrics["nis_values"].append(nis)
                        if nis > float(getattr(self, "nis_soft_gate", 12.0)):
                            metrics["nis_soft_violations"] += 1
                        if nis > float(getattr(self, "nis_hard_gate", 20.0)):
                            metrics["nis_hard_violations"] += 1
                    mode = getattr(kf, "last_update_mode", None)
                    if mode in metrics["kf_mode_counts"]:
                        metrics["kf_mode_counts"][mode] += 1
                selected_source_id = getattr(agent, "last_selected_source_actor_id", None)
                selected_actor_id = getattr(agent, "last_selected_actor_id", None)
                if candidates and selected_source_id is not None:
                    metrics["leader_frames"] += 1
                    if selected_source_id == metric_target.id:
                        metrics["correct_leader_frames"] += 1
                    else:
                        metrics["wrong_leader_frames"] += 1
                    prev_selected = metrics["prev_selected_actor_id"]
                    if prev_selected is not None and selected_actor_id != prev_selected:
                        metrics["selection_id_switches"] += 1
                    metrics["prev_selected_actor_id"] = selected_actor_id
                if blackout_prev and not blackout_active:
                    recovery_start_frame = frame
                if recovery_start_frame is not None:
                    if kf is not None and getattr(kf, "is_initialized", False) and getattr(kf, "lost_steps", 999) == 0:
                        metrics["recovery_times"].append((frame - recovery_start_frame) * 0.05)
                        recovery_start_frame = None
                blackout_prev = blackout_active
                
                # --- Metrics Collection ---
                # HACK: Access internal state of Agent to get selected ID
                # This depends on agent implementation.
                # Assuming agent.tracker stores the current target ID?
                # Or we can infer it from 'candidates' if we knew which one was picked.
                # But `run_step` doesn't return ID.
                
                # Let's peek into agent.tracker.last_id if it exists?
                # Or agent.kf.id?
                # In `run_closed_loop.py`, `QGIPAgent` has `self.kf`.
                # But `self.kf` is a KalmanTracker, does it store ID?
                # No, `KalmanTracker` stores state `x`.
                
                # Wait, `QGIPAgent.run_step` calls `self.model(...)` which returns `scores`.
                # Then it picks `best_idx`.
                # We can't see `best_idx` from here without modifying `QGIPAgent`.
                
                # FOR NOW: We rely on 'Success' as the ultimate metric.
                # If it switches to Distractor, it will likely fail (distractor is faster/different path).
                # But to count ID switches, we really need the ID.
                
                # Since we can't easily modify Agent in this turn without risking breakage,
                # let's stick to Success/Lost as the primary metric.
                # It's robust enough if Distractor behaves differently (e.g. faster).
                
                ego.apply_control(control)
                self.world.tick()
                
            # Calculate Mean Jerk
            mean_jerk = 0.0
            if len(acc_history) > 1:
                acc_np = np.array(acc_history)
                # diff between frames. dt=0.05
                jerk = np.diff(acc_np, axis=0) / 0.05
                jerk_mag = np.linalg.norm(jerk, axis=1)
                mean_jerk = np.mean(jerk_mag)
            
            print(f"[RESULT] Ep {episode_id}: Success! Jerk={mean_jerk:.2f}", flush=True)
            return self._finish_episode("Success", acc_history, metrics)
            
        except Exception as e:
            print(f"[ERROR] Ep {episode_id}: Exception {e}", flush=True)
            return {
                "Result": "SetupFail",
                "Jerk": 0.0,
                "JerkP95": 0.0,
                "MinDistance": "",
                "MinTTC": "",
                "MinHeadway": "",
                "NearMiss": 0,
                "DropoutFrames": 0,
                "RecoveryTime": "",
                "CandidateFrames": 0,
                "FaultedCandidateFrames": 0,
                "FalsePositiveFrames": 0,
                "FalseNegativeFrames": 0,
            }
        finally:
            for actor in actors:
                if actor and actor.is_alive: actor.destroy()

    def run_benchmark(self, num_episodes=50, log_file="stress_test_100_progress.csv", blind_duration=1.0):
        print(f"[BENCHMARK] START: {num_episodes} Episodes (Blind={blind_duration}s)", flush=True)
        print(f"[BENCHMARK] Logging to: {log_file}", flush=True)
        
        # CSV Logging for long-running stability
        csv_file = log_file
        
        # Check if file exists to resume
        start_ep = 0# Stats
        stats = {
            "Success": 0, "Collision": 0, "Lost": 0, "SetupFail": 0, "ValidDegradation": 0,
            # Diagnostic Metrics
            "GhostActiveSteps": 0, "TotalSteps": 0, "HardResetCount": 0,
            "TotalJerk": 0.0, "JerkCount": 0 # For Mean Jerk Calculation
        }
        
        if os.path.exists(csv_file):
            print(f"[INFO] Found existing log {csv_file}, attempting to resume...", flush=True)
            try:
                with open(csv_file, "r", newline="") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    start_ep = len(rows)
                    for row in rows:
                        res = row.get("Result", "")
                        if res in stats:
                            stats[res] += 1
                        try:
                            j = float(row.get("Jerk", ""))
                            stats["TotalJerk"] += j
                            stats["JerkCount"] += 1
                        except Exception:
                            pass
                                
                print(f"[INFO] Resuming from Episode {start_ep+1}. Current Stats: {stats}", flush=True)
            except Exception as e:
                print(f"[WARN] Failed to resume: {e}. Starting fresh.", flush=True)
                start_ep = 0
                stats = {
                    "Success": 0, "Collision": 0, "Lost": 0, "SetupFail": 0, "ValidDegradation": 0,
                    "GhostActiveSteps": 0, "TotalSteps": 0, "HardResetCount": 0,
                    "TotalJerk": 0.0, "JerkCount": 0
                }
                with open(csv_file, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=EPISODE_CSV_FIELDS)
                    writer.writeheader()
        else:
            # Ensure directory exists
            log_dir = os.path.dirname(csv_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            with open(csv_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=EPISODE_CSV_FIELDS)
                writer.writeheader()
            
        target_episodes = num_episodes # Total target
        # If user passes 300, and we have 175, we run 125 more.
        # But if user passes 125, and we have 175, what does it mean?
        # Usually num_episodes means "Target Total".
        
        if start_ep >= target_episodes:
            print(f"[INFO] Already completed {start_ep} episodes. Target is {target_episodes}. Exiting.", flush=True)
            return

        for i in range(start_ep, target_episodes):
            episode_row = self.run_episode(i+1)
            res = episode_row["Result"]
            jerk = float(episode_row.get("Jerk") or 0.0)
            stats[res] += 1
            if jerk > 0:
                stats["TotalJerk"] += jerk
                stats["JerkCount"] += 1
            
            # Print Progress
            total = i + 1
            sr_strict = stats['Success'] / total
            sr_loose = (stats['Success'] + stats['ValidDegradation']) / total
            avg_jerk = stats["TotalJerk"] / max(1, stats["JerkCount"])
            
            print(f"STATS | Ep {i+1} | Result: {res} | Strict SR: {sr_strict:.1%} | Loose SR: {sr_loose:.1%} | Avg Jerk: {avg_jerk:.2f}", flush=True)
            
            # Append to CSV
            try:
                row = dict(episode_row)
                row["Episode"] = i + 1
                row["StrictSR"] = f"{sr_strict:.4f}"
                row["LooseSR"] = f"{sr_loose:.4f}"
                with open(csv_file, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=EPISODE_CSV_FIELDS, extrasaction="ignore")
                    writer.writerow(row)
            except Exception as exc:
                print(f"[WARN] Failed to append CSV row: {exc}", flush=True)
            
        print("="*50, flush=True)
        print("FINAL RESULTS:", flush=True)
        print(stats, flush=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--num-episodes", type=int, default=50)
    parser.add_argument("--log-file", type=str, default="stress_test_100_progress.csv")
    parser.add_argument("--blind-duration", type=float, default=1.0)
    parser.add_argument("--town", type=str, default="Town05")
    parser.add_argument("--qgip-model-path", type=str, default="checkpoints/best_model.pth")
    parser.add_argument("--leader-ckpt", type=str, default="checkpoints/v7/llc_epoch_20.pth")
    parser.add_argument("--ablation-no-query", action="store_true")
    parser.add_argument("--ambiguity-test", action="store_true")
    parser.add_argument("--lane-gating", action="store_true", help="Enable symbolic lane gating")
    parser.add_argument("--blind-interval", type=float, default=5.0)
    parser.add_argument("--observation-noise", type=float, default=0.0)
    parser.add_argument("--velocity-noise", type=float, default=0.0)
    parser.add_argument("--delay-ms", type=float, default=0.0)
    parser.add_argument("--false-positive-rate", type=float, default=0.0)
    parser.add_argument("--false-negative-rate", type=float, default=0.0)
    parser.add_argument("--id-switch-probability", type=float, default=0.0)
    parser.add_argument("--near-miss-distance", type=float, default=5.0)
    parser.add_argument("--near-miss-ttc", type=float, default=1.0)
    parser.add_argument("--near-miss-headway", type=float, default=0.8)
    parser.add_argument("--nis-soft-gate", type=float, default=12.0)
    parser.add_argument("--nis-hard-gate", type=float, default=20.0)
    parser.add_argument("--scenario-profile", type=str, default="following")
    parser.add_argument("--query-profile", type=str, default="follow")
    parser.add_argument("--query-delay-frames", type=int, default=0)
    parser.add_argument("--weather-profile", type=str, default="clear")
    parser.add_argument("--sensor-profile", type=str, default="none")
    parser.add_argument("--random-seed", type=int, default=7)
    args = parser.parse_args()
    
    try:
        os.environ["QGIP_MODEL_PATH"] = args.qgip_model_path
        os.environ["QGIP_LEADER_CKPT"] = args.leader_ckpt
        os.environ["QGIP_NIS_SOFT_GATE"] = str(args.nis_soft_gate)
        os.environ["QGIP_NIS_HARD_GATE"] = str(args.nis_hard_gate)
        evaluator = BatchEvaluator(town=args.town, model_path=args.qgip_model_path)
        evaluator.ambiguity_test = args.ambiguity_test
        evaluator.lane_gating = args.lane_gating
        
        if args.ambiguity_test:
            print("[INFO] AMBIGUITY TEST ENABLED: Spawning Distractors!", flush=True)
            if args.lane_gating:
                print("[INFO] LANE GATING ENABLED: Filtering lateral offsets > 1.5m", flush=True)
            
        # Inject Ablation Flag
        if args.ablation_no_query:
            print("[WARN] ABLATION MODE: NO_QUERY (legacy query+edge conditioning disabled)", flush=True)
            # Need to pass this to the agent -> model
            # This is tricky because Agent init creates the model.
            # We might need to monkey-patch or pass it via Agent.
            QGIPAgent.ABLATION_NO_QUERY = True
            
        # Inject blind duration into evaluator (hacky but works)
        evaluator.blind_duration = args.blind_duration
        evaluator.blind_interval_s = args.blind_interval
        evaluator.observation_noise_m = args.observation_noise
        evaluator.velocity_noise_mps = args.velocity_noise
        evaluator.delay_ms = args.delay_ms
        evaluator.false_positive_rate = args.false_positive_rate
        evaluator.false_negative_rate = args.false_negative_rate
        evaluator.id_switch_probability = args.id_switch_probability
        evaluator.near_miss_distance_m = args.near_miss_distance
        evaluator.near_miss_ttc_s = args.near_miss_ttc
        evaluator.near_miss_headway_s = args.near_miss_headway
        evaluator.nis_soft_gate = args.nis_soft_gate
        evaluator.nis_hard_gate = args.nis_hard_gate
        evaluator.scenario_profile = args.scenario_profile
        evaluator.query_profile = args.query_profile
        evaluator.query_delay_frames = args.query_delay_frames
        evaluator.weather_profile = args.weather_profile
        evaluator.sensor_profile = args.sensor_profile
        evaluator.random_seed = args.random_seed
        evaluator.run_benchmark(args.num_episodes, log_file=args.log_file, blind_duration=args.blind_duration)
    except Exception as e:
        print(f"CRITICAL: {e}", flush=True)
        raise
    finally:
        if "evaluator" in locals():
            evaluator.close()
