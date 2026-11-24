from __future__ import annotations

import json
import math
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from default_profiles import DEFAULT_PROFILE_NAME, has_profile, resolve_tpms_thresholds, resolve_zone_settings


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "zone_params.json"

AXES = ("x", "y", "z")
INPUT_MODES = ("insole_solid", "plantar_scan_surface")
SIDES = ("left", "right")
LONGITUDINAL_ZONE_ORDER = ("heel", "arch", "forefoot", "toe")
ANATOMICAL_ZONE_ORDER = (
    "innerHeel",
    "outerHeel",
    "innerArch",
    "outerArch",
    "innerForefoot",
    "centralForefoot",
    "outerForefoot",
    "toe",
)


@dataclass
class MeshSummary:
    name: str
    path: str
    triangle_count: int
    min_bounds_mm: list[float]
    max_bounds_mm: list[float]
    extents_mm: list[float]
    units_guess: str
    likely_long_axis: str
    watertight: bool | None = None
    volume_mm3: float | None = None
    surface_area_mm2: float | None = None
    euler_number: int | None = None
    is_volume: bool | None = None
    vertex_count: int | None = None
    face_count: int | None = None


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    validate_config(config)
    return config


def output_root(config: dict[str, Any]) -> Path:
    return ROOT_DIR / config.get("output", {}).get("root", "output")


def resolve_workspace_path(path: str | Path) -> Path:
    target = Path(path)
    if not target.is_absolute():
        target = ROOT_DIR / target
    return target.resolve()


def default_prepared_input_path(config: dict[str, Any], input_name: str) -> Path:
    return (output_root(config) / "prepared" / f"{input_name}_prepared_insole.stl").resolve()


