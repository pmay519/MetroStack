"""
app/api/routes/upload.py
File upload endpoints for CAD meshes and scan point clouds.
Files are saved to disk then processed asynchronously.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.models import CADModel, Project, ProjectStatus, ScanCloud
from app.schemas.schemas import CADModelOut, MessageOut, ScanCloudOut
from app.services.ingest import (
    CAD_FORMATS, SCAN_FORMATS, STEP_FORMATS,
    detect_format, load_cad_mesh, load_point_cloud, validate_file_size,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}", tags=["Upload"])

_UPLOAD_ROOT = settings.UPLOAD_DIR
_MAX_MB      = settings.MAX_UPLOAD_SIZE_MB


# ── CAD upload ────────────────────────────────────────────────────────────────

@router.post("/upload-cad",
             response_model=CADModelOut,
             status_code=status.HTTP_201_CREATED)
async def upload_cad(project_id: uuid.UUID,
                     background_tasks: BackgroundTasks,
                     file: UploadFile = File(...),
                     db: AsyncSession = Depends(get_db)) -> CADModelOut:
    """
    Upload a CAD reference mesh.
    Accepted: STL, OBJ, PLY, OFF, GLB, STEP, IGES.
    Processing (mesh repair + metadata extraction) runs as a background task.
    """
    project = await _get_project_or_404(db, project_id)

    ext = Path(file.filename).suffix.lower()
    allowed = CAD_FORMATS | STEP_FORMATS
    if ext not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported CAD format '{ext}'. Allowed: {sorted(allowed)}",
        )

    # Save to disk
    dest_dir  = _upload_dir(project_id, "cad")
    dest_path = dest_dir / _safe_filename(file.filename)
    await _stream_upload(file, dest_path)

    validate_file_size(dest_path, _MAX_MB)

    file_size = dest_path.stat().st_size

    # Create DB record (unprocessed)
    # Remove existing CAD model if re-uploading
    if False:  # lazy load disabled
        await db.delete(project.cad_model)
        await db.flush()

    cad_record = CADModel(
        project_id     = project_id,
        filename       = file.filename,
        file_path      = str(dest_path),
        file_format    = ext.lstrip("."),
        file_size_bytes = file_size,
        is_processed   = False,
    )
    db.add(cad_record)
    await db.flush()
    await db.refresh(cad_record)

    # Background: load, repair, extract metadata, update DB
    background_tasks.add_task(
        _process_cad_background, str(cad_record.id), str(dest_path)
    )

    return _cad_to_out(cad_record)


# ── Scan upload ────────────────────────────────────────────────────────────────

@router.post("/upload-scan",
             response_model=ScanCloudOut,
             status_code=status.HTTP_201_CREATED)
async def upload_scan(project_id: uuid.UUID,
                      background_tasks: BackgroundTasks,
                      file: UploadFile = File(...),
                      db: AsyncSession = Depends(get_db)) -> ScanCloudOut:
    """
    Upload a scan point cloud.
    Accepted: PLY, PCD, XYZ, XYZN, E57, LAS, LAZ, CSV, PTS.
    """
    project = await _get_project_or_404(db, project_id)

    ext = Path(file.filename).suffix.lower()
    if ext not in SCAN_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported scan format '{ext}'. Allowed: {sorted(SCAN_FORMATS)}",
        )

    dest_dir  = _upload_dir(project_id, "scan")
    dest_path = dest_dir / _safe_filename(file.filename)
    await _stream_upload(file, dest_path)

    validate_file_size(dest_path, _MAX_MB)

    file_size = dest_path.stat().st_size

    if False:  # lazy load disabled
        await db.delete(project.scan_cloud)
        await db.flush()

    scan_record = ScanCloud(
        project_id      = project_id,
        filename        = file.filename,
        file_path       = str(dest_path),
        file_format     = ext.lstrip("."),
        file_size_bytes = file_size,
        is_processed    = False,
    )
    db.add(scan_record)
    await db.flush()
    await db.refresh(scan_record)

    background_tasks.add_task(
        _process_scan_background, str(scan_record.id), str(dest_path)
    )

    return _scan_to_out(scan_record)


# ── Status endpoints ──────────────────────────────────────────────────────────

@router.get("/cad", response_model=CADModelOut)
async def get_cad_info(project_id: uuid.UUID,
                       db: AsyncSession = Depends(get_db)) -> CADModelOut:
    project = await _get_project_or_404(db, project_id)
    if not project.cad_model:
        raise HTTPException(status_code=404, detail="No CAD model uploaded yet.")
    return _cad_to_out(project.cad_model)


@router.get("/scan", response_model=ScanCloudOut)
async def get_scan_info(project_id: uuid.UUID,
                        db: AsyncSession = Depends(get_db)) -> ScanCloudOut:
    project = await _get_project_or_404(db, project_id)
    if not project.scan_cloud:
        raise HTTPException(status_code=404, detail="No scan cloud uploaded yet.")
    return _scan_to_out(project.scan_cloud)


@router.delete("/cad", response_model=MessageOut)
async def delete_cad(project_id: uuid.UUID,
                     db: AsyncSession = Depends(get_db)) -> MessageOut:
    project = await _get_project_or_404(db, project_id)
    if not project.cad_model:
        raise HTTPException(status_code=404, detail="No CAD model to delete.")
    path = Path(project.cad_model.file_path)
    await db.delete(project.cad_model)
    if path.exists():
        path.unlink()
    return MessageOut(message="CAD model deleted.")


@router.delete("/scan", response_model=MessageOut)
async def delete_scan(project_id: uuid.UUID,
                      db: AsyncSession = Depends(get_db)) -> MessageOut:
    project = await _get_project_or_404(db, project_id)
    if not project.scan_cloud:
        raise HTTPException(status_code=404, detail="No scan cloud to delete.")
    path = Path(project.scan_cloud.file_path)
    await db.delete(project.scan_cloud)
    if path.exists():
        path.unlink()
    return MessageOut(message="Scan cloud deleted.")


# ── Background processing ──────────────────────────────────────────────────────

async def _process_cad_background(record_id: str, filepath: str) -> None:
    import psycopg2
    from app.core.config import settings
    try:
        mesh_info = load_cad_mesh(filepath)
    except Exception as exc:
        logger.error(f"CAD processing failed for {record_id}: {exc}")
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST, dbname=settings.POSTGRES_DB,
            user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD
        )
        cur = conn.cursor()
        cur.execute("UPDATE cad_models SET repair_log=%s WHERE id=%s", (f"ERROR: {exc}", record_id))
        conn.commit(); conn.close()
        return
    conn = psycopg2.connect(
        host=settings.POSTGRES_HOST, dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("""UPDATE cad_models SET vertex_count=%s, face_count=%s, is_watertight=%s,
        bbox_min_x=%s, bbox_min_y=%s, bbox_min_z=%s, bbox_max_x=%s, bbox_max_y=%s, bbox_max_z=%s,
        repair_log=%s, is_processed=true WHERE id=%s""",
        (mesh_info.vertex_count, mesh_info.face_count, mesh_info.is_watertight,
         mesh_info.bbox_min[0], mesh_info.bbox_min[1], mesh_info.bbox_min[2],
         mesh_info.bbox_max[0], mesh_info.bbox_max[1], mesh_info.bbox_max[2],
         mesh_info.repair_log, record_id))
    conn.commit(); conn.close()
    logger.info(f"CAD record {record_id} processed: {mesh_info.vertex_count} verts")


async def _process_scan_background(record_id: str, filepath: str) -> None:
    import psycopg2
    from app.core.config import settings
    try:
        cloud_info = load_point_cloud(filepath)
    except Exception as exc:
        logger.error(f"Scan processing failed for {record_id}: {exc}")
        return
    conn = psycopg2.connect(
        host=settings.POSTGRES_HOST, dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD
    )
    cur = conn.cursor()
    cur.execute("""UPDATE scan_clouds SET point_count=%s, has_normals=%s, has_intensity=%s,
        has_rgb=%s, bbox_min_x=%s, bbox_min_y=%s, bbox_min_z=%s,
        bbox_max_x=%s, bbox_max_y=%s, bbox_max_z=%s, units=%s, is_processed=true WHERE id=%s""",
        (cloud_info.point_count, cloud_info.has_normals, cloud_info.has_intensity,
         cloud_info.has_rgb, cloud_info.bbox_min[0], cloud_info.bbox_min[1], cloud_info.bbox_min[2],
         cloud_info.bbox_max[0], cloud_info.bbox_max[1], cloud_info.bbox_max[2],
         cloud_info.units, record_id))
    conn.commit(); conn.close()
    logger.info(f"Scan record {record_id} processed: {cloud_info.point_count} points")


# ── Utilities ─────────────────────────────────────────────────────────────────

async def _stream_upload(file: UploadFile, dest: Path) -> None:
    """Stream upload to disk in 1 MB chunks."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(dest, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            await f.write(chunk)


