from __future__ import annotations

import argparse
from pathlib import Path

from common import AXES, discover_inputs, load_config, output_root, read_json, try_load_trimesh, write_json
from default_profiles import resolve_tpms_thresholds
from render_preview import save_slice_preview
from zone_strategy import label_zone_points, resolve_curve_config


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate TPMS voxel fields for insoles.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    return parser


def gyroid_field(points, wavelength_mm):
    import numpy as np  # type: ignore

    omega = (2.0 * np.pi) / wavelength_mm
    x = points[:, 0] * omega
    y = points[:, 1] * omega
    z = points[:, 2] * omega
    return np.sin(x) * np.cos(y) + np.sin(y) * np.cos(z) + np.sin(z) * np.cos(x)


def threshold_map_from_labels(labels, thresholds):
    import numpy as np  # type: ignore

    result = np.full(len(labels), thresholds["toe"], dtype=float)
    for zone_name, threshold in thresholds.items():
        result[labels == zone_name] = float(threshold)
    return result


def edge_frame_mask(points, bounds, margin_mm):
    import numpy as np  # type: ignore

    minimum = bounds[0]
    maximum = bounds[1]
    near_x = (points[:, 0] - minimum[0] <= margin_mm) | (maximum[0] - points[:, 0] <= margin_mm)
    near_y = (points[:, 1] - minimum[1] <= margin_mm) | (maximum[1] - points[:, 1] <= margin_mm)
    return near_x | near_y


def apply_top_density_boost(thresholds, points, bounds, pitch_mm, top_dense_layers, threshold_boost):
    import numpy as np  # type: ignore

    if top_dense_layers <= 0 or threshold_boost <= 0:
        return thresholds

    depth_mm = float(top_dense_layers) * float(pitch_mm)
    top_limit = float(bounds[1][2]) - depth_mm
    boosted = thresholds.copy()
    top_mask = points[:, 2] >= top_limit
    boosted[top_mask] = boosted[top_mask] + float(threshold_boost)
    return boosted


def voxel_points(voxelized):
    import numpy as np  # type: ignore
    import trimesh  # type: ignore

    shape = voxelized.matrix.shape
    indices = np.indices(shape).reshape(3, -1).T
    transform = voxelized.transform
    matrix = transform.matrix if hasattr(transform, "matrix") else transform
    points = trimesh.transform_points(indices.astype(float), matrix)
    return indices, points


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    trimesh = try_load_trimesh()
    if trimesh is None:
        raise RuntimeError("generate_tpms.py requires trimesh")

    import numpy as np  # type: ignore

    tpms_dir = output_root(config) / "tpms"
    pitch = float(config["voxel_pitch_mm"])
    wavelength = float(config["tpms"]["wavelength_mm"])
    thresholds = resolve_tpms_thresholds(config)
    edge_margin = float(config["edge_frame_margin_mm"])
    max_voxels = int(config.get("max_voxels", 1500000))
    surface = dict(config.get("surface", {}))
    top_dense_layers = int(surface.get("top_dense_layers", 0))
    top_dense_threshold_boost = float(surface.get("top_dense_threshold_boost", 0.0))
    if config["tpms"]["type"] != "gyroid":
        raise ValueError(f"Unsupported tpms.type: {config['tpms']['type']}")

    for item in discover_inputs(config):
        zone_path = output_root(config) / "zones" / f"{item['name']}_zones.json"
        if not Path(zone_path).exists():
            raise FileNotFoundError(f"Zone definition missing: {zone_path}")
        zones = read_json(zone_path)
        mesh = trimesh.load_mesh(item["path"], process=False)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        filled = mesh.voxelized(pitch).fill()
        inside_mask = filled.matrix.astype(bool)
        if int(np.prod(inside_mask.shape)) > max_voxels:
            raise RuntimeError(
                f"Voxel grid too large for current limits: {inside_mask.shape} > {max_voxels} voxels"
            )
        _, points = voxel_points(filled)

        axis_index = AXES.index(zones["long_axis"])
        zone_labels = label_zone_points(
            points=points,
            axis_index=axis_index,
            bounds=mesh.bounds,
            boundaries=zones["boundaries"],
            edge_margin=edge_margin,
            curve_config=resolve_curve_config(zones.get("zone_shape", config.get("zone_shape"))),
        )
        local_thresholds = threshold_map_from_labels(zone_labels, thresholds)
        edge_mask = edge_frame_mask(points, mesh.bounds, edge_margin)
        local_thresholds[edge_mask] = float(thresholds["edgeFrame"])
        local_thresholds = apply_top_density_boost(
            thresholds=local_thresholds,
            points=points,
            bounds=mesh.bounds,
            pitch_mm=pitch,
            top_dense_layers=top_dense_layers,
            threshold_boost=top_dense_threshold_boost,
        )
        field = gyroid_field(points, wavelength_mm=wavelength)
        tpms_mask = inside_mask.reshape(-1) & (np.abs(field) <= local_thresholds)

        data = {
            "input_name": item["name"],
            "default_profile": config.get("default_profile"),
            "pitch_mm": pitch,
            "wavelength_mm": wavelength,
            "grid_shape": list(inside_mask.shape),
            "long_axis": zones["long_axis"],
            "boundaries": zones["boundaries"],
            "thresholds": thresholds,
            "surface": {
                "top_dense_layers": top_dense_layers,
                "top_dense_threshold_boost": top_dense_threshold_boost,
            },
            "origin_mm": [
                round(float(value), 6)
                for value in (
                    filled.transform.matrix[:3, 3] if hasattr(filled.transform, "matrix") else filled.transform[:3, 3]
                )
            ],
        }
        write_json(tpms_dir / f"{item['name']}_tpms.json", data)

        np.savez_compressed(
            tpms_dir / f"{item['name']}_tpms.npz",
            inside_mask=inside_mask,
            tpms_mask=tpms_mask.reshape(inside_mask.shape),
            pitch=np.array([pitch], dtype=float),
            transform=filled.transform.matrix if hasattr(filled.transform, "matrix") else filled.transform,
        )

        save_slice_preview(
            array=tpms_mask.reshape(inside_mask.shape).astype(float),
            output_path=tpms_dir / f"{item['name']}_tpms_slice.png",
            title=f"{item['name']} TPMS mask",
            cmap="magma",
        )


if __name__ == "__main__":
    main()
