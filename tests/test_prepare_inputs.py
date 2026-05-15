from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import trimesh


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from prepare_inputs import build_prepared_insole_mesh, resolve_scan_preprocess_config  # type: ignore


def build_open_plantar_surface(length_mm: float, width_mm: float, arch_height_mm: float = 10.0) -> trimesh.Trimesh:
    xs = np.linspace(0.0, width_mm, 7)
    ys = np.linspace(0.0, length_mm, 13)
    vertices = []
    for y in ys:
        for x in xs:
            arch_profile = np.sin(np.pi * y / length_mm)
            medial_bias = np.exp(-((x - width_mm * 0.35) ** 2) / (2.0 * (width_mm * 0.16) ** 2))
            z = arch_height_mm * arch_profile * medial_bias
            vertices.append([x, y, z])

    faces = []
    columns = len(xs)
    for row in range(len(ys) - 1):
        for col in range(len(xs) - 1):
            a = row * columns + col
            b = a + 1
            c = a + columns
            d = c + 1
            faces.append([a, c, b])
            faces.append([b, c, d])

    return trimesh.Trimesh(vertices=np.array(vertices, dtype=float), faces=np.array(faces), process=False)


class PrepareInputsTests(unittest.TestCase):
    def test_open_plantar_surface_becomes_watertight_insole_body(self) -> None:
        config = resolve_scan_preprocess_config(
            {
                "length_axis": "y",
                "lateral_axis": "x",
                "surface_axis": "z",
                "surface_direction": "positive",
                "target_thickness_mm": 6.0,
                "bottom_clearance_mm": 0.5,
                "outline_margin_mm": 0.0,
                "max_gap_mm": 50.0,
            }
        )
        source = build_open_plantar_surface(length_mm=240.0, width_mm=82.0)

        prepared, report = build_prepared_insole_mesh(source, config)

        self.assertTrue(prepared.is_watertight)
        self.assertTrue(prepared.is_volume)
        self.assertAlmostEqual(float(prepared.bounds[0][2]), 0.0, places=4)
        self.assertGreater(float(prepared.bounds[1][2]), 6.0)
        self.assertAlmostEqual(report["foot_length_mm"], 240.0, delta=1.0)
        self.assertAlmostEqual(report["foot_width_mm"], 82.0, delta=1.0)

    def test_prepared_body_scales_with_each_persons_foot_dimensions(self) -> None:
        config = resolve_scan_preprocess_config({"max_gap_mm": 60.0})
        small_source = build_open_plantar_surface(length_mm=220.0, width_mm=72.0)
        large_source = build_open_plantar_surface(length_mm=285.0, width_mm=100.0)

        small_mesh, small_report = build_prepared_insole_mesh(small_source, config)
        large_mesh, large_report = build_prepared_insole_mesh(large_source, config)

        self.assertLess(float(small_mesh.extents[1]), float(large_mesh.extents[1]))
        self.assertLess(float(small_mesh.extents[0]), float(large_mesh.extents[0]))
        self.assertAlmostEqual(small_report["foot_length_mm"], 220.0, delta=1.0)
        self.assertAlmostEqual(large_report["foot_length_mm"], 285.0, delta=1.0)


if __name__ == "__main__":
    unittest.main()
