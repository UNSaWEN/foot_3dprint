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


def _expand_xy(points_xy: np.ndarray, margin_mm: float) -> np.ndarray:
    if margin_mm <= 0:
        return points_xy.copy()
    center = points_xy.mean(axis=0)
    vectors = points_xy - center
    distances = np.linalg.norm(vectors, axis=1)
    expanded = points_xy.copy()
    nonzero = distances > 1e-9
    expanded[nonzero] = points_xy[nonzero] + (vectors[nonzero] / distances[nonzero, None]) * margin_mm
    return expanded


def _filtered_delaunay_faces(points_xy: np.ndarray, max_gap_mm: float) -> np.ndarray:
    from scipy.spatial import Delaunay  # type: ignore

    if len(points_xy) < 3:
        raise ValueError("Plant scan must contain at least three unique XY points")
    simplices = Delaunay(points_xy).simplices
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

    foot_length = float(mapped[:, 1].max() - mapped[:, 1].min())
    foot_width = float(mapped[:, 0].max() - mapped[:, 0].min())
    warnings: list[str] = []
    if foot_length < config["min_foot_length_mm"] or foot_length > config["max_foot_length_mm"]:
        warnings.append(
            "foot_length_outside_expected_range: "
            f"{foot_length:.2f} mm not in {config['min_foot_length_mm']:.2f}-{config['max_foot_length_mm']:.2f} mm"
        )

    expanded_xy = _expand_xy(mapped[:, :2], float(config["outline_margin_mm"]))
    top_z = mapped[:, 2] + float(config["target_thickness_mm"]) + float(config["bottom_clearance_mm"])
    top_vertices = np.column_stack((expanded_xy, top_z))
    bottom_vertices = np.column_stack((expanded_xy, np.zeros(len(expanded_xy), dtype=float)))

    top_faces = _filtered_delaunay_faces(expanded_xy, float(config["max_gap_mm"]))
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
