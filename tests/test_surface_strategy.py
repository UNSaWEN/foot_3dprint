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
    def test_surface_layer_mask_follows_local_column_surfaces(self) -> None:
        inside = np.zeros((1, 2, 8), dtype=bool)
        inside[0, 0, 1:4] = True
        inside[0, 1, 5:8] = True

        bottom = surface_layer_mask(inside, layers=1, surface="bottom")
        top = surface_layer_mask(inside, layers=2, surface="top")

        self.assertTrue(bottom[0, 0, 1])
        self.assertFalse(bottom[0, 0, 2])
        self.assertTrue(bottom[0, 1, 5])
        self.assertFalse(bottom[0, 1, 6])
        self.assertListEqual(np.flatnonzero(top[0, 0]).tolist(), [2, 3])
        self.assertListEqual(np.flatnonzero(top[0, 1]).tolist(), [6, 7])
        self.assertFalse(bool(top[0, 0, 7]))

    def test_apply_top_density_boost_follows_local_top(self) -> None:
        inside = np.zeros((1, 2, 6), dtype=bool)
        inside[0, 0, 0:3] = True
        inside[0, 1, 4:6] = True
        thresholds = np.full(inside.size, 0.12, dtype=float)

        boosted = apply_top_density_boost(
            thresholds=thresholds,
            inside_mask=inside,
            top_dense_layers=1,
            threshold_boost=0.08,
        ).reshape(inside.shape)

        self.assertAlmostEqual(float(boosted[0, 0, 2]), 0.20)
        self.assertAlmostEqual(float(boosted[0, 0, 1]), 0.12)
        self.assertAlmostEqual(float(boosted[0, 1, 5]), 0.20)
        self.assertAlmostEqual(float(boosted[0, 1, 4]), 0.12)
        self.assertAlmostEqual(float(boosted[0, 0, 5]), 0.12)


if __name__ == "__main__":
    unittest.main()
