from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_zones import build_zone_definition  # type: ignore
from export_zoned_3mf import build_zone_settings  # type: ignore
from default_profiles import DEFAULT_PROFILE_NAME  # type: ignore
from common import compute_zone_boundaries, load_config, longest_axis, validate_config  # type: ignore
from zone_strategy import label_zone_points, resolve_curve_config, resolve_heel_at  # type: ignore


class Zone3mfTests(unittest.TestCase):
    def test_label_zone_points_assigns_anatomical_regions(self) -> None:
        points = np.array(
            [
                [1.0, 10.0, 2.0],
                [70.0, 25.0, 2.0],
                [20.0, 25.0, 2.0],
                [68.0, 95.0, 2.0],
                [22.0, 95.0, 2.0],
                [68.0, 175.0, 2.0],
                [45.0, 175.0, 2.0],
                [22.0, 175.0, 2.0],
                [45.0, 240.0, 2.0],
                [89.0, 120.0, 2.0],
            ],
            dtype=float,
        )
        bounds = np.array([[0.0, 0.0, 0.0], [90.0, 265.0, 10.0]], dtype=float)
        boundaries = {
            "heel": {"min_mm": 0.0, "max_mm": 66.25},
            "arch": {"min_mm": 66.25, "max_mm": 132.5},
            "forefoot": {"min_mm": 132.5, "max_mm": 212.0},
            "toe": {"min_mm": 212.0, "max_mm": 265.0},
        }

        dx = np.minimum(points[:, 0] - bounds[0, 0], bounds[1, 0] - points[:, 0])
        dy = np.minimum(points[:, 1] - bounds[0, 1], bounds[1, 1] - points[:, 1])
        labels = label_zone_points(
            points=points,
            axis_index=1,
            bounds=bounds,
            boundaries=boundaries,
            edge_margin=5.0,
            curve_config=resolve_curve_config(),
            outline_distance_mm=np.minimum(dx, dy),
        )

        self.assertListEqual(
            labels.tolist(),
            [
                "edgeFrame",
                "innerHeel",
                "outerHeel",
                "innerArch",
                "outerArch",
                "innerForefoot",
                "centralForefoot",
                "outerForefoot",
                "toe",
                "edgeFrame",
            ],
        )

    def test_build_zone_settings_returns_expected_slicer_defaults(self) -> None:
        settings = build_zone_settings()

        self.assertEqual(DEFAULT_PROFILE_NAME, "healthy_asian_male_mixed")
        self.assertEqual(settings["base"]["infill_pattern"], "gyroid")
        self.assertEqual(settings["base"]["walls"], 3)
        self.assertEqual(settings["innerArch"]["infill_density_percent"], 34)
        self.assertEqual(settings["centralForefoot"]["infill_density_percent"], 22)
        self.assertEqual(settings["outerHeel"]["infill_density_percent"], 20)
        self.assertIsNone(settings["innerArch"]["walls"])
        self.assertIsNone(settings["centralForefoot"]["walls"])
        self.assertIsNone(settings["edgeFrame"]["walls"])
        self.assertEqual(settings["edgeFrame"]["infill_density_percent"], 70)
        self.assertEqual(settings["toe"]["infill_density_percent"], 13)

    def test_build_zone_settings_supports_profile_switching(self) -> None:
        settings = build_zone_settings({"default_profile": "healthy_asian_male_daily_soft"})

        self.assertEqual(settings["base"]["infill_density_percent"], 18)
        self.assertEqual(settings["innerArch"]["infill_density_percent"], 30)
        self.assertEqual(settings["centralForefoot"]["infill_density_percent"], 19)
        self.assertEqual(settings["edgeFrame"]["infill_density_percent"], 65)
        self.assertIsNone(settings["innerArch"]["walls"])

    def test_explicit_long_axis_scales_zone_boundaries_with_foot_length(self) -> None:
        ratios = {"heel": 0.25, "arch": 0.25, "forefoot": 0.30, "toe": 0.20}
        small_axis = longest_axis([74.0, 225.0, 16.0], configured_axis="y")
        large_axis = longest_axis([102.0, 290.0, 18.0], configured_axis="y")

        small = compute_zone_boundaries([0.0, 0.0, 0.0], [74.0, 225.0, 16.0], ratios, small_axis)
        large = compute_zone_boundaries([0.0, 0.0, 0.0], [102.0, 290.0, 18.0], ratios, large_axis)

        self.assertEqual(small["toe"]["max_mm"], 225.0)
        self.assertEqual(large["toe"]["max_mm"], 290.0)
        self.assertLess(small["arch"]["max_mm"], large["arch"]["max_mm"])

    def test_edge_frame_follows_outline_instead_of_bounding_box(self) -> None:
        points = np.array(
            [
                [1.0, 20.0, 2.0],
                [40.0, 20.0, 2.0],
            ],
            dtype=float,
        )
        bounds = np.array([[0.0, 0.0, 0.0], [100.0, 200.0, 10.0]], dtype=float)
        boundaries = {
            "heel": {"min_mm": 0.0, "max_mm": 50.0},
            "arch": {"min_mm": 50.0, "max_mm": 100.0},
            "forefoot": {"min_mm": 100.0, "max_mm": 160.0},
            "toe": {"min_mm": 160.0, "max_mm": 200.0},
        }

        labels = label_zone_points(
            points=points,
            axis_index=1,
            bounds=bounds,
            boundaries=boundaries,
            edge_margin=5.0,
            curve_config=resolve_curve_config({"enabled": False, "heel_at": "min"}),
            outline_distance_mm=np.array([40.0, 1.0]),
        )

        self.assertNotEqual(labels[0], "edgeFrame")
        self.assertEqual(labels[1], "edgeFrame")

    def test_heel_at_auto_uses_the_narrow_end(self) -> None:
        footprint = np.zeros((40, 100), dtype=bool)
        footprint[:, :30] = True
        footprint[10:30, 30:70] = True
        footprint[15:25, 70:] = True

        self.assertEqual(resolve_heel_at("auto", footprint, long_axis_index=1, pitch=1.0), "max")
        self.assertEqual(resolve_heel_at("auto", footprint[:, ::-1], long_axis_index=1, pitch=1.0), "min")
        self.assertEqual(resolve_heel_at("min", footprint, long_axis_index=1, pitch=1.0), "min")
        self.assertEqual(resolve_heel_at("max", footprint, long_axis_index=1, pitch=1.0), "max")

    def test_flipped_long_axis_keeps_heel_to_toe_order(self) -> None:
        ratios = {"heel": 0.25, "arch": 0.25, "forefoot": 0.30, "toe": 0.20}
        bounds = np.array([[0.0, 0.0, 0.0], [40.0, 100.0, 10.0]], dtype=float)
        boundaries = compute_zone_boundaries(bounds[0], bounds[1], ratios, axis_index=1, heel_at="max")

        self.assertEqual(boundaries["heel"]["min_mm"], 75.0)
        self.assertEqual(boundaries["heel"]["max_mm"], 100.0)
        self.assertEqual(boundaries["toe"]["min_mm"], 0.0)
        self.assertEqual(boundaries["toe"]["max_mm"], 20.0)
        self.assertGreater(boundaries["heel"]["min_mm"], boundaries["toe"]["max_mm"])

        points = np.array(
            [
                [20.0, 90.0, 2.0],
                [20.0, 10.0, 2.0],
            ],
            dtype=float,
        )
        labels = label_zone_points(
            points=points,
            axis_index=1,
            bounds=bounds,
            boundaries=boundaries,
            edge_margin=5.0,
            curve_config=resolve_curve_config({"enabled": False, "heel_at": "max", "inner_side": "min"}),
            outline_distance_mm=np.array([20.0, 20.0]),
        )

        self.assertListEqual(labels.tolist(), ["innerHeel", "toe"])

    def test_zone_definition_records_side_and_narrow_heel(self) -> None:
        import trimesh

        points = np.array(
            [
                [-25.0, -40.0, 0.0],
                [25.0, -40.0, 0.0],
                [-25.0, -40.0, 8.0],
                [25.0, -40.0, 8.0],
                [-6.0, 40.0, 0.0],
                [6.0, 40.0, 0.0],
                [-6.0, 40.0, 8.0],
                [6.0, 40.0, 8.0],
            ],
            dtype=float,
        )
        mesh = trimesh.convex.convex_hull(points)
        config = {
            "long_axis": "y",
            "zone_ratios": {"heel": 0.25, "arch": 0.25, "forefoot": 0.30, "toe": 0.20},
            "edge_frame_margin_mm": 3.0,
            "voxel_pitch_mm": 2.0,
            "zone_shape": {"enabled": False, "heel_at": "auto", "inner_side": "min"},
        }

        payload, _labels = build_zone_definition(
            mesh,
            input_name="right",
            input_path="memory",
            side="right",
            config=config,
        )
        length = float(mesh.bounds[1][1] - mesh.bounds[0][1])
        heel_span = payload["boundaries"]["heel"]["max_mm"] - payload["boundaries"]["heel"]["min_mm"]
        toe_span = payload["boundaries"]["toe"]["max_mm"] - payload["boundaries"]["toe"]["min_mm"]

        self.assertEqual(payload["side"], "right")
        self.assertEqual(payload["heel_at"], "max")
        self.assertEqual(payload["zone_shape"]["heel_at"], "max")
        self.assertGreater(payload["boundaries"]["heel"]["min_mm"], payload["boundaries"]["toe"]["max_mm"])
        self.assertAlmostEqual(payload["boundaries"]["heel"]["max_mm"], float(mesh.bounds[1][1]), places=3)
        self.assertAlmostEqual(payload["boundaries"]["toe"]["min_mm"], float(mesh.bounds[0][1]), places=3)
        self.assertAlmostEqual(heel_span, 0.25 * length, delta=0.05)
        self.assertAlmostEqual(toe_span, 0.20 * length, delta=0.05)

    def test_config_records_new_keys_and_rejects_bad_heel_at(self) -> None:
        config = load_config()

        self.assertEqual(config["zone_shape"]["heel_at"], "auto")
        self.assertEqual(config["zone_shape"]["inner_side"], "auto")
        self.assertEqual(config["print_preset"]["nozzle_diameter_mm"], 0.4)
        self.assertEqual(config["print_preset"]["material"], "TPU 95A")
        self.assertEqual(config["print_preset"]["layer_height_mm"], 0.2)
        self.assertIn("局部墙", config["print_preset"]["notes"])
        self.assertEqual(config["voxel_pitch_mm"], 1.0)
        self.assertEqual(config["tpms"]["wavelength_mm"], 12.0)
        self.assertEqual(config["default_profile"], "healthy_asian_male_mixed")
        self.assertEqual(config["zone_ratios"]["heel"], 0.25)

        broken = copy.deepcopy(config)
        broken["zone_shape"]["heel_at"] = "toe"
        with self.assertRaisesRegex(ValueError, "heel_at"):
            validate_config(broken)


if __name__ == "__main__":
    unittest.main()
