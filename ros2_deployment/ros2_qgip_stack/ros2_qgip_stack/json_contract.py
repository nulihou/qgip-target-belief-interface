"""JSON message helpers for early ROS2 experiments.

The preflight stack intentionally uses std_msgs/String plus these schemas so
that the robots can run before custom messages are frozen.
"""

from __future__ import annotations

import json
import math
from typing import Any, Iterable


def loads_payload(text: str) -> dict[str, Any]:
    if not text:
        return {}
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("JSON payload must be an object")
    return value


def dumps_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def normalize_detection(raw: dict[str, Any], fallback_stamp_s: float = 0.0) -> dict[str, Any]:
    object_id = raw.get("id", raw.get("object_id", "unknown"))
    return {
        "id": str(object_id),
        "class_name": str(raw.get("class_name", "leader")),
        "x": _finite_float(raw.get("x", 0.0)),
        "y": _finite_float(raw.get("y", 0.0)),
        "vx": _finite_float(raw.get("vx", 0.0)),
        "vy": _finite_float(raw.get("vy", 0.0)),
        "confidence": float(min(1.0, max(0.0, _finite_float(raw.get("confidence", 1.0))))),
        "stamp_s": _finite_float(raw.get("stamp_s", fallback_stamp_s)),
    }


def normalize_detections(payload: dict[str, Any]) -> list[dict[str, Any]]:
    stamp_s = _finite_float(payload.get("stamp_s", 0.0))
    detections = payload.get("detections", [])
    if not isinstance(detections, Iterable) or isinstance(detections, (str, bytes)):
        return []
    return [normalize_detection(item, stamp_s) for item in detections if isinstance(item, dict)]


def select_front_leader(
    detections: list[dict[str, Any]],
    leader_id_filter: str = "",
    min_confidence: float = 0.0,
    max_abs_y_m: float = 10.0,
    front_only: bool = True,
) -> dict[str, Any] | None:
    candidates = []
    for det in detections:
        if leader_id_filter and det["id"] != leader_id_filter:
            continue
        if det["confidence"] < min_confidence:
            continue
        if front_only and det["x"] <= 0.0:
            continue
        if abs(det["y"]) > max_abs_y_m:
            continue
        candidates.append(det)
    if not candidates:
        return None
    return max(candidates, key=lambda d: (d["confidence"], -abs(d["y"]), -abs(d["x"] - 1.0)))


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default
