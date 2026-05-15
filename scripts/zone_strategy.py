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


def label_zone_points(
    points: np.ndarray,
    axis_index: int,
    bounds: np.ndarray,
    boundaries: dict[str, dict[str, float]],
    edge_margin: float,
    curve_config: dict[str, float | bool | str] | None = None,
) -> np.ndarray:
    labels = np.full(len(points), "toe", dtype=object)
    axis_values = points[:, axis_index]
    near_x = (points[:, 0] - bounds[0][0] <= edge_margin) | (bounds[1][0] - points[:, 0] <= edge_margin)
    near_y = (points[:, 1] - bounds[0][1] <= edge_margin) | (bounds[1][1] - points[:, 1] <= edge_margin)

    merged_curve = resolve_curve_config(curve_config)
    inner_coordinate, _inner_side = inner_outer_coordinates(points, bounds, axis_index, boundaries, merged_curve)
    forefoot_center_width = float(merged_curve["forefoot_center_width_ratio"])
    center_min = max((1.0 - forefoot_center_width) / 2.0, 0.0)
    center_max = min(1.0 - center_min, 1.0)

    if bool(merged_curve["enabled"]):
        bias = center_bias(points, bounds, axis_index, merged_curve)
        heel_max = boundaries["heel"]["max_mm"] + float(merged_curve["heel_curve_mm"]) * bias
        arch_max = boundaries["arch"]["max_mm"] + float(merged_curve["arch_curve_mm"]) * bias
        forefoot_max = boundaries["forefoot"]["max_mm"] - float(merged_curve["toe_curve_mm"]) * bias
    else:
        heel_max = np.full(len(points), boundaries["heel"]["max_mm"], dtype=float)
        arch_max = np.full(len(points), boundaries["arch"]["max_mm"], dtype=float)
        forefoot_max = np.full(len(points), boundaries["forefoot"]["max_mm"], dtype=float)

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
    labels[near_x | near_y] = "edgeFrame"
    return labels
