from __future__ import annotations

import argparse
from pathlib import Path

from common import discover_inputs, load_config, output_root, read_json, write_json
from default_profiles import resolve_tpms_thresholds
from render_preview import save_slice_preview
from voxel_fields import as_transform_matrix, load_closed_mesh, local_surface_mask, voxel_zone_labels
from zone_strategy import resolve_curve_config


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


def blend_zone_thresholds(labels, zone_thresholds, inside_mask, pitch, transition_mm):
    """Blend hard zone thresholds where a different zone is within ``transition_mm``.

    ``transition_mm == 0`` keeps the hard assignment. Inside the band the value
    is a distance-weighted mix of the two neighboring thresholds.
    """
    import numpy as np  # type: ignore
    from scipy import ndimage  # type: ignore

    labels = np.asarray(labels)
    inside = np.asarray(inside_mask, dtype=bool)
    hard = threshold_map_from_labels(labels.reshape(-1), zone_thresholds)
    transition = float(transition_mm)
    if transition <= 0.0:
        return hard

    shape = inside.shape
    labels_3d = labels.reshape(shape)
    present = [str(name) for name in np.unique(labels_3d[inside])]
    if len(present) < 2:
        return hard

    distances = []
    for name in present:
        zone_mask = inside & (labels_3d == name)
        distances.append(ndimage.distance_transform_edt(~zone_mask) * float(pitch))
    distance_stack = np.stack(distances, axis=0)

    own_index = np.zeros(shape, dtype=np.int32)
    for index, name in enumerate(present):
        own_index[labels_3d == name] = index

    other_distances = distance_stack.copy()
    grid = np.indices(shape)
    other_distances[own_index, grid[0], grid[1], grid[2]] = np.inf
    nearest_distance = np.min(other_distances, axis=0)
    nearest_index = np.argmin(other_distances, axis=0)

    hard_3d = hard.reshape(shape)
    other_threshold = np.array([float(zone_thresholds[name]) for name in present], dtype=float)[nearest_index]
    own_weight = 0.5 + 0.5 * np.clip(nearest_distance / transition, 0.0, 1.0)
    blended = own_weight * hard_3d + (1.0 - own_weight) * other_threshold
    use_blend = inside & np.isfinite(nearest_distance) & (nearest_distance <= transition)
    return np.where(use_blend, blended, hard_3d).reshape(-1)


def apply_top_density_boost(thresholds, inside_mask, top_dense_layers, threshold_boost):
    import numpy as np  # type: ignore

    values = np.array(thresholds, dtype=float, copy=True).reshape(-1)
    if int(top_dense_layers) <= 0 or float(threshold_boost) <= 0.0:
        return values

    top_mask = local_surface_mask(inside_mask, int(top_dense_layers), "top").reshape(-1)
    if top_mask.shape != values.shape:
        raise ValueError("thresholds must have one value per voxel")
    values[top_mask] = values[top_mask] + float(threshold_boost)
    return values


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_config(args.config)

    import numpy as np  # type: ignore

    tpms_dir = output_root(config) / "tpms"
    pitch = float(config["voxel_pitch_mm"])
    wavelength = float(config["tpms"]["wavelength_mm"])
    thresholds = resolve_tpms_thresholds(config)
    edge_margin = float(config["edge_frame_margin_mm"])
    max_voxels = int(config.get("max_voxels", 1500000))
    transition_mm = float(config["tpms"]["transition_mm"])
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
        mesh = load_closed_mesh(item["path"])
        curve_config = resolve_curve_config(zones.get("zone_shape", config.get("zone_shape")))
        voxelized, inside_mask, points, zone_labels = voxel_zone_labels(
            mesh,
            zones,
            pitch=pitch,
            edge_margin=edge_margin,
            curve_config=curve_config,
            max_voxels=max_voxels,
        )

        local_thresholds = blend_zone_thresholds(
            labels=zone_labels,
            zone_thresholds=thresholds,
            inside_mask=inside_mask,
            pitch=pitch,
            transition_mm=transition_mm,
        )
        local_thresholds = apply_top_density_boost(
            thresholds=local_thresholds,
            inside_mask=inside_mask,
            top_dense_layers=top_dense_layers,
            threshold_boost=top_dense_threshold_boost,
        )
        field = gyroid_field(points, wavelength_mm=wavelength)
        tpms_mask = inside_mask.reshape(-1) & (np.abs(field) <= local_thresholds)
        transform = as_transform_matrix(voxelized)

        data = {
            "input_name": item["name"],
            "default_profile": config.get("default_profile"),
            "pitch_mm": pitch,
            "wavelength_mm": wavelength,
            "transition_mm": transition_mm,
            "grid_shape": list(inside_mask.shape),
            "long_axis": zones["long_axis"],
            "boundaries": zones["boundaries"],
            "thresholds": thresholds,
            "surface": {
                "top_dense_layers": top_dense_layers,
                "top_dense_threshold_boost": top_dense_threshold_boost,
            },
            "origin_mm": [round(float(value), 6) for value in transform[:3, 3]],
        }
        write_json(tpms_dir / f"{item['name']}_tpms.json", data)

        np.savez_compressed(
            tpms_dir / f"{item['name']}_tpms.npz",
            inside_mask=inside_mask,
            tpms_mask=tpms_mask.reshape(inside_mask.shape),
            pitch=np.array([pitch], dtype=float),
            transform=transform,
        )

        save_slice_preview(
            array=tpms_mask.reshape(inside_mask.shape).astype(float),
            output_path=tpms_dir / f"{item['name']}_tpms_slice.png",
            title=f"{item['name']} TPMS mask",
            cmap="magma",
        )


if __name__ == "__main__":
    main()
