from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_pipeline import build_argument_parser  # type: ignore


class RunPipelineTests(unittest.TestCase):
    def test_default_pipeline_prepares_inputs_before_inspection(self) -> None:
        args = build_argument_parser().parse_args([])

        self.assertEqual(args.steps[:3], ["prepare_inputs", "inspect_mesh", "build_zones"])


if __name__ == "__main__":
    unittest.main()
