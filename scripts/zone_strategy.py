from __future__ import annotations

from typing import Any

import numpy as np


DEFAULT_CURVE_CONFIG: dict[str, float | bool | str] = {
    "enabled": True,
    "heel_curve_mm": 12.0,
    "arch_curve_mm": 10.0,
    "toe_curve_mm": 12.0,
    "center_power": 1.6,
    "inner_side": "auto",
    "heel_at": "auto",
    "forefoot_center_width_ratio": 0.28,
}


def resolve_curve_config(config: dict[str, Any] | None = None) -> dict[str, float | bool | str]:
    merged = dict(DEFAULT_CURVE_CONFIG)
    if config:
        merged.update(config)
    return merged


def lateral_axis_index(axis_index: int) -> int:
    return 0 if axis_index != 0 else 1


def normalized_lateral(points: np.ndarray, bounds: np.ndarray, axis_index: int) -> np.ndarray:
    lateral_index = lateral_axis_index(axis_index)
    minimum = float(bounds[0][lateral_index])
    maximum = float(bounds[1][lateral_index])
    span = max(maximum - minimum, 1e-6)
    return (points[:, lateral_index] - minimum) / span


def center_bias(points: np.ndarray, bounds: np.ndarray, axis_index: int, curve_config: dict[str, float | bool | str]) -> np.ndarray:
    normalized = normalized_lateral(points, bounds, axis_index)
    centered = np.clip(1.0 - np.abs((normalized * 2.0) - 1.0), 0.0, 1.0)
    power = float(curve_config["center_power"])
    return centered**power


def resolve_inner_side(
    points: np.ndarray,
    bounds: np.ndarray,
    axis_index: int,
    boundaries: dict[str, dict[str, float]],
    curve_config: dict[str, float | bool | str],
) -> str:
    configured = str(curve_config.get("inner_side", "auto"))
    if configured in {"min", "max"}:
        return configured

    lateral = normalized_lateral(points, bounds, axis_index)
    axis_values = points[:, axis_index]
    arch_band = (axis_values >= boundaries["arch"]["min_mm"]) & (axis_values <= boundaries["arch"]["max_mm"])
    arch_core = arch_band & (lateral >= 0.1) & (lateral <= 0.9)
    effective_band = arch_core if np.any(arch_core) else arch_band
    lower_count = int(np.count_nonzero(effective_band & (lateral <= 0.5)))
    upper_count = int(np.count_nonzero(effective_band & (lateral > 0.5)))
    return "min" if lower_count < upper_count else "max"


def inner_outer_coordinates(
    points: np.ndarray,
    bounds: np.ndarray,
    axis_index: int,
    boundaries: dict[str, dict[str, float]],
    curve_config: dict[str, float | bool | str],
) -> tuple[np.ndarray, str]:
    normalized = normalized_lateral(points, bounds, axis_index)
    inner_side = resolve_inner_side(points, bounds, axis_index, boundaries, curve_config)
    if inner_side == "max":
        return normalized, inner_side
    return 1.0 - normalized, inner_side


def resolve_heel_at(configured: str, footprint: np.ndarray, long_axis_index: int, pitch: float) -> str:
    """Pick the heel end. ``auto`` compares end widths and keeps the narrower end."""
    choice = str(configured or "auto")
    if choice in {"min", "max"}:
        return choice
    if choice != "auto":
        raise ValueError("zone_shape heel_at must be one of: auto, min, max")
    if long_axis_index not in {0, 1}:
        return "min"

    widths = _end_width_profile(np.asarray(footprint, dtype=bool), long_axis_index, float(pitch))
    occupied = np.flatnonzero(widths > 0.0)
    if occupied.size == 0:
        return "min"

    start = int(occupied[0])
    end = int(occupied[-1])
    band = max(int(round((end - start + 1) * 0.25)), 1)
    low_width = float(np.max(widths[start : start + band]))
    high_width = float(np.max(widths[end - band + 1 : end + 1]))
    if high_width + float(pitch) < low_width:
        return "max"
    return "min"


def _end_width_profile(footprint: np.ndarray, long_axis_index: int, pitch: float) -> np.ndarray:
    lines = footprint if long_axis_index == 0 else footprint.T
    occupied = lines.any(axis=1)
    first = lines.argmax(axis=1)
    last = lines.shape[1] - 1 - lines[:, ::-1].argmax(axis=1)
    widths = (last - first + 1).astype(float) * pitch
    return np.where(occupied, widths, 0.0)


