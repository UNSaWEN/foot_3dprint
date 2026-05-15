from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import trimesh


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import mesh_summary_from_trimesh  # type: ignore


class MeshSummaryTests(unittest.TestCase):
    def test_trimesh_summary_uses_configured_input_name(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temp_dir:
            stl_path = Path(temp_dir) / "generated_box.stl"
            trimesh.creation.box(extents=(80.0, 240.0, 12.0)).export(stl_path)

            summary = mesh_summary_from_trimesh(stl_path, name="left")

        self.assertEqual(summary.name, "left")
        self.assertEqual(summary.units_guess, "mm")
        self.assertEqual(summary.likely_long_axis, "y")
        self.assertTrue(summary.watertight)
        self.assertTrue(summary.is_volume)


if __name__ == "__main__":
    unittest.main()
