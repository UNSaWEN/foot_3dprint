# Input Models

This directory is for local foot input files. Raw STL scans and meshes are not committed to the repository.

## Two Data Sources

This project supports two input modes, switched via the `mode` field in `inputs` within `config/zone_params.json`:

### Mode 1: `insole_solid` (Existing Closed Insole STL)

If you already have a complete insole 3D model (watertight solid):

```json
{
  "name": "left",
  "path": "input/left_insole.stl",
  "mode": "insole_solid",
  "side": "left"
}
```

- Source: CAD modeling software export, existing insole STL files
- Preprocessing: This mode skips preprocessing and reuses the original STL directly

### Mode 2: `plantar_scan_surface` (Direct Plantar Scan Open Surface STL)

If you scanned the sole of your foot using an iPhone/FaceID-like app:

```json
{
  "name": "left",
  "path": "input/left_plantar_scan.stl",
  "mode": "plantar_scan_surface",
  "side": "left"
}
```

- Source: 3D scanning apps (e.g., Polycam, Scaniverse) exporting plantar surface
- Preprocessing: `prepare_inputs.py` closes the open surface into a printable insole blank. The outline is offset by `outline_margin_mm`, the bottom stays flat, the top follows the scan, and rise above the lowest point defaults to at most `scan_preprocess.max_relief_mm` (`8.0`)
- Note: You must confirm `scan_preprocess.*` axis parameters match the app's coordinate system

## Local File Names

Use these names as examples when placing your own input files here, or point `config/zone_params.json` to any resolvable path.

- `left_insole.stl`: example name for a left closed insole input
- `right_insole.stl`: example name for a right closed insole input
- `left_plantar_scan.stl`: example name for a left plantar scan input
- `right_plantar_scan.stl`: example name for a right plantar scan input

These names document the expected configuration only and are not committed as sample assets.

## Quick Switching Example

Full configuration example (left foot uses closed STL, right foot uses scan):

```json
"inputs": [
  {
    "name": "left",
    "path": "input/left_insole.stl",
    "mode": "insole_solid",
    "side": "left"
  },
  {
    "name": "right",
    "path": "input/right_plantar_scan.stl",
    "mode": "plantar_scan_surface",
    "side": "right"
  }
]
```

Each input's mode is independent and can be mixed.

## Path Flexibility

The project does not require inputs to live inside `input/` as long as the configured paths resolve correctly.
