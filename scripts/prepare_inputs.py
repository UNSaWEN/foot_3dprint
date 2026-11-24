from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

import numpy as np

from common import (
    AXES,
    discover_inputs,
    ensure_directory,
    load_config,
    output_root,
    try_load_trimesh,
    write_json,
)
from render_preview import save_mesh_projection_preview


DEFAULT_SCAN_PREPROCESS_CONFIG: dict[str, Any] = {
    "length_axis": "y",
    "lateral_axis": "x",
    "surface_axis": "z",
    "surface_direction": "positive",
    "target_thickness_mm": 6.0,
    "bottom_clearance_mm": 0.5,
    "outline_margin_mm": 2.0,
    "max_relief_mm": 8.0,
    "smoothing_iterations": 0,
    "max_gap_mm": 35.0,
    "min_foot_length_mm": 180.0,
    "max_foot_length_mm": 350.0,
}


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare configured insole inputs for the lattice pipeline.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    return parser


def resolve_scan_preprocess_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(DEFAULT_SCAN_PREPROCESS_CONFIG)
    if config:
        merged.update(config)

    for key in ("length_axis", "lateral_axis", "surface_axis"):
        axis = str(merged[key]).lower()
        if axis not in AXES:
            raise ValueError(f"scan_preprocess {key} must be one of: x, y, z")
        merged[key] = axis
    if len({merged["length_axis"], merged["lateral_axis"], merged["surface_axis"]}) != 3:
        raise ValueError("scan_preprocess axes must be distinct")

    direction = str(merged["surface_direction"]).lower()
    if direction not in {"positive", "negative"}:
        raise ValueError("scan_preprocess surface_direction must be positive or negative")
    merged["surface_direction"] = direction

    for key in (
        "target_thickness_mm",
        "bottom_clearance_mm",
        "outline_margin_mm",
        "max_relief_mm",
        "max_gap_mm",
        "min_foot_length_mm",
        "max_foot_length_mm",
    ):
        value = float(merged[key])
        if not math.isfinite(value):
            raise ValueError(f"scan_preprocess {key} must be finite")
        if key != "bottom_clearance_mm" and value < 0:
            raise ValueError(f"scan_preprocess {key} must be non-negative")
        merged[key] = value

    if merged["target_thickness_mm"] <= 0:
        raise ValueError("scan_preprocess target_thickness_mm must be positive")
    if merged["max_gap_mm"] <= 0:
        raise ValueError("scan_preprocess max_gap_mm must be positive")
    if merged["min_foot_length_mm"] >= merged["max_foot_length_mm"]:
        raise ValueError("scan_preprocess min_foot_length_mm must be smaller than max_foot_length_mm")

    smoothing_iterations = int(merged.get("smoothing_iterations", 0))
    if smoothing_iterations < 0:
        raise ValueError("scan_preprocess smoothing_iterations must be non-negative")
    merged["smoothing_iterations"] = smoothing_iterations
    return merged


def _axis_index(axis_name: str) -> int:
    return AXES.index(axis_name)


def _unique_surface_points(mapped_points: np.ndarray) -> np.ndarray:
    rounded_xy = np.round(mapped_points[:, :2], decimals=5)
    _, unique_indices = np.unique(rounded_xy, axis=0, return_index=True)
    return mapped_points[np.sort(unique_indices)]


