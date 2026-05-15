from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from common import AXES, discover_inputs, ensure_directory, load_config, output_root, read_json, try_load_trimesh
from default_profiles import resolve_zone_settings
from zone_strategy import label_zone_points, resolve_curve_config


ZONE_ORDER = (
    "innerHeel",
    "outerHeel",
    "innerArch",
    "outerArch",
    "innerForefoot",
    "centralForefoot",
    "outerForefoot",
    "toe",
    "edgeFrame",
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export zoned 3MF files for slicer modifiers.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    return parser

def voxel_points(voxelized):
    import trimesh  # type: ignore

    indices = np.indices(voxelized.matrix.shape).reshape(3, -1).T
    transform = voxelized.transform.matrix if hasattr(voxelized.transform, "matrix") else voxelized.transform
    points = trimesh.transform_points(indices.astype(float), transform)
    return points


def build_zone_settings(config: dict[str, object] | None = None) -> dict[str, dict[str, object]]:
    return resolve_zone_settings(config)


def export_scene_3mf(scene, output_path: Path) -> None:
    exported = scene.export(file_type="3mf")
    if isinstance(exported, str):
        output_path.write_text(exported, encoding="utf-8")
    else:
        output_path.write_bytes(exported)


def write_recommendation_markdown(path: Path, foot_name: str, settings: dict[str, dict[str, object]]) -> None:
    base_walls = settings["base"]["walls"]
    lines = [
        f"# {foot_name} 分区切片建议",
        "",
        "导入 `3mf` 后，保留 `base` 为主体模型，其他对象在拓竹/Orca 中手动设为 `modifier`。",
        "",
        "| 区域 | 对象名 | 建议填充 | 建议密度 | 壁数 | 说明 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    object_names = {
        "base": f"{foot_name}_base",
        "innerHeel": f"{foot_name}_innerHeel",
        "outerHeel": f"{foot_name}_outerHeel",
        "innerArch": f"{foot_name}_innerArch",
        "outerArch": f"{foot_name}_outerArch",
        "innerForefoot": f"{foot_name}_innerForefoot",
        "centralForefoot": f"{foot_name}_centralForefoot",
        "outerForefoot": f"{foot_name}_outerForefoot",
        "toe": f"{foot_name}_toe",
        "edgeFrame": f"{foot_name}_edgeFrame",
    }
    for zone_name in ("base",) + ZONE_ORDER:
        setting = settings[zone_name]
        lines.append(
            "| {zone} | `{obj}` | `{pattern}` | `{density}%` | `{walls}` | {notes} |".format(
                zone=zone_name,
                obj=object_names[zone_name],
                pattern=setting["infill_pattern"],
                density=setting["infill_density_percent"],
                walls=setting["walls"] if setting["walls"] is not None else f"inherit({base_walls})",
                notes=setting["notes"],
            )
        )

    ensure_directory(path.parent)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    trimesh = try_load_trimesh()
    if trimesh is None:
        raise RuntimeError("export_zoned_3mf.py requires trimesh")

    from trimesh.voxel.ops import matrix_to_marching_cubes  # type: ignore

    final_dir = ensure_directory(output_root(config) / "final")
    pitch = float(config["voxel_pitch_mm"])
    edge_margin = float(config["edge_frame_margin_mm"])
    settings = build_zone_settings(config)

    combined_manifest: dict[str, object] = {"files": []}

    for item in discover_inputs(config):
        zone_path = output_root(config) / "zones" / f"{item['name']}_zones.json"
        if not Path(zone_path).exists():
            raise FileNotFoundError(f"Zone definition missing: {zone_path}")
        zones = read_json(zone_path)

        mesh = trimesh.load_mesh(item["path"], process=True)
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        voxelized = mesh.voxelized(pitch).fill()
        inside_mask = voxelized.matrix.astype(bool)
        points = voxel_points(voxelized)
        axis_index = AXES.index(zones["long_axis"])
        labels = label_zone_points(
            points=points,
            axis_index=axis_index,
            bounds=mesh.bounds,
            boundaries=zones["boundaries"],
            edge_margin=edge_margin,
            curve_config=resolve_curve_config(zones.get("zone_shape", config.get("zone_shape"))),
        ).reshape(inside_mask.shape)

        scene = trimesh.Scene()
        scene.add_geometry(mesh.copy(), geom_name=f"{item['name']}_base")

        exported_zones = []
        for zone_name in ZONE_ORDER:
            zone_mask = inside_mask & (labels == zone_name)
            if not np.any(zone_mask):
                continue
            zone_mesh = matrix_to_marching_cubes(zone_mask, pitch=pitch)
            zone_mesh.process(validate=True)
            scene.add_geometry(zone_mesh, geom_name=f"{item['name']}_{zone_name}")
            exported_zones.append(zone_name)

        scene.metadata["zone_settings"] = json.dumps(settings, ensure_ascii=False)
        output_path = final_dir / f"{item['name']}_zoned_modifiers.3mf"
        export_scene_3mf(scene, output_path)

        settings_path = final_dir / f"{item['name']}_zoned_modifiers_settings.json"
        settings_payload = {
            "foot": item["name"],
            "path": str(output_path),
            "zones_exported": exported_zones,
            "instructions": [
                "导入 3mf 后，保留 *_base 为普通模型。",
                "将其余解剖分区对象逐个设置为 modifier。",
                "再按本文件中的建议填充密度设置各分区参数。",
            ],
            "settings": settings,
        }
        settings_path.write_text(json.dumps(settings_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        write_recommendation_markdown(final_dir / f"{item['name']}_zoned_modifiers_settings.md", item["name"], settings)

        combined_manifest["files"].append(
            {
                "foot": item["name"],
                "3mf": str(output_path),
                "settings_json": str(settings_path),
                "zones_exported": exported_zones,
            }
        )

    (final_dir / "zoned_3mf_manifest.json").write_text(
        json.dumps(combined_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
