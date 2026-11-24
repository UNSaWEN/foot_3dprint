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

    def test_high_arch_thickness_respects_max_relief(self) -> None:
        target_thickness = 6.0
        bottom_clearance = 0.5
        raw_config = {
            "target_thickness_mm": target_thickness,
            "bottom_clearance_mm": bottom_clearance,
            "outline_margin_mm": 0.0,
            "max_gap_mm": 50.0,
        }
        self.assertEqual(resolve_scan_preprocess_config(raw_config)["max_relief_mm"], 8.0)

        source = build_open_plantar_surface(length_mm=240.0, width_mm=82.0, arch_height_mm=25.0)
        self.assertGreater(float(source.vertices[:, 2].max()), 8.0)
        prepared, report = build_prepared_insole_mesh(source, raw_config)

        cap = target_thickness + bottom_clearance + 8.0
        max_thickness = float(prepared.bounds[1][2] - prepared.bounds[0][2])
        self.assertAlmostEqual(float(prepared.bounds[0][2]), 0.0, places=4)
        self.assertLessEqual(max_thickness, cap + 1e-3)
        self.assertAlmostEqual(max_thickness, cap, delta=1e-3)
        self.assertEqual(report["max_relief_mm"], 8.0)
        self.assertLessEqual(report["thickness_max_mm"], cap + 1e-3)
        self.assertAlmostEqual(report["thickness_max_mm"], cap, delta=1e-3)
        self.assertGreaterEqual(report["thickness_min_mm"], target_thickness + bottom_clearance - 1e-3)
        self.assertLessEqual(report["thickness_max_mm"] - report["thickness_min_mm"], 8.0 + 1e-3)

        tight_config = dict(raw_config)
        tight_config["max_relief_mm"] = 3.0
        tight_mesh, tight_report = build_prepared_insole_mesh(source, tight_config)
        tight_cap = target_thickness + bottom_clearance + 3.0
        tight_thickness = float(tight_mesh.bounds[1][2] - tight_mesh.bounds[0][2])
        self.assertLessEqual(tight_thickness, tight_cap + 1e-3)
        self.assertAlmostEqual(tight_thickness, tight_cap, delta=1e-3)
        self.assertEqual(tight_report["max_relief_mm"], 3.0)
        self.assertLessEqual(tight_report["thickness_max_mm"], tight_cap + 1e-3)

    def test_outline_offset_follows_margin_around_narrow_toe(self) -> None:
        """The blank outline stays about one margin off the foot, including a narrow toe.

        Centroid radial expansion would shove that toe forward and leave the sides
        of the tip almost as narrow as the scan.
        """
        margin = 6.0
        config = {
            "outline_margin_mm": margin,
            "max_gap_mm": 30.0,
            "target_thickness_mm": 6.0,
            "bottom_clearance_mm": 0.5,
            "max_relief_mm": 8.0,
        }
        source = build_narrow_toe_surface()
        prepared, report = build_prepared_insole_mesh(source, config)
        xy = np.unique(np.round(prepared.vertices[:, :2], 5), axis=0)

        self.assertTrue(prepared.is_watertight)
        self.assertAlmostEqual(float(prepared.bounds[0][2]), 0.0, places=3)
        self.assertAlmostEqual(float(xy[:, 0].min()), -margin, delta=0.75)
        self.assertAlmostEqual(float(xy[:, 0].max()), 80.0 + margin, delta=0.75)
        self.assertAlmostEqual(float(xy[:, 1].min()), -margin, delta=0.75)
        self.assertAlmostEqual(float(xy[:, 1].max()) - 250.0, margin, delta=0.75)

        outside = _outside_outline_distances(xy, NARROW_TOE_OUTLINE)
        self.assertGreater(len(outside), 20)
        self.assertAlmostEqual(float(np.median(outside)), margin, delta=0.35)
        self.assertLess(float(np.max(np.abs(outside - margin))), 0.75)

        # Past the original tip, a round equidistant corner is several millimetres
        # wide. Radial expansion keeps that same region needle-thin.
        beyond_tip = xy[xy[:, 1] > 251.0]
        self.assertGreater(len(beyond_tip), 0)
        self.assertGreater(float(np.max(np.abs(beyond_tip[:, 0] - 40.0))), 4.0)
        self.assertEqual(report["outline_margin_mm"], margin)
        self.assertLessEqual(report["thickness_max_mm"], 6.0 + 0.5 + 8.0 + 1e-6)

    def test_outline_offset_rejects_too_few_points(self) -> None:
        config = {
            "outline_margin_mm": 3.0,
            "max_gap_mm": 30.0,
            "min_foot_length_mm": 0.0,
            "max_foot_length_mm": 1000.0,
        }
        mesh = trimesh.Trimesh(
            vertices=np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [20.0, 0.0, 1.0]], dtype=float),
            faces=np.array([[0, 1, 2]]),
            process=False,
        )
        with self.assertRaises(ValueError) as caught:
            build_prepared_insole_mesh(mesh, config)
        message = str(caught.exception).lower()
        self.assertTrue("outline" in message or "collinear" in message or "three" in message)


