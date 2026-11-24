# Research-Driven Insole Zoning and Lattice Workflow

[中文文档](README.zh-CN.md) | [English](README.en.md)

Generates zoned `3MF` files, Bambu engineering `3MF` with local parameters, and printable TPMS/gyroid lattice insole `STL` from left/right insole `STL` models.

Default zoning uses a research-driven anatomical region model:

- `innerHeel`
- `outerHeel`
- `innerArch`
- `outerArch`
- `innerForefoot`
- `centralForefoot`
- `outerForefoot`
- `toe`
- `edgeFrame`

The goal is to separate common high-pressure plantar regions, arch support zones, and outer rim stabilization zones. The default template targets `healthy adult Asian males` in a `daily walking + light sports` mixed scenario, while retaining profile switching capability for different user needs.

## Project Goals

- Automatically generate zoned results from existing insole `STL` without interactive modeling software
- Control infill patterns and density per zone via slicer modifiers
- Preserve a direct path to printable lattice `STL`
- Make parameters, zoning, and export workflows fully scriptable and reproducible

## Design Rationale

Default zones and parameters are engineering starting points based on public literature, not medical prescriptions. The default template primarily references:

- Plantar pressure redistribution in asymptomatic men using different insoles
- Baseline plantar pressure in normal young Chinese adults during standing and walking
- General principles of arch support, total contact, and porous structure for pressure redistribution
- Engineering needs for outer rim stability in slicing and print durability

Short reference sources in `REFERENCES.en.md`.

## Data Source Switching

This project supports two input data sources. Each input can independently choose its mode, and they can be mixed.

### Source 1: Existing Closed Insole STL (`insole_solid`)

Use case: You already have a complete insole 3D model (watertight solid), such as an STL exported from CAD software.

```json
{
  "name": "left",
  "path": "input/left_insole.stl",
  "mode": "insole_solid",
  "side": "left"
}
```

- In this mode, `prepare_inputs.py` skips preprocessing and reuses the original STL directly
- No `scan_preprocess` configuration needed

### Source 2: Direct Plantar Scan Open Surface STL (`plantar_scan_surface`)

Use case: You scanned the sole of the foot using a 3D scanning app (e.g., Polycam, Scaniverse) and got an **open surface** rather than a closed solid.

```json
{
  "name": "left",
  "path": "input/left_plantar_scan.stl",
  "mode": "plantar_scan_surface",
  "side": "left"
}
```

- In this mode, `prepare_inputs.py` closes the open surface into a printable insole blank
- The outline is offset outward by `outline_margin_mm`; the bottom is flat and the top follows the scan
- `scan_preprocess.max_relief_mm` defaults to `8.0` and limits rise above the lowest point; the prepare report includes the thickness range
- **Must configure** `scan_preprocess` axis parameters to match the app's exported coordinate system
- Recommended coordinate convention: foot width = X, foot length = Y, sole height/insole thickness = Z

### Mixed Usage Example

Left and right feet can use different data sources:

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

### Switching Steps Summary

1. Place STL files in `input/` (or any resolvable path)
2. Edit the `inputs` section in `config/zone_params.json`
3. If using scan data, confirm `scan_preprocess.*` axis parameters match
4. Run `python scripts/prepare_inputs.py` to verify preprocessing results

## Directory Structure

- `config/zone_params.json`: Main configuration file
- `scripts/prepare_inputs.py`: Preprocess plantar scan surfaces into closed insole blanks
- `scripts/inspect_mesh.py`: Inspect STL dimensions, bounding box, watertightness, and export previews
- `scripts/build_zones.py`: Generate research-driven anatomical zones and zone previews
- `scripts/generate_tpms.py`: Generate gyroid voxel fields from zone thresholds
- `scripts/clip_lattice.py`: Clip voxel lattice into insole shape and export final STL
- `scripts/export_result.py`: Validate exported final STL
- `scripts/export_zoned_3mf.py`: Export basic insole + modifier zone geometry as standard `3MF`
- `scripts/export_bambu_project_3mf.py`: Export Bambu engineering `3MF` with local slicer parameters from template
- `scripts/run_pipeline.py`: Run the full workflow in order
- `scripts/generate_placeholders.py`: Generate placeholder STL files for first-run validation
- `tests/`: Core logic regression tests
- `bootstrap_uv.ps1`: Initialize local virtual environment using `uv`