def _label_heel_direction(curve_config: dict[str, float | bool | str]) -> str:
    heel_at = str(curve_config.get("heel_at", "min"))
    if heel_at == "auto":
        return "min"
    if heel_at not in {"min", "max"}:
        raise ValueError("zone_shape heel_at must be one of: auto, min, max")
    return heel_at


def _values_from_heel(values: np.ndarray, bounds: np.ndarray, axis_index: int, heel_at: str) -> np.ndarray:
    coordinates = np.asarray(values, dtype=float)
    if heel_at != "max":
        return coordinates
    low = float(bounds[0][axis_index])
    high = float(bounds[1][axis_index])
    return (low + high) - coordinates


def _boundaries_from_heel(
    boundaries: dict[str, dict[str, float]],
    bounds: np.ndarray,
    axis_index: int,
    heel_at: str,
) -> dict[str, dict[str, float]]:
    if heel_at != "max":
        return boundaries
    low = float(bounds[0][axis_index])
    high = float(bounds[1][axis_index])
    flipped: dict[str, dict[str, float]] = {}
    for name, span in boundaries.items():
        flipped[name] = {
            "min_mm": (low + high) - float(span["max_mm"]),
            "max_mm": (low + high) - float(span["min_mm"]),
        }
    return flipped


def label_zone_points(
    points: np.ndarray,
    axis_index: int,
    bounds: np.ndarray,
    boundaries: dict[str, dict[str, float]],
    edge_margin: float,
    curve_config: dict[str, float | bool | str] | None = None,
    outline_distance_mm: np.ndarray | None = None,
) -> np.ndarray:
    """Label anatomical zones. The rim follows outline distance, not the bounding box."""
    if outline_distance_mm is None:
        raise ValueError("outline_distance_mm is required; edgeFrame follows the foot outline")

    distances = np.asarray(outline_distance_mm, dtype=float)
    if distances.shape != (len(points),):
        raise ValueError("outline_distance_mm must have one value per point")

    labels = np.full(len(points), "toe", dtype=object)
    merged_curve = resolve_curve_config(curve_config)
    heel_at = _label_heel_direction(merged_curve)
    axis_values = _values_from_heel(points[:, axis_index], bounds, axis_index, heel_at)
    working_boundaries = _boundaries_from_heel(boundaries, bounds, axis_index, heel_at)
    inner_coordinate, _inner_side = inner_outer_coordinates(points, bounds, axis_index, boundaries, merged_curve)
    forefoot_center_width = float(merged_curve["forefoot_center_width_ratio"])
    center_min = max((1.0 - forefoot_center_width) / 2.0, 0.0)
    center_max = min(1.0 - center_min, 1.0)

    if bool(merged_curve["enabled"]):
        bias = center_bias(points, bounds, axis_index, merged_curve)
        heel_max = working_boundaries["heel"]["max_mm"] + float(merged_curve["heel_curve_mm"]) * bias
        arch_max = working_boundaries["arch"]["max_mm"] + float(merged_curve["arch_curve_mm"]) * bias
        forefoot_max = working_boundaries["forefoot"]["max_mm"] - float(merged_curve["toe_curve_mm"]) * bias
    else:
        heel_max = np.full(len(points), working_boundaries["heel"]["max_mm"], dtype=float)
        arch_max = np.full(len(points), working_boundaries["arch"]["max_mm"], dtype=float)
        forefoot_max = np.full(len(points), working_boundaries["forefoot"]["max_mm"], dtype=float)

    heel_mask = axis_values <= heel_max
    arch_mask = (axis_values > heel_max) & (axis_values <= arch_max)
    forefoot_mask = (axis_values > arch_max) & (axis_values <= forefoot_max)

    labels[heel_mask & (inner_coordinate >= 0.5)] = "innerHeel"
    labels[heel_mask & (inner_coordinate < 0.5)] = "outerHeel"
    labels[arch_mask & (inner_coordinate >= 0.5)] = "innerArch"
    labels[arch_mask & (inner_coordinate < 0.5)] = "outerArch"
    labels[forefoot_mask & (inner_coordinate > center_max)] = "innerForefoot"
    labels[forefoot_mask & (inner_coordinate >= center_min) & (inner_coordinate <= center_max)] = "centralForefoot"
    labels[forefoot_mask & (inner_coordinate < center_min)] = "outerForefoot"
    labels[distances <= float(edge_margin)] = "edgeFrame"
    return labels
