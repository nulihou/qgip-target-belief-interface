"""Pure-Python contract tests for the ROS2 QGIP preflight package.

These tests intentionally avoid importing rclpy or ROS2 message modules so that
the numerical and JSON contracts can be exercised by colcon/pytest before node
integration tests are run in a full ROS2 workspace.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from ros2_qgip_stack.fault_injection_core import Detection, DetectionFaultInjector, FaultConfig
from ros2_qgip_stack.json_contract import dumps_payload, loads_payload, normalize_detection, normalize_detections, select_front_leader
from ros2_qgip_stack.pop_nis_kf_core import NISGatedPOP, POPConfig, TrackMode


def test_json_contract_normalizes_nonfinite_and_clamps_confidence() -> None:
    payload = {
        "stamp_s": 1.2,
        "detections": [
            {"object_id": "robot_2", "x": "nan", "y": 0.1, "vx": 0.2, "confidence": 3.0},
            {"id": "robot_3", "x": 1.4, "y": float("inf"), "confidence": -2.0},
        ],
    }

    detections = normalize_detections(payload)

    assert detections[0]["id"] == "robot_2"
    assert detections[0]["x"] == 0.0
    assert detections[0]["confidence"] == 1.0
    assert detections[1]["id"] == "robot_3"
    assert detections[1]["y"] == 0.0
    assert detections[1]["confidence"] == 0.0


def test_json_roundtrip_rejects_non_object_payload() -> None:
    text = dumps_payload({"mode": "TRACKING", "safety_stop": False})

    assert loads_payload(text)["mode"] == "TRACKING"
    with pytest.raises(ValueError):
        loads_payload(json.dumps(["not", "an", "object"]))


def test_select_front_leader_prefers_confident_centered_front_candidate() -> None:
    detections = [
        normalize_detection({"id": "behind", "x": -0.2, "y": 0.0, "confidence": 1.0}),
        normalize_detection({"id": "wide", "x": 1.0, "y": 3.0, "confidence": 0.99}),
        normalize_detection({"id": "leader", "x": 1.3, "y": 0.1, "confidence": 0.92}),
        normalize_detection({"id": "distractor", "x": 1.0, "y": 0.4, "confidence": 0.85}),
    ]

    selected = select_front_leader(detections, min_confidence=0.5, max_abs_y_m=1.5)

    assert selected is not None
    assert selected["id"] == "leader"


def test_fault_injector_dropout_delay_and_id_switch() -> None:
    detections = [
        Detection("robot_2", x=1.0, y=0.0, confidence=0.9),
        Detection("robot_3", x=1.2, y=0.5, confidence=0.8),
    ]

    dropout = DetectionFaultInjector(FaultConfig(dropout_period_s=1.0, dropout_duration_s=0.2))
    assert dropout.in_dropout_window(0.1)
    assert dropout.apply(detections, 0.1) == []

    delay = DetectionFaultInjector(FaultConfig(delay_s=0.1))
    assert delay.apply(detections, 0.0) == []
    delayed = delay.apply(detections, 0.1)
    assert [det.object_id for det in delayed] == ["robot_2", "robot_3"]

    switcher = DetectionFaultInjector(FaultConfig(id_switch_probability=1.0, random_seed=3))
    switched = switcher.apply(detections, 0.3)
    assert [det.object_id for det in switched] == ["robot_3", "robot_2"]


def test_pop_tracker_progresses_tracking_to_ghost_to_lost() -> None:
    tracker = NISGatedPOP(POPConfig(dt=0.1, ghost_horizon_s=0.2, lost_timeout_s=0.3))
    tracker.reset(np.array([1.0, 0.0, 0.2, 0.0]), leader_id="robot_2")

    states = [tracker.update(None, confidence=0.0).mode for _ in range(4)]

    assert TrackMode.GHOST in states
    assert states[-1] == TrackMode.LOST


def test_pop_soft_and_hard_nis_gates() -> None:
    soft = NISGatedPOP(POPConfig(dt=0.1, nis_soft_threshold=2.0, nis_hard_threshold=4.0, high_confidence_threshold=0.95))
    soft.reset(np.zeros(4), leader_id="robot_2")
    soft_state = soft.update(np.array([0.5, 0.0, 0.0, 0.0]), confidence=0.8, leader_id="robot_2")

    hard = NISGatedPOP(POPConfig(dt=0.1, nis_soft_threshold=2.0, nis_hard_threshold=4.0, high_confidence_threshold=0.85))
    hard.reset(np.zeros(4), leader_id="robot_2")
    hard_measurement = np.array([0.8, 0.1, 0.0, 0.0])
    hard_state = hard.update(hard_measurement, confidence=0.96, leader_id="robot_2")

    assert soft_state.mode == TrackMode.DEGRADED
    assert soft_state.nis > soft.cfg.nis_soft_threshold
    assert hard_state.mode == TrackMode.TRACKING
    assert np.allclose(hard_state.x, hard_measurement)


def test_pop_covariance_remains_finite_symmetric_psd() -> None:
    tracker = NISGatedPOP()
    tracker.reset(np.array([1.0, 0.0, 0.2, 0.0]), leader_id="robot_2")
    for k in range(10):
        state = tracker.update(np.array([1.0 + 0.02 * k, 0.01, 0.2, 0.0]), confidence=0.9, leader_id="robot_2")

    eigenvalues = np.linalg.eigvalsh(state.P)

    assert np.all(np.isfinite(state.P))
    assert np.allclose(state.P, state.P.T, atol=1e-9)
    assert float(np.min(eigenvalues)) >= -1e-9
    assert math.isfinite(state.nis)
