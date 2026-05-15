"""Generate minimal placeholder STL files for pipeline validation."""

import struct
from pathlib import Path


def write_binary_stl(path: str, vertices: list[tuple[float, float, float]], faces: list[tuple[int, int, int]]) -> None:
    """Write a minimal binary STL file."""
    with open(path, "wb") as f:
        # 80-byte header
        f.write(b"Placeholder STL - Replace with actual insole data")
        f.write(b"\x00" * 33)  # Pad to 80 bytes
        # Number of triangles
        f.write(struct.pack("<I", len(faces)))
        # Write each triangle
        for a, b, c in faces:
            # Normal vector (set to zero, many slicers ignore this)
            f.write(struct.pack("<3f", 0.0, 0.0, 0.0))
            # Three vertices
            for idx in (a, b, c):
                f.write(struct.pack("<3f", *vertices[idx]))
            # Attribute byte count
            f.write(struct.pack("<H", 0))


def create_insole_placeholder(path: str, length: float = 250.0, width: float = 90.0, height: float = 15.0) -> None:
    """Create a simple elongated box placeholder resembling an insole blank."""
    # Simple rectangular prism (elongated along Y axis like an insole)
    l, w, h = length / 2, width / 2, height / 2
    vertices = [
        (-l, -w, 0),    # 0: bottom-left-front
        (l, -w, 0),     # 1: bottom-right-front
        (l, w, 0),      # 2: bottom-right-back
        (-l, w, 0),     # 3: bottom-left-back
        (-l, -w, h),    # 4: top-left-front
        (l, -w, h),     # 5: top-right-front
        (l, w, h),      # 6: top-right-back
        (-l, w, h),     # 7: top-left-back
    ]
    faces = [
        # Bottom
        (0, 2, 1), (0, 3, 2),
        # Top
        (4, 5, 6), (4, 6, 7),
        # Front
        (0, 1, 5), (0, 5, 4),
        # Back
        (2, 3, 7), (2, 7, 6),
        # Left
        (0, 4, 7), (0, 7, 3),
        # Right
        (1, 2, 6), (1, 6, 5),
    ]
    write_binary_stl(path, vertices, faces)


def create_scan_placeholder(path: str, length: float = 240.0, width: float = 85.0) -> None:
    """Create a simple flat surface placeholder resembling a plantar scan."""
    # Flat surface (open mesh) - just the top face
    l, w = length / 2, width / 2
    vertices = [
        (-l, -w, 0),  # 0
        (l, -w, 0),   # 1
        (l, w, 0),    # 2
        (-l, w, 0),   # 3
    ]
    faces = [
        (0, 2, 1),  # One triangle covering the rectangle
        (0, 3, 2),  # Second triangle
    ]
    write_binary_stl(path, vertices, faces)


def main():
    input_dir = Path(__file__).resolve().parent.parent / "input"
    input_dir.mkdir(exist_ok=True)

    # Create closed insole placeholders
    create_insole_placeholder(str(input_dir / "left_insole.stl"))
    create_insole_placeholder(str(input_dir / "right_insole.stl"))

    # Create plantar scan placeholders
    create_scan_placeholder(str(input_dir / "left_plantar_scan.stl"))
    create_scan_placeholder(str(input_dir / "right_plantar_scan.stl"))

    print(f"Generated placeholder STL files in {input_dir}")
    for f in sorted(input_dir.glob("*.stl")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
