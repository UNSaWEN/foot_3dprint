from __future__ import annotations

from pathlib import Path

from common import AXES, ensure_directory


def try_import_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except ImportError:
        return None
    return plt


def save_mesh_projection_preview(mesh, output_path: str | Path, title: str) -> bool:
    plt = try_import_matplotlib()
    if plt is None:
        return False

    vertices = mesh.vertices
    sample_step = max(len(vertices) // 5000, 1)
    sampled = vertices[::sample_step]

    projections = ((0, 1), (1, 2), (0, 2))
    figure, axes = plt.subplots(1, 3, figsize=(15, 5))

    for axis, (u, v) in zip(axes, projections):
        axis.scatter(sampled[:, u], sampled[:, v], s=0.2, alpha=0.7)
        axis.set_xlabel(f"{AXES[u]} (mm)")
        axis.set_ylabel(f"{AXES[v]} (mm)")
        axis.set_title(f"{AXES[u].upper()} / {AXES[v].upper()}")
        axis.set_aspect("equal", adjustable="box")

    figure.suptitle(title)
    figure.tight_layout()
    output = Path(output_path)
    ensure_directory(output.parent)
    figure.savefig(output, dpi=200)
    plt.close(figure)
    return True


def save_zone_preview(
    points,
    labels,
    output_path: str | Path,
    long_axis_index: int,
    title: str,
) -> bool:
    plt = try_import_matplotlib()
    if plt is None:
        return False

    import numpy as np  # type: ignore

    # Prefer a plane that clearly shows the long-axis banding.
    if long_axis_index == 0:
        plane_axes = [0, 1]
    elif long_axis_index == 1:
        plane_axes = [0, 1]
    else:
        plane_axes = [0, 2]

    label_order = [
        "edgeFrame",
        "innerHeel",
        "outerHeel",
        "innerArch",
        "outerArch",
        "innerForefoot",
        "centralForefoot",
        "outerForefoot",
        "toe",
    ]
    color_map = {
        "edgeFrame": "#444444",
        "innerHeel": "#1f77b4",
        "outerHeel": "#6baed6",
        "innerArch": "#2ca02c",
        "outerArch": "#98df8a",
        "innerForefoot": "#ff7f0e",
        "centralForefoot": "#f2b134",
        "outerForefoot": "#f7c97f",
        "toe": "#d62728",
    }

    figure, axis = plt.subplots(1, 1, figsize=(8, 14))
    for label in label_order:
        mask = labels == label
        if not np.any(mask):
            continue
        axis.scatter(
            points[mask, plane_axes[0]],
            points[mask, plane_axes[1]],
            s=0.4,
            alpha=0.7,
            label=label,
            c=color_map[label],
        )

    axis.set_title(title)
    axis.set_xlabel(f"{AXES[plane_axes[0]]} (mm)")
    axis.set_ylabel(f"{AXES[plane_axes[1]]} (mm)")
    axis.set_aspect("equal", adjustable="box")
    axis.legend(markerscale=6)
    figure.tight_layout()

    output = Path(output_path)
    ensure_directory(output.parent)
    figure.savefig(output, dpi=200)
    plt.close(figure)
    return True


def save_slice_preview(
    array,
    output_path: str | Path,
    title: str,
    cmap: str = "viridis",
) -> bool:
    plt = try_import_matplotlib()
    if plt is None:
        return False

    z_index = array.shape[2] // 2
    figure, axis = plt.subplots(1, 1, figsize=(8, 10))
    axis.imshow(array[:, :, z_index].T, origin="lower", cmap=cmap)
    axis.set_title(f"{title} (mid Z slice)")
    axis.set_xlabel("grid x")
    axis.set_ylabel("grid y")
    figure.tight_layout()

    output = Path(output_path)
    ensure_directory(output.parent)
    figure.savefig(output, dpi=200)
    plt.close(figure)
    return True
