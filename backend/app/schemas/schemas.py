"""
app/schemas/schemas.py
Pydantic v2 schemas for all API request bodies and responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from app.models.models import (
    AlignmentMethod,
    AnalysisType,
    GDTFeatureType,
    JobStatus,
    ProjectStatus,
)


# ── Shared config ─────────────────────────────────────────────────────────────

class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    part_number: str | None = Field(None, max_length=100)
    revision: str | None    = Field(None, max_length=20)


class ProjectUpdate(BaseModel):
    name: str | None        = Field(None, min_length=1, max_length=255)
    description: str | None = None
    part_number: str | None = None
    revision: str | None    = None


class ProjectOut(ORMBase):
    id: uuid.UUID
    name: str
    description: str | None
    part_number: str | None
    revision: str | None
    status: ProjectStatus
    created_at: datetime | None
    updated_at: datetime | None

    # Summarised child info (avoids full nested models on list endpoints)
    has_cad: bool   = False
    has_scan: bool  = False
    has_alignment: bool = False


class ProjectListOut(ORMBase):
    items: list[ProjectOut]
    total: int


# ── CAD Model ─────────────────────────────────────────────────────────────────

class CADModelOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    file_format: str
    file_size_bytes: int
    vertex_count: int | None
    face_count: int | None
    is_watertight: bool | None
    bbox_min_x: float | None
    bbox_min_y: float | None
    bbox_min_z: float | None
    bbox_max_x: float | None
    bbox_max_y: float | None
    bbox_max_z: float | None
    repair_log: str | None
    is_processed: bool
    uploaded_at: datetime


# ── Scan Cloud ────────────────────────────────────────────────────────────────

class ScanCloudOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    file_format: str
    file_size_bytes: int
    point_count: int | None
    has_normals: bool | None
    has_intensity: bool | None
    has_rgb: bool | None
    bbox_min_x: float | None
    bbox_min_y: float | None
    bbox_min_z: float | None
    bbox_max_x: float | None
    bbox_max_y: float | None
    bbox_max_z: float | None
    units: str | None
    is_processed: bool
    uploaded_at: datetime


# ── Alignment ─────────────────────────────────────────────────────────────────

class AlignmentRequest(BaseModel):
    method: AlignmentMethod = AlignmentMethod.ICP
    # Optional: user supplies manual 4×4 matrix (flat list of 16 floats)
    manual_matrix: list[float] | None = Field(None, min_length=16, max_length=16)
    # Optional datum constraints
    datum_constraints: dict[str, Any] | None = None
    # ICP tuning overrides
    max_correspondence_dist_mm: float | None = None
    max_iterations: int | None = None


class AlignmentOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    method: AlignmentMethod
    transform_matrix: str    # 16 floats, comma-separated
    inlier_rmse_mm: float | None
    fitness_score: float | None
    inlier_count: int | None
    iteration_count: int | None
    datum_constraints: str | None
    created_at: datetime | None


# ── Analysis Job ──────────────────────────────────────────────────────────────

class AnalysisJobOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    analysis_type: AnalysisType
    status: JobStatus
    celery_task_id: str | None
    progress_pct: int
    progress_msg: str | None
    error_message: str | None
    parameters: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime | None


# ── Deviation ─────────────────────────────────────────────────────────────────

class DeviationRequest(BaseModel):
    scale_min_mm: float | None = None   # clamp heatmap scale manually
    scale_max_mm: float | None = None
    downsample_to: int = Field(500_000, ge=1000, le=5_000_000)


class DeviationStats(BaseModel):
    min_mm: float
    max_mm: float
    mean_mm: float
    rms_mm: float
    p95_mm: float
    p99_mm: float
    point_count: int
    scale_min_mm: float
    scale_max_mm: float


class DeviationPointsOut(BaseModel):
    """
    Compact columnar format for frontend Three.js rendering.
    Positions and deviations in parallel arrays — avoids JSON object overhead.
    """
    x: list[float]
    y: list[float]
    z: list[float]
    deviation_mm: list[float]
    stats: DeviationStats


# ── GD&T ─────────────────────────────────────────────────────────────────────

class GDTFeatureCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    feature_type: GDTFeatureType
    nominal_x: float | None = None
    nominal_y: float | None = None
    nominal_z: float | None = None
    nominal_diameter: float | None = None
    roi_min_x: float | None = None
    roi_min_y: float | None = None
    roi_min_z: float | None = None
    roi_max_x: float | None = None
    roi_max_y: float | None = None
    roi_max_z: float | None = None
    primary_datum: str | None   = Field(None, max_length=10)
    secondary_datum: str | None = Field(None, max_length=10)
    tertiary_datum: str | None  = Field(None, max_length=10)
    tolerance_upper_mm: float | None = None
    tolerance_lower_mm: float | None = None


class GDTFeatureOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    feature_type: GDTFeatureType
    nominal_x: float | None
    nominal_y: float | None
    nominal_z: float | None
    nominal_diameter: float | None
    roi_min_x: float | None
    roi_min_y: float | None
    roi_min_z: float | None
    roi_max_x: float | None
    roi_max_y: float | None
    roi_max_z: float | None
    primary_datum: str | None
    secondary_datum: str | None
    tertiary_datum: str | None
    tolerance_upper_mm: float | None
    tolerance_lower_mm: float | None
    created_at: datetime | None


class GDTResultOut(ORMBase):
    id: uuid.UUID
    project_id: uuid.UUID
    feature_id: uuid.UUID
    job_id: uuid.UUID
    actual_value_mm: float
    nominal_value_mm: float | None
    deviation_mm: float | None
    in_tolerance: bool
    fit_center_x: float | None
    fit_center_y: float | None
    fit_center_z: float | None
    fit_normal_x: float | None
    fit_normal_y: float | None
    fit_normal_z: float | None
    fit_radius: float | None
    fit_residual_rms: float | None
    point_count_used: int | None
    created_at: datetime | None

    # Denormalised feature info for convenience
    feature_name: str | None = None
    feature_type: GDTFeatureType | None = None
    tolerance_upper_mm: float | None = None
    tolerance_lower_mm: float | None = None


class GDTRunRequest(BaseModel):
    feature_ids: list[uuid.UUID] | None = None  # None → run all features


# ── Wall Thickness ────────────────────────────────────────────────────────────

class WallThicknessRequest(BaseModel):
    sample_count: int = Field(20_000, ge=100, le=200_000)


class WallThicknessStats(BaseModel):
    min_mm: float
    max_mm: float
    mean_mm: float
    std_mm: float
    sample_count: int


class WallThicknessOut(BaseModel):
    x: list[float]
    y: list[float]
    z: list[float]
    thickness_mm: list[float]
    stats: WallThicknessStats


# ── Generic responses ─────────────────────────────────────────────────────────

class MessageOut(BaseModel):
    message: str


class JobStartedOut(BaseModel):
    job_id: uuid.UUID
    status: JobStatus = JobStatus.QUEUED
    message: str