NARROW_TOE_OUTLINE = np.array(
    [
        [0.0, 0.0],
        [80.0, 0.0],
        [80.0, 180.0],
        [40.0, 250.0],
        [0.0, 180.0],
    ],
    dtype=float,
)


def build_narrow_toe_surface() -> trimesh.Trimesh:
    """Convex foot with a triangular toe, filled so the outline is the true polygon."""
    points: list[list[float]] = []
    inside = _points_inside_outline
    grid = np.array([[x, y] for y in np.linspace(0.0, 250.0, 51) for x in np.linspace(0.0, 80.0, 17)])
    mask = inside(grid, NARROW_TOE_OUTLINE)
    for x, y in grid[mask]:
        points.append([float(x), float(y), 0.0])
    for index in range(len(NARROW_TOE_OUTLINE)):
        start = NARROW_TOE_OUTLINE[index]
        end = NARROW_TOE_OUTLINE[(index + 1) % len(NARROW_TOE_OUTLINE)]
        length = float(np.linalg.norm(end - start))
        steps = max(1, int(np.ceil(length / 4.0)))
        for step in range(steps + 1):
            point = start + (end - start) * (step / steps)
            points.append([float(point[0]), float(point[1]), 0.0])
    vertices = np.unique(np.round(np.array(points, dtype=float), 5), axis=0)
    return trimesh.Trimesh(vertices=vertices, faces=np.array([[0, 1, 2]]), process=False)


def _distance_to_outline(points: np.ndarray, outline: np.ndarray) -> np.ndarray:
    distances = np.full(len(points), np.inf)
    for index in range(len(outline)):
        start = outline[index]
        end = outline[(index + 1) % len(outline)]
        edge = end - start
        length_sq = float(np.dot(edge, edge))
        if length_sq < 1e-18:
            candidate = np.linalg.norm(points - start, axis=1)
        else:
            t = np.clip(((points - start) @ edge) / length_sq, 0.0, 1.0)
            candidate = np.linalg.norm(points - (start + t[:, None] * edge), axis=1)
        distances = np.minimum(distances, candidate)
    return distances


def _points_inside_outline(points: np.ndarray, outline: np.ndarray) -> np.ndarray:
    x = points[:, 0]
    y = points[:, 1]
    inside = np.zeros(len(points), dtype=bool)
    for index in range(len(outline)):
        x1, y1 = outline[index]
        x2, y2 = outline[(index + 1) % len(outline)]
        if y1 == y2:
            continue
        crosses = (y1 > y) != (y2 > y)
        if not np.any(crosses):
            continue
        x_at_y = (x2 - x1) * (y[crosses] - y1) / (y2 - y1) + x1
        inside[crosses] ^= x[crosses] < x_at_y
    return inside


def _outside_outline_distances(points: np.ndarray, outline: np.ndarray) -> np.ndarray:
    distances = _distance_to_outline(points, outline)
    inside = _points_inside_outline(points, outline)
    return distances[(~inside) & (distances > 1e-3)]


if __name__ == "__main__":
    unittest.main()
