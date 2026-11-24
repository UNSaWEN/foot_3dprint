"""Shared voxelization, world-space meshing, and column masks.

Marching cubes is evaluated in voxel index space (pitch = 1). The voxel grid
transform already contains the pitch scale and the world translation, so the
mesh is placed by applying that matrix once.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import ndimage


VERTICAL_AXIS = 2


def load_closed_mesh(path):
    """Load one closed blank with ``process=False`` so world placement is kept."""
    from common import try_load_trimesh

    trimesh = try_load_trimesh()
    if trimesh is None:
        raise RuntimeError("trimesh is required to load a closed insole mesh")

    mesh = trimesh.load_mesh(path, process=False)
    if isinstance(mesh, trimesh.Scene):
        geometries = tuple(mesh.geometry.values())
        if not geometries:
            raise ValueError(f"Mesh scene is empty: {path}")
        mesh = trimesh.util.concatenate(geometries)
    return mesh


def voxelize_filled(mesh, pitch: float):
    return mesh.voxelized(float(pitch)).fill()


def as_transform_matrix(transform) -> np.ndarray:
    """Accept a voxel grid, a transform wrapper, or a raw 4x4 matrix."""
    if hasattr(transform, "transform"):
        transform = transform.transform
    if hasattr(transform, "matrix"):
        transform = transform.matrix
    matrix = np.asarray(transform, dtype=float)
    if matrix.shape != (4, 4):
        raise ValueError(f"Expected a 4x4 voxel transform, got {matrix.shape}")
    return matrix


def ensure_voxel_budget(shape, max_voxels: int) -> None:
    if math.prod(shape) > int(max_voxels):
        raise RuntimeError(
            f"Voxel grid too large for current limits: {tuple(shape)} > {max_voxels} voxels"
        )


def voxel_world_points(voxelized):
    """Return voxel indices and the same samples in world coordinates."""
    import trimesh

    indices = np.indices(np.asarray(voxelized.matrix).shape).reshape(3, -1).T
    points = trimesh.transform_points(indices.astype(float), as_transform_matrix(voxelized))
    return indices, points


def mesh_from_voxel_mask(mask: np.ndarray, transform):
    """Mesh a voxel mask and return it in the same world frame as the blank."""
    from trimesh.voxel.ops import matrix_to_marching_cubes

    meshed = matrix_to_marching_cubes(np.asarray(mask, dtype=bool), pitch=1.0)
    meshed.apply_transform(as_transform_matrix(transform))
    return meshed


def column_outline_distance_mm(inside_mask: np.ndarray, pitch: float) -> np.ndarray:
    """Distance from each voxel column to the plantar outline, in millimetres.

    Horizontal voxel axes are 0 and 1. Outside columns are ``inf`` so they are
    not treated as an edge. A False border is padded before the distance
    transform so a footprint that fills the grid still has an outline.
    """
    inside = np.asarray(inside_mask, dtype=bool)
    if inside.ndim != 3:
        raise ValueError("inside_mask must be a 3D voxel grid")

    footprint = np.any(inside, axis=VERTICAL_AXIS)
    padded = np.pad(footprint, 1, mode="constant", constant_values=False)
    distance_mm = ndimage.distance_transform_edt(padded)[1:-1, 1:-1] * float(pitch)
    distance_mm = np.where(footprint, distance_mm, np.inf)
    return np.repeat(distance_mm[:, :, None], inside.shape[VERTICAL_AXIS], axis=VERTICAL_AXIS)


def outline_distance_for_points(points: np.ndarray, inside_mask: np.ndarray, transform, pitch: float) -> np.ndarray:
    """Sample column outline distance at arbitrary world points.

    One extra voxel of neighborhood is included so vertices that land just
    outside the voxel shell still see the rim. Export labeling uses
    ``column_outline_distance_mm`` directly and does not dilate.
    """
    distance_2d = column_outline_distance_mm(inside_mask, pitch)[:, :, 0]
    expanded = ndimage.minimum_filter(np.where(np.isfinite(distance_2d), distance_2d, 1.0e9), size=3)
    expanded = np.where(expanded >= 1.0e8, np.inf, expanded)

    matrix = as_transform_matrix(transform)
    scale = np.diag(matrix[:2, :2])
    scale = np.where(np.abs(scale) < 1.0e-9, 1.0, scale)
    indices = (np.asarray(points, dtype=float)[:, :2] - matrix[:2, 3]) / scale
    rounded = np.rint(indices).astype(int)

    distances = np.full(len(points), np.inf, dtype=float)
    valid = (
        (rounded[:, 0] >= 0)
        & (rounded[:, 0] < expanded.shape[0])
        & (rounded[:, 1] >= 0)
        & (rounded[:, 1] < expanded.shape[1])
    )
    distances[valid] = expanded[rounded[valid, 0], rounded[valid, 1]]
    return distances


def local_surface_mask(inside_mask: np.ndarray, layers: int, surface: str) -> np.ndarray:
    """Keep the N inside layers at the top or bottom of each horizontal column."""
    inside = np.asarray(inside_mask, dtype=bool)
    if inside.ndim != 3:
        raise ValueError("inside_mask must be a 3D voxel grid")
    count = int(layers)
    if count <= 0:
        return np.zeros(inside.shape, dtype=bool)
    if surface == "bottom":
        return _layers_from_column_start(inside, count)
    if surface == "top":
        return _layers_from_column_start(inside[:, :, ::-1], count)[:, :, ::-1]
    raise ValueError(f"Unsupported surface: {surface}")


def _layers_from_column_start(inside: np.ndarray, count: int) -> np.ndarray:
    has_voxel = inside.any(axis=VERTICAL_AXIS)
    first = np.argmax(inside, axis=VERTICAL_AXIS)
    depth = np.arange(inside.shape[VERTICAL_AXIS])
    window = (depth[None, None, :] >= first[:, :, None]) & (depth[None, None, :] < first[:, :, None] + count)
    return has_voxel[:, :, None] & window & inside


def voxel_zone_labels(
    mesh,
    zones: dict[str, Any],
    *,
    pitch: float,
    edge_margin: float,
    curve_config: dict[str, Any],
    max_voxels: int | None = None,
):
    """Voxelize one closed blank and label every voxel, including the outline rim."""
    from zone_strategy import label_zone_points

    voxelized = voxelize_filled(mesh, pitch)
    inside = np.asarray(voxelized.matrix, dtype=bool)
    if max_voxels is not None:
        ensure_voxel_budget(inside.shape, max_voxels)

    _indices, points = voxel_world_points(voxelized)
    long_axis = zones["long_axis"]
    from common import AXES

    axis_index = AXES.index(str(long_axis))
    labels = label_zone_points(
        points=points,
        axis_index=axis_index,
        bounds=np.asarray(mesh.bounds, dtype=float),
        boundaries=zones["boundaries"],
        edge_margin=float(edge_margin),
        curve_config=curve_config,
        outline_distance_mm=column_outline_distance_mm(inside, pitch).reshape(-1),
    )
    return voxelized, inside, points, labels
