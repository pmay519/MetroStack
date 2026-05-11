"""
app/api/routes/analysis.py
All metrology analysis endpoints — alignment, deviation, GD&T, wall thickness.
Heavy compute runs as background tasks; status polled via /jobs/{job_id}.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, AsyncSessionLocal
from app.models.models import (
    Alignment, AlignmentMethod, AnalysisJob, AnalysisType,
    CADModel, DeviationSummary, GDTFeature, GDTResult,
    JobStatus, Project, ProjectStatus, ScanCloud,
    WallThicknessSample,
)
from app.schemas.schemas import (
    AlignmentOut, AlignmentRequest,
    AnalysisJobOut, DeviationRequest, DeviationPointsOut, DeviationStats,
    GDTFeatureCreate, GDTFeatureOut, GDTResultOut, GDTRunRequest,
    JobStartedOut, MessageOut,
    WallThicknessRequest, WallThicknessOut, WallThicknessStats,
)
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}", tags=["Analysis"])


# ═══════════════════════════════════════════════════════════════════════════════
# ALIGNMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/align", response_model=JobStartedOut, status_code=status.HTTP_202_ACCEPTED)
async def run_alignment(project_id: uuid.UUID,
                        payload: AlignmentRequest,
                        background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db)) -> JobStartedOut:
    """
    Trigger alignment of the scan cloud to the CAD mesh.
    Returns immediately; poll /jobs/{job_id} for progress.
    """
    project = await _ready_project_or_error(db, project_id)

    job = AnalysisJob(
        project_id    = project_id,
        analysis_type = AnalysisType.DEVIATION,  # alignment is pre-step
        status        = JobStatus.QUEUED,
        parameters    = json.dumps(payload.model_dump()),
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    background_tasks.add_task(
        _alignment_task,
        str(project_id),
        str(job.id),
        payload.model_dump(),
    )

    return JobStartedOut(job_id=job.id, message="Alignment queued.")


@router.get("/alignment", response_model=AlignmentOut)
async def get_alignment(project_id: uuid.UUID,
                        db: AsyncSession = Depends(get_db)) -> AlignmentOut:
    result = await db.execute(
        select(Alignment).where(Alignment.project_id == project_id)
    )
    alignment = result.scalar_one_or_none()
    if alignment is None:
        raise HTTPException(404, "No alignment found — run /align first.")
    return _alignment_to_out(alignment)


# ═══════════════════════════════════════════════════════════════════════════════
# DEVIATION ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze/deviation",
             response_model=JobStartedOut,
             status_code=status.HTTP_202_ACCEPTED)
async def run_deviation(project_id: uuid.UUID,
                        payload: DeviationRequest,
                        background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db)) -> JobStartedOut:
    """Start a full point-to-CAD deviation analysis job."""
    await _aligned_project_or_error(db, project_id)

    job = AnalysisJob(
        project_id    = project_id,
        analysis_type = AnalysisType.DEVIATION,
        status        = JobStatus.QUEUED,
        parameters    = json.dumps(payload.model_dump()),
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    background_tasks.add_task(
        _deviation_task,
        str(project_id),
        str(job.id),
        payload.model_dump(),
    )

    return JobStartedOut(job_id=job.id, message="Deviation analysis queued.")


@router.get("/results/deviation", response_model=DeviationPointsOut)
async def get_deviation_results(project_id: uuid.UUID,
                                downsample_to: int = 500_000,
                                db: AsyncSession = Depends(get_db)) -> DeviationPointsOut:
    """
    Return deviation point cloud for frontend heatmap rendering.
    Automatically downsampled to `downsample_to` points for performance.
    """
    # Get latest summary for this project
    summary_q = await db.execute(
        select(DeviationSummary)
        .where(DeviationSummary.project_id == project_id)
        .order_by(DeviationSummary.created_at.desc())
        .limit(1)
    )
    summary = summary_q.scalar_one_or_none()
    if summary is None:
        raise HTTPException(404, "No deviation results found — run analysis first.")

    # Query raw point data from bulk table
    # Use raw SQL for performance on millions of rows
    from sqlalchemy import text
    raw_sql = text("""
        SELECT pt_x, pt_y, pt_z, deviation_mm
        FROM deviation_points
        WHERE project_id = :pid
        ORDER BY RANDOM()
        LIMIT :lim
    """)
    rows = await db.execute(raw_sql, {"pid": str(project_id), "lim": downsample_to})
    data = rows.fetchall()

    if not data:
        raise HTTPException(404, "Deviation point data not found.")

    xs   = [r[0] for r in data]
    ys   = [r[1] for r in data]
    zs   = [r[2] for r in data]
    devs = [r[3] for r in data]

    scale_min = summary.scale_min_mm if summary.scale_min_mm else summary.dev_min_mm
    scale_max = summary.scale_max_mm if summary.scale_max_mm else summary.dev_max_mm

    return DeviationPointsOut(
        x=xs, y=ys, z=zs, deviation_mm=devs,
        stats=DeviationStats(
            min_mm      = summary.dev_min_mm,
            max_mm      = summary.dev_max_mm,
            mean_mm     = summary.dev_mean_mm,
            rms_mm      = summary.dev_rms_mm,
            p95_mm      = summary.dev_p95_mm,
            p99_mm      = summary.dev_p99_mm,
            point_count = summary.point_count,
            scale_min_mm = scale_min,
            scale_max_mm = scale_max,
        )
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GD&T
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/gdt/features",
             response_model=GDTFeatureOut,
             status_code=status.HTTP_201_CREATED)
async def create_gdt_feature(project_id: uuid.UUID,
                              payload: GDTFeatureCreate,
                              db: AsyncSession = Depends(get_db)) -> GDTFeatureOut:
    """Define a GD&T feature callout to be evaluated during analysis."""
    project = await _get_project_or_404(db, project_id)

    feature = GDTFeature(project_id=project_id, **payload.model_dump())
    db.add(feature)
    await db.flush()
    await db.refresh(feature)
    return _gdt_feature_to_out(feature)


@router.get("/gdt/features", response_model=list[GDTFeatureOut])
async def list_gdt_features(project_id: uuid.UUID,
                             db: AsyncSession = Depends(get_db)) -> list[GDTFeatureOut]:
    result = await db.execute(
        select(GDTFeature).where(GDTFeature.project_id == project_id)
    )
    return [_gdt_feature_to_out(f) for f in result.scalars().all()]


@router.delete("/gdt/features/{feature_id}", response_model=MessageOut)
async def delete_gdt_feature(project_id: uuid.UUID,
                              feature_id: uuid.UUID,
                              db: AsyncSession = Depends(get_db)) -> MessageOut:
    result = await db.execute(
        select(GDTFeature)
        .where(GDTFeature.id == feature_id, GDTFeature.project_id == project_id)
    )
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(404, "Feature not found.")
    name = feature.name
    await db.delete(feature)
    return MessageOut(message=f"Feature '{name}' deleted.")


@router.post("/analyze/gdt",
             response_model=JobStartedOut,
             status_code=status.HTTP_202_ACCEPTED)
async def run_gdt_analysis(project_id: uuid.UUID,
                            payload: GDTRunRequest,
                            background_tasks: BackgroundTasks,
                            db: AsyncSession = Depends(get_db)) -> JobStartedOut:
    """Run GD&T analysis for all (or specified) features."""
    await _aligned_project_or_error(db, project_id)

    job = AnalysisJob(
        project_id    = project_id,
        analysis_type = AnalysisType.GDT,
        status        = JobStatus.QUEUED,
        parameters    = json.dumps({
            "feature_ids": [str(fid) for fid in (payload.feature_ids or [])]
        }),
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    background_tasks.add_task(
        _gdt_task,
        str(project_id),
        str(job.id),
        [str(fid) for fid in (payload.feature_ids or [])],
    )

    return JobStartedOut(job_id=job.id, message="GD&T analysis queued.")


@router.get("/results/gdt", response_model=list[GDTResultOut])
async def get_gdt_results(project_id: uuid.UUID,
                           db: AsyncSession = Depends(get_db)) -> list[GDTResultOut]:
    """Return latest GD&T results for all features."""
    result = await db.execute(
        select(GDTResult, GDTFeature)
        .join(GDTFeature, GDTResult.feature_id == GDTFeature.id)
        .where(GDTResult.project_id == project_id)
        .order_by(GDTResult.created_at.desc())
    )
    rows = result.all()

    seen_features = set()
    out = []
    for gdt_result, feature in rows:
        if gdt_result.feature_id in seen_features:
            continue   # only latest result per feature
        seen_features.add(gdt_result.feature_id)
        out.append(_gdt_result_to_out(gdt_result, feature))
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# WALL THICKNESS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze/wall-thickness",
             response_model=JobStartedOut,
             status_code=status.HTTP_202_ACCEPTED)
async def run_wall_thickness(project_id: uuid.UUID,
                              payload: WallThicknessRequest,
                              background_tasks: BackgroundTasks,
                              db: AsyncSession = Depends(get_db)) -> JobStartedOut:
    """Ray-cast wall thickness analysis on the CAD mesh."""
    project = await _get_project_or_404(db, project_id)
    if not project.cad_model or not project.cad_model.is_processed:
        raise HTTPException(400, "CAD model not ready — upload and wait for processing.")

    job = AnalysisJob(
        project_id    = project_id,
        analysis_type = AnalysisType.WALL_THICKNESS,
        status        = JobStatus.QUEUED,
        parameters    = json.dumps(payload.model_dump()),
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    background_tasks.add_task(
        _wall_thickness_task,
        str(project_id),
        str(job.id),
        payload.model_dump(),
    )

    return JobStartedOut(job_id=job.id, message="Wall thickness analysis queued.")


@router.get("/results/wall-thickness", response_model=WallThicknessOut)
async def get_wall_thickness_results(project_id: uuid.UUID,
                                      downsample_to: int = 50_000,
                                      db: AsyncSession = Depends(get_db)) -> WallThicknessOut:
    """Return wall thickness point cloud for frontend heatmap."""
    from sqlalchemy import func as sqlfunc

    # Get latest job id for wall thickness
    job_q = await db.execute(
        select(AnalysisJob)
        .where(
            AnalysisJob.project_id == project_id,
            AnalysisJob.analysis_type == AnalysisType.WALL_THICKNESS,
            AnalysisJob.status == JobStatus.COMPLETE,
        )
        .order_by(AnalysisJob.created_at.desc())
        .limit(1)
    )
    job = job_q.scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "No wall thickness results — run analysis first.")

    from sqlalchemy import text
    rows_q = await db.execute(text("""
        SELECT sample_x, sample_y, sample_z, thickness_mm
        FROM wall_thickness_samples
        WHERE project_id = :pid AND job_id = :jid
        ORDER BY RANDOM()
        LIMIT :lim
    """), {"pid": str(project_id), "jid": str(job.id), "lim": downsample_to})

    rows = rows_q.fetchall()
    if not rows:
        raise HTTPException(404, "Wall thickness point data not found.")

    xs   = [r[0] for r in rows]
    ys   = [r[1] for r in rows]
    zs   = [r[2] for r in rows]
    thks = [r[3] for r in rows]

    # Stats from full dataset
    stats_q = await db.execute(text("""
        SELECT
            MIN(thickness_mm), MAX(thickness_mm),
            AVG(thickness_mm), STDDEV(thickness_mm),
            COUNT(*)
        FROM wall_thickness_samples
        WHERE project_id = :pid AND job_id = :jid
    """), {"pid": str(project_id), "jid": str(job.id)})
    s = stats_q.fetchone()

    return WallThicknessOut(
        x=xs, y=ys, z=zs, thickness_mm=thks,
        stats=WallThicknessStats(
            min_mm       = s[0],
            max_mm       = s[1],
            mean_mm      = s[2],
            std_mm       = s[3],
            sample_count = s[4],
        )
    )


# ═══════════════════════════════════════════════════════════════════════════════
# JOB STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/jobs", response_model=list[AnalysisJobOut])
async def list_jobs(project_id: uuid.UUID,
                    db: AsyncSession = Depends(get_db)) -> list[AnalysisJobOut]:
    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == project_id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(50)
    )
    return [_job_to_out(j) for j in result.scalars().all()]


@router.get("/jobs/{job_id}", response_model=AnalysisJobOut)
async def get_job(project_id: uuid.UUID,
                  job_id: uuid.UUID,
                  db: AsyncSession = Depends(get_db)) -> AnalysisJobOut:
    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.id == job_id, AnalysisJob.project_id == project_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "Job not found.")
    return _job_to_out(job)


# ═══════════════════════════════════════════════════════════════════════════════
# BACKGROUND TASK IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def _alignment_task(project_id: str, job_id: str, params: dict) -> None:
    loop = asyncio.get_event_loop()

    async with AsyncSessionLocal() as db:
        await _update_job(db, job_id, JobStatus.RUNNING, 0, "Loading files...")

    try:
        # Load files
        cad_path, scan_path, _ = await _load_project_files(project_id)

        from app.services.ingest import load_cad_mesh, load_point_cloud
        from app.services.alignment import align_icp, align_datum_constrained

        mesh_info  = await loop.run_in_executor(None, load_cad_mesh, cad_path)
        cloud_info = await loop.run_in_executor(None, load_point_cloud, scan_path)

        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 30, "Running alignment...")

        method = params.get("method", AlignmentMethod.ICP)
        init_transform = None

        if params.get("manual_matrix"):
            import numpy as np
            init_transform = np.array(params["manual_matrix"]).reshape(4, 4)

        if method == AlignmentMethod.DATUM_LOCKED and params.get("datum_constraints"):
            align_result = await loop.run_in_executor(
                None,
                align_datum_constrained,
                cloud_info.cloud,
                mesh_info.mesh,
                params["datum_constraints"],
                None,
            )
        else:
            max_dist = params.get("max_correspondence_dist_mm",
                                   settings.ICP_MAX_CORRESPONDENCE_DIST_MM)
            max_iter = params.get("max_iterations", settings.ICP_MAX_ITERATIONS)

            from functools import partial
            fn = partial(
                align_icp,
                cloud_info.cloud,
                mesh_info.mesh,
                init_transform,
                max_dist,
                max_iter,
            )
            align_result = await loop.run_in_executor(None, fn)

        # Save alignment to DB
        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 90, "Saving alignment...")

            # Remove old alignment if exists
            old_q = await db.execute(
                select(Alignment).where(Alignment.project_id == uuid.UUID(project_id))
            )
            old = old_q.scalar_one_or_none()
            if old:
                await db.delete(old)
                await db.flush()

            alignment = Alignment(
                project_id       = uuid.UUID(project_id),
                method           = align_result.method_used,
                transform_matrix = Alignment.matrix_to_str(align_result.transform),
                inlier_rmse_mm   = align_result.inlier_rmse_mm,
                fitness_score    = align_result.fitness_score,
                inlier_count     = align_result.inlier_count,
                iteration_count  = align_result.iteration_count,
                datum_constraints = json.dumps(params.get("datum_constraints") or {}),
            )
            db.add(alignment)

            # Update project status
            proj_q = await db.execute(
                select(Project).where(Project.id == uuid.UUID(project_id))
            )
            proj = proj_q.scalar_one_or_none()
            if proj:
                proj.status = ProjectStatus.ALIGNED

            await _update_job(db, job_id, JobStatus.COMPLETE, 100, "Alignment complete.")
            await db.commit()

    except Exception as exc:
        logger.exception(f"Alignment task failed: {exc}")
        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.FAILED, 0,
                              f"Alignment failed: {exc}", error=str(exc))


async def _deviation_task(project_id: str, job_id: str, params: dict) -> None:
    loop = asyncio.get_event_loop()

    try:
        cad_path, scan_path, transform = await _load_project_files_with_alignment(project_id)

        from app.services.ingest import load_cad_mesh, load_point_cloud
        from app.services.deviation import (
            compute_deviation, downsample_for_display,
            compute_heatmap_scale, bulk_insert_deviation_points
        )

        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 10, "Loading files...")

        mesh_info  = await loop.run_in_executor(None, load_cad_mesh, cad_path)
        cloud_info = await loop.run_in_executor(None, load_point_cloud, scan_path)

        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 30, "Computing deviation...")

        from functools import partial
        dev_fn = partial(compute_deviation, cloud_info.cloud, mesh_info.mesh, transform)
        dev_result = await loop.run_in_executor(None, dev_fn)

        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 80, "Storing results...")

        # Bulk insert using raw asyncpg connection for COPY performance
        import asyncpg
        from app.core.config import settings
        conn_str = (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
        raw_conn = await asyncpg.connect(conn_str)
        try:
            await bulk_insert_deviation_points(
                raw_conn, project_id, job_id, dev_result,
                batch_size=settings.DEVIATION_BATCH_SIZE
            )
        finally:
            await raw_conn.close()

        # Save summary
        scale_min, scale_max = compute_heatmap_scale(dev_result.deviations_mm)
        async with AsyncSessionLocal() as db:
            summary = DeviationSummary(
                project_id   = uuid.UUID(project_id),
                job_id       = uuid.UUID(job_id),
                point_count  = dev_result.stats["point_count"],
                dev_min_mm   = dev_result.stats["min_mm"],
                dev_max_mm   = dev_result.stats["max_mm"],
                dev_mean_mm  = dev_result.stats["mean_mm"],
                dev_rms_mm   = dev_result.stats["rms_mm"],
                dev_p95_mm   = dev_result.stats["p95_mm"],
                dev_p99_mm   = dev_result.stats["p99_mm"],
                scale_min_mm = scale_min,
                scale_max_mm = scale_max,
            )
            db.add(summary)

            proj_q = await db.execute(
                select(Project).where(Project.id == uuid.UUID(project_id))
            )
            proj = proj_q.scalar_one_or_none()
            if proj:
                proj.status = ProjectStatus.ANALYZED

            await _update_job(db, job_id, JobStatus.COMPLETE, 100, "Deviation analysis complete.")
            await db.commit()

    except Exception as exc:
        logger.exception(f"Deviation task failed: {exc}")
        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.FAILED, 0,
                              f"Deviation failed: {exc}", error=str(exc))


async def _gdt_task(project_id: str, job_id: str, feature_ids: list[str]) -> None:
    loop = asyncio.get_event_loop()

    try:
        cad_path, scan_path, transform = await _load_project_files_with_alignment(project_id)

        from app.services.ingest import load_cad_mesh, load_point_cloud
        from app.services.gdt import analyse_feature

        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 10, "Loading files...")

        mesh_info  = await loop.run_in_executor(None, load_cad_mesh, cad_path)
        cloud_info = await loop.run_in_executor(None, load_point_cloud, scan_path)

        pts = np.asarray(cloud_info.cloud.points)
        if transform is not None:
            R = transform[:3, :3]
            t = transform[:3, 3]
            pts = (R @ pts.T).T + t

        # Load features from DB
        async with AsyncSessionLocal() as db:
            q = select(GDTFeature).where(GDTFeature.project_id == uuid.UUID(project_id))
            if feature_ids:
                q = q.where(GDTFeature.id.in_([uuid.UUID(fid) for fid in feature_ids]))
            result = await db.execute(q)
            features = result.scalars().all()

        if not features:
            raise ValueError("No GD&T features defined for this project.")

        total = len(features)
        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 20,
                              f"Analysing {total} features...")

        results_to_save = []
        for i, feature in enumerate(features):
            feat_dict = {
                "name":               feature.name,
                "feature_type":       feature.feature_type,
                "nominal_x":          feature.nominal_x,
                "nominal_y":          feature.nominal_y,
                "nominal_z":          feature.nominal_z,
                "nominal_diameter":   feature.nominal_diameter,
                "roi_min_x":          feature.roi_min_x,
                "roi_min_y":          feature.roi_min_y,
                "roi_min_z":          feature.roi_min_z,
                "roi_max_x":          feature.roi_max_x,
                "roi_max_y":          feature.roi_max_y,
                "roi_max_z":          feature.roi_max_z,
                "primary_datum":      feature.primary_datum,
                "secondary_datum":    feature.secondary_datum,
                "tertiary_datum":     feature.tertiary_datum,
                "tolerance_upper_mm": feature.tolerance_upper_mm,
                "tolerance_lower_mm": feature.tolerance_lower_mm,
            }

            try:
                from functools import partial
                fn = partial(analyse_feature, feat_dict, pts, mesh_info.mesh, None)
                gdt_result = await loop.run_in_executor(None, fn)

                fit_c = gdt_result.fit_center
                fit_n = gdt_result.fit_normal

                results_to_save.append(GDTResult(
                    project_id         = uuid.UUID(project_id),
                    feature_id         = feature.id,
                    job_id             = uuid.UUID(job_id),
                    actual_value_mm    = gdt_result.actual_value_mm,
                    nominal_value_mm   = gdt_result.nominal_value_mm,
                    deviation_mm       = gdt_result.deviation_mm,
                    in_tolerance       = gdt_result.in_tolerance,
                    fit_center_x       = float(fit_c[0]) if fit_c is not None else None,
                    fit_center_y       = float(fit_c[1]) if fit_c is not None else None,
                    fit_center_z       = float(fit_c[2]) if fit_c is not None else None,
                    fit_normal_x       = float(fit_n[0]) if fit_n is not None else None,
                    fit_normal_y       = float(fit_n[1]) if fit_n is not None else None,
                    fit_normal_z       = float(fit_n[2]) if fit_n is not None else None,
                    fit_radius         = gdt_result.fit_radius,
                    fit_residual_rms   = gdt_result.fit_residual_rms,
                    point_count_used   = gdt_result.point_count_used,
                ))
            except Exception as feat_exc:
                logger.warning(f"Feature '{feature.name}' failed: {feat_exc}")

            pct = 20 + int(((i + 1) / total) * 75)
            async with AsyncSessionLocal() as db:
                await _update_job(db, job_id, JobStatus.RUNNING, pct,
                                  f"Processed {i+1}/{total} features...")

        async with AsyncSessionLocal() as db:
            for r in results_to_save:
                db.add(r)
            await _update_job(db, job_id, JobStatus.COMPLETE, 100, "GD&T analysis complete.")
            await db.commit()

    except Exception as exc:
        logger.exception(f"GD&T task failed: {exc}")
        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.FAILED, 0,
                              f"GD&T failed: {exc}", error=str(exc))


async def _wall_thickness_task(project_id: str, job_id: str, params: dict) -> None:
    loop = asyncio.get_event_loop()

    try:
        cad_path, _, _ = await _load_project_files(project_id)

        from app.services.ingest import load_cad_mesh
        from app.services.wall_thickness import compute_wall_thickness

        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 10, "Loading CAD mesh...")

        mesh_info = await loop.run_in_executor(None, load_cad_mesh, cad_path)

        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 30, "Ray-casting thickness...")

        from functools import partial
        fn = partial(
            compute_wall_thickness,
            mesh_info.mesh,
            params.get("sample_count", settings.WALL_THICKNESS_SAMPLE_COUNT),
        )
        wt_result = await loop.run_in_executor(None, fn)

        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.RUNNING, 80, "Saving results...")

            samples = [
                WallThicknessSample(
                    project_id   = uuid.UUID(project_id),
                    job_id       = uuid.UUID(job_id),
                    sample_x     = float(wt_result.sample_points[i, 0]),
                    sample_y     = float(wt_result.sample_points[i, 1]),
                    sample_z     = float(wt_result.sample_points[i, 2]),
                    thickness_mm = float(wt_result.thickness_mm[i]),
                    normal_x     = float(wt_result.normals[i, 0]),
                    normal_y     = float(wt_result.normals[i, 1]),
                    normal_z     = float(wt_result.normals[i, 2]),
                )
                for i in range(len(wt_result.thickness_mm))
            ]
            db.add_all(samples)
            await _update_job(db, job_id, JobStatus.COMPLETE, 100,
                              f"Wall thickness complete — {len(samples):,} samples.")
            await db.commit()

    except Exception as exc:
        logger.exception(f"Wall thickness task failed: {exc}")
        async with AsyncSessionLocal() as db:
            await _update_job(db, job_id, JobStatus.FAILED, 0,
                              f"Wall thickness failed: {exc}", error=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

async def _get_project_or_404(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id).options(selectinload(Project.cad_model), selectinload(Project.scan_cloud), selectinload(Project.alignment)))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(404, f"Project '{project_id}' not found.")
    return project


async def _ready_project_or_error(db: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await _get_project_or_404(db, project_id)
    if not (project.cad_model and project.cad_model.is_processed):
        raise HTTPException(400, "CAD model not ready.")
    if not (project.scan_cloud and project.scan_cloud.is_processed):
        raise HTTPException(400, "Scan cloud not ready.")
    return project


async def _aligned_project_or_error(db: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await _ready_project_or_error(db, project_id)
    if project.alignment is None:
        raise HTTPException(400, "Alignment not run yet — call /align first.")
    return project


async def _load_project_files(project_id: str) -> tuple[str, str | None, None]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_id} not found.")
        cad_path  = project.cad_model.file_path if project.cad_model else None
        scan_path = project.scan_cloud.file_path if project.scan_cloud else None
    return cad_path, scan_path, None


async def _load_project_files_with_alignment(project_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        project = result.scalar_one_or_none()
        if project is None:
            raise ValueError(f"Project {project_id} not found.")
        cad_path  = project.cad_model.file_path if project.cad_model else None
        scan_path = project.scan_cloud.file_path if project.scan_cloud else None
        transform = None
        if project.alignment:
            transform = project.alignment.get_matrix_numpy()
    return cad_path, scan_path, transform


async def _update_job(db: AsyncSession,
                      job_id: str,
                      new_status: JobStatus,
                      pct: int,
                      msg: str,
                      error: str | None = None) -> None:
    result = await db.execute(
        select(AnalysisJob).where(AnalysisJob.id == uuid.UUID(job_id))
    )
    job = result.scalar_one_or_none()
    if job is None:
        return
    job.status       = new_status
    job.progress_pct = pct
    job.progress_msg = msg
    if error:
        job.error_message = error
    if new_status == JobStatus.RUNNING and job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    if new_status in (JobStatus.COMPLETE, JobStatus.FAILED):
        job.finished_at = datetime.now(timezone.utc)
    await db.flush()


def _job_to_out(j: AnalysisJob) -> AnalysisJobOut:
    return AnalysisJobOut(
        id             = j.id,
        project_id     = j.project_id,
        analysis_type  = j.analysis_type,
        status         = j.status,
        celery_task_id = j.celery_task_id,
        progress_pct   = j.progress_pct,
        progress_msg   = j.progress_msg,
        error_message  = j.error_message,
        parameters     = j.parameters,
        started_at     = j.started_at,
        finished_at    = j.finished_at,
        created_at     = j.created_at,
    )


def _alignment_to_out(a: Alignment) -> AlignmentOut:
    return AlignmentOut(
        id                = a.id,
        project_id        = a.project_id,
        method            = a.method,
        transform_matrix  = a.transform_matrix,
        inlier_rmse_mm    = a.inlier_rmse_mm,
        fitness_score     = a.fitness_score,
        inlier_count      = a.inlier_count,
        iteration_count   = a.iteration_count,
        datum_constraints = a.datum_constraints,
        created_at        = a.created_at,
    )


def _gdt_feature_to_out(f: GDTFeature) -> GDTFeatureOut:
    return GDTFeatureOut(
        id                 = f.id,
        project_id         = f.project_id,
        name               = f.name,
        feature_type       = f.feature_type,
        nominal_x          = f.nominal_x,
        nominal_y          = f.nominal_y,
        nominal_z          = f.nominal_z,
        nominal_diameter   = f.nominal_diameter,
        roi_min_x          = f.roi_min_x,
        roi_min_y          = f.roi_min_y,
        roi_min_z          = f.roi_min_z,
        roi_max_x          = f.roi_max_x,
        roi_max_y          = f.roi_max_y,
        roi_max_z          = f.roi_max_z,
        primary_datum      = f.primary_datum,
        secondary_datum    = f.secondary_datum,
        tertiary_datum     = f.tertiary_datum,
        tolerance_upper_mm = f.tolerance_upper_mm,
        tolerance_lower_mm = f.tolerance_lower_mm,
        created_at         = f.created_at,
    )


def _gdt_result_to_out(r: GDTResult, f: GDTFeature) -> GDTResultOut:
    return GDTResultOut(
        id                 = r.id,
        project_id         = r.project_id,
        feature_id         = r.feature_id,
        job_id             = r.job_id,
        actual_value_mm    = r.actual_value_mm,
        nominal_value_mm   = r.nominal_value_mm,
        deviation_mm       = r.deviation_mm,
        in_tolerance       = r.in_tolerance,
        fit_center_x       = r.fit_center_x,
        fit_center_y       = r.fit_center_y,
        fit_center_z       = r.fit_center_z,
        fit_normal_x       = r.fit_normal_x,
        fit_normal_y       = r.fit_normal_y,
        fit_normal_z       = r.fit_normal_z,
        fit_radius         = r.fit_radius,
        fit_residual_rms   = r.fit_residual_rms,
        point_count_used   = r.point_count_used,
        created_at         = r.created_at,
        feature_name       = f.name,
        feature_type       = f.feature_type,
        tolerance_upper_mm = f.tolerance_upper_mm,
        tolerance_lower_mm = f.tolerance_lower_mm,
    )
