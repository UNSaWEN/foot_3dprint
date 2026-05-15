from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from default_profiles import resolve_tpms_thresholds  # type: ignore
from generate_tpms import threshold_map_from_labels  # type: ignore


class TpmsThresholdTests(unittest.TestCase):
    def test_resolve_tpms_thresholds_uses_healthy_mixed_profile_by_default(self) -> None:
        thresholds = resolve_tpms_thresholds({"tpms": {}})

        self.assertTrue(
            np.allclose(
                [
                    thresholds["innerHeel"],
                    thresholds["outerHeel"],
                    thresholds["innerArch"],
                    thresholds["outerArch"],
                    thresholds["innerForefoot"],
                    thresholds["centralForefoot"],
                    thresholds["outerForefoot"],
                    thresholds["toe"],
                    thresholds["edgeFrame"],
                ],
                [0.18, 0.17, 0.24, 0.19, 0.17, 0.18, 0.14, 0.10, 0.35],
            )
        )

    def test_resolve_tpms_thresholds_supports_profile_switching(self) -> None:
        thresholds = resolve_tpms_thresholds(
            {
                "default_profile": "healthy_asian_male_sport_stable",
                "tpms": {},
            }
        )

        self.assertTrue(
            np.allclose(
                [thresholds["innerArch"], thresholds["centralForefoot"], thresholds["outerHeel"]],
                [0.27, 0.20, 0.18],
            )
        )

    def test_threshold_map_from_labels_uses_zone_specific_thresholds(self) -> None:
        labels = np.array(
            [
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
            dtype=object,
        )
        thresholds = {
            "innerHeel": 0.23,
            "outerHeel": 0.18,
            "innerArch": 0.30,
            "outerArch": 0.24,
            "innerForefoot": 0.22,
            "centralForefoot": 0.18,
            "outerForefoot": 0.15,
            "toe": 0.10,
            "edgeFrame": 0.35,
        }

        result = threshold_map_from_labels(labels, thresholds)

        self.assertTrue(np.allclose(result, [0.23, 0.18, 0.30, 0.24, 0.22, 0.18, 0.15, 0.10, 0.35]))


if __name__ == "__main__":
    unittest.main()
