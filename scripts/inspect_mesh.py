from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    discover_inputs,
    load_config,
    mesh_summary_from_trimesh,
    mesh_summary_to_dict,
    output_root,
    write_json,
)
from render_preview import save_mesh_projection_preview


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect insole STL meshes.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    return parser


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    inspection_dir = output_root(config) / "inspection"
    report: list[dict] = []

    trimesh_module = None
    try:
        import trimesh as trimesh_module  # type: ignore
    except ImportError:
        trimesh_module = None

    for item in discover_inputs(config):
        summary = mesh_summary_from_trimesh(item["path"], name=item["name"])
        payload = mesh_summary_to_dict(summary)
        payload["mode"] = item["mode"]
        payload["raw_path"] = str(item["raw_path"])
        payload["prepared_path"] = str(item["prepared_path"])
        report.append(payload)

        write_json(inspection_dir / f"{item['name']}_inspection.json", payload)

        if trimesh_module is not None:
            mesh = trimesh_module.load_mesh(item["path"], process=False)
            if isinstance(mesh, trimesh_module.Scene):
                mesh = trimesh_module.util.concatenate(tuple(mesh.geometry.values()))
            save_mesh_projection_preview(
                mesh=mesh,
                output_path=inspection_dir / f"{item['name']}_projection.png",
                title=f"{item['name']} mesh projections",
            )

            if item["mode"] == "plantar_scan_surface":
                raw_mesh = trimesh_module.load_mesh(item["raw_path"], process=False)
                if isinstance(raw_mesh, trimesh_module.Scene):
                    raw_mesh = trimesh_module.util.concatenate(tuple(raw_mesh.geometry.values()))
                raw_summary = mesh_summary_to_dict(mesh_summary_from_trimesh(item["raw_path"], name=f"{item['name']}_raw"))
                raw_summary["mode"] = item["mode"]
                raw_summary["raw_path"] = str(item["raw_path"])
                raw_summary["prepared_path"] = str(item["prepared_path"])
                write_json(inspection_dir / f"{item['name']}_raw_inspection.json", raw_summary)
                save_mesh_projection_preview(
                    mesh=raw_mesh,
                    output_path=inspection_dir / f"{item['name']}_raw_projection.png",
                    title=f"{item['name']} raw scan projections",
                )

    combined = {
        "inputs": report,
        "notes": [
            "units_guess 仅用于初步判断，实际单位仍需结合人工确认。",
            "直扫输入会同时检查原始扫描和预处理后的封闭鞋垫坯体。",
            "如果缺少 trimesh 或 matplotlib，将只输出 JSON，不生成预览图。",
        ],
    }
    write_json(inspection_dir / "inspection_summary.json", combined)


if __name__ == "__main__":
    main()
