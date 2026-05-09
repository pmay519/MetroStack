"""
app/models/models.py
SQLAlchemy ORM models.  Mirror the schema from the design doc —
PostGIS geometry columns stored as TEXT (WKT) at the ORM layer;
raw SQL handles ST_* operations directly via text() queries.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Double,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    BigInteger,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


# ── Enumerations ──────────────────────────────────────────────────────────────

class ProjectStatus(str, PyEnum):
    PENDING    = "pending"
    READY      = "ready"       # both CAD + scan uploaded
    ALIGNED    = "aligned"     # alignment completed
    ANALYZED   = "analyzed"    # at least one analysis run
    ERROR      = "error"


class JobStatus(str, PyEnum):
    QUEUED     = "queued"
    RUNNING    = "running"
    COMPLETE   = "complete"
    FAILED     = "failed"


class AnalysisType(str, PyEnum):
    DEVIATION       = "deviation"
    GDT             = "gdt"
    WALL_THICKNESS  = "wall_thickness"
    CROSS_SECTION   = "cross_section"


class GDTFeatureType(str, PyEnum):
    FLATNESS        = "flatness"
    STRAIGHTNESS    = "straightness"
    CIRCULARITY     = "circularity"
    CYLINDRICITY    = "cylindricity"
    POSITION        = "position"
    PARALLELISM     = "parallelism"
    PERPENDICULARITY = "perpendicularity"
    ANGULARITY      = "angularity"
    PROFILE_SURFACE = "profile_surface"
    RUNOUT          = "runout"
    TOTAL_RUNOUT    = "total_runout"


class AlignmentMethod(str, PyEnum):
    ICP             = "icp"           # Iterative Closest Point (best-fit)
    FGR             = "fgr"           # Fast Global Registration (coarse)
    DATUM_LOCKED    = "datum_locked"  # Constrained to DRF
    MANUAL          = "manual"        # User-supplied 4×4 matrix


# ── Project ───────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str]         = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    part_number: Mapped[str | None] = mapped_column(String(100))
    revision: Mapped[str | None]    = mapped_column(String(20))
    status: Mapped[ProjectStatus]   = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    cad_model:        Mapped["CADModel | None"]       = relationship(back_populates="project", uselist=False)
    scan_cloud:       Mapped["ScanCloud | None"]      = relationship(back_populates="project", uselist=False)
    alignment:        Mapped["Alignment | None"]      = relationship(back_populates="project", uselist=False)
    analysis_jobs:    Mapped[list["AnalysisJob"]]     = relationship(back_populates="project")
    gdt_features:     Mapped[list["GDTFeature"]]      = relationship(back_populates="project")
    gdt_results:      Mapped[list["GDTResult"]]       = relationship(back_populates="project")
    wall_thickness:   Mapped[list["WallThicknessSample"]] = relationship(back_populates="project")


# ── CAD Model ─────────────────────────────────────────────────────────────────

class CADModel(Base):
    __tablename__ = "cad_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    filename: Mapped[str]      = mapped_column(String(512))
    file_path: Mapped[str]     = mapped_column(String(1024))  # server filesystem path
    file_format: Mapped[str]   = mapped_column(String(20))    # stl | obj | ply | step | iges
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Mesh statistics
    vertex_count: Mapped[int | None]   = mapped_column(Integer)
    face_count: Mapped[int | None]     = mapped_column(Integer)
    is_watertight: Mapped[bool | None] = mapped_column(Boolean)

    # Bounding box (stored as JSON-serializable floats)
    bbox_min_x: Mapped[float | None] = mapped_column(Double)
    bbox_min_y: Mapped[float | None] = mapped_column(Double)
    bbox_min_z: Mapped[float | None] = mapped_column(Double)
    bbox_max_x: Mapped[float | None] = mapped_column(Double)
    bbox_max_y: Mapped[float | None] = mapped_column(Double)
    bbox_max_z: Mapped[float | None] = mapped_column(Double)

    # Mesh repair log
    repair_log: Mapped[str | None] = mapped_column(Text)
    is_processed: Mapped[bool]     = mapped_column(Boolean, default=False)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="cad_model")


# ── Scan Point Cloud ──────────────────────────────────────────────────────────

class ScanCloud(Base):
    __tablename__ = "scan_clouds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    filename: Mapped[str]    = mapped_column(String(512))
    file_path: Mapped[str]   = mapped_column(String(1024))
    file_format: Mapped[str] = mapped_column(String(20))  # e57 | ply | pcd | xyz | las | laz | csv
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    # Cloud statistics
    point_count: Mapped[int | None]     = mapped_column(BigInteger)
    has_normals: Mapped[bool | None]    = mapped_column(Boolean)
    has_intensity: Mapped[bool | None]  = mapped_column(Boolean)
    has_rgb: Mapped[bool | None]        = mapped_column(Boolean)

    # Bounding box
    bbox_min_x: Mapped[float | None] = mapped_column(Double)
    bbox_min_y: Mapped[float | None] = mapped_column(Double)
    bbox_min_z: Mapped[float | None] = mapped_column(Double)
    bbox_max_x: Mapped[float | None] = mapped_column(Double)
    bbox_max_y: Mapped[float | None] = mapped_column(Double)
    bbox_max_z: Mapped[float | None] = mapped_column(Double)

    # Units detected from file header
    units: Mapped[str | None] = mapped_column(String(20))  # mm | m | inch

    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="scan_cloud")


# ── Alignment ─────────────────────────────────────────────────────────────────

class Alignment(Base):
    """
    Stores the 4×4 rigid-body transformation matrix (row-major, 16 floats)
    that maps the scan point cloud into the CAD coordinate frame.
    """
    __tablename__ = "alignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), unique=True)

    method: Mapped[AlignmentMethod] = mapped_column(Enum(AlignmentMethod))

    # 4×4 transform stored as 16 comma-separated doubles
    transform_matrix: Mapped[str] = mapped_column(Text)  # "1.0,0.0,...,1.0"

    # Quality metrics
    inlier_rmse_mm: Mapped[float | None]  = mapped_column(Double)
    fitness_score: Mapped[float | None]   = mapped_column(Double)  # 0.0 – 1.0
    inlier_count: Mapped[int | None]      = mapped_column(Integer)
    iteration_count: Mapped[int | None]   = mapped_column(Integer)

    # Datum constraints used (JSON text: {"A": [nx,ny,nz], "B": ...})
    datum_constraints: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="alignment")

    def get_matrix_numpy(self):
        """Deserialize stored matrix back to 4×4 numpy array."""
        import numpy as np
        vals = [float(v) for v in self.transform_matrix.split(",")]
        return np.array(vals).reshape(4, 4)

    @classmethod
    def matrix_to_str(cls, matrix) -> str:
        """Serialize 4×4 numpy array to storable string."""
        return ",".join(f"{v:.10f}" for v in matrix.flatten())


# ── Analysis Job ──────────────────────────────────────────────────────────────

class AnalysisJob(Base):
    """
    Tracks background analysis tasks (Celery jobs).
    Frontend polls this to show progress.
    """
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    analysis_type: Mapped[AnalysisType] = mapped_column(Enum(AnalysisType))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))

    progress_pct: Mapped[int]      = mapped_column(Integer, default=0)   # 0–100
    progress_msg: Mapped[str | None] = mapped_column(String(512))
    error_message: Mapped[str | None] = mapped_column(Text)

    # Parameters used for this run (JSON)
    parameters: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None]  = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]         = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="analysis_jobs")


# ── Deviation Results (summary + sampled points) ──────────────────────────────

class DeviationSummary(Base):
    """
    Aggregate statistics per analysis run — fast to query for dashboard.
    Full point-level data lives in the PostgreSQL COPY-loaded deviation_points
    table (managed outside ORM for bulk performance).
    """
    __tablename__ = "deviation_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID]     = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"))

    point_count: Mapped[int]       = mapped_column(BigInteger)
    dev_min_mm: Mapped[float]      = mapped_column(Double)
    dev_max_mm: Mapped[float]      = mapped_column(Double)
    dev_mean_mm: Mapped[float]     = mapped_column(Double)
    dev_rms_mm: Mapped[float]      = mapped_column(Double)
    dev_p95_mm: Mapped[float]      = mapped_column(Double)  # 95th percentile abs
    dev_p99_mm: Mapped[float]      = mapped_column(Double)

    # Colour scale bounds used for heatmap (may be clamped)
    scale_min_mm: Mapped[float | None] = mapped_column(Double)
    scale_max_mm: Mapped[float | None] = mapped_column(Double)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── GD&T Feature Definitions ──────────────────────────────────────────────────

class GDTFeature(Base):
    """
    User-defined GD&T callout to evaluate.
    Each feature references a region of the scan cloud by bounding box
    or a named datum.
    """
    __tablename__ = "gdt_features"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    name: Mapped[str]               = mapped_column(String(255))
    feature_type: Mapped[GDTFeatureType] = mapped_column(Enum(GDTFeatureType))

    # Nominal geometry (optional — used for position/angularity)
    nominal_x: Mapped[float | None] = mapped_column(Double)
    nominal_y: Mapped[float | None] = mapped_column(Double)
    nominal_z: Mapped[float | None] = mapped_column(Double)
    nominal_diameter: Mapped[float | None] = mapped_column(Double)

    # Region of interest (axis-aligned bounding box to extract scan points)
    roi_min_x: Mapped[float | None] = mapped_column(Double)
    roi_min_y: Mapped[float | None] = mapped_column(Double)
    roi_min_z: Mapped[float | None] = mapped_column(Double)
    roi_max_x: Mapped[float | None] = mapped_column(Double)
    roi_max_y: Mapped[float | None] = mapped_column(Double)
    roi_max_z: Mapped[float | None] = mapped_column(Double)

    # Datum reference frame
    primary_datum: Mapped[str | None]   = mapped_column(String(10))   # "A"
    secondary_datum: Mapped[str | None] = mapped_column(String(10))   # "B"
    tertiary_datum: Mapped[str | None]  = mapped_column(String(10))   # "C"

    # Tolerances
    tolerance_upper_mm: Mapped[float | None] = mapped_column(Double)
    tolerance_lower_mm: Mapped[float | None] = mapped_column(Double)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"]         = relationship(back_populates="gdt_features")
    results: Mapped[list["GDTResult"]] = relationship(back_populates="feature")


# ── GD&T Results ──────────────────────────────────────────────────────────────

class GDTResult(Base):
    __tablename__ = "gdt_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID]  = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    feature_id: Mapped[uuid.UUID]  = mapped_column(ForeignKey("gdt_features.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID]      = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"))

    actual_value_mm: Mapped[float]  = mapped_column(Double)
    nominal_value_mm: Mapped[float | None] = mapped_column(Double)
    deviation_mm: Mapped[float | None]     = mapped_column(Double)
    in_tolerance: Mapped[bool]             = mapped_column(Boolean)

    # Best-fit geometry results
    fit_center_x: Mapped[float | None] = mapped_column(Double)
    fit_center_y: Mapped[float | None] = mapped_column(Double)
    fit_center_z: Mapped[float | None] = mapped_column(Double)
    fit_normal_x: Mapped[float | None] = mapped_column(Double)
    fit_normal_y: Mapped[float | None] = mapped_column(Double)
    fit_normal_z: Mapped[float | None] = mapped_column(Double)
    fit_radius: Mapped[float | None]   = mapped_column(Double)
    fit_residual_rms: Mapped[float | None] = mapped_column(Double)

    point_count_used: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"]  = relationship(back_populates="gdt_results")
    feature: Mapped["GDTFeature"] = relationship(back_populates="results")


# ── Wall Thickness Samples ────────────────────────────────────────────────────

class WallThicknessSample(Base):
    """
    Individual ray-cast thickness measurements.
    Bulk-inserted — one row per sample point.
    """
    __tablename__ = "wall_thickness_samples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID]     = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"))

    sample_x: Mapped[float]     = mapped_column(Double)
    sample_y: Mapped[float]     = mapped_column(Double)
    sample_z: Mapped[float]     = mapped_column(Double)
    thickness_mm: Mapped[float] = mapped_column(Double)

    # Normal direction of the ray
    normal_x: Mapped[float | None] = mapped_column(Double)
    normal_y: Mapped[float | None] = mapped_column(Double)
    normal_z: Mapped[float | None] = mapped_column(Double)

    project: Mapped["Project"] = relationship(back_populates="wall_thickness")
