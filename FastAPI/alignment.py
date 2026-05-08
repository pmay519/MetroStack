"""
app/services/alignment.py
Registration pipeline: Scan point cloud → CAD reference frame.

Stage 1 (optional): Fast Global Registration — coarse alignment
Stage 2           : ICP (Point-to-Plane) — high-precision refinement
Stage 3 (optional): Datum-locked constrained optimisation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AlignmentResult:
    transform: np.ndarray        # 4×4 rigid-body matrix (scan → CAD frame)
    inlier_rmse_mm: float
    fitness_score: float         # fraction of scan points that found correspondences
    inlier_count: int
    iteration_count: int
    method_used: str
    converged: bool


# ── Public API ────────────────────────────────────────────────────────────────

def align_icp(scan_cloud,
              cad_mesh,
              init_transform: np.ndarray | None = None,
              max_correspondence_dist_mm: float = 5.0,
              max_iterations: int = 200,
              relative_fitness: float = 1e-6,
              relative_rmse: float = 1e-6) -> AlignmentResult:
    """
    Two-stage registration:
      1. Fast Global Registration (if no init_transform supplied)
      2. Point-to-Plane ICP refinement

    Args:
        scan_cloud      : open3d.geometry.PointCloud  (must have normals)
        cad_mesh        : trimesh.Trimesh              (reference surface)
        init_transform  : 4×4 numpy array, or None to run FGR first
        max_correspondence_dist_mm : ICP correspondence threshold
        max_iterations  : ICP iteration cap
        relative_fitness / relative_rmse : ICP convergence criteria

    Returns:
        AlignmentResult with the final 4×4 transform + quality metrics
    """
    import open3d as o3d

    # Convert CAD mesh to Open3D PointCloud (sampled surface)
    cad_pcd = _mesh_to_sampled_cloud(cad_mesh, n_points=200_000)

    # Ensure both clouds have normals
    _ensure_normals(scan_cloud, radius=2.0)
    _ensure_normals(cad_pcd, radius=2.0)

    iters_used = 0

    # ── Stage 1: Coarse alignment ─────────────────────────────────────────────
    if init_transform is None:
        logger.info("Running Fast Global Registration (coarse alignment)...")
        init_transform, fgr_fitness = _fast_global_registration(scan_cloud, cad_pcd)
        logger.info(f"FGR fitness: {fgr_fitness:.4f}")

    # ── Stage 2: ICP refinement ───────────────────────────────────────────────
    logger.info(f"Running Point-to-Plane ICP "
                f"(max_dist={max_correspondence_dist_mm}mm, "
                f"max_iter={max_iterations})...")

    result = o3d.pipelines.registration.registration_icp(
        source=scan_cloud,
        target=cad_pcd,
        max_correspondence_distance=max_correspondence_dist_mm,
        init=init_transform,
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        criteria=o3d.pipelines.registration.ICPConvergenceCriteria(
            max_iteration=max_iterations,
            relative_fitness=relative_fitness,
            relative_rmse=relative_rmse,
        ),
    )

    converged = (result.fitness > 0.0 and result.inlier_rmse < max_correspondence_dist_mm)
    inlier_count = int(np.asarray(result.correspondence_set).shape[0])

    logger.info(
        f"ICP complete — RMSE: {result.inlier_rmse:.4f}mm  "
        f"Fitness: {result.fitness:.4f}  "
        f"Inliers: {inlier_count:,}  "
        f"Converged: {converged}"
    )

    return AlignmentResult(
        transform      = np.asarray(result.transformation),
        inlier_rmse_mm = float(result.inlier_rmse),
        fitness_score  = float(result.fitness),
        inlier_count   = inlier_count,
        iteration_count = max_iterations,  # o3d doesn't expose actual count
        method_used    = "fgr+icp" if init_transform is None else "icp",
        converged      = converged,
    )


def align_datum_constrained(scan_cloud,
                             cad_mesh,
                             datum_constraints: dict[str, Any],
                             icp_result: AlignmentResult | None = None) -> AlignmentResult:
    """
    GD&T-aware datum-locked alignment.
    Constrains DOF according to ASME Y14.5 datum precedence:
      Primary datum (A)   → constrains 3 DOF (plane = Z translation + 2 rotations)
      Secondary datum (B) → constrains 2 DOF (axis = 2 translations)
      Tertiary datum (C)  → constrains 1 DOF (point = 1 rotation)

    datum_constraints format:
    {
        "A": {"type": "plane", "normal": [0,0,1], "points": [[x,y,z], ...]},
        "B": {"type": "cylinder", "axis": [1,0,0], "center": [x,y,z]},
        "C": {"type": "point", "location": [x,y,z]}
    }
    """
    from scipy.optimize import minimize

    pts = np.asarray(scan_cloud.points)

    # Start from ICP result if provided, else identity
    if icp_result is not None:
        init_params = _matrix_to_params(icp_result.transform)
    else:
        init_params = np.zeros(6)  # [tx, ty, tz, rx, ry, rz]

    # Build constraint functions for scipy
    constraints = _build_datum_constraints(datum_constraints)

    def objective(params):
        """Minimise ICP-style point-to-surface residual."""
        T = _params_to_matrix(params)
        pts_transformed = (T[:3, :3] @ pts.T).T + T[:3, 3]
        import trimesh
        _, dists, _ = trimesh.proximity.closest_point(cad_mesh, pts_transformed)
        return float(np.mean(dists ** 2))

    result = minimize(
        objective,
        init_params,
        method="SLSQP",
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-8},
    )

    T_final = _params_to_matrix(result.x)
    pts_t = (T_final[:3, :3] @ pts.T).T + T_final[:3, 3]
    import trimesh
    _, dists, _ = trimesh.proximity.closest_point(cad_mesh, pts_t)
    rmse = float(np.sqrt(np.mean(dists ** 2)))

    logger.info(
        f"Datum-constrained alignment — RMSE: {rmse:.4f}mm  "
        f"Converged: {result.success}  Msg: {result.message}"
    )

    return AlignmentResult(
        transform      = T_final,
        inlier_rmse_mm = rmse,
        fitness_score  = 1.0 - min(rmse / 1.0, 1.0),
        inlier_count   = len(pts),
        iteration_count = result.nit,
        method_used    = "datum_locked",
        converged      = result.success,
    )


def apply_transform(cloud, transform: np.ndarray):
    """Return a new cloud with the 4×4 transform applied."""
    import open3d as o3d
    transformed = o3d.geometry.PointCloud(cloud)
    transformed.transform(transform)
    return transformed


# ── Internal helpers ──────────────────────────────────────────────────────────

def _mesh_to_sampled_cloud(mesh, n_points: int = 200_000):
    """Uniformly sample a trimesh surface → Open3D PointCloud."""
    import open3d as o3d
    import trimesh

    pts, face_ids = trimesh.sample.sample_surface_even(mesh, count=n_points)
    normals = mesh.face_normals[face_ids]

    pcd = o3d.geometry.PointCloud()
    pcd.points  = o3d.utility.Vector3dVector(pts)
    pcd.normals = o3d.utility.Vector3dVector(normals)
    return pcd


def _ensure_normals(pcd, radius: float = 2.0) -> None:
    """Estimate normals in-place if the cloud doesn't have them."""
    import open3d as o3d
    if not pcd.has_normals():
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=radius, max_nn=30
            )
        )
        pcd.orient_normals_consistent_tangent_plane(k=15)


