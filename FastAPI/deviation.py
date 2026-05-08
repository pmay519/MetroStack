"""
app/services/deviation.py
Signed deviation analysis: every scan point → nearest CAD surface triangle.
Positive = outside (proud), Negative = inside (undercut).
Results streamed to PostgreSQL in configurable batch sizes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DeviationResult:
    scan_points: np.ndarray       # (N, 3)
    closest_cad_points: np.ndarray  # (N, 3)
    deviations_mm: np.ndarray     # (N,) signed
    normals: np.ndarray           # (N, 3) surface normals at closest pts
    stats: dict


def compute_deviation(scan_cloud,
                      cad_mesh,
                      transform: np.ndarray | None = None,
                      batch_size: int = 100_000) -> DeviationResult:
    """
    Compute signed point-to-surface deviation for every scan point.

    Args:
        scan_cloud  : open3d.geometry.PointCloud (already aligned, or supply transform)
        cad_mesh    : trimesh.Trimesh
        transform   : optional 4×4 matrix to apply to scan before analysis
        batch_size  : process this many points at a time (memory management)

    Returns:
        DeviationResult with per-point signed deviations and aggregate stats.
    """
    import trimesh

    pts = np.asarray(scan_cloud.points, dtype=np.float64)

    # Apply alignment transform if supplied
    if transform is not None:
        R = transform[:3, :3]
        t = transform[:3,  3]
        pts = (R @ pts.T).T + t

    n_points = len(pts)
    logger.info(f"Computing deviation for {n_points:,} points in batches of {batch_size:,}...")

    closest_pts  = np.empty_like(pts)
    distances    = np.empty(n_points, dtype=np.float64)
    face_normals = np.empty_like(pts)

    # ── Batched proximity query ───────────────────────────────────────────────
    for start in range(0, n_points, batch_size):
        end   = min(start + batch_size, n_points)
        batch = pts[start:end]

        cp, dist, tri_ids = trimesh.proximity.closest_point(cad_mesh, batch)

        closest_pts[start:end]  = cp
        distances[start:end]    = dist
        face_normals[start:end] = cad_mesh.face_normals[tri_ids]

        pct = int((end / n_points) * 100)
        if pct % 10 == 0 or end == n_points:
            logger.info(f"  Deviation progress: {pct}% ({end:,}/{n_points:,} pts)")

    # ── Sign determination ────────────────────────────────────────────────────
    # Vector from CAD surface toward scan point
    scan_to_surface = pts - closest_pts  # (N, 3)

    # Dot product with outward surface normal — positive = scan is outside CAD
    dot_products = np.einsum("ij,ij->i", scan_to_surface, face_normals)
    signs = np.sign(dot_products)
    signs[signs == 0] = 1  # zero-crossings treated as positive

    signed_deviations = distances * signs  # (N,) in mm

    # ── Statistics ────────────────────────────────────────────────────────────
    abs_devs = np.abs(signed_deviations)
    stats = {
        "point_count": n_points,
        "min_mm":  float(signed_deviations.min()),
        "max_mm":  float(signed_deviations.max()),
        "mean_mm": float(signed_deviations.mean()),
        "rms_mm":  float(np.sqrt(np.mean(signed_deviations ** 2))),
        "p95_mm":  float(np.percentile(abs_devs, 95)),
        "p99_mm":  float(np.percentile(abs_devs, 99)),
        "pct_in_tol_005": float(np.mean(abs_devs <= 0.05) * 100),
        "pct_in_tol_010": float(np.mean(abs_devs <= 0.10) * 100),
        "pct_in_tol_025": float(np.mean(abs_devs <= 0.25) * 100),
    }

    logger.info(
        f"Deviation complete — "
        f"min: {stats['min_mm']:.3f}mm  max: {stats['max_mm']:.3f}mm  "
        f"RMS: {stats['rms_mm']:.3f}mm  P95: {stats['p95_mm']:.3f}mm"
    )

    return DeviationResult(
        scan_points      = pts,
        closest_cad_points = closest_pts,
        deviations_mm    = signed_deviations,
        normals          = face_normals,
        stats            = stats,
    )


def downsample_for_display(result: DeviationResult,
                            max_points: int = 500_000) -> DeviationResult:
    """
    Randomly downsample a large result for real-time frontend rendering.
    Preserves extreme outliers (top/bottom 1%) to keep heatmap meaningful.
    """
    n = len(result.deviations_mm)
    if n <= max_points:
        return result

    devs = result.deviations_mm
    abs_devs = np.abs(devs)
    p99_threshold = np.percentile(abs_devs, 99)

    # Always keep outlier points
    outlier_mask = abs_devs >= p99_threshold
    normal_mask  = ~outlier_mask

    # Random sample from the bulk
    normal_indices  = np.where(normal_mask)[0]
    outlier_indices = np.where(outlier_mask)[0]

    n_outliers = len(outlier_indices)
    n_normal   = min(max_points - n_outliers, len(normal_indices))
    sampled_normal = np.random.choice(normal_indices, size=n_normal, replace=False)

    keep = np.sort(np.concatenate([sampled_normal, outlier_indices]))

    return DeviationResult(
        scan_points        = result.scan_points[keep],
        closest_cad_points = result.closest_cad_points[keep],
        deviations_mm      = result.deviations_mm[keep],
        normals            = result.normals[keep],
        stats              = result.stats,  # stats from full dataset preserved
    )


def compute_heatmap_scale(deviations_mm: np.ndarray,
                           clip_percentile: float = 99.0
                           ) -> tuple[float, float]:
    """
    Compute symmetric colour scale bounds, clipped to percentile
    to prevent extreme outliers from collapsing the colour range.
    Returns (scale_min, scale_max).
    """
    abs_devs = np.abs(deviations_mm)
    clip_val = float(np.percentile(abs_devs, clip_percentile))
    return -clip_val, clip_val


async def bulk_insert_deviation_points(conn,
                                        project_id: str,
                                        job_id: str,
                                        result: DeviationResult,
                                        batch_size: int = 100_000) -> None:
    """
    Bulk-insert deviation points into PostgreSQL using COPY.
    Uses asyncpg's copy_records_to_table for maximum throughput.

    Args:
        conn       : asyncpg Connection (not SQLAlchemy session)
        project_id : UUID string
        job_id     : UUID string
        result     : DeviationResult
        batch_size : rows per COPY batch
    """
    import uuid

    pts  = result.scan_points
    devs = result.deviations_mm
    nrms = result.normals
    cpts = result.closest_cad_points

    n = len(pts)
    logger.info(f"Bulk-inserting {n:,} deviation points into PostgreSQL...")

    # Ensure table exists (raw DDL — not ORM-managed due to bulk volume)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS deviation_points (
            id           UUID DEFAULT gen_random_uuid(),
            project_id   UUID NOT NULL,
            job_id       UUID NOT NULL,
            pt_x         DOUBLE PRECISION,
            pt_y         DOUBLE PRECISION,
            pt_z         DOUBLE PRECISION,
            deviation_mm DOUBLE PRECISION,
            cad_x        DOUBLE PRECISION,
            cad_y        DOUBLE PRECISION,
            cad_z        DOUBLE PRECISION,
            normal_x     DOUBLE PRECISION,
            normal_y     DOUBLE PRECISION,
            normal_z     DOUBLE PRECISION
        )
    """)

    proj_uuid = uuid.UUID(project_id)
    job_uuid  = uuid.UUID(job_id)

    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)

        records = [
            (
                proj_uuid,
                job_uuid,
                float(pts[i, 0]),
                float(pts[i, 1]),
                float(pts[i, 2]),
                float(devs[i]),
                float(cpts[i, 0]),
                float(cpts[i, 1]),
                float(cpts[i, 2]),
                float(nrms[i, 0]),
                float(nrms[i, 1]),
                float(nrms[i, 2]),
            )
            for i in range(start, end)
        ]

        await conn.copy_records_to_table(
            "deviation_points",
            records=records,
            columns=[
                "project_id", "job_id",
                "pt_x", "pt_y", "pt_z",
                "deviation_mm",
                "cad_x", "cad_y", "cad_z",
                "normal_x", "normal_y", "normal_z",
            ],
        )
        logger.info(f"  Inserted rows {start:,}–{end:,}")

    logger.info("Deviation bulk-insert complete.")