def _upload_dir(project_id: uuid.UUID, subdir: str) -> Path:
    path = _UPLOAD_ROOT / str(project_id) / subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_filename(filename: str) -> str:
    """Strip path separators from original filename."""
    return Path(filename).name


async def _get_project_or_404(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id).options(selectinload(Project.cad_model), selectinload(Project.scan_cloud), selectinload(Project.alignment)))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    return project


def _cad_to_out(rec: CADModel) -> CADModelOut:
    return CADModelOut(
        id              = rec.id,
        project_id      = rec.project_id,
        filename        = rec.filename,
        file_format     = rec.file_format,
        file_size_bytes = rec.file_size_bytes,
        vertex_count    = rec.vertex_count,
        face_count      = rec.face_count,
        is_watertight   = rec.is_watertight,
        bbox_min_x      = rec.bbox_min_x,
        bbox_min_y      = rec.bbox_min_y,
        bbox_min_z      = rec.bbox_min_z,
        bbox_max_x      = rec.bbox_max_x,
        bbox_max_y      = rec.bbox_max_y,
        bbox_max_z      = rec.bbox_max_z,
        repair_log      = rec.repair_log,
        is_processed    = rec.is_processed,
        uploaded_at     = rec.uploaded_at,
    )


def _scan_to_out(rec: ScanCloud) -> ScanCloudOut:
    return ScanCloudOut(
        id              = rec.id,
        project_id      = rec.project_id,
        filename        = rec.filename,
        file_format     = rec.file_format,
        file_size_bytes = rec.file_size_bytes,
        point_count     = rec.point_count,
        has_normals     = rec.has_normals,
        has_intensity   = rec.has_intensity,
        has_rgb         = rec.has_rgb,
        bbox_min_x      = rec.bbox_min_x,
        bbox_min_y      = rec.bbox_min_y,
        bbox_min_z      = rec.bbox_min_z,
        bbox_max_x      = rec.bbox_max_x,
        bbox_max_y      = rec.bbox_max_y,
        bbox_max_z      = rec.bbox_max_z,
        units           = rec.units,
        is_processed    = rec.is_processed,
        uploaded_at     = rec.uploaded_at,
    )


# ── Serve raw files for 3D viewer ─────────────────────────────────────────────
from fastapi.responses import FileResponse

@router.get("/cad/file")
async def get_cad_file(project_id: uuid.UUID,
                       db: AsyncSession = Depends(get_db)):
    project = await _get_project_or_404(db, project_id)
    result = await db.execute(
        select(CADModel).where(CADModel.project_id == project_id)
    )
    cad = result.scalar_one_or_none()
    if not cad:
        raise HTTPException(status_code=404, detail="No CAD file found.")
    return FileResponse(cad.file_path, media_type="application/octet-stream",
                        filename=cad.filename)
