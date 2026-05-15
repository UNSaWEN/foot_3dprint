from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from export_zoned_3mf import build_zone_settings  # type: ignore
from default_profiles import DEFAULT_PROFILE_NAME  # type: ignore
from common import compute_zone_boundaries, longest_axis  # type: ignore
from zone_strategy import label_zone_points, resolve_curve_config  # type: ignore


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

        labels = label_zone_points(
            points=points,
            axis_index=1,
            bounds=bounds,
            boundaries=boundaries,
            edge_margin=5.0,
            curve_config=resolve_curve_config(),
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


if __name__ == "__main__":
    unittest.main()
