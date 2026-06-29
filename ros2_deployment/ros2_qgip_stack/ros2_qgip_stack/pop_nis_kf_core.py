#!/usr/bin/env python3
"""Installable POP / NIS-gated Kalman filter core."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class TrackMode(str, Enum):
    TRACKING = "TRACKING"
    DEGRADED = "DEGRADED"
    GHOST = "GHOST"
    LOST = "LOST"


@dataclass
class POPConfig:
    dt: float = 0.05
    confidence_threshold: float = 0.5
    high_confidence_threshold: float = 0.85
    nis_soft_threshold: float = 12.0
    nis_hard_threshold: float = 20.0
    r_inflation: float = 10.0
    ghost_horizon_s: float = 1.0
    lost_timeout_s: float = 1.5
    process_noise_diag: tuple[float, float, float, float] = (0.01, 0.01, 0.05, 0.05)
    measurement_noise_diag: tuple[float, float, float, float] = (0.02, 0.02, 0.08, 0.08)


@dataclass
class POPState:
    x: np.ndarray
    P: np.ndarray
    mode: TrackMode
    nis: float
    ghost_age_s: float
    leader_id: Optional[str] = None


class NISGatedPOP:
    """4D constant-velocity POP tracker with NIS gating."""

    def __init__(self, config: POPConfig | None = None):
        self.cfg = config or POPConfig()
        self.F = np.array(
            [
                [1.0, 0.0, self.cfg.dt, 0.0],
                [0.0, 1.0, 0.0, self.cfg.dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=float,
        )
        self.H = np.eye(4)
        self.Q = np.diag(self.cfg.process_noise_diag)
        self.R = np.diag(self.cfg.measurement_noise_diag)
        self.x = np.zeros(4, dtype=float)
        self.P = np.eye(4, dtype=float)
        self.mode = TrackMode.LOST
        self.ghost_age_s = self.cfg.lost_timeout_s
        self.nis = float("nan")
        self.leader_id: Optional[str] = None

    def reset(self, measurement: np.ndarray, leader_id: Optional[str] = None) -> POPState:
        z = np.asarray(measurement, dtype=float).reshape(4)
        self.x = z.copy()
        self.P = np.diag([0.05, 0.05, 0.2, 0.2])
        self.mode = TrackMode.TRACKING
        self.ghost_age_s = 0.0
        self.nis = 0.0
        self.leader_id = leader_id
        return self.state()

    def predict(self) -> None:
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, measurement: Optional[np.ndarray], confidence: float, leader_id: Optional[str] = None) -> POPState:
        self.predict()

        if measurement is None or confidence < self.cfg.confidence_threshold:
            self.ghost_age_s += self.cfg.dt
            self.mode = TrackMode.GHOST if self.ghost_age_s <= self.cfg.ghost_horizon_s else TrackMode.LOST
            self.nis = float("nan")
            return self.state()

        z = np.asarray(measurement, dtype=float).reshape(4)
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + self.R
        self.nis = float(y.T @ np.linalg.inv(S) @ y)

        if self.nis > self.cfg.nis_hard_threshold and confidence >= self.cfg.high_confidence_threshold:
            self.x = z.copy()
            self.P = np.diag([0.05, 0.05, 0.2, 0.2])
            self.mode = TrackMode.TRACKING
            self.ghost_age_s = 0.0
            self.leader_id = leader_id
            return self.state()

        R_eff = self.R * self.cfg.r_inflation if self.nis > self.cfg.nis_soft_threshold else self.R
        S_eff = self.H @ self.P @ self.H.T + R_eff
        K = self.P @ self.H.T @ np.linalg.inv(S_eff)
        self.x = self.x + K @ y
        self.P = (np.eye(4) - K @ self.H) @ self.P
        self.mode = TrackMode.DEGRADED if self.nis > self.cfg.nis_soft_threshold else TrackMode.TRACKING
        self.ghost_age_s = 0.0
        self.leader_id = leader_id
        return self.state()

    def state(self) -> POPState:
        return POPState(
            x=self.x.copy(),
            P=self.P.copy(),
            mode=self.mode,
            nis=self.nis,
            ghost_age_s=self.ghost_age_s,
            leader_id=self.leader_id,
        )
