from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from clip_lattice import surface_layer_mask  # type: ignore
from generate_tpms import apply_top_density_boost  # type: ignore


class SurfaceStrategyTests(unittest.TestCase):
    def test_surface_layer_mask_reserves_bottom_and_top_bands(self) -> None:
        points = np.array(
            [
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 1.9],
                [0.0, 0.0, 2.1],
                [0.0, 0.0, 4.1],
                [0.0, 0.0, 6.0],
            ],
            dtype=float,
        )
        bounds = np.array([[0.0, 0.0, 0.0], [10.0, 10.0, 6.0]], dtype=float)

        bottom_mask = surface_layer_mask(points, bounds, pitch_mm=2.0, layers=1, surface="bottom")
        top_mask = surface_layer_mask(points, bounds, pitch_mm=2.0, layers=1, surface="top")

        self.assertListEqual(bottom_mask.tolist(), [True, True, False, False, False])
        self.assertListEqual(top_mask.tolist(), [False, False, False, True, True])

    def test_apply_top_density_boost_only_changes_top_band(self) -> None:
        points = np.array(
            [
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0],
                [0.0, 0.0, 3.9],
                [0.0, 0.0, 4.1],
                [0.0, 0.0, 6.0],
            ],
            dtype=float,
        )
        bounds = np.array([[0.0, 0.0, 0.0], [10.0, 10.0, 6.0]], dtype=float)
        thresholds = np.array([0.12, 0.12, 0.12, 0.12, 0.12], dtype=float)

        boosted = apply_top_density_boost(
            thresholds=thresholds,
            points=points,
            bounds=bounds,
            pitch_mm=2.0,
            top_dense_layers=1,
            threshold_boost=0.08,
        )

        self.assertListEqual(boosted.round(4).tolist(), [0.12, 0.12, 0.12, 0.2, 0.2])


if __name__ == "__main__":
    unittest.main()
