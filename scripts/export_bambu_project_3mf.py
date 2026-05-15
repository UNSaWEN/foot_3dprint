from __future__ import annotations

import argparse
import json
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from common import discover_inputs, ensure_directory, load_config, output_root
from export_zoned_3mf import build_zone_settings, export_scene_3mf, label_zone_points, voxel_points


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
BAMBU_NS = "http://schemas.bambulab.com/package/2021"

ET.register_namespace("", CORE_NS)
ET.register_namespace("p", PROD_NS)
ET.register_namespace("BambuStudio", BAMBU_NS)

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
    parser = argparse.ArgumentParser(description="Export Bambu project 3MFs with modifier settings.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    parser.add_argument(
        "--template",
        default=None,
        help="Existing BambuStudio project 3mf used as parameter template.",
    )
    return parser


def patch_project_settings(payload: dict[str, Any], settings: dict[str, dict[str, object]]) -> dict[str, Any]:
    patched = dict(payload)
    base = settings["base"]
    patched["sparse_infill_pattern"] = str(base["infill_pattern"])
    patched["sparse_infill_density"] = f"{int(base['infill_density_percent'])}%"
    patched["wall_loops"] = str(int(base["walls"]))
    patched["top_shell_layers"] = str(int(base["top_shell_layers"]))
    patched["bottom_shell_layers"] = str(int(base["bottom_shell_layers"]))
    return patched


def generate_uuid() -> str:
    return str(uuid.uuid4())


def object_display_name(foot_name: str, zone_name: str) -> str:
    return f"{foot_name}_{zone_name}"


