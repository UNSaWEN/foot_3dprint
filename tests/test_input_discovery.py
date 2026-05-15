from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import discover_inputs  # type: ignore


class InputDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(dir=ROOT)
        self.temp_path = Path(self.temp_dir.name)
        self.raw_path = self.temp_path / "raw_scan.stl"
        self.raw_path.write_bytes(b"not a real stl; discovery only checks paths")
        self.relative_raw_path = self.raw_path.relative_to(ROOT).as_posix()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_solid_inputs_keep_existing_path_contract(self) -> None:
        config = {"inputs": [{"name": "left", "path": self.relative_raw_path}]}

        [item] = discover_inputs(config)

        self.assertEqual(item["mode"], "insole_solid")
        self.assertEqual(item["name"], "left")
        self.assertEqual(item["path"], self.raw_path.resolve())
        self.assertEqual(item["raw_path"], self.raw_path.resolve())
        self.assertEqual(item["prepared_path"], self.raw_path.resolve())

    def test_scan_surface_inputs_resolve_default_prepared_path_without_requiring_it(self) -> None:
        config = {
            "inputs": [
                {
                    "name": "left",
                    "path": self.relative_raw_path,
                    "mode": "plantar_scan_surface",
                    "side": "left",
                }
            ]
        }

        [item] = discover_inputs(config, require_prepared=False)

        self.assertEqual(item["mode"], "plantar_scan_surface")
        self.assertEqual(item["side"], "left")
        self.assertEqual(item["raw_path"], self.raw_path.resolve())
        self.assertEqual(item["prepared_path"], (ROOT / "output" / "prepared" / "left_prepared_insole.stl").resolve())
        self.assertEqual(item["path"], item["prepared_path"])

    def test_scan_surface_inputs_require_prepared_mesh_by_default(self) -> None:
        config = {
            "inputs": [
                {
                    "name": "left",
                    "path": self.relative_raw_path,
                    "mode": "plantar_scan_surface",
                }
            ]
        }

        with self.assertRaisesRegex(FileNotFoundError, "Prepared insole STL not found"):
            discover_inputs(config)


if __name__ == "__main__":
    unittest.main()