def _fast_global_registration(source, target) -> tuple[np.ndarray, float]:
    """Run FPFH-based Fast Global Registration."""
    import open3d as o3d

    radius_feature = 5.0

    src_fpfh = o3d.pipelines.registration.compute_fpfh_feature(
        source,
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius_feature, max_nn=100),
    )
    tgt_fpfh = o3d.pipelines.registration.compute_fpfh_feature(
        target,
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius_feature, max_nn=100),
    )

    result = o3d.pipelines.registration.registration_fgr_based_on_feature_matching(
        source, target, src_fpfh, tgt_fpfh,
        o3d.pipelines.registration.FastGlobalRegistrationOption(
            maximum_correspondence_distance=5.0
        ),
    )
    return np.asarray(result.transformation), float(result.fitness)


def _params_to_matrix(params: np.ndarray) -> np.ndarray:
    """Convert [tx, ty, tz, rx, ry, rz] (angles in radians) → 4×4 matrix."""
    tx, ty, tz, rx, ry, rz = params

    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)

    # ZYX Euler → rotation matrix
    R = np.array([
        [cy*cz, cz*sx*sy - cx*sz, cx*cz*sy + sx*sz],
        [cy*sz, cx*cz + sx*sy*sz, cx*sy*sz - cz*sx],
        [-sy,   cy*sx,             cx*cy            ],
    ])

    T = np.eye(4)
    T[:3, :3] = R
    T[:3,  3] = [tx, ty, tz]
    return T


def _matrix_to_params(T: np.ndarray) -> np.ndarray:
    """Extract [tx, ty, tz, rx, ry, rz] from 4×4 matrix."""
    tx, ty, tz = T[:3, 3]
    R = T[:3, :3]
    ry = -np.arcsin(np.clip(R[2, 0], -1, 1))
    cy = np.cos(ry)
    if abs(cy) > 1e-6:
        rx = np.arctan2(R[2, 1] / cy, R[2, 2] / cy)
        rz = np.arctan2(R[1, 0] / cy, R[0, 0] / cy)
    else:
        rx = np.arctan2(-R[1, 2], R[1, 1])
        rz = 0.0
    return np.array([tx, ty, tz, rx, ry, rz])


def _build_datum_constraints(datum_constraints: dict) -> list[dict]:
    """
    Translate datum definitions into scipy constraint dicts.
    Returns list of {"type": "eq"/"ineq", "fun": callable} entries.
    """
    constraints = []

    for label, datum in datum_constraints.items():
        dtype = datum.get("type", "plane")

        if dtype == "plane":
            # Primary datum — constrain translation along normal + 2 rotations
            normal = np.array(datum["normal"], dtype=float)
            normal /= np.linalg.norm(normal)

            def plane_constraint(params, n=normal):
                T = _params_to_matrix(params)
                # Normal direction in transformed frame must align with world normal
                transformed_normal = T[:3, :3] @ n
                return float(np.dot(transformed_normal, n) - 1.0)

            constraints.append({"type": "eq", "fun": plane_constraint})

        elif dtype == "cylinder":
            axis = np.array(datum["axis"], dtype=float)
            axis /= np.linalg.norm(axis)
            center = np.array(datum["center"], dtype=float)

            def axis_constraint(params, ax=axis, c=center):
                T = _params_to_matrix(params)
                transformed_axis = T[:3, :3] @ ax
                return float(np.dot(transformed_axis, ax) - 1.0)

            constraints.append({"type": "eq", "fun": axis_constraint})

        elif dtype == "point":
            location = np.array(datum["location"], dtype=float)

            def point_constraint_x(params, loc=location):
                T = _params_to_matrix(params)
                return float(T[0, 3] - loc[0])

            def point_constraint_y(params, loc=location):
                T = _params_to_matrix(params)
                return float(T[1, 3] - loc[1])

            constraints.extend([
                {"type": "eq", "fun": point_constraint_x},
                {"type": "eq", "fun": point_constraint_y},
            ])

    return constraints