## Quick Start

### 1. Install Dependencies

**Recommended (cross-platform): Use uv**

[uv](https://github.com/astral-sh/uv) is a fast Python package manager supporting Windows / macOS / Linux.

After installing uv, run in the project directory:

```powershell
# Windows
.\bootstrap_uv.ps1
```

```bash
# macOS / Linux
uv venv --python 3.12 && uv pip install -r requirements.txt
```

**Alternative: Direct pip install**

If you already have a working Python:

```bash
python -m pip install -r requirements.txt
```

### 2. Run the Full Pipeline

```bash
python scripts/run_pipeline.py
```

If you want to use your own input files without editing the config file:

```bash
# Override left and right input paths
python scripts/run_pipeline.py \
  --input "left=input/my_left.stl,mode=insole_solid,side=left" \
  --input "right=input/my_right.stl,mode=insole_solid,side=right"

# Left uses closed STL, right uses plantar scan
python scripts/run_pipeline.py \
  --input "left=input/my_left.stl,mode=insole_solid,side=left" \
  --input "right=input/my_right_scan.stl,mode=plantar_scan_surface,side=right"
```

Note: The `--input` format uses comma-separated key=value pairs to avoid conflicts with Windows drive letters (`C:\`).

### 3. Run Step by Step

If you want to manually inspect at confirmation points:

```bash
python scripts/prepare_inputs.py
python scripts/inspect_mesh.py
python scripts/build_zones.py
python scripts/generate_tpms.py
python scripts/clip_lattice.py
python scripts/export_result.py
python scripts/export_zoned_3mf.py
python scripts/export_bambu_project_3mf.py
```

## Output Files

### 1. Prepared Insole Blanks

Under `output/prepared/`:

- `left_prepared_insole.stl`
- `right_prepared_insole.stl`
- `left_prepare_report.json`
- `right_prepare_report.json`

When input is `plantar_scan_surface`, this step closes the open plantar surface into a voxel-fillable insole blank: the outline is offset outward by `outline_margin_mm`, the bottom is flat, the top follows the scan, and rise above the lowest point is limited by `scan_preprocess.max_relief_mm` (default `8.0`). The prepare report includes the thickness range. When input is `insole_solid`, it reuses the original closed STL and only outputs the preparation report.

### 2. Zone Previews

Under `output/zones/`:

- `left_zones.json`
- `right_zones.json`
- `left_zones.png`
- `right_zones.png`

Here you can see:

- Insole long axis identification result
- Macro longitudinal zone boundaries: `heel / arch / forefoot / toe`
- Curve zone parameters, including the heel end selected by `zone_shape.heel_at`
- `side` written into the zone JSON (from `inputs[].side`)
- Anatomical zone preview

### 3. Printable Lattice STL

Under `output/final/`:

- `left_lattice_insole.stl`
- `right_lattice_insole.stl`

These files already include:

- An `edgeFrame` inset from the plantar projection outline
- Top and bottom solid layers taken along each column's local surface
- A full-perimeter shell from `shell.skin_layers` (default `1`; at `0` the sides are only `edgeFrame`)
- Internal zoned gyroid with thresholds blended by `tpms.transition_mm`

### 4. Standard Zoned 3MF

Under `output/final/`:

- `left_zoned_modifiers.3mf`
- `right_zoned_modifiers.3mf`

Each `3MF` contains:

- `*_base`
- `*_innerHeel`
- `*_outerHeel`
- `*_innerArch`
- `*_outerArch`
- `*_innerForefoot`
- `*_centralForefoot`
- `*_outerForefoot`
- `*_toe`
- `*_edgeFrame`

Companion settings files:

- `left_zoned_modifiers_settings.json`
- `right_zoned_modifiers_settings.json`
- `left_zoned_modifiers_settings.md`
- `right_zoned_modifiers_settings.md`

Recommended workflow in Bambu Studio/OrcaSlicer:

1. Keep `*_base` as a normal model
2. Set all other objects as `modifier`
3. Override infill per zone using the suggested parameters

### 5. Bambu Engineering 3MF with Local Parameters

Under `output/final/`:

- `left_engineering_modifiers.3mf`
- `right_engineering_modifiers.3mf`

These files write discrete infill density for each zone, suitable for direct observation and test slicing in Bambu Studio. The Bambu engineering `3MF` does not add a transition modifier, and it does not write local walls by default. `tpms.transition_mm` only blends thresholds on the direct lattice STL.

The engineering `3MF` still needs a Bambu template, for example an existing project passed to `export_bambu_project_3mf.py --template`. Export overwrites `nozzle_diameter`, `filament_type`, and `layer_height` only when those keys are already present in the template. If the template cannot be found, export fails and says the template was not found. This path does not generate a complete printer profile from scratch.

The wear-tested combination is recorded in `print_preset`: `0.4 mm` nozzle, `TPU 95A`, and `0.2 mm` layer height.

## Default Zoning Strategy

### Macro Longitudinal Zones

Default longitudinal ratios:

- `heel`: `25%`
- `arch`: `25%`
- `forefoot`: `30%`
- `toe`: `20%`

### Anatomical Zone Logic

The current version further subdivides longitudinal zones into:

- Heel: `innerHeel` / `outerHeel`
- Midfoot: `innerArch` / `outerArch`
- Forefoot: `innerForefoot` / `centralForefoot` / `outerForefoot`
- Toe: `toe`
- Outer rim stabilization: `edgeFrame`

`edgeFrame` is inset from the plantar projection outline by `edge_frame_margin_mm`. It is no longer the four sides of the bounding box. `zone_shape.heel_at` is `auto`, `min`, or `max`. `auto` treats the narrower end of the long axis as the heel; `min` / `max` fix the heel at the lower or higher coordinate end of that axis. `inputs[].side` is written into the zone JSON. `zone_shape.inner_side` remains `auto`, `min`, or `max`.

### Default Slicing Suggestions

The default profile `healthy_asian_male_mixed` uses the infill below. Only the base model writes a wall count. Zone modifiers do not write local walls, so they inherit the base walls:

- `base`: `gyroid 20%`, `3` walls
- `innerHeel`: `gyroid 24%`
- `outerHeel`: `gyroid 20%`
- `innerArch`: `gyroid 34%`
- `outerArch`: `gyroid 26%`
- `innerForefoot`: `gyroid 22%`
- `centralForefoot`: `gyroid 22%`
- `outerForefoot`: `gyroid 17%`
- `toe`: `gyroid 13%`
- `edgeFrame`: `grid 70%`

### Switchable Profiles

Switch built-in profiles via `default_profile` in `config/zone_params.json`:

- `healthy_asian_male_mixed`: Default, suitable for daily walking and light sports mixed scenarios, `no local wall overrides`
- `healthy_asian_male_daily_soft`: Softer daily feel, `no local wall overrides`
- `healthy_asian_male_sport_stable`: More stable light sports template, `no local wall overrides`
- `supportive_generic`: Stronger support generic template, `retains local wall overrides`

The default design choice avoids writing individual local wall counts in modifiers to reduce hard peaks caused by additional perimeters at zone boundaries. Rim reinforcement primarily relies on `edgeFrame` high density and rim width rather than extra local walls.

## Key Parameters

The main parameter tuning entry point is `config/zone_params.json`.

### Input Parameters

- `inputs[].mode`: `insole_solid` for existing closed insole STL, `plantar_scan_surface` for open plantar scan STL from iPhone/FaceID-like apps
- `inputs[].side`: `left / right`, written into the corresponding zone JSON
- `inputs[].prepared_path`: Optional; specify closed blank path after preprocessing scan input, defaults to `output/prepared/<name>_prepared_insole.stl`
- `long_axis`: Length direction for downstream zoning; if scan data has unstable coordinates, explicitly set to `x / y / z`

### Plantar Scan Preprocessing Parameters

- `scan_preprocess.length_axis`: Heel-to-toe direction in the raw scan
- `scan_preprocess.lateral_axis`: Medial-lateral direction in the raw scan
- `scan_preprocess.surface_axis`: Sole height direction in the raw scan; preprocessing output normalizes to Z thickness direction
- `scan_preprocess.surface_direction`: Positive or negative direction along the axis for sole surface height
- `scan_preprocess.target_thickness_mm`: Base thickness for generating the insole blank
- `scan_preprocess.bottom_clearance_mm`: Extra clearance between top plantar surface and bottom
- `scan_preprocess.outline_margin_mm`: Equidistant outward offset of the outline. The scan blank has a flat bottom and a top that follows the scan
- `scan_preprocess.max_relief_mm`: Defaults to `8.0`. Limits top-surface rise above the lowest point. The prepare report includes the thickness range
- `scan_preprocess.max_gap_mm`: Filters triangles spanning gaps too large across the scan
- `scan_preprocess.min_foot_length_mm` / `max_foot_length_mm`: Quality check thresholds for unit or foot length anomalies

### Zone Parameters

- `default_profile`: Switch default template
- `zone_settings_overrides`: Per-zone overrides for slicer suggestions in the current template, including whether to enable local walls
- `zone_ratios`: Controls length ratios for `heel / arch / forefoot / toe` segments
- `zone_shape.heel_curve_mm`: Heel boundary forward extension amplitude in the middle
- `zone_shape.arch_curve_mm`: Arch boundary forward extension amplitude in the middle
- `zone_shape.toe_curve_mm`: Forefoot-to-toe boundary early convergence amplitude in the middle
- `zone_shape.heel_at`: `auto | min | max`. `auto` treats the narrower end of the long axis as the heel; `min` / `max` fix the lower or higher coordinate end of that axis
- `zone_shape.inner_side`: Remains `auto | min | max`, and determines which side is closer to medial
- `zone_shape.forefoot_center_width_ratio`: Central forefoot width ratio

### Lattice Parameters

- `voxel_pitch_mm`: Voxel resolution, currently defaults to `1.0 mm`
- `tpms.wavelength_mm`: Gyroid wavelength
- `tpms.threshold_overrides`: Local overrides for TPMS thresholds in the current template
- `tpms.transition_mm`: Affects threshold blending on the direct lattice STL only. The Bambu `3MF` stays on discrete zone densities, adds no transition modifier, and does not write local walls by default
- `edge_frame_margin_mm`: Inset distance of `edgeFrame` from the plantar projection outline, not the four sides of the bounding box

### Surface and Slicer-Friendly Parameters

- `surface.bottom_solid_layers`: Bottom solid layer count. On the lattice STL these layers follow each column's local bottom surface
- `surface.top_skin_layers`: Top solid layer count. On the lattice STL these layers follow each column's local top surface
- `surface.top_dense_layers`: Number of top dense reinforcement layers
- `surface.top_dense_threshold_boost`: Extra threshold for top dense layers
- `shell.skin_layers`: Full-perimeter shell layer count, default `1`. At `0`, the sides are only `edgeFrame`

### Print Preset

`print_preset` in `config/zone_params.json` is the combination already worn and tested: `0.4 mm` nozzle, `TPU 95A`, and `0.2 mm` layer height.

The engineering `3MF` still needs a Bambu template. Export overwrites `nozzle_diameter`, `filament_type`, and `layer_height` only when those keys already exist in the template. If the template cannot be found, export fails and says the template was not found. It does not generate a complete printer profile from scratch.

## Suggested Workflow

### A. Model Size and Orientation

First check `output/inspection/` to confirm:

- Left and right foot orientations are correct
- Length, width, and thickness match expectations
- No obvious flipping or unit anomalies

For scan inputs, also check `output/prepared/*_prepare_report.json` to confirm:

- `foot_length_mm` and `foot_width_mm` match the actual foot
- `watertight` and `is_volume` are `true`
- The thickness range is plausible: flat bottom, top follows the scan, and rise above the lowest point stays within `scan_preprocess.max_relief_mm` (default `8.0`)
- No unit, length, or blank generation anomalies in `warnings`

Recommended scan coordinate convention: foot width = X, foot length = Y, sole height/insole thickness = Z. If your app outputs different coordinates, explicitly specify via `scan_preprocess.*_axis` and `long_axis` rather than relying on `auto` guessing.

### B. Anatomical Zone Reasonableness

Check `output/zones/*.png`, focusing on:

- Whether the arch support zone lands where you want it lifted
- Whether the forefoot tri-zones are too wide or narrow
- Whether the heel medial/lateral zones are too aggressive
- Whether `edgeFrame` is inset along the plantar projection outline rather than the bounding-box sides
- Whether the heel sits at the end selected by `heel_at`; with `auto` it should be the narrower end of the long axis

### C. Slicer Readability

Check:

- `output/final/*_zoned_modifiers.3mf`
- `output/final/*_engineering_modifiers.3mf`

Key confirmations:

- All modifiers are recognized by the slicer
- Zone boundaries are not excessively jagged
- Parameters are correctly written in the slicer

### D. Actual Printing and Fitting

Recommended order:

1. Test slice first
2. Then print single foot or partial samples
3. Finally try full insoles

If the foot feel is not right, prioritize adjusting:

- Arch too stiff: Lower `innerArch` threshold or density
- Forefoot too firm: Lower `innerForefoot` / `centralForefoot`
- Heel too hard: Lower `innerHeel` first, then `outerHeel`
- Outer edge collapses easily: Increase `edgeFrame` density or rim width

## Parameter Tuning Tips

- Quick style swap: Switch `default_profile` first
- Zone transition on the direct lattice STL is a threshold blend controlled by `tpms.transition_mm`. The Bambu engineering `3MF` keeps discrete zone densities, adds no transition modifier, and does not write local walls by default
- Smoother boundaries: Lower `voxel_pitch_mm`
- More arch support: Raise `innerArch`
- Softer forefoot: Lower `innerForefoot`, `centralForefoot`, `outerForefoot`
- More stable heel: Raise `innerHeel`
- Fewer slicer errors: Adjust `surface.bottom_solid_layers` and `surface.top_skin_layers` first

## Tests

Run regression tests:

```bash
python -m unittest discover -s tests
```

Current test coverage:

- Input mode discovery and scan preprocessing
- Anatomical zone naming and region assignment
- TPMS threshold mapping
- Engineering `3MF` parameter writing
- Top/bottom surface strategies

## Limitations and Notes

- Default parameters are engineering starting points, not a substitute for clinical prescriptions or personalized medical advice
- The engineering `3MF` needs an existing Bambu template and does not generate a complete printer profile from scratch. Only `nozzle_diameter`, `filament_type`, and `layer_height` that already exist in the template are overwritten from `print_preset` (`0.4 mm` nozzle, `TPU 95A`, `0.2 mm` layer height). If the template cannot be found, export fails and says the template was not found. Other slicers may still need their own template fields adapted
- Default thresholds and densities lean toward daily support/cushioning scenarios; sports scenarios typically require re-tuning

## Future Improvements

- Add example zone preview screenshots