def ensure_directory(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    ensure_directory(target.parent)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def read_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def discover_inputs(config: dict[str, Any], require_prepared: bool = True) -> list[dict[str, Any]]:
    inputs = []
    for item in config.get("inputs", []):
        if "name" not in item or "path" not in item:
            raise ValueError("Each input must define both 'name' and 'path'")
        mode = str(item.get("mode", item.get("input_mode", "insole_solid")))
        if mode not in INPUT_MODES:
            raise ValueError(f"Unsupported input mode: {mode}")
        side = item.get("side")
        if side is not None and str(side) not in SIDES:
            raise ValueError("Input side must be one of: left, right")

        raw_path = resolve_workspace_path(item["path"])
        if not raw_path.exists():
            raise FileNotFoundError(f"Input STL not found: {raw_path}")

        if mode == "plantar_scan_surface":
            prepared_path = (
                resolve_workspace_path(item["prepared_path"])
                if item.get("prepared_path")
                else default_prepared_input_path(config, str(item["name"]))
            )
            if require_prepared and not prepared_path.exists():
                raise FileNotFoundError(f"Prepared insole STL not found: {prepared_path}")
            resolved = prepared_path
        else:
            prepared_path = raw_path
            resolved = raw_path

        inputs.append(
            {
                "name": item["name"],
                "path": resolved,
                "raw_path": raw_path,
                "prepared_path": prepared_path,
                "mode": mode,
                "side": str(side) if side is not None else None,
            }
        )
    return inputs


def guess_units(extents_mm_like: Iterable[float]) -> str:
    longest = max(extents_mm_like)
    if 180.0 <= longest <= 350.0:
        return "mm"
    if 18.0 <= longest <= 35.0:
        return "cm"
    return "unknown"


def axis_index_from_name(axis_name: str) -> int:
    lowered = axis_name.lower()
    if lowered not in AXES:
        raise ValueError(f"Unsupported axis: {axis_name}")
    return AXES.index(lowered)


def longest_axis(extents: Iterable[float], configured_axis: str = "auto") -> int:
    if configured_axis != "auto":
        return axis_index_from_name(configured_axis)
    extents_list = list(extents)
    return max(range(len(extents_list)), key=extents_list.__getitem__)


def normalize_zone_ratios(zone_ratios: dict[str, float]) -> dict[str, float]:
    normalized_input = dict(zone_ratios)
    if "forefoot" not in normalized_input and "metatarsal" in normalized_input:
        normalized_input["forefoot"] = normalized_input["metatarsal"]

    missing = [name for name in LONGITUDINAL_ZONE_ORDER if name not in normalized_input]
    if missing:
        raise ValueError(f"Missing zone ratios: {', '.join(missing)}")
    total = sum(normalized_input[name] for name in LONGITUDINAL_ZONE_ORDER)
    if math.isclose(total, 0.0, abs_tol=1e-9):
        raise ValueError("Zone ratios must not sum to zero")
    if not math.isclose(total, 1.0, abs_tol=1e-6):
        return {name: normalized_input[name] / total for name in LONGITUDINAL_ZONE_ORDER}
    return {name: normalized_input[name] for name in LONGITUDINAL_ZONE_ORDER}


def compute_zone_boundaries(
    bounds_min: Iterable[float],
    bounds_max: Iterable[float],
    zone_ratios: dict[str, float],
    axis_index: int,
    heel_at: str = "min",
) -> dict[str, dict[str, float]]:
    """Split the long axis from heel toward the toes.

    ``heel_at="min"`` puts the heel at the small coordinate. ``heel_at="max"``
    puts it at the large coordinate, and the same ratios still run
    heel, arch, forefoot, toe.
    """
    normalized = normalize_zone_ratios(zone_ratios)
    minimum = list(bounds_min)[axis_index]
    maximum = list(bounds_max)[axis_index]
    length = maximum - minimum
    if length <= 0:
        raise ValueError("Mesh has a non-positive length on the selected long axis")

    direction = str(heel_at)
    if direction not in {"min", "max"}:
        raise ValueError("heel_at must be min or max when computing zone boundaries")

    cursor = minimum if direction == "min" else maximum
    boundaries: dict[str, dict[str, float]] = {}
    for zone_name in LONGITUDINAL_ZONE_ORDER:
        width = length * normalized[zone_name]
        if direction == "min":
            zone_min = cursor
            zone_max = maximum if zone_name == LONGITUDINAL_ZONE_ORDER[-1] else cursor + width
            cursor = zone_max
        else:
            zone_max = cursor
            zone_min = minimum if zone_name == LONGITUDINAL_ZONE_ORDER[-1] else cursor - width
            cursor = zone_min
        boundaries[zone_name] = {
            "min_mm": round(zone_min, 4),
            "max_mm": round(zone_max, 4),
        }
    return boundaries


def binary_stl_summary(path: str | Path) -> MeshSummary:
    target = Path(path)
    with target.open("rb") as handle:
        header = handle.read(80)
        if len(header) != 80:
            raise ValueError(f"{target.name} is too small to be a valid binary STL")
        if header[:5].lower() == b"solid":
            raise ValueError(
                f"{target.name} looks like an ASCII STL. This script currently expects binary STL."
            )
        triangle_count = struct.unpack("<I", handle.read(4))[0]

        min_bounds = [math.inf, math.inf, math.inf]
        max_bounds = [-math.inf, -math.inf, -math.inf]

        for _ in range(triangle_count):
            handle.read(12)
            for _vertex in range(3):
                x, y, z = struct.unpack("<fff", handle.read(12))
                coords = (x, y, z)
                for axis in range(3):
                    if coords[axis] < min_bounds[axis]:
                        min_bounds[axis] = coords[axis]
                    if coords[axis] > max_bounds[axis]:
                        max_bounds[axis] = coords[axis]
            handle.read(2)

    extents = [max_bounds[i] - min_bounds[i] for i in range(3)]
    return MeshSummary(
        name=target.stem,
        path=str(target),
        triangle_count=triangle_count,
        min_bounds_mm=[round(value, 4) for value in min_bounds],
        max_bounds_mm=[round(value, 4) for value in max_bounds],
        extents_mm=[round(value, 4) for value in extents],
        units_guess=guess_units(extents),
        likely_long_axis=AXES[longest_axis(extents)],
    )


def mesh_summary_to_dict(summary: MeshSummary) -> dict[str, Any]:
    return asdict(summary)


def try_load_trimesh():
    try:
        import trimesh  # type: ignore
    except ImportError:
        return None
    return trimesh


def update_summary_from_trimesh(summary: MeshSummary) -> MeshSummary:
    trimesh = try_load_trimesh()
    if trimesh is None:
        return summary

    mesh = trimesh.load_mesh(summary.path, process=True)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

    summary.vertex_count = int(len(mesh.vertices))
    summary.face_count = int(len(mesh.faces))
    summary.triangle_count = summary.face_count
    summary.watertight = bool(mesh.is_watertight)
    summary.is_volume = bool(mesh.is_volume)
    summary.surface_area_mm2 = round(float(mesh.area), 4)
    try:
        summary.euler_number = int(mesh.euler_number)
    except Exception:
        summary.euler_number = None
    if mesh.is_volume:
        try:
            summary.volume_mm3 = round(float(mesh.volume), 4)
        except Exception:
            summary.volume_mm3 = None
    return summary


def mesh_summary_from_trimesh(path: str | Path, name: str | None = None) -> MeshSummary:
    trimesh = try_load_trimesh()
    if trimesh is None:
        raise RuntimeError("trimesh is required to summarize non-binary STL meshes")

    target = Path(path)
    mesh = trimesh.load_mesh(target, process=True)
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

    min_bounds = [float(value) for value in mesh.bounds[0]]
    max_bounds = [float(value) for value in mesh.bounds[1]]
    extents = [float(value) for value in mesh.extents]
    summary = MeshSummary(
        name=name or target.stem,
        path=str(target),
        triangle_count=int(len(mesh.faces)),
        min_bounds_mm=[round(value, 4) for value in min_bounds],
        max_bounds_mm=[round(value, 4) for value in max_bounds],
        extents_mm=[round(value, 4) for value in extents],
        units_guess=guess_units(extents),
        likely_long_axis=AXES[longest_axis(extents)],
        watertight=bool(mesh.is_watertight),
        volume_mm3=round(float(mesh.volume), 4) if mesh.is_volume else None,
        surface_area_mm2=round(float(mesh.area), 4),
        is_volume=bool(mesh.is_volume),
        vertex_count=int(len(mesh.vertices)),
        face_count=int(len(mesh.faces)),
    )
    try:
        summary.euler_number = int(mesh.euler_number)
    except Exception:
        summary.euler_number = None
    return summary


def validate_config(config: dict[str, Any]) -> None:
    required_top_level = ["inputs", "zone_ratios", "edge_frame_margin_mm", "voxel_pitch_mm", "tpms", "shell"]
    missing = [key for key in required_top_level if key not in config]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")

    if not isinstance(config["inputs"], list) or not config["inputs"]:
        raise ValueError("Config 'inputs' must be a non-empty list")
    for item in config["inputs"]:
        mode = str(item.get("mode", item.get("input_mode", "insole_solid")))
        if mode not in INPUT_MODES:
            raise ValueError(f"Unsupported input mode: {mode}")
        side = item.get("side")
        if side is not None and str(side) not in SIDES:
            raise ValueError("Input side must be one of: left, right")

    configured_long_axis = str(config.get("long_axis", "auto"))
    if configured_long_axis != "auto" and configured_long_axis not in AXES:
        raise ValueError("long_axis must be auto, x, y, or z")

    profile_name = str(config.get("default_profile", DEFAULT_PROFILE_NAME))
    if not has_profile(profile_name):
        raise ValueError(f"Unknown default_profile: {profile_name}")

    normalize_zone_ratios(config["zone_ratios"])

    voxel_pitch = float(config["voxel_pitch_mm"])
    if not math.isfinite(voxel_pitch) or voxel_pitch <= 0:
        raise ValueError("voxel_pitch_mm must be a positive finite number")

    edge_margin = float(config["edge_frame_margin_mm"])
    if not math.isfinite(edge_margin) or edge_margin < 0:
        raise ValueError("edge_frame_margin_mm must be a non-negative finite number")

    zone_shape = config.get("zone_shape", {})
    for name in ["heel_curve_mm", "arch_curve_mm", "toe_curve_mm"]:
        value = float(zone_shape.get(name, 0.0))
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"zone_shape {name} must be a non-negative finite number")
    center_power = float(zone_shape.get("center_power", 1.0))
    if not math.isfinite(center_power) or center_power <= 0:
        raise ValueError("zone_shape center_power must be a positive finite number")
    inner_side = str(zone_shape.get("inner_side", "auto"))
    if inner_side not in {"auto", "min", "max"}:
        raise ValueError("zone_shape inner_side must be one of: auto, min, max")
    heel_at = str(zone_shape.get("heel_at", "auto"))
    if heel_at not in {"auto", "min", "max"}:
        raise ValueError("zone_shape heel_at must be one of: auto, min, max")
    forefoot_center_width_ratio = float(zone_shape.get("forefoot_center_width_ratio", 0.28))
    if not math.isfinite(forefoot_center_width_ratio) or not (0.0 < forefoot_center_width_ratio < 1.0):
        raise ValueError("zone_shape forefoot_center_width_ratio must be between 0 and 1")

    tpms_required = ["type", "wavelength_mm", "transition_mm"]
    tpms_missing = [key for key in tpms_required if key not in config["tpms"]]
    if tpms_missing:
        raise ValueError(f"Missing tpms config keys: {', '.join(tpms_missing)}")

    if config["tpms"]["type"] != "gyroid":
        raise ValueError("Only tpms.type = 'gyroid' is currently supported")

    wavelength = float(config["tpms"]["wavelength_mm"])
    if not math.isfinite(wavelength) or wavelength <= 0:
        raise ValueError("tpms.wavelength_mm must be a positive finite number")

    transition = float(config["tpms"]["transition_mm"])
    if not math.isfinite(transition) or transition < 0:
        raise ValueError("tpms.transition_mm must be a non-negative finite number")

    thresholds = resolve_tpms_thresholds(config)
    resolve_zone_settings(config)
    for name in list(ANATOMICAL_ZONE_ORDER) + ["edgeFrame"]:
        if name not in thresholds:
            raise ValueError(f"Missing TPMS threshold for zone: {name}")
        value = float(thresholds[name])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"TPMS threshold for {name} must be a non-negative finite number")

    shell_required = ["skin_layers", "close_iterations"]
    shell_missing = [key for key in shell_required if key not in config["shell"]]
    if shell_missing:
        raise ValueError(f"Missing shell config keys: {', '.join(shell_missing)}")

    skin_layers = int(config["shell"]["skin_layers"])
    close_iterations = int(config["shell"]["close_iterations"])
    if skin_layers < 0 or close_iterations < 0:
        raise ValueError("shell skin_layers and close_iterations must be non-negative integers")

    surface = config.get("surface", {})
    for name in ["bottom_solid_layers", "top_skin_layers", "top_dense_layers"]:
        value = int(surface.get(name, 0))
        if value < 0:
            raise ValueError(f"surface {name} must be a non-negative integer")
    top_dense_threshold_boost = float(surface.get("top_dense_threshold_boost", 0.0))
    if not math.isfinite(top_dense_threshold_boost) or top_dense_threshold_boost < 0:
        raise ValueError("surface top_dense_threshold_boost must be a non-negative finite number")

    print_preset = config.get("print_preset")
    if print_preset is not None:
        if not isinstance(print_preset, dict):
            raise ValueError("print_preset must be an object")
        nozzle_diameter = float(print_preset.get("nozzle_diameter_mm", 0.4))
        layer_height = float(print_preset.get("layer_height_mm", 0.2))
        if not math.isfinite(nozzle_diameter) or nozzle_diameter <= 0:
            raise ValueError("print_preset nozzle_diameter_mm must be a positive finite number")
        if not math.isfinite(layer_height) or layer_height <= 0:
            raise ValueError("print_preset layer_height_mm must be a positive finite number")
        if not str(print_preset.get("material", "")).strip():
            raise ValueError("print_preset material must be a non-empty string")

