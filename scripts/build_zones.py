from __future__ import annotations

import argparse

from common import (
    AXES,
    compute_zone_boundaries,
    discover_inputs,
    load_config,
    longest_axis,
    normalize_zone_ratios,
    output_root,
    try_load_trimesh,
    write_json,
)
from render_preview import save_zone_preview
from zone_strategy import label_zone_points, resolve_curve_config


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build top-level insole zones.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    return parser

def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    trimesh = try_load_trimesh()
    if trimesh is None:
        raise RuntimeError("build_zones.py requires trimesh")

    zone_dir = output_root(config) / "zones"
    ratios = normalize_zone_ratios(config["zone_ratios"])
    edge_margin = float(config["edge_frame_margin_mm"])
    curve_config = resolve_curve_config(config.get("zone_shape"))

    for item in discover_inputs(config):
        mesh = trimesh.load_mesh(item["path"], process=False)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        bounds = mesh.bounds
        extents = bounds[1] - bounds[0]
        axis_index = longest_axis(extents, config.get("long_axis", "auto"))
        boundaries = compute_zone_boundaries(
            bounds_min=bounds[0],
            bounds_max=bounds[1],
            zone_ratios=ratios,
            axis_index=axis_index,
        )

        labels = label_zone_points(
            points=mesh.vertices,
            axis_index=axis_index,
            bounds=mesh.bounds,
            boundaries=boundaries,
            edge_margin=edge_margin,
            curve_config=curve_config,
        )

        payload = {
            "input_name": item["name"],
            "input_path": str(item["path"]),
            "bounds_min_mm": [round(float(value), 4) for value in bounds[0]],
            "bounds_max_mm": [round(float(value), 4) for value in bounds[1]],
            "extents_mm": [round(float(value), 4) for value in extents],
            "long_axis": AXES[axis_index],
            "zone_ratios": ratios,
            "edge_frame_margin_mm": edge_margin,
            "boundaries": boundaries,
            "zone_shape": curve_config,
        }
        write_json(zone_dir / f"{item['name']}_zones.json", payload)

        save_zone_preview(
            points=mesh.vertices,
            labels=labels,
            output_path=zone_dir / f"{item['name']}_zones.png",
            long_axis_index=axis_index,
            title=f"{item['name']} zone preview ({AXES[axis_index]} axis)",
        )


if __name__ == "__main__":
    main()
