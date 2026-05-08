"""
app/api/routes/projects.py
Project lifecycle endpoints — create, list, get, update, delete.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.models import Project, ProjectStatus
from app.schemas.schemas import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectListOut, MessageOut
)

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate,
                         db: AsyncSession = Depends(get_db)) -> ProjectOut:
    project = Project(**payload.model_dump())
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return _to_out(project)


@router.get("", response_model=ProjectListOut)
async def list_projects(skip: int = 0,
                        limit: int = 50,
                        db: AsyncSession = Depends(get_db)) -> ProjectListOut:
    total_q = await db.execute(select(func.count()).select_from(Project))
    total   = total_q.scalar_one()

    rows_q = await db.execute(
        select(Project).order_by(Project.updated_at.desc()).offset(skip).limit(limit)
    )
    projects = rows_q.scalars().all()

    return ProjectListOut(items=[_to_out(p) for p in projects], total=total)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: uuid.UUID,
                      db: AsyncSession = Depends(get_db)) -> ProjectOut:
    project = await _get_or_404(db, project_id)
    return _to_out(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: uuid.UUID,
                         payload: ProjectUpdate,
                         db: AsyncSession = Depends(get_db)) -> ProjectOut:
    project = await _get_or_404(db, project_id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    await db.flush()
    await db.refresh(project)
    return _to_out(project)


@router.delete("/{project_id}", response_model=MessageOut)
async def delete_project(project_id: uuid.UUID,
                         db: AsyncSession = Depends(get_db)) -> MessageOut:
    project = await _get_or_404(db, project_id)
    await db.delete(project)
    return MessageOut(message=f"Project '{project.name}' deleted.")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, project_id: uuid.UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found."
        )
    return project


def _to_out(p: Project) -> ProjectOut:
    return ProjectOut(
        id          = p.id,
        name        = p.name,
        description = p.description,
        part_number = p.part_number,
        revision    = p.revision,
        status      = p.status,
        created_at  = p.created_at,
        updated_at  = p.updated_at,
        has_cad     = p.cad_model is not None,
        has_scan    = p.scan_cloud is not None,
        has_alignment = p.alignment is not None,
    )