def build_model_settings_xml(project_name: str, object_infos: list[dict[str, Any]], settings: dict[str, dict[str, object]]) -> str:
    root = ET.Element("config")
    object_node = ET.SubElement(root, "object", {"id": str(max(info["id"] for info in object_infos) + 1)})
    ET.SubElement(object_node, "metadata", {"key": "name", "value": project_name})
    ET.SubElement(object_node, "metadata", {"key": "extruder", "value": "1"})

    total_faces = sum(int(info.get("face_count", 0)) for info in object_infos)
    ET.SubElement(object_node, "metadata", {"face_count": str(total_faces)})

    for info in object_infos:
        zone_name = info.get("zone_name") or str(info["name"]).split("_", 1)[1]
        subtype = "normal_part" if zone_name == "base" else "modifier_part"
        part = ET.SubElement(object_node, "part", {"id": str(info["id"]), "subtype": subtype})
        ET.SubElement(part, "metadata", {"key": "name", "value": info["name"]})
        ET.SubElement(part, "metadata", {"key": "matrix", "value": "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"})
        ET.SubElement(part, "metadata", {"key": "source_file", "value": f"{project_name}.3mf"})
        ET.SubElement(part, "metadata", {"key": "source_object_id", "value": str(info["id"] - 1)})
        ET.SubElement(part, "metadata", {"key": "source_volume_id", "value": "0"})
        center = info.get("center", [0.0, 0.0, 0.0])
        ET.SubElement(part, "metadata", {"key": "source_offset_x", "value": f"{float(center[0]):.6f}"})
        ET.SubElement(part, "metadata", {"key": "source_offset_y", "value": f"{float(center[1]):.6f}"})
        ET.SubElement(part, "metadata", {"key": "source_offset_z", "value": f"{float(center[2]):.6f}"})
        ET.SubElement(part, "metadata", {"key": "extruder", "value": "1"})

        if zone_name != "base":
            zone_settings = settings[zone_name]
            ET.SubElement(part, "metadata", {"key": "skeleton_infill_density", "value": f"{int(zone_settings['infill_density_percent'])}%"})
            ET.SubElement(part, "metadata", {"key": "skin_infill_density", "value": f"{int(zone_settings['infill_density_percent'])}%"})
            ET.SubElement(part, "metadata", {"key": "sparse_infill_density", "value": f"{int(zone_settings['infill_density_percent'])}%"})
            ET.SubElement(part, "metadata", {"key": "sparse_infill_pattern", "value": str(zone_settings["infill_pattern"])})
            if zone_settings["walls"] is not None:
                ET.SubElement(part, "metadata", {"key": "wall_loops", "value": str(int(zone_settings["walls"]))})

        ET.SubElement(
            part,
            "mesh_stat",
            {
                "face_count": str(int(info.get("face_count", 0))),
                "edges_fixed": "0",
                "degenerate_facets": "0",
                "facets_removed": "0",
                "facets_reversed": "0",
                "backwards_edges": "0",
            },
        )

    plate = ET.SubElement(root, "plate")
    ET.SubElement(plate, "metadata", {"key": "plater_id", "value": "1"})
    ET.SubElement(plate, "metadata", {"key": "plater_name", "value": ""})
    ET.SubElement(plate, "metadata", {"key": "locked", "value": "false"})
    ET.SubElement(plate, "metadata", {"key": "filament_map_mode", "value": "Auto For Flush"})
    model_instance = ET.SubElement(plate, "model_instance")
    ET.SubElement(model_instance, "metadata", {"key": "object_id", "value": str(max(info["id"] for info in object_infos) + 1)})
    ET.SubElement(model_instance, "metadata", {"key": "instance_id", "value": "0"})
    ET.SubElement(model_instance, "metadata", {"key": "identify_id", "value": "170"})

    assemble = ET.SubElement(root, "assemble")
    ET.SubElement(
        assemble,
        "assemble_item",
        {
            "object_id": str(max(info["id"] for info in object_infos) + 1),
            "instance_id": "0",
            "transform": "1 0 0 0 1 0 0 0 1 0 0 15",
            "offset": "0 0 0",
        },
    )

    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def build_plate_metadata_json(project_name: str, base_info: dict[str, Any]) -> str:
    bbox = [
        round(base_info["bounds_min"][0], 4),
        round(base_info["bounds_min"][1], 4),
        round(base_info["bounds_max"][0], 4),
        round(base_info["bounds_max"][1], 4),
    ]
    payload = {
        "bbox_all": bbox,
        "bbox_objects": [
            {
                "area": round(base_info["area_xy"], 6),
                "bbox": bbox,
                "id": 250,
                "layer_height": 0.2,
                "name": project_name,
            }
        ],
        "bed_type": "hot_plate",
        "filament_colors": [],
        "filament_ids": [],
        "first_extruder": 0,
        "first_layer_time": 0,
        "is_seq_print": False,
        "nozzle_diameter": 0.4,
        "version": 2,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def parse_plain_3mf(plain_bytes: bytes) -> tuple[str, list[dict[str, Any]]]:
    with zipfile.ZipFile(BytesIO(plain_bytes), "r") as archive:
        model_xml = archive.read("3D/3dmodel.model").decode("utf-8")

    root = ET.fromstring(model_xml)
    resources = root.find(f"{{{CORE_NS}}}resources")
    if resources is None:
        raise ValueError("Plain 3MF missing resources node")

    object_infos: list[dict[str, Any]] = []
    for object_node in resources.findall(f"{{{CORE_NS}}}object"):
        mesh_node = object_node.find(f"{{{CORE_NS}}}mesh")
        if mesh_node is None:
            continue
        vertices_node = mesh_node.find(f"{{{CORE_NS}}}vertices")
        triangles_node = mesh_node.find(f"{{{CORE_NS}}}triangles")
        if vertices_node is None or triangles_node is None:
            continue

        xs: list[float] = []
        ys: list[float] = []
        zs: list[float] = []
        for vertex in vertices_node.findall(f"{{{CORE_NS}}}vertex"):
            xs.append(float(vertex.attrib["x"]))
            ys.append(float(vertex.attrib["y"]))
            zs.append(float(vertex.attrib["z"]))

        face_count = len(triangles_node.findall(f"{{{CORE_NS}}}triangle"))
        bounds_min = [min(xs), min(ys), min(zs)]
        bounds_max = [max(xs), max(ys), max(zs)]
        center = [
            (bounds_min[0] + bounds_max[0]) / 2.0,
            (bounds_min[1] + bounds_max[1]) / 2.0,
            (bounds_min[2] + bounds_max[2]) / 2.0,
        ]

        name = object_node.attrib.get("name", f"object_{object_node.attrib['id']}")
        zone_name = name.split("_", 1)[1] if "_" in name else name
        object_infos.append(
            {
                "id": int(object_node.attrib["id"]),
                "name": name,
                "zone_name": zone_name,
                "face_count": face_count,
                "center": center,
                "bounds_min": bounds_min,
                "bounds_max": bounds_max,
                "area_xy": (bounds_max[0] - bounds_min[0]) * (bounds_max[1] - bounds_min[1]),
            }
        )

    return model_xml, object_infos


def build_object_1_model_from_plain(plain_model_xml: str) -> str:
    plain_root = ET.fromstring(plain_model_xml)
    resources = plain_root.find(f"{{{CORE_NS}}}resources")
    if resources is None:
        raise ValueError("Plain 3MF missing resources")

    model = ET.Element(
        f"{{{CORE_NS}}}model",
        {
            "unit": "millimeter",
            "{http://www.w3.org/XML/1998/namespace}lang": "en-US",
            "requiredextensions": "p",
        },
    )
    ET.SubElement(model, f"{{{CORE_NS}}}metadata", {"name": "BambuStudio:3mfVersion"}).text = "1"
    new_resources = ET.SubElement(model, f"{{{CORE_NS}}}resources")
    for object_node in resources.findall(f"{{{CORE_NS}}}object"):
        new_resources.append(object_node)
    return ET.tostring(model, encoding="unicode", xml_declaration=True)


def build_top_model(object_infos: list[dict[str, Any]], project_name: str) -> str:
    model = ET.Element(
        f"{{{CORE_NS}}}model",
        {
            "unit": "millimeter",
            "{http://www.w3.org/XML/1998/namespace}lang": "en-US",
            "requiredextensions": "p",
        },
    )
    ET.SubElement(model, f"{{{CORE_NS}}}metadata", {"name": "Application"}).text = "BambuStudio-02.05.02.51"
    ET.SubElement(model, f"{{{CORE_NS}}}metadata", {"name": "BambuStudio:3mfVersion"}).text = "1"
    ET.SubElement(model, f"{{{CORE_NS}}}metadata", {"name": "CreationDate"}).text = "2026-03-28"
    ET.SubElement(model, f"{{{CORE_NS}}}metadata", {"name": "ModificationDate"}).text = "2026-03-28"

    resources = ET.SubElement(model, f"{{{CORE_NS}}}resources")
    project_object_id = max(info["id"] for info in object_infos) + 1
    project_object = ET.SubElement(
        resources,
        f"{{{CORE_NS}}}object",
        {
            "id": str(project_object_id),
            f"{{{PROD_NS}}}UUID": generate_uuid(),
            "type": "model",
        },
    )
    components = ET.SubElement(project_object, f"{{{CORE_NS}}}components")
    for info in object_infos:
        ET.SubElement(
            components,
            f"{{{CORE_NS}}}component",
            {
                f"{{{PROD_NS}}}path": "/3D/Objects/object_1.model",
                "objectid": str(info["id"]),
                f"{{{PROD_NS}}}UUID": generate_uuid(),
                "transform": "1 0 0 0 1 0 0 0 1 0 0 0",
            },
        )

    build = ET.SubElement(model, f"{{{CORE_NS}}}build", {f"{{{PROD_NS}}}UUID": generate_uuid()})
    ET.SubElement(
        build,
        f"{{{CORE_NS}}}item",
        {
            "objectid": str(project_object_id),
            f"{{{PROD_NS}}}UUID": generate_uuid(),
            "transform": "1 0 0 0 1 0 0 0 1 0 0 15",
            "printable": "1",
        },
    )
    return ET.tostring(model, encoding="unicode", xml_declaration=True)


def replace_file_bytes(zip_data: bytes, replacements: dict[str, bytes]) -> bytes:
    source = BytesIO(zip_data)
    output = BytesIO()
    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        existing = set()
        for item in zin.infolist():
            data = replacements.get(item.filename, zin.read(item.filename))
            zout.writestr(item.filename, data)
            existing.add(item.filename)
        for name, data in replacements.items():
            if name not in existing:
                zout.writestr(name, data)
    return output.getvalue()


def resolve_template_path(cli_template: str | None, final_dir: Path) -> Path:
    candidates = []
    if cli_template:
        path = Path(cli_template)
        candidates.append(path if path.is_absolute() else (Path.cwd() / path).resolve())
    candidates.extend(
        [
            final_dir / "bambu_template_left.3mf",
            final_dir / "left_engineering_modifiers.3mf",
            final_dir / "left_zoned_modifiers.3mf",
        ]
    )

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            with zipfile.ZipFile(candidate, "r") as archive:
                if "Metadata/project_settings.config" in archive.namelist():
                    return candidate
        except zipfile.BadZipFile:
            continue

    raise FileNotFoundError("No valid BambuStudio template 3mf found.")


def build_plain_scene_bytes(config: dict[str, Any], item: dict[str, Any]) -> bytes:
    trimesh = __import__("trimesh")
    import numpy as np  # type: ignore
    from trimesh.voxel.ops import matrix_to_marching_cubes  # type: ignore

    pitch = float(config["voxel_pitch_mm"])
    edge_margin = float(config["edge_frame_margin_mm"])
    zone_path = output_root(config) / "zones" / f"{item['name']}_zones.json"
    if not zone_path.exists():
        raise FileNotFoundError(f"Zone definition missing: {zone_path}")
    zones = json.loads(zone_path.read_text(encoding="utf-8"))

    mesh = trimesh.load_mesh(item["path"], process=True)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

    voxelized = mesh.voxelized(pitch).fill()
    inside_mask = voxelized.matrix.astype(bool)
    points = voxel_points(voxelized)
    axis_index = ("x", "y", "z").index(zones["long_axis"])
    labels = label_zone_points(
        points=points,
        axis_index=axis_index,
        bounds=mesh.bounds,
        boundaries=zones["boundaries"],
        edge_margin=edge_margin,
        curve_config=zones.get("zone_shape", config.get("zone_shape")),
    ).reshape(inside_mask.shape)

    scene = trimesh.Scene()
    scene.add_geometry(mesh.copy(), geom_name=f"{item['name']}_base")
    for zone_name in ZONE_ORDER:
        zone_mask = inside_mask & (labels == zone_name)
        if not np.any(zone_mask):
            continue
        zone_mesh = matrix_to_marching_cubes(zone_mask, pitch=pitch)
        zone_mesh.process(validate=True)
        scene.add_geometry(zone_mesh, geom_name=f"{item['name']}_{zone_name}")

    output = BytesIO()
    exported = scene.export(file_type="3mf")
    if isinstance(exported, str):
        output.write(exported.encode("utf-8"))
    else:
        output.write(exported)
    return output.getvalue()


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    final_dir = ensure_directory(output_root(config) / "final")
    template_path = resolve_template_path(args.template, final_dir)

    template_bytes = template_path.read_bytes()
    settings = build_zone_settings(config)

    manifest: dict[str, Any] = {"template": str(template_path), "files": []}

    for item in discover_inputs(config):
        plain_model_xml, object_infos = parse_plain_3mf(build_plain_scene_bytes(config, item))
        object_1_model_xml = build_object_1_model_from_plain(plain_model_xml)
        top_model_xml = build_top_model(object_infos, f"{item['name']}_engineering_modifiers")
        model_settings_xml = build_model_settings_xml(
            project_name=f"{item['name']}_engineering_modifiers",
            object_infos=object_infos,
            settings=settings,
        )

        with zipfile.ZipFile(BytesIO(template_bytes), "r") as archive:
            project_settings = json.loads(archive.read("Metadata/project_settings.config").decode("utf-8-sig", errors="ignore"))
        patched_project_settings = patch_project_settings(project_settings, settings)

        base_info = next(info for info in object_infos if info["zone_name"] == "base")
        replacements = {
            "3D/3dmodel.model": top_model_xml.encode("utf-8"),
            "3D/Objects/object_1.model": object_1_model_xml.encode("utf-8"),
            "Metadata/model_settings.config": model_settings_xml.encode("utf-8"),
            "Metadata/project_settings.config": json.dumps(
                patched_project_settings, ensure_ascii=False, indent=4
            ).encode("utf-8"),
            "Metadata/plate_1.json": build_plate_metadata_json(f"{item['name']}_engineering_modifiers", base_info).encode(
                "utf-8"
            ),
        }

        output_bytes = replace_file_bytes(template_bytes, replacements)
        out_path = final_dir / f"{item['name']}_engineering_modifiers.3mf"
        out_path.write_bytes(output_bytes)

        manifest["files"].append(
            {
                "foot": item["name"],
                "path": str(out_path),
                "settings": settings,
            }
        )

    (final_dir / "engineering_3mf_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
