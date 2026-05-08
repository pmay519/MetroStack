"""
app/services/wall_thickness.py
Ray-cast wall thickness measurement.
Shoots inward rays from sampled surface points along their normals
and measures the distance to the opposite wall.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class WallThicknessResult:
    sample_points: np.ndarray    # (N, 3) origin of each ray
    normals: np.ndarray          # (N, 3) inward ray directions
    thickness_mm: np.ndarray     # (N,)  measured thickness
    hit_points: np.ndarray       # (N, 3) opposite-wall intersection
    stats: dict


def compute_wall_thickness(cad_mesh,
                            sample_count: int = 20_000,
                            ray_offset_mm: float = 0.01,
                            min_thickness_mm: float = 0.1,
                            max_thickness_mm: float | None = None) -> WallThicknessResult:
    """
    Measure wall thickness across a watertight mesh by ray-casting.

    Algorithm:
      1. Uniformly sample N points on the outer surface.
      2. For each point, shoot a ray inward along the surface normal.
      3. The first intersection with the opposite wall is the thickness.

    Args:
        cad_mesh         : trimesh.Trimesh (should be watertight for best results)
        sample_count     : number of sample rays to cast
        ray_offset_mm    : move ray origin slightly inside surface to avoid
                           self-intersection at origin face
        min_thickness_mm : discard hits below this — likely self-intersections
        max_thickness_mm : discard hits above this — likely open-surface leakage

    Returns:
        WallThicknessResult with per-sample thickness and statistics.
    """
    import trimesh

    if not cad_mesh.is_watertight:
        logger.warning(
            "Mesh is not watertight — wall thickness results may contain "
            "artifacts from open boundary faces."
        )

    logger.info(f"Sampling {sample_count:,} surface points for wall thickness...")

    # ── Step 1: Sample surface points + normals ───────────────────────────────
    sample_pts, face_ids = trimesh.sample.sample_surface_even(
        cad_mesh, count=sample_count
    )
    outward_normals = cad_mesh.face_normals[face_ids]   # (N, 3)
    inward_normals  = -outward_normals                  # flip inward

    # Offset origins slightly inward to skip the origin face
    ray_origins = sample_pts + inward_normals * ray_offset_mm

    # ── Step 2: Batch ray casting ─────────────────────────────────────────────
    logger.info("Ray-casting inward...")

    # trimesh ray.intersects_location returns all hits; we want first per ray
    locations, ray_ids, face_ids_hit = cad_mesh.ray.intersects_location(
        ray_origins    = ray_origins,
        ray_directions = inward_normals,
        multiple_hits  = False,
    )

    logger.info(f"Got {len(locations):,} ray hits from {sample_count:,} rays.")

    if len(locations) == 0:
        raise RuntimeError(
            "No ray intersections found. "
            "Check that the mesh is closed and watertight."
        )

    # ── Step 3: Compute distances ─────────────────────────────────────────────
    hit_origins = ray_origins[ray_ids]
    raw_distances = np.linalg.norm(locations - hit_origins, axis=1)

    # ── Step 4: Filter outliers ───────────────────────────────────────────────
    valid_mask = raw_distances >= min_thickness_mm
    if max_thickness_mm is not None:
        valid_mask &= raw_distances <= max_thickness_mm

    # Also filter by statistical outlier: keep within mean ± 3σ
    d_mean, d_std = raw_distances.mean(), raw_distances.std()
    stat_mask = np.abs(raw_distances - d_mean) <= 3.0 * d_std
    valid_mask &= stat_mask

    valid_ray_ids   = ray_ids[valid_mask]
    valid_distances = raw_distances[valid_mask]
    valid_locations = locations[valid_mask]

    logger.info(
        f"Valid hits after filtering: {valid_mask.sum():,} / {len(raw_distances):,}"
    )

    # Map back to original sample points
    out_pts     = sample_pts[valid_ray_ids]
    out_normals = inward_normals[valid_ray_ids]

    # ── Step 5: Statistics ────────────────────────────────────────────────────
    stats = _compute_stats(valid_distances)

    logger.info(
        f"Wall thickness — min: {stats['min_mm']:.3f}mm  "
        f"max: {stats['max_mm']:.3f}mm  "
        f"mean: {stats['mean_mm']:.3f}mm  "
        f"std: {stats['std_mm']:.3f}mm"
    )

    return WallThicknessResult(
        sample_points = out_pts,
        normals       = out_normals,
        thickness_mm  = valid_distances,
        hit_points    = valid_locations,
        stats         = stats,
    )


def compute_section_thickness(cad_mesh,
                               plane_origin: np.ndarray,
                               plane_normal: np.ndarray,
                               sample_count: int = 5_000) -> WallThicknessResult:
    """
    Wall thickness along a cross-section plane.
    Intersects the mesh with a plane, then measures thickness
    perpendicular to the cutting plane within that cross-section.

    Args:
        cad_mesh      : trimesh.Trimesh
        plane_origin  : (3,) point on the cutting plane
        plane_normal  : (3,) normal to the cutting plane
        sample_count  : rays to cast within the section

    Returns:
        WallThicknessResult for the section.
    """
    import trimesh

    plane_normal = plane_normal / np.linalg.norm(plane_normal)

    # Get cross-section path
    section = cad_mesh.section(
        plane_origin=plane_origin,
        plane_normal=plane_normal
    )

    if section is None:
        raise ValueError(
            "Cross-section plane does not intersect the mesh. "
            "Check plane_origin is inside the bounding box."
        )

    # Project cross-section to 2D
    path_2d, transform = section.to_planar()

    # Sample points along the section boundary
    pts_2d = []
    for entity in path_2d.entities:
        verts = path_2d.vertices[entity.points]
        for i in range(len(verts) - 1):
            n_interp = max(2, int(np.linalg.norm(verts[i+1] - verts[i]) * 10))
            interp = np.linspace(verts[i], verts[i+1], n_interp)
            pts_2d.extend(interp)

    pts_2d = np.array(pts_2d[:sample_count])

    # Cast rays across the section (perpendicular to section boundary normals)
    # Simplified: cast in +/- directions from boundary midpoints
    # This is a common approximation for 2D cross-section thickness
    centroid_2d = pts_2d.mean(axis=0)
    ray_dirs_2d = centroid_2d - pts_2d
    norms = np.linalg.norm(ray_dirs_2d, axis=1, keepdims=True)
    ray_dirs_2d /= np.where(norms > 0, norms, 1)

    # Build 3D versions
    inv_transform = np.linalg.inv(transform)
    pts_2d_h  = np.column_stack([pts_2d, np.zeros(len(pts_2d)), np.ones(len(pts_2d))])
    dirs_2d_h = np.column_stack([ray_dirs_2d, np.zeros(len(ray_dirs_2d)), np.zeros(len(ray_dirs_2d))])

    pts_3d  = (inv_transform @ pts_2d_h.T).T[:, :3]
    dirs_3d = (inv_transform @ dirs_2d_h.T).T[:, :3]

    # Normalise 3D dirs
    d_norms = np.linalg.norm(dirs_3d, axis=1, keepdims=True)
    dirs_3d /= np.where(d_norms > 0, d_norms, 1)

    locs, ray_ids, _ = cad_mesh.ray.intersects_location(
        ray_origins    = pts_3d,
        ray_directions = dirs_3d,
        multiple_hits  = False,
    )

    if len(locs) == 0:
        raise RuntimeError("No cross-section ray intersections found.")

    distances = np.linalg.norm(locs - pts_3d[ray_ids], axis=1)
    valid = distances > 0.1

    stats = _compute_stats(distances[valid])

    return WallThicknessResult(
        sample_points = pts_3d[ray_ids[valid]],
        normals       = dirs_3d[ray_ids[valid]],
        thickness_mm  = distances[valid],
        hit_points    = locs[valid],
        stats         = stats,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_stats(thickness: np.ndarray) -> dict:
    if len(thickness) == 0:
        return {"min_mm": 0, "max_mm": 0, "mean_mm": 0, "std_mm": 0, "sample_count": 0}

    return {
        "min_mm":      float(thickness.min()),
        "max_mm":      float(thickness.max()),
        "mean_mm":     float(thickness.mean()),
        "std_mm":      float(thickness.std()),
        "median_mm":   float(np.median(thickness)),
        "p5_mm":       float(np.percentile(thickness, 5)),
        "p95_mm":      float(np.percentile(thickness, 95)),
        "sample_count": int(len(thickness)),
    }


def downsample_for_display(result: WallThicknessResult,
                            max_points: int = 50_000) -> WallThicknessResult:
    """Random downsample for frontend rendering."""
    n = len(result.thickness_mm)
    if n <= max_points:
        return result

    idx = np.random.choice(n, size=max_points, replace=False)
    idx.sort()

    return WallThicknessResult(
        sample_points = result.sample_points[idx],
        normals       = result.normals[idx],
        thickness_mm  = result.thickness_mm[idx],
        hit_points    = result.hit_points[idx],
        stats         = result.stats,  # full-dataset stats preserved
    )
