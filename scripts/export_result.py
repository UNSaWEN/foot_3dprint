from __future__ import annotations

import argparse

from pathlib import Path

from common import discover_inputs, load_config, output_root, try_load_trimesh, write_json
from render_preview import save_mesh_projection_preview


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate exported lattice STLs.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    trimesh = try_load_trimesh()
    if trimesh is None:
        raise RuntimeError("export_result.py requires trimesh")

    config = load_config(args.config)
    final_dir = output_root(config) / "final"

    for item in discover_inputs(config):
        stl_path = final_dir / f"{item['name']}_lattice_insole.stl"
        if not Path(stl_path).exists():
            raise FileNotFoundError(f"Final STL missing: {stl_path}")
        mesh = trimesh.load_mesh(stl_path, process=True)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        payload = {
            "input_name": item["name"],
            "result_path": str(stl_path),
            "watertight": bool(mesh.is_watertight),
            "is_volume": bool(mesh.is_volume),
            "vertex_count": int(len(mesh.vertices)),
            "face_count": int(len(mesh.faces)),
            "surface_area_mm2": round(float(mesh.area), 4),
            "volume_mm3": round(float(mesh.volume), 4) if mesh.is_volume else None,
            "bounds_min_mm": [round(float(value), 4) for value in mesh.bounds[0]],
            "bounds_max_mm": [round(float(value), 4) for value in mesh.bounds[1]],
        }
        write_json(final_dir / f"{item['name']}_export_report.json", payload)
        save_mesh_projection_preview(
            mesh=mesh,
            output_path=final_dir / f"{item['name']}_export_projection.png",
            title=f"{item['name']} exported lattice projections",
        )


if __name__ == "__main__":
    main()
