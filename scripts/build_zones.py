from __future__ import annotations

import argparse
import math

import numpy as np

from common import (
    AXES,
    compute_zone_boundaries,
    discover_inputs,
    load_config,
    longest_axis,
    normalize_zone_ratios,
    output_root,
    write_json,
)
from render_preview import save_zone_preview
from voxel_fields import load_closed_mesh, outline_distance_for_points, voxelize_filled
from zone_strategy import label_zone_points, resolve_curve_config, resolve_heel_at


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build top-level insole zones.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    return parser


def build_zone_definition(mesh, *, input_name: str, input_path: str, side: str | None, config: dict):
    """Resolve heel direction from the outline and record the input side."""
    bounds = np.asarray(mesh.bounds, dtype=float)
    extents = bounds[1] - bounds[0]
    axis_index = longest_axis(extents, config.get("long_axis", "auto"))
    pitch = float(config["voxel_pitch_mm"])
    edge_margin = float(config["edge_frame_margin_mm"])
    ratios = normalize_zone_ratios(config["zone_ratios"])
    curve_config = dict(resolve_curve_config(config.get("zone_shape")))

    voxelized = voxelize_filled(mesh, pitch)
    inside = np.asarray(voxelized.matrix, dtype=bool)
    max_voxels = int(config.get("max_voxels", 1500000))
    if math.prod(inside.shape) > max_voxels:
        raise RuntimeError(
            f"Voxel grid too large for current limits: {tuple(inside.shape)} > {max_voxels} voxels"
        )

    footprint = np.any(inside, axis=2)
    heel_at = resolve_heel_at(str(curve_config.get("heel_at", "auto")), footprint, axis_index, pitch)
    curve_config["heel_at"] = heel_at
    boundaries = compute_zone_boundaries(
        bounds_min=bounds[0],
        bounds_max=bounds[1],
        zone_ratios=ratios,
        axis_index=axis_index,
        heel_at=heel_at,
    )
    labels = label_zone_points(
        points=np.asarray(mesh.vertices, dtype=float),
        axis_index=axis_index,
        bounds=bounds,
        boundaries=boundaries,
        edge_margin=edge_margin,
        curve_config=curve_config,
        outline_distance_mm=outline_distance_for_points(mesh.vertices, inside, voxelized, pitch),
    )
    payload = {
        "input_name": input_name,
        "input_path": input_path,
        "side": side,
        "bounds_min_mm": [round(float(value), 4) for value in bounds[0]],
        "bounds_max_mm": [round(float(value), 4) for value in bounds[1]],
        "extents_mm": [round(float(value), 4) for value in extents],
        "long_axis": AXES[axis_index],
        "heel_at": heel_at,
        "zone_ratios": ratios,
        "edge_frame_margin_mm": edge_margin,
        "boundaries": boundaries,
        "zone_shape": curve_config,
    }
    return payload, labels


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    zone_dir = output_root(config) / "zones"

    for item in discover_inputs(config):
        mesh = load_closed_mesh(item["path"])
        payload, labels = build_zone_definition(
            mesh,
            input_name=item["name"],
            input_path=str(item["path"]),
            side=item.get("side"),
            config=config,
        )
        write_json(zone_dir / f"{item['name']}_zones.json", payload)
        save_zone_preview(
            points=mesh.vertices,
            labels=labels,
            output_path=zone_dir / f"{item['name']}_zones.png",
            long_axis_index=AXES.index(payload["long_axis"]),
            title=f"{item['name']} zone preview ({payload['long_axis']} axis)",
        )


if __name__ == "__main__":
    main()