def _signed_area(ring: np.ndarray) -> float:
    x = ring[:, 0]
    y = ring[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _clean_ring(points: np.ndarray, tol: float = 1e-6) -> np.ndarray:
    if len(points) == 0:
        return np.zeros((0, 2), dtype=float)
    cleaned = [np.asarray(points[0], dtype=float)]
    for point in points[1:]:
        candidate = np.asarray(point, dtype=float)
        if float(np.linalg.norm(candidate - cleaned[-1])) > tol:
            cleaned.append(candidate)
    if len(cleaned) > 1 and float(np.linalg.norm(cleaned[0] - cleaned[-1])) <= tol:
        cleaned.pop()
    return np.vstack(cleaned)


def _resample_closed_ring(points: np.ndarray, spacing: float) -> np.ndarray:
    if len(points) < 2 or spacing <= 0:
        return _clean_ring(points)
    samples: list[np.ndarray] = []
    count = len(points)
    for index in range(count):
        start = points[index]
        end = points[(index + 1) % count]
        edge = end - start
        length = float(np.linalg.norm(edge))
        if length < 1e-9:
            continue
        steps = max(1, int(math.ceil(length / spacing)))
        for step in range(steps):
            samples.append(start + edge * (step / steps))
    ring = _clean_ring(np.vstack(samples) if samples else points)
    if len(ring) < 3:
        raise ValueError(f"Plantar outline has too few points to offset (got {len(ring)}, need at least 3)")
    return ring


def _closest_on_ring(ring: np.ndarray, queries: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    starts = ring
    ends = np.roll(ring, -1, axis=0)
    edges = ends - starts
    lengths_sq = np.maximum(np.sum(edges * edges, axis=1), 1e-18)
    query = queries[:, None, :]
    raw_t = np.sum((query - starts) * edges, axis=2) / lengths_sq
    t = np.clip(raw_t, 0.0, 1.0)
    projected = starts + t[..., None] * edges
    distance_sq = np.sum((query - projected) ** 2, axis=2)
    segment = np.argmin(distance_sq, axis=1)
    rows = np.arange(len(queries))
    return projected[rows, segment], t[rows, segment], segment


def _distance_to_ring(ring: np.ndarray, points: np.ndarray) -> np.ndarray:
    closest, _, _ = _closest_on_ring(ring, points)
    return np.linalg.norm(points - closest, axis=1)


def _points_in_ring(ring: np.ndarray, points: np.ndarray) -> np.ndarray:
    x = points[:, 0]
    y = points[:, 1]
    inside = np.zeros(len(points), dtype=bool)
    x1s = ring[:, 0]
    y1s = ring[:, 1]
    x2s = np.roll(x1s, -1)
    y2s = np.roll(y1s, -1)
    for x1, y1, x2, y2 in zip(x1s, y1s, x2s, y2s):
        if y1 == y2:
            continue
        crosses = (y1 > y) != (y2 > y)
        if not np.any(crosses):
            continue
        x_at_y = (x2 - x1) * (y[crosses] - y1) / (y2 - y1) + x1
        inside[crosses] ^= x[crosses] < x_at_y
    return inside


def _interpolate_ring_values(ring: np.ndarray, values: np.ndarray, queries: np.ndarray) -> np.ndarray:
    _, t, segment = _closest_on_ring(ring, queries)
    start_values = values
    end_values = np.roll(values, -1)
    return (1.0 - t) * start_values[segment] + t * end_values[segment]


def _line_intersection(origin_a: np.ndarray, direction_a: np.ndarray, origin_b: np.ndarray, direction_b: np.ndarray) -> np.ndarray | None:
    denominator = direction_a[0] * direction_b[1] - direction_a[1] * direction_b[0]
    if abs(denominator) < 1e-12:
        return None
    difference = origin_b - origin_a
    distance = (difference[0] * direction_b[1] - difference[1] * direction_b[0]) / denominator
    return origin_a + distance * direction_a


def _segments_properly_intersect(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> bool:
    if max(a[0], b[0]) < min(c[0], d[0]) - 1e-9 or max(c[0], d[0]) < min(a[0], b[0]) - 1e-9:
        return False
    if max(a[1], b[1]) < min(c[1], d[1]) - 1e-9 or max(c[1], d[1]) < min(a[1], b[1]) - 1e-9:
        return False

    def orient(p: np.ndarray, q: np.ndarray, r: np.ndarray) -> float:
        return float((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]))

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    epsilon = 1e-8
    if min(abs(o1), abs(o2), abs(o3), abs(o4)) <= epsilon:
        return False
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def _ring_self_intersects(ring: np.ndarray) -> bool:
    count = len(ring)
    if count < 4:
        return False
    for index in range(count):
        start = ring[index]
        end = ring[(index + 1) % count]
        for other in range(index + 2, count):
            if index == 0 and other == count - 1:
                continue
            if _segments_properly_intersect(start, end, ring[other], ring[(other + 1) % count]):
                return True
    return False


def _equidistant_offset_ring(ring: np.ndarray, margin_mm: float) -> np.ndarray:
    """Outward round-join offset of one closed plantar outline."""
    polygon = _clean_ring(ring)
    if len(polygon) < 3 or abs(_signed_area(polygon)) <= 1e-6:
        raise ValueError(f"Plantar outline has too few points to offset (got {len(polygon)}, need at least 3)")
    if _signed_area(polygon) < 0:
        polygon = polygon[::-1].copy()

    min_turn = math.radians(8.0)
    arc_step = math.radians(12.0)
    # Shallow reflex corners make infinite-line intersections spike; bevel those.
    mitre_limit = 3.0
    emitted: list[np.ndarray] = []
    count = len(polygon)
    for index in range(count):
        previous = polygon[(index - 1) % count]
        current = polygon[index]
        nxt = polygon[(index + 1) % count]
        incoming = current - previous
        outgoing = nxt - current
        incoming_length = float(np.linalg.norm(incoming))
        outgoing_length = float(np.linalg.norm(outgoing))
        if incoming_length < 1e-8 or outgoing_length < 1e-8:
            continue
        incoming_dir = incoming / incoming_length
        outgoing_dir = outgoing / outgoing_length
        # CCW outline: outward normal is the right-hand normal of the edge.
        incoming_normal = np.array([incoming_dir[1], -incoming_dir[0]])
        outgoing_normal = np.array([outgoing_dir[1], -outgoing_dir[0]])
        cross = incoming_dir[0] * outgoing_dir[1] - incoming_dir[1] * outgoing_dir[0]
        dot = float(np.dot(incoming_dir, outgoing_dir))
        turn = math.atan2(cross, dot)
        if turn > min_turn:
            start_angle = math.atan2(float(incoming_normal[1]), float(incoming_normal[0]))
            steps = max(1, int(math.ceil(turn / arc_step)))
            for step in range(steps + 1):
                angle = start_angle + turn * (step / steps)
                emitted.append(current + margin_mm * np.array([math.cos(angle), math.sin(angle)]))
        elif turn < -min_turn:
            intersection = _line_intersection(
                current + incoming_normal * margin_mm,
                incoming_dir,
                current + outgoing_normal * margin_mm,
                outgoing_dir,
            )
            if intersection is not None and float(np.linalg.norm(intersection - current)) <= mitre_limit * margin_mm:
                emitted.append(np.asarray(intersection, dtype=float))
            else:
                emitted.append(current + incoming_normal * margin_mm)
                emitted.append(current + outgoing_normal * margin_mm)
        else:
            emitted.append(current + incoming_normal * margin_mm)

    offset = _clean_ring(np.vstack(emitted) if emitted else polygon)
    if len(offset) < 3:
        raise ValueError(f"Plantar outline has too few points to offset (got {len(offset)}, need at least 3)")
    return offset


def _rasterize_ring(ring: np.ndarray, origin: np.ndarray, pitch: float, width: int, height: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    xs = ring[:, 0]
    ys = ring[:, 1]
    count = len(ring)
    origin_x = float(origin[0])
    for row in range(height):
        y = float(origin[1] + row * pitch)
        crossings: list[float] = []
        for index in range(count):
            y1 = float(ys[index])
            y2 = float(ys[(index + 1) % count])
            if y1 == y2:
                continue
            if (y1 <= y < y2) or (y2 <= y < y1):
                t = (y - y1) / (y2 - y1)
                crossings.append(float(xs[index] + t * (xs[(index + 1) % count] - xs[index])))
        crossings.sort()
        for index in range(0, len(crossings) - 1, 2):
            first = int(math.ceil((crossings[index] - origin_x) / pitch - 1e-9))
            last = int(math.floor((crossings[index + 1] - origin_x) / pitch - 1e-9))
            if first <= last:
                mask[row, max(0, first) : min(width, last + 1)] = True
    return mask


def _isoline_segments(distance: np.ndarray, origin: np.ndarray, pitch: float, level: float) -> list[tuple[np.ndarray, np.ndarray]]:
    def interpolate(start: np.ndarray, end: np.ndarray, start_value: float, end_value: float) -> np.ndarray:
        if abs(end_value - start_value) < 1e-12:
            return (start + end) * 0.5
        t = min(1.0, max(0.0, (level - start_value) / (end_value - start_value)))
        return start + t * (end - start)

    corner_pairs = ((0, 1), (1, 2), (2, 3), (3, 0))
    table = {
        1: ((3, 0),),
        2: ((0, 1),),
        3: ((3, 1),),
        4: ((1, 2),),
        6: ((0, 2),),
        7: ((3, 2),),
        8: ((2, 3),),
        9: ((0, 2),),
        11: ((1, 2),),
        12: ((1, 3),),
        13: ((0, 1),),
        14: ((3, 0),),
    }
    segments: list[tuple[np.ndarray, np.ndarray]] = []
    rows, cols = distance.shape
    for row in range(rows - 1):
        for col in range(cols - 1):
            values = (
                float(distance[row, col]),
                float(distance[row, col + 1]),
                float(distance[row + 1, col + 1]),
                float(distance[row + 1, col]),
            )
            index = (
                (1 if values[0] <= level else 0)
                | (2 if values[1] <= level else 0)
                | (4 if values[2] <= level else 0)
                | (8 if values[3] <= level else 0)
            )
            if index in (0, 15):
                continue
            corners = (
                origin + np.array([col * pitch, row * pitch]),
                origin + np.array([(col + 1) * pitch, row * pitch]),
                origin + np.array([(col + 1) * pitch, (row + 1) * pitch]),
                origin + np.array([col * pitch, (row + 1) * pitch]),
            )

            def edge_point(edge: int, corners: tuple[np.ndarray, ...] = corners, values: tuple[float, ...] = values) -> np.ndarray:
                a, b = corner_pairs[edge]
                return interpolate(corners[a], corners[b], values[a], values[b])

            center = sum(values) / 4.0
            if index == 5:
                chosen = ((3, 2), (0, 1)) if center <= level else ((3, 0), (1, 2))
            elif index == 10:
                chosen = ((3, 1), (2, 0)) if center <= level else ((3, 0), (1, 2))
            else:
                chosen = table.get(index)
                if chosen is None:
                    continue
            for first_edge, second_edge in chosen:
                segments.append((edge_point(first_edge), edge_point(second_edge)))
    return segments


def _chain_segments(segments: list[tuple[np.ndarray, np.ndarray]], tol: float) -> list[np.ndarray]:
    def key(point: np.ndarray) -> tuple[int, int]:
        return (round(float(point[0]) / tol), round(float(point[1]) / tol))

    adjacency: dict[tuple[int, int], list[tuple[int, int]]] = {}
    point_of: dict[tuple[int, int], np.ndarray] = {}
    unused: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for start, end in segments:
        start_key = key(start)
        end_key = key(end)
        if start_key == end_key:
            continue
        point_of[start_key] = np.asarray(start, dtype=float)
        point_of[end_key] = np.asarray(end, dtype=float)
        adjacency.setdefault(start_key, []).append(end_key)
        adjacency.setdefault(end_key, []).append(start_key)
        unused.add(tuple(sorted((start_key, end_key))))

    loops: list[np.ndarray] = []
    while unused:
        start_key, end_key = next(iter(unused))
        unused.remove(tuple(sorted((start_key, end_key))))
        loop = [start_key, end_key]
        previous, current = start_key, end_key
        closed = False
        while True:
            nxt = None
            for candidate in adjacency[current]:
                edge = tuple(sorted((current, candidate)))
                if edge in unused and candidate != previous:
                    nxt = candidate
                    break
            if nxt is None:
                for candidate in adjacency[current]:
                    edge = tuple(sorted((current, candidate)))
                    if edge in unused:
                        nxt = candidate
                        break
            if nxt is None:
                break
            unused.remove(tuple(sorted((current, nxt))))
            loop.append(nxt)
            previous, current = current, nxt
            if current == start_key:
                closed = True
                break
        if closed and len(loop) >= 4:
            loops.append(np.vstack([point_of[item] for item in loop[:-1]]))
    return loops


def _snap_to_margin(outline: np.ndarray, points: np.ndarray, margin_mm: float) -> np.ndarray:
    closest, _, _ = _closest_on_ring(outline, points)
    inside = _points_in_ring(outline, points)
    outward = np.empty_like(points)
    outward[~inside] = points[~inside] - closest[~inside]
    outward[inside] = closest[inside] - points[inside]
    length = np.linalg.norm(outward, axis=1, keepdims=True)
    usable = length[:, 0] > 1e-8
    outward[usable] = outward[usable] / length[usable]
    snapped = closest + outward * margin_mm
    snapped[~usable] = points[~usable]
    return snapped


def _morphological_offset_ring(outline: np.ndarray, margin_mm: float) -> np.ndarray:
    """Euclidean dilation of the outline, used when the parallel curve self-intersects."""
    from scipy.ndimage import distance_transform_edt

    polygon = _clean_ring(outline)
    if len(polygon) < 3:
        raise ValueError(f"Plantar outline has too few points to offset (got {len(polygon)}, need at least 3)")
    span = float(np.max(polygon.max(axis=0) - polygon.min(axis=0))) + 2.0 * margin_mm
    pitch = min(0.5, max(0.2, margin_mm / 10.0))
    pitch = max(pitch, span / 1500.0)
    pad = margin_mm + pitch * 4.0
    origin = polygon.min(axis=0) - pad
    maximum = polygon.max(axis=0) + pad
    width = int(math.ceil((maximum[0] - origin[0]) / pitch)) + 2
    height = int(math.ceil((maximum[1] - origin[1]) / pitch)) + 2
    mask = _rasterize_ring(polygon, origin, pitch, width, height)
    if int(mask.sum()) < 3:
        raise ValueError("Plantar outline is degenerate and cannot be offset")
    distance = distance_transform_edt(~mask, sampling=pitch)
    segments = _isoline_segments(distance, origin, pitch, margin_mm)
    loops = _chain_segments(segments, pitch * 0.25)
    if not loops:
        raise ValueError("Plantar outline offset could not be traced")
    areas = [abs(_signed_area(loop)) for loop in loops]
    contour = _snap_to_margin(polygon, loops[int(np.argmax(areas))], margin_mm)
    contour = _clean_ring(contour, tol=max(1e-6, pitch * 0.05))
    distances = _distance_to_ring(polygon, contour)
    # Drop samples that snapped into a pocket and are no longer on the dilation boundary.
    contour = contour[distances >= margin_mm - max(0.35, pitch)]
    contour = _clean_ring(contour)
    if len(contour) < 3:
        raise ValueError(f"Plantar outline has too few points to offset (got {len(contour)}, need at least 3)")
    return contour


def _offset_outline_ring(outline: np.ndarray, margin_mm: float) -> np.ndarray:
    offset = _equidistant_offset_ring(outline, margin_mm)
    distances = _distance_to_ring(outline, offset)
    collapsed = float(distances.min()) < margin_mm * 0.85 or float(distances.max()) > margin_mm * 1.35
    if collapsed or _ring_self_intersects(offset):
        offset = _morphological_offset_ring(outline, margin_mm)
    return offset


def _filtered_delaunay_faces(points_xy: np.ndarray, max_gap_mm: float) -> np.ndarray:
    from scipy.spatial import Delaunay, QhullError

    if len(points_xy) < 3:
        raise ValueError("Plant scan must contain at least three unique XY points")
    try:
        simplices = Delaunay(points_xy).simplices
    except QhullError as exc:
        raise ValueError("Plant scan must contain at least three non-collinear XY points") from exc
    kept = []
    for tri in simplices:
        vertices = points_xy[tri]
        edge_lengths = (
            np.linalg.norm(vertices[0] - vertices[1]),
            np.linalg.norm(vertices[1] - vertices[2]),
            np.linalg.norm(vertices[2] - vertices[0]),
        )
        if max(edge_lengths) <= max_gap_mm:
            kept.append(tri)
    if not kept:
        raise ValueError("No surface triangles remain after max_gap_mm filtering")
    return np.array(kept, dtype=int)


def _boundary_edges(faces: np.ndarray) -> list[tuple[int, int]]:
    edge_counts: dict[tuple[int, int], int] = {}
    for a, b, c in faces:
        for edge in ((a, b), (b, c), (c, a)):
            key = tuple(sorted((int(edge[0]), int(edge[1]))))
            edge_counts[key] = edge_counts.get(key, 0) + 1
    return [edge for edge, count in edge_counts.items() if count == 1]


def _closed_loops(edges: list[tuple[int, int]]) -> list[list[int]]:
    if len(edges) < 3:
        raise ValueError(
            f"Plantar outline has too few points to offset (got {len(edges)} boundary edges, need at least 3)"
        )
    adjacency: dict[int, list[int]] = {}
    unused: set[tuple[int, int]] = set()
    for a, b in edges:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)
        unused.add((a, b) if a < b else (b, a))

    loops: list[list[int]] = []
    while unused:
        start, nxt = next(iter(unused))
        unused.remove((start, nxt) if start < nxt else (nxt, start))
        loop = [start, nxt]
        current = nxt
        closed = False
        while True:
            neighbor = None
            for candidate in adjacency[current]:
                key = (current, candidate) if current < candidate else (candidate, current)
                if key in unused:
                    neighbor = candidate
                    break
            if neighbor is None:
                break
            unused.remove((current, neighbor) if current < neighbor else (neighbor, current))
            loop.append(neighbor)
            current = neighbor
            if current == start:
                closed = True
                break
        if not closed or len(loop) < 4:
            raise ValueError("Plantar outline is not a closed loop and cannot be offset")
        loops.append(loop[:-1])
    return loops


def _outline_ring(points_xy: np.ndarray, max_gap_mm: float) -> tuple[np.ndarray, np.ndarray]:
    try:
        faces = _filtered_delaunay_faces(points_xy, max_gap_mm)
    except ValueError as exc:
        raise ValueError(
            "Plantar outline has too few points to offset; need a closed outline of at least three non-collinear points"
        ) from exc
    loops = _closed_loops(_boundary_edges(faces))
    best = max(loops, key=lambda loop: abs(_signed_area(points_xy[np.asarray(loop, dtype=int)])))
    indices = np.asarray(best, dtype=int)
    ring = _clean_ring(points_xy[indices])
    if len(ring) < 3 or abs(_signed_area(ring)) <= 1e-6:
        raise ValueError(f"Plantar outline has too few points to offset (got {len(ring)}, need at least 3)")
    return points_xy[indices], indices


def _keep_faces_inside_ring(points_xy: np.ndarray, faces: np.ndarray, ring: np.ndarray) -> np.ndarray:
    if len(faces) == 0:
        raise ValueError("No surface triangles remain after max_gap_mm filtering")
    centroids = points_xy[faces].mean(axis=1)
    inside = _points_in_ring(ring, centroids)
    near_boundary = _distance_to_ring(ring, centroids) <= 0.5
    kept = faces[inside | near_boundary]
    if len(kept) == 0:
        raise ValueError("No surface triangles remain after outline offset")
    return kept


def _expand_xy(
    points_xy: np.ndarray,
    heights: np.ndarray,
    margin_mm: float,
    max_gap_mm: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Offset the plantar outline by a constant distance.

    Interior scan points stay where they are, so a narrow toe is not stretched
    away from the centroid. The returned ring is the expanded outline used to
    clip the surface triangulation. A margin of zero leaves the points unchanged.
    """
    if margin_mm <= 0:
        return points_xy.copy(), heights.copy(), None
    if len(points_xy) < 3:
        raise ValueError(f"Plantar outline has too few points to offset (got {len(points_xy)}, need at least 3)")

    outline_xy, outline_index = _outline_ring(points_xy, max_gap_mm)
    outline_z = heights[outline_index]
    offset_xy = _offset_outline_ring(outline_xy, margin_mm)
    spacing = min(2.0, max(0.75, max_gap_mm * 0.45))
    offset_xy = _resample_closed_ring(offset_xy, spacing)
    offset_z = _interpolate_ring_values(outline_xy, outline_z, offset_xy)
    combined = np.column_stack(
        (
            np.vstack((points_xy, offset_xy)),
            np.concatenate((heights, offset_z)),
        )
    )
    combined = _unique_surface_points(combined)
    return combined[:, :2], combined[:, 2], offset_xy


def build_prepared_insole_mesh(scan_mesh: Any, preprocess_config: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    trimesh = try_load_trimesh()
    if trimesh is None:
        raise RuntimeError("prepare_inputs.py requires trimesh")

    config = resolve_scan_preprocess_config(preprocess_config)
    vertices = np.asarray(scan_mesh.vertices, dtype=float)
    if len(vertices) < 3:
        raise ValueError("Plant scan mesh does not contain enough vertices")

    length_index = _axis_index(config["length_axis"])
    lateral_index = _axis_index(config["lateral_axis"])
    surface_index = _axis_index(config["surface_axis"])
    direction = 1.0 if config["surface_direction"] == "positive" else -1.0

    mapped = np.column_stack(
        (
            vertices[:, lateral_index],
            vertices[:, length_index],
            vertices[:, surface_index] * direction,
        )
    )
    mapped[:, 0] -= float(mapped[:, 0].min())
    mapped[:, 1] -= float(mapped[:, 1].min())
    mapped[:, 2] -= float(mapped[:, 2].min())
    mapped = _unique_surface_points(mapped)
    mapped[:, 2] = np.minimum(mapped[:, 2], float(config["max_relief_mm"]))

    foot_length = float(mapped[:, 1].max() - mapped[:, 1].min())
    foot_width = float(mapped[:, 0].max() - mapped[:, 0].min())
    warnings: list[str] = []
    if foot_length < config["min_foot_length_mm"] or foot_length > config["max_foot_length_mm"]:
        warnings.append(
            "foot_length_outside_expected_range: "
            f"{foot_length:.2f} mm not in {config['min_foot_length_mm']:.2f}-{config['max_foot_length_mm']:.2f} mm"
        )

    expanded_xy, surface_z, offset_ring = _expand_xy(
        mapped[:, :2],
        mapped[:, 2],
        float(config["outline_margin_mm"]),
        float(config["max_gap_mm"]),
    )
    top_z = surface_z + float(config["target_thickness_mm"]) + float(config["bottom_clearance_mm"])
    top_vertices = np.column_stack((expanded_xy, top_z))
    bottom_vertices = np.column_stack((expanded_xy, np.zeros(len(expanded_xy), dtype=float)))

    top_faces = _filtered_delaunay_faces(expanded_xy, float(config["max_gap_mm"]))
    if offset_ring is not None:
        top_faces = _keep_faces_inside_ring(expanded_xy, top_faces, offset_ring)
    boundary_edges = _boundary_edges(top_faces)
    vertex_count = len(top_vertices)

    faces: list[list[int]] = []
    faces.extend(top_faces.tolist())
    faces.extend((top_faces[:, ::-1] + vertex_count).tolist())
    for a, b in boundary_edges:
        faces.append([a, b, b + vertex_count])
        faces.append([a, b + vertex_count, a + vertex_count])

    prepared = trimesh.Trimesh(
        vertices=np.vstack((top_vertices, bottom_vertices)),
        faces=np.array(faces, dtype=int),
        process=True,
    )
    prepared.remove_unreferenced_vertices()
    prepared.fix_normals()

    for _ in range(int(config["smoothing_iterations"])):
        trimesh.smoothing.filter_laplacian(prepared, lamb=0.25, iterations=1)

    report = {
        "input_vertex_count": int(len(vertices)),
        "prepared_vertex_count": int(len(prepared.vertices)),
        "prepared_face_count": int(len(prepared.faces)),
        "foot_length_mm": round(foot_length, 4),
        "foot_width_mm": round(foot_width, 4),
        "target_thickness_mm": float(config["target_thickness_mm"]),
        "bottom_clearance_mm": float(config["bottom_clearance_mm"]),
        "outline_margin_mm": float(config["outline_margin_mm"]),
        "max_relief_mm": float(config["max_relief_mm"]),
        "thickness_min_mm": round(float(np.min(top_z)), 4),
        "thickness_max_mm": round(float(np.max(top_z)), 4),
        "axes": {
            "length_axis": config["length_axis"],
            "lateral_axis": config["lateral_axis"],
            "surface_axis": config["surface_axis"],
            "surface_direction": config["surface_direction"],
        },
        "watertight": bool(prepared.is_watertight),
        "is_volume": bool(prepared.is_volume),
        "bounds_min_mm": [round(float(value), 4) for value in prepared.bounds[0]],
        "bounds_max_mm": [round(float(value), 4) for value in prepared.bounds[1]],
        "warnings": warnings,
    }
    if not prepared.is_watertight:
        report["warnings"].append("prepared_mesh_is_not_watertight")
    return prepared, report


def _load_mesh(path: Path):
    trimesh = try_load_trimesh()
    if trimesh is None:
        raise RuntimeError("prepare_inputs.py requires trimesh")
    mesh = trimesh.load_mesh(path, process=True)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))
    return mesh


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    prepared_dir = ensure_directory(output_root(config) / "prepared")
    preprocess_config = resolve_scan_preprocess_config(config.get("scan_preprocess"))
    reports: list[dict[str, Any]] = []

    for item in discover_inputs(config, require_prepared=False):
        if item["mode"] == "insole_solid":
            report = {
                "input_name": item["name"],
                "mode": item["mode"],
                "raw_path": str(item["raw_path"]),
                "prepared_path": str(item["prepared_path"]),
                "action": "reuse_solid_input",
                "warnings": [],
            }
            write_json(prepared_dir / f"{item['name']}_prepare_report.json", report)
            reports.append(report)
            continue

        raw_mesh = _load_mesh(item["raw_path"])
        prepared_mesh, report = build_prepared_insole_mesh(raw_mesh, preprocess_config)
        ensure_directory(Path(item["prepared_path"]).parent)
        prepared_mesh.export(item["prepared_path"])
        save_mesh_projection_preview(
            mesh=prepared_mesh,
            output_path=prepared_dir / f"{item['name']}_prepared_projection.png",
            title=f"{item['name']} prepared insole projections",
        )
        report.update(
            {
                "input_name": item["name"],
                "mode": item["mode"],
                "side": item.get("side"),
                "raw_path": str(item["raw_path"]),
                "prepared_path": str(item["prepared_path"]),
            }
        )
        write_json(prepared_dir / f"{item['name']}_prepare_report.json", report)
        reports.append(report)

    write_json(prepared_dir / "prepare_summary.json", {"inputs": reports})


if __name__ == "__main__":
    main()
