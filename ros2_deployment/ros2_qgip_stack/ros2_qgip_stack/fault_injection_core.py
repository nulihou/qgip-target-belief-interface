#!/usr/bin/env python3
"""Installable copy of the detection fault-injection core."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Deque, Iterable, List, Optional

import numpy as np


@dataclass
class Detection:
    object_id: str
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    confidence: float = 1.0
    class_name: str = "leader"
    stamp_s: float = 0.0


@dataclass
class FaultConfig:
    dropout_period_s: float = 5.0
    dropout_duration_s: float = 0.0
    position_noise_std_m: float = 0.0
    velocity_noise_std_mps: float = 0.0
    false_positive_rate: float = 0.0
    false_negative_rate: float = 0.0
    confidence_scale: float = 1.0
    delay_s: float = 0.0
    id_switch_probability: float = 0.0
    random_seed: int = 7


class DetectionFaultInjector:
    def __init__(self, config: FaultConfig):
        self.cfg = config
        self.rng = np.random.default_rng(config.random_seed)
        self.delay_queue: Deque[tuple[float, List[Detection]]] = deque()

    def in_dropout_window(self, stamp_s: float) -> bool:
        if self.cfg.dropout_duration_s <= 0.0:
            return False
        phase = stamp_s % self.cfg.dropout_period_s
        return phase < self.cfg.dropout_duration_s

    def apply(self, detections: Iterable[Detection], stamp_s: float) -> List[Detection]:
        current = [replace(det) for det in detections]

        if self.in_dropout_window(stamp_s):
            current = []
        else:
            current = self._apply_false_negative(current)
            current = self._apply_noise(current)
            current = self._apply_confidence_scale(current)
            current = self._apply_id_switch(current)
            current = self._apply_false_positive(current, stamp_s)

        if self.cfg.delay_s > 0.0:
            self.delay_queue.append((stamp_s, current))
            delayed: Optional[List[Detection]] = None
            while self.delay_queue and stamp_s - self.delay_queue[0][0] >= self.cfg.delay_s:
                _, delayed = self.delay_queue.popleft()
            return delayed if delayed is not None else []

        return current

    def _apply_false_negative(self, detections: List[Detection]) -> List[Detection]:
        if self.cfg.false_negative_rate <= 0.0:
            return detections
        return [det for det in detections if self.rng.random() >= self.cfg.false_negative_rate]

    def _apply_noise(self, detections: List[Detection]) -> List[Detection]:
        for det in detections:
            if self.cfg.position_noise_std_m > 0.0:
                det.x += float(self.rng.normal(0.0, self.cfg.position_noise_std_m))
                det.y += float(self.rng.normal(0.0, self.cfg.position_noise_std_m))
            if self.cfg.velocity_noise_std_mps > 0.0:
                det.vx += float(self.rng.normal(0.0, self.cfg.velocity_noise_std_mps))
                det.vy += float(self.rng.normal(0.0, self.cfg.velocity_noise_std_mps))
        return detections

    def _apply_confidence_scale(self, detections: List[Detection]) -> List[Detection]:
        for det in detections:
            det.confidence = float(np.clip(det.confidence * self.cfg.confidence_scale, 0.0, 1.0))
        return detections

    def _apply_id_switch(self, detections: List[Detection]) -> List[Detection]:
        if len(detections) < 2 or self.cfg.id_switch_probability <= 0.0:
            return detections
        if self.rng.random() < self.cfg.id_switch_probability:
            detections[0].object_id, detections[1].object_id = detections[1].object_id, detections[0].object_id
        return detections

    def _apply_false_positive(self, detections: List[Detection], stamp_s: float) -> List[Detection]:
        if self.cfg.false_positive_rate <= 0.0:
            return detections
        if self.rng.random() < self.cfg.false_positive_rate:
            detections.append(
                Detection(
                    object_id=f"fp_{stamp_s:.2f}",
                    x=float(self.rng.uniform(0.4, 2.0)),
                    y=float(self.rng.uniform(-0.8, 0.8)),
                    confidence=float(self.rng.uniform(0.3, 0.8)),
                    class_name="false_positive",
                    stamp_s=stamp_s,
                )
            )
        return detections
