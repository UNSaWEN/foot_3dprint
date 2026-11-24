from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from voxel_fields import column_outline_distance_mm, mesh_from_voxel_mask, voxel_world_points  # type: ignore


class VoxelFieldTests(unittest.TestCase):
    def test_marching_cubes_bounds_follow_translated_mesh(self) -> None:
        import trimesh

        mesh = trimesh.creation.box(extents=(40.0, 30.0, 10.0))
        mesh.apply_translation((120.0, 35.0, 10.0))
        pitch = 2.0
        voxelized = mesh.voxelized(pitch).fill()

        restored = mesh_from_voxel_mask(voxelized.matrix, voxelized)

        delta = np.abs(np.asarray(restored.bounds, dtype=float) - np.asarray(mesh.bounds, dtype=float))
        self.assertLessEqual(float(delta.max()), pitch + 1.0e-6)
        self.assertGreater(float(np.min(restored.bounds)), 0.0)

    def test_outline_distance_ignores_empty_bbox_corner(self) -> None:
        inside = np.zeros((20, 10, 2), dtype=bool)
        inside[5:15, :, :] = True

        distance = column_outline_distance_mm(inside, pitch=1.0)

        self.assertFalse(np.isfinite(distance[0, 4, 0]))
        self.assertLessEqual(float(distance[5, 4, 0]), 5.0)
        self.assertGreater(float(distance[9, 4, 0]), float(distance[5, 4, 0]))

    def test_column_distance_matches_voxel_point_order(self) -> None:
        inside = np.zeros((2, 3, 2), dtype=bool)
        inside[0, 0, :] = True
        inside[1, 2, :] = True

        class _FakeGrid:
            def __init__(self, matrix, transform):
                self.matrix = matrix
                self.transform = transform

        _indices, _points = voxel_world_points(_FakeGrid(inside, np.eye(4)))
        distance = column_outline_distance_mm(inside, pitch=1.0)
        flat = distance.reshape(-1)
        for index, value in zip(_indices, flat):
            self.assertEqual(float(value), float(distance[tuple(int(axis) for axis in index)]))


if __name__ == "__main__":
    unittest.main()
