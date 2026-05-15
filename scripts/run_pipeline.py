from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from common import load_config

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the full insole lattice pipeline.")
    parser.add_argument("--config", default=None, help="Path to config JSON.")
    parser.add_argument(
        "--steps",
        nargs="*",
        default=[
            "prepare_inputs",
            "inspect_mesh",
            "build_zones",
            "generate_tpms",
            "clip_lattice",
            "export_result",
            "export_zoned_3mf",
            "export_bambu_project_3mf",
        ],
        help="Subset of scripts to run in order.",
    )
    parser.add_argument(
        "--input",
        action="append",
        dest="inputs",
        default=None,
        help=(
            "Override a single input entry. Format: 'name=path,mode=...,side=...'. "
            "Example: --input 'left=input/my_left.stl,mode=insole_solid,side=left'. "
            "Can be passed multiple times to override or add inputs."
        ),
    )
    return parser


def parse_input_override(raw: str) -> dict:
    """Parse input override string. Format: 'name=path,mode=...,side=...'

    Uses comma as delimiter to avoid conflicts with Windows drive letters (e.g. C:\\).
    """
    parts = raw.split(",")
    name_path = parts[0].split("=", 1)
    if len(name_path) != 2:
        raise ValueError(f"Invalid --input format (need name=path): {raw}")
    entry = {"name": name_path[0], "path": name_path[1]}
    for part in parts[1:]:
        if "=" not in part:
            raise ValueError(f"Invalid key=value pair in --input: {part}")
        key, value = part.split("=", 1)
        entry[key] = value
    return entry


def build_merged_config_path(base_config_path: str | None, input_overrides: list[str] | None) -> str | None:
    if not input_overrides:
        return base_config_path

    config = load_config(base_config_path)
    parsed = [parse_input_override(raw) for raw in input_overrides]

    existing_by_name = {item["name"]: idx for idx, item in enumerate(config["inputs"])}
    for entry in parsed:
        if entry["name"] in existing_by_name:
            idx = existing_by_name[entry["name"]]
            config["inputs"][idx].update(entry)
        else:
            config["inputs"].append(entry)

    tmp_path = ROOT_DIR / ".tmp_config_override.json"
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return str(tmp_path)


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    effective_config = build_merged_config_path(args.config, args.inputs)

    for step in args.steps:
        script_path = SCRIPT_DIR / f"{step}.py"
        if not script_path.exists():
            raise FileNotFoundError(f"Unknown step: {step}")

        command = [sys.executable, str(script_path)]
        if effective_config:
            command.extend(["--config", effective_config])

        print(f"[pipeline] running {step}")
        subprocess.run(command, check=True, cwd=ROOT_DIR)


if __name__ == "__main__":
    main()
