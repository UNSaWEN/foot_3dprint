from __future__ import annotations

import argparse
from pathlib import Path

from common import AXES, discover_inputs, ensure_directory, load_config, output_root, read_json, write_json
from render_preview import save_slice_preview


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clip TPMS lattice into insole shell.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    return parser


def mask_points(shape, transform):
    import numpy as np  # type: ignore
    import trimesh  # type: ignore

    indices = np.indices(shape).reshape(3, -1).T
    points = trimesh.transform_points(indices.astype(float), transform)
    return points


def edge_frame_mask(points, bounds, margin_mm):
    import numpy as np  # type: ignore

    minimum = bounds[0]
    maximum = bounds[1]
    near_x = (points[:, 0] - minimum[0] <= margin_mm) | (maximum[0] - points[:, 0] <= margin_mm)
    near_y = (points[:, 1] - minimum[1] <= margin_mm) | (maximum[1] - points[:, 1] <= margin_mm)
    return near_x | near_y


def surface_layer_mask(points, bounds, pitch_mm, layers, surface):
    import numpy as np  # type: ignore

    if layers <= 0:
        return np.zeros(len(points), dtype=bool)

    depth_mm = float(layers) * float(pitch_mm)
    if surface == "bottom":
        limit = float(bounds[0][2]) + depth_mm
        return points[:, 2] <= limit
    if surface == "top":
        limit = float(bounds[1][2]) - depth_mm
        return points[:, 2] >= limit
    raise ValueError(f"Unsupported surface: {surface}")


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_config(args.config)

    import numpy as np  # type: ignore
    import trimesh  # type: ignore
    from scipy import ndimage  # type: ignore
    from trimesh.voxel.ops import matrix_to_marching_cubes  # type: ignore

    final_dir = ensure_directory(output_root(config) / "final")
    pitch = float(config["voxel_pitch_mm"])
    shell_layers = int(config["shell"]["skin_layers"])
    close_iterations = int(config["shell"]["close_iterations"])
    edge_margin = float(config["edge_frame_margin_mm"])
    surface = dict(config.get("surface", {}))
    bottom_solid_layers = int(surface.get("bottom_solid_layers", 0))
    top_skin_layers = int(surface.get("top_skin_layers", 0))

    for item in discover_inputs(config):
        tpms_path = output_root(config) / "tpms" / f"{item['name']}_tpms.npz"
        zone_path = output_root(config) / "zones" / f"{item['name']}_zones.json"
        if not Path(tpms_path).exists():
            raise FileNotFoundError(f"TPMS data missing: {tpms_path}")
        if not Path(zone_path).exists():
            raise FileNotFoundError(f"Zone definition missing: {zone_path}")

        tpms_data = np.load(tpms_path)
        zones = read_json(zone_path)
        mesh = trimesh.load_mesh(item["path"], process=False)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        inside_mask = tpms_data["inside_mask"].astype(bool)
        tpms_mask = tpms_data["tpms_mask"].astype(bool)
        transform = tpms_data["transform"]
        if inside_mask.shape != tpms_mask.shape:
            raise ValueError(f"inside_mask and tpms_mask shape mismatch for {item['name']}")
        if transform.shape != (4, 4):
            raise ValueError(f"Invalid transform shape for {item['name']}: {transform.shape}")
        points = mask_points(inside_mask.shape, transform)

        eroded = ndimage.binary_erosion(inside_mask, iterations=max(shell_layers, 0))
        shell_mask = inside_mask & ~eroded
        edge_mask = edge_frame_mask(points, mesh.bounds, edge_margin).reshape(inside_mask.shape) & inside_mask
        bottom_solid_mask = (
            surface_layer_mask(points, mesh.bounds, pitch_mm=pitch, layers=bottom_solid_layers, surface="bottom")
            .reshape(inside_mask.shape)
            & inside_mask
        )
        top_skin_mask = (
            surface_layer_mask(points, mesh.bounds, pitch_mm=pitch, layers=top_skin_layers, surface="top")
            .reshape(inside_mask.shape)
            & inside_mask
        )

        final_mask = tpms_mask | shell_mask | edge_mask | bottom_solid_mask | top_skin_mask
        if close_iterations > 0:
            final_mask = ndimage.binary_closing(final_mask, iterations=close_iterations)
        if not np.any(final_mask):
            raise RuntimeError(f"Final lattice mask is empty for {item['name']}")

        result_mesh = matrix_to_marching_cubes(final_mask, pitch=pitch)
        result_mesh.process(validate=True)

        stl_path = final_dir / f"{item['name']}_lattice_insole.stl"
        result_mesh.export(stl_path)

        payload = {
            "input_name": item["name"],
            "long_axis": zones["long_axis"],
            "pitch_mm": pitch,
            "skin_layers": shell_layers,
            "edge_frame_margin_mm": edge_margin,
            "bottom_solid_layers": bottom_solid_layers,
            "top_skin_layers": top_skin_layers,
            "voxel_shape": list(final_mask.shape),
            "watertight": bool(result_mesh.is_watertight),
            "volume_mm3": round(float(result_mesh.volume), 4) if result_mesh.is_volume else None,
            "surface_area_mm2": round(float(result_mesh.area), 4),
            "vertex_count": int(len(result_mesh.vertices)),
            "face_count": int(len(result_mesh.faces)),
        }
        write_json(final_dir / f"{item['name']}_lattice_report.json", payload)

        save_slice_preview(
            array=final_mask.astype(float),
            output_path=final_dir / f"{item['name']}_final_slice.png",
            title=f"{item['name']} final lattice mask",
            cmap="viridis",
        )


if __name__ == "__main__":
    main()
