from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from export_bambu_project_3mf import build_model_settings_xml, patch_project_settings  # type: ignore
from export_zoned_3mf import build_zone_settings  # type: ignore


class BambuProject3mfTests(unittest.TestCase):
    def test_build_model_settings_xml_marks_zone_parts_as_modifiers(self) -> None:
        settings = build_zone_settings()
        object_infos = [
            {"id": 1, "name": "left_base"},
            {"id": 2, "name": "left_innerHeel"},
            {"id": 3, "name": "left_outerHeel"},
            {"id": 4, "name": "left_innerArch"},
            {"id": 5, "name": "left_outerArch"},
            {"id": 6, "name": "left_innerForefoot"},
            {"id": 7, "name": "left_centralForefoot"},
            {"id": 8, "name": "left_outerForefoot"},
            {"id": 9, "name": "left_toe"},
            {"id": 10, "name": "left_edgeFrame"},
        ]

        xml_text = build_model_settings_xml(
            project_name="left_engineering_modifiers",
            object_infos=object_infos,
            settings=settings,
        )

        self.assertIn('subtype="normal_part"', xml_text)
        self.assertEqual(xml_text.count('subtype="modifier_part"'), 9)
        self.assertIn('key="sparse_infill_pattern" value="gyroid"', xml_text)
        self.assertIn('key="sparse_infill_density" value="34%"', xml_text)
        self.assertNotIn('key="wall_loops" value="4"', xml_text)
        self.assertNotIn('key="wall_loops" value="3"', xml_text)
        self.assertNotIn('key="wall_loops" value="2"', xml_text)
        self.assertIn('key="sparse_infill_pattern" value="grid"', xml_text)
        self.assertIn('key="sparse_infill_density" value="70%"', xml_text)

    def test_patch_project_settings_updates_base_defaults(self) -> None:
        settings = build_zone_settings()
        payload = {
            "sparse_infill_pattern": "grid",
            "sparse_infill_density": "15%",
            "wall_loops": "2",
            "top_shell_layers": "3",
            "bottom_shell_layers": "3",
        }

        patched = patch_project_settings(payload, settings)

        self.assertEqual(patched["sparse_infill_pattern"], "gyroid")
        self.assertEqual(patched["sparse_infill_density"], "20%")
        self.assertEqual(patched["wall_loops"], "3")
        self.assertEqual(patched["top_shell_layers"], "4")
        self.assertEqual(patched["bottom_shell_layers"], "4")


if __name__ == "__main__":
    unittest.main()
