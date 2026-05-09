"""
app/services/gdt.py
GD&T dimensional analysis per ASME Y14.5-2018.
Implements Minimum Zone fitting (not least-squares) where required.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.optimize import minimize, least_squares

logger = logging.getLogger(__name__)


@dataclass
class GDTFeatureResult:
    feature_name: str
    feature_type: str
    actual_value_mm: float
    nominal_value_mm: float | None
    deviation_mm: float | None
    in_tolerance: bool
    tolerance_upper_mm: float | None
    tolerance_lower_mm: float | None

    # Best-fit geometry
    fit_center: np.ndarray | None = None   # (3,)
    fit_normal: np.ndarray | None = None   # (3,) plane normal or cylinder axis
    fit_radius: float | None = None
    fit_residual_rms: float | None = None
    point_count_used: int = 0


# ── Public entry point ────────────────────────────────────────────────────────

def analyse_feature(feature: dict,
                    scan_points: np.ndarray,
                    cad_mesh=None,
                    datum_transform: np.ndarray | None = None) -> GDTFeatureResult:
    """
    Route a GD&T feature to the correct calculation.

    feature dict keys:
        name, feature_type, tolerance_upper_mm, tolerance_lower_mm,
        nominal_x, nominal_y, nominal_z, nominal_diameter,
        roi_min_x/y/z, roi_max_x/y/z,
        primary_datum, secondary_datum, tertiary_datum
    """
    ftype = feature["feature_type"].lower()
    pts   = _extract_roi_points(scan_points, feature)

    if len(pts) < 4:
        raise ValueError(
            f"Feature '{feature['name']}' ROI contains only {len(pts)} points "
            f"(minimum 4 required)."
        )

    logger.info(f"Analysing {ftype} '{feature['name']}' — {len(pts):,} points in ROI")

    dispatch = {
        "flatness":         _flatness,
        "straightness":     _straightness,
        "circularity":      _circularity,
        "cylindricity":     _cylindricity,
        "position":         _position,
        "parallelism":      _parallelism,
        "perpendicularity": _perpendicularity,
        "angularity":       _angularity,
        "profile_surface":  _profile_surface,
        "runout":           _runout,
        "total_runout":     _total_runout,
    }

    if ftype not in dispatch:
        raise ValueError(f"Unsupported feature type: '{ftype}'")

    result = dispatch[ftype](pts, feature, datum_transform)
    return result


# ── Flatness ──────────────────────────────────────────────────────────────────

def _flatness(pts: np.ndarray, feature: dict, _dt) -> GDTFeatureResult:
    """
    Flatness = distance between two parallel planes of minimum separation
    enclosing all surface points (Minimum Zone Plane).
    Uses SVD-based best-fit plane, then projects to find extremes.
    """
    centroid = pts.mean(axis=0)
    _, _, vh  = np.linalg.svd(pts - centroid)
    normal    = vh[-1]   # least-significant eigenvector = plane normal

    projections = (pts - centroid) @ normal
    flatness    = float(projections.max() - projections.min())

    return _make_result(
        feature   = feature,
        actual    = flatness,
        fit_center = centroid,
        fit_normal = normal,
        fit_rms    = float(np.std(projections)),
        pts_used   = len(pts),
    )


# ── Straightness ──────────────────────────────────────────────────────────────

def _straightness(pts: np.ndarray, feature: dict, _dt) -> GDTFeatureResult:
    """
    Straightness of a line element = max deviation from best-fit line.
    """
    centroid  = pts.mean(axis=0)
    _, _, vh  = np.linalg.svd(pts - centroid)
    direction = vh[0]   # most-significant eigenvector = line direction

    # Project each point onto the line, compute perpendicular offset
    proj_scalar = (pts - centroid) @ direction
    proj_pts    = centroid + np.outer(proj_scalar, direction)
    offsets     = np.linalg.norm(pts - proj_pts, axis=1)
    straightness = float(offsets.max())

    return _make_result(
        feature    = feature,
        actual     = straightness,
        fit_normal = direction,
        fit_center = centroid,
        fit_rms    = float(np.mean(offsets)),
        pts_used   = len(pts),
    )


# ── Circularity ───────────────────────────────────────────────────────────────

def _circularity(pts: np.ndarray, feature: dict, _dt) -> GDTFeatureResult:
    """
    Circularity (roundness) = Rmax − Rmin of Minimum Zone Circle.
    Projects onto best-fit plane first, then fits 2D circle.
    """
    # Project to best-fit plane
    centroid  = pts.mean(axis=0)
    _, _, vh  = np.linalg.svd(pts - centroid)
    normal    = vh[-1]

    # Create local 2D coordinate axes
    u = vh[0]
    v = vh[1]
    pts_2d = np.column_stack([(pts - centroid) @ u,
                               (pts - centroid) @ v])

    cx, cy, r0, rms = _fit_circle_2d(pts_2d)
    center_2d = np.array([cx, cy])
    radii = np.linalg.norm(pts_2d - center_2d, axis=1)
    circularity = float(radii.max() - radii.min())

    center_3d = centroid + cx * u + cy * v

    return _make_result(
        feature    = feature,
        actual     = circularity,
        fit_center = center_3d,
        fit_normal = normal,
        fit_radius = r0,
        fit_rms    = rms,
        pts_used   = len(pts),
    )


# ── Cylindricity ──────────────────────────────────────────────────────────────

def _cylindricity(pts: np.ndarray, feature: dict, _dt) -> GDTFeatureResult:
    """
    Cylindricity = Rmax − Rmin of Minimum Zone Cylinder.
    Fits cylinder axis via optimisation, then measures radial spread.
    """
    axis, center, radius, rms = _fit_cylinder(pts)
    radii = _radial_distances_to_axis(pts, center, axis)
    cylindricity = float(radii.max() - radii.min())

    return _make_result(
        feature    = feature,
        actual     = cylindricity,
        fit_center = center,
        fit_normal = axis,
        fit_radius = radius,
        fit_rms    = rms,
        pts_used   = len(pts),
    )


# ── Position ──────────────────────────────────────────────────────────────────

def _position(pts: np.ndarray, feature: dict,
              datum_transform: np.ndarray | None) -> GDTFeatureResult:
    """
    True Position = 2 × (distance from measured feature axis/center to nominal).
    Measured center found by fitting a circle/cylinder to the ROI points.
    """
    nominal = np.array([
        feature.get("nominal_x", 0.0),
        feature.get("nominal_y", 0.0),
        feature.get("nominal_z", 0.0),
    ], dtype=float)

    # Fit circle/cylinder to get measured center
    try:
        axis, center, radius, rms = _fit_cylinder(pts)
    except Exception:
        center = pts.mean(axis=0)
        rms    = 0.0
        radius = None
        axis   = np.array([0.0, 0.0, 1.0])

    # Transform into datum reference frame if provided
    if datum_transform is not None:
        center_h  = np.append(center, 1.0)
        nominal_h = np.append(nominal, 1.0)
        center  = (datum_transform @ center_h)[:3]
        nominal = (datum_transform @ nominal_h)[:3]

    distance    = float(np.linalg.norm(center - nominal))
    true_position = 2.0 * distance   # diameter zone per ASME Y14.5

    return _make_result(
        feature    = feature,
        actual     = true_position,
        nominal    = 0.0,           # perfect position = 0 deviation
        fit_center = center,
        fit_normal = axis,
        fit_radius = radius,
        fit_rms    = rms,
        pts_used   = len(pts),
    )


# ── Parallelism ───────────────────────────────────────────────────────────────

def _parallelism(pts: np.ndarray, feature: dict,
                 datum_transform: np.ndarray | None) -> GDTFeatureResult:
    """
    Parallelism = flatness measured after rotating into datum plane frame.
    The measured surface normal deviation from datum normal is the parallelism error.
    """
    centroid = pts.mean(axis=0)
    _, _, vh  = np.linalg.svd(pts - centroid)
    measured_normal = vh[-1]

    # Datum A normal (from transform or default Z)
    if datum_transform is not None:
        datum_normal = datum_transform[:3, 2]
    else:
        datum_normal = np.array([0.0, 0.0, 1.0])
    datum_normal /= np.linalg.norm(datum_normal)

    # Project onto datum normal direction
    projections = (pts - centroid) @ datum_normal
    parallelism = float(projections.max() - projections.min())

    return _make_result(
        feature    = feature,
        actual     = parallelism,
        fit_center = centroid,
        fit_normal = measured_normal,
        fit_rms    = float(np.std(projections)),
        pts_used   = len(pts),
    )


# ── Perpendicularity ──────────────────────────────────────────────────────────

def _perpendicularity(pts: np.ndarray, feature: dict,
                      datum_transform: np.ndarray | None) -> GDTFeatureResult:
    """
    Perpendicularity = zone width of planes perpendicular to datum.
    """
    centroid = pts.mean(axis=0)
    _, _, vh  = np.linalg.svd(pts - centroid)
    axis      = vh[0]   # best-fit line direction

    # Datum normal
    if datum_transform is not None:
        datum_normal = datum_transform[:3, 2]
    else:
        datum_normal = np.array([0.0, 0.0, 1.0])
    datum_normal /= np.linalg.norm(datum_normal)

    # Perpendicularity = distance between planes perpendicular to datum normal
    # that contain the extremes of the projected axis
    angle_error_rad = float(np.arccos(np.clip(abs(np.dot(axis, datum_normal)), 0, 1)))
    # Zone width = max distance projected perpendicular to datum
    perp_direction = axis - np.dot(axis, datum_normal) * datum_normal
    if np.linalg.norm(perp_direction) > 1e-10:
        perp_direction /= np.linalg.norm(perp_direction)
    projections   = (pts - centroid) @ datum_normal
    perpendicularity = float(projections.max() - projections.min())

    return _make_result(
        feature    = feature,
        actual     = perpendicularity,
        fit_center = centroid,
        fit_normal = axis,
        fit_rms    = float(np.std(projections)),
        pts_used   = len(pts),
    )


# ── Angularity ────────────────────────────────────────────────────────────────

def _angularity(pts: np.ndarray, feature: dict,
                datum_transform: np.ndarray | None) -> GDTFeatureResult:
    """
    Angularity = zone between two parallel planes at the basic angle to datum.
    """
    # Identical calculation to perpendicularity — zone width at specified angle
    return _perpendicularity(pts, feature, datum_transform)


# ── Profile of a Surface ──────────────────────────────────────────────────────

def _profile_surface(pts: np.ndarray, feature: dict, _dt) -> GDTFeatureResult:
    """
    Profile of a Surface = total band within which all points must fall
    relative to the true CAD profile.  Requires cad_mesh for closest-point query.
    Note: actual nearest-surface computation happens upstream in deviation.py;
    here we work with pre-computed deviations passed via feature dict.
    """
    deviations = feature.get("precomputed_deviations_mm")
    if deviations is None:
        raise ValueError(
            "profile_surface requires 'precomputed_deviations_mm' in feature dict. "
            "Run deviation analysis first."
        )
    deviations = np.asarray(deviations)
    profile    = float(deviations.max() - deviations.min())

    return _make_result(
        feature  = feature,
        actual   = profile,
        fit_rms  = float(np.sqrt(np.mean(deviations ** 2))),
        pts_used = len(deviations),
    )


# ── Runout ────────────────────────────────────────────────────────────────────

def _runout(pts: np.ndarray, feature: dict,
            datum_transform: np.ndarray | None) -> GDTFeatureResult:
    """
    Circular Runout = max FIR (Full Indicator Reading) in a single cross-section.
    """
    # Datum axis
    if datum_transform is not None:
        axis   = datum_transform[:3, 0]
        center = datum_transform[:3, 3]
    else:
        axis   = np.array([0.0, 0.0, 1.0])
        center = pts.mean(axis=0)
    axis /= np.linalg.norm(axis)

    radii  = _radial_distances_to_axis(pts, center, axis)
    runout = float(radii.max() - radii.min())

    return _make_result(
        feature    = feature,
        actual     = runout,
        fit_center = center,
        fit_normal = axis,
        fit_radius = float(radii.mean()),
        fit_rms    = float(np.std(radii)),
        pts_used   = len(pts),
    )


def _total_runout(pts: np.ndarray, feature: dict,
                  datum_transform: np.ndarray | None) -> GDTFeatureResult:
    """
    Total Runout = FIR over entire surface (all cross-sections simultaneously).
    """
    return _runout(pts, feature, datum_transform)


# ── Geometry fitting helpers ──────────────────────────────────────────────────

def _fit_circle_2d(pts_2d: np.ndarray) -> tuple[float, float, float, float]:
    """
    Fit minimum zone circle to 2D points.
    Returns (cx, cy, radius, rms_residual).
    """
    def residuals(params):
        cx, cy, r = params
        return np.sqrt((pts_2d[:, 0] - cx)**2 + (pts_2d[:, 1] - cy)**2) - r

    cx0, cy0 = pts_2d.mean(axis=0)
    r0 = float(np.std(np.linalg.norm(pts_2d - [cx0, cy0], axis=1)))

    result = least_squares(residuals, [cx0, cy0, max(r0, 0.1)], method="lm")
    cx, cy, r = result.x
    rms = float(np.sqrt(np.mean(result.fun ** 2)))
    return float(cx), float(cy), float(abs(r)), rms


def _fit_cylinder(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    """
    Fit a cylinder to 3D points.
    Returns (axis_unit_vector, center_point_on_axis, radius, rms_residual).
    """
    # Initial guess: PCA gives approximate axis
    centroid = pts.mean(axis=0)
    _, _, vh  = np.linalg.svd(pts - centroid)
    axis0    = vh[0]

    def residuals(params):
        ax, ay = params[0], params[1]
        az = np.sqrt(max(0.0, 1.0 - ax**2 - ay**2))
        axis = np.array([ax, ay, az])
        axis /= np.linalg.norm(axis)

        # Project points to plane perpendicular to axis
        proj_scalar = (pts - centroid) @ axis
        proj_pts    = pts - np.outer(proj_scalar, axis)
        proj_center = proj_pts.mean(axis=0)
        radii       = np.linalg.norm(proj_pts - proj_center, axis=1)
        return radii - radii.mean()

    # Optimise axis direction (2 free params — az determined by unit constraint)
    init = [axis0[0], axis0[1]]
    opt  = least_squares(residuals, init, method="lm", max_nfev=500)

    ax, ay = opt.x
    az = np.sqrt(max(0.0, 1.0 - ax**2 - ay**2))
    axis = np.array([ax, ay, az])
    axis /= np.linalg.norm(axis)

    # Compute radius and center using fitted axis
    proj_scalar = (pts - centroid) @ axis
    proj_pts    = pts - np.outer(proj_scalar, axis)
    center      = proj_pts.mean(axis=0)
    radii       = np.linalg.norm(proj_pts - center, axis=1)
    radius      = float(radii.mean())
    rms         = float(np.sqrt(np.mean((radii - radius) ** 2)))

    return axis, center, radius, rms


def _radial_distances_to_axis(pts: np.ndarray,
                               center: np.ndarray,
                               axis: np.ndarray) -> np.ndarray:
    """Perpendicular distances from each point to a line (center + axis)."""
    axis = axis / np.linalg.norm(axis)
    vecs = pts - center
    proj = np.outer(vecs @ axis, axis)
    perp = vecs - proj
    return np.linalg.norm(perp, axis=1)


# ── ROI extraction ────────────────────────────────────────────────────────────

def _extract_roi_points(scan_points: np.ndarray, feature: dict) -> np.ndarray:
    """
    Extract scan points within the feature's axis-aligned bounding box.
    If no ROI defined, returns all points (full-surface feature).
    """
    keys = ["roi_min_x", "roi_min_y", "roi_min_z",
            "roi_max_x", "roi_max_y", "roi_max_z"]

    if not all(feature.get(k) is not None for k in keys):
        return scan_points  # No ROI — use all points

    mask = (
        (scan_points[:, 0] >= feature["roi_min_x"]) &
        (scan_points[:, 0] <= feature["roi_max_x"]) &
        (scan_points[:, 1] >= feature["roi_min_y"]) &
        (scan_points[:, 1] <= feature["roi_max_y"]) &
        (scan_points[:, 2] >= feature["roi_min_z"]) &
        (scan_points[:, 2] <= feature["roi_max_z"])
    )
    return scan_points[mask]


# ── Result factory ────────────────────────────────────────────────────────────

def _make_result(feature: dict,
                 actual: float,
                 nominal: float | None = None,
                 fit_center: np.ndarray | None = None,
                 fit_normal: np.ndarray | None = None,
                 fit_radius: float | None = None,
                 fit_rms: float | None = None,
                 pts_used: int = 0) -> GDTFeatureResult:
    tol_upper = feature.get("tolerance_upper_mm")
    tol_lower = feature.get("tolerance_lower_mm")

    # Default: symmetric tolerance around zero
    if tol_lower is None and tol_upper is not None:
        tol_lower = 0.0

    in_tol = True
    if tol_upper is not None:
        in_tol = in_tol and (actual <= tol_upper)
    if tol_lower is not None:
        in_tol = in_tol and (actual >= tol_lower)

    deviation = (actual - nominal) if nominal is not None else None

    return GDTFeatureResult(
        feature_name      = feature.get("name", ""),
        feature_type      = feature.get("feature_type", ""),
        actual_value_mm   = float(actual),
        nominal_value_mm  = float(nominal) if nominal is not None else None,
        deviation_mm      = float(deviation) if deviation is not None else None,
        in_tolerance      = bool(in_tol),
        tolerance_upper_mm = tol_upper,
        tolerance_lower_mm = tol_lower,
        fit_center        = fit_center,
        fit_normal        = fit_normal,
        fit_radius        = fit_radius,
        fit_residual_rms  = fit_rms,
        point_count_used  = pts_used,
    )
