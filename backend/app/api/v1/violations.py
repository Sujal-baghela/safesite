"""
Violations API endpoints.

GET  /api/v1/violations          — paginated, filterable list
GET  /api/v1/violations/{id}     — single violation detail with fresh signed URL
PATCH /api/v1/violations/{id}/resolve — mark resolved / re-open
GET  /api/v1/jobs/{job_id}       — poll async video-processing job status
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.dependencies import get_current_user, get_db
from app.core.storage import get_signed_url
from app.crud.violation import (
    get_violation,
    list_violations,
    resolve_violation,
)
from app.models.user import User
from app.schemas.violation import (
    ViolationFilterParams,
    ViolationListResponse,
    ViolationResolveRequest,
    ViolationResponse,
)

router = APIRouter(prefix="/violations", tags=["violations"])
jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])


def _build_response(violation, fresh_url: str | None = None) -> ViolationResponse:
    """Build a ViolationResponse, substituting a fresh signed URL if provided."""
    resp = ViolationResponse.model_validate(violation)
    if fresh_url:
        resp.snapshot_url = fresh_url
    return resp


@router.get(
    "",
    response_model=ViolationListResponse,
    summary="List violations with optional filters",
)
async def list_violations_endpoint(
    site_id: Annotated[str | None, Query()] = None,
    camera_id: Annotated[str | None, Query()] = None,
    type: Annotated[str | None, Query()] = None,
    resolved: Annotated[bool | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ViolationListResponse:
    filters = ViolationFilterParams(
        site_id=site_id,
        camera_id=camera_id,
        type=type,
        resolved=resolved,
        page=page,
        page_size=page_size,
    )
    violations, total = await list_violations(db, filters)

    # Resolve signed URLs for snapshots in bulk
    items = []
    for v in violations:
        fresh_url = None
        if v.snapshot_key:
            fresh_url = await get_signed_url(v.snapshot_key)
        items.append(_build_response(v, fresh_url))

    return ViolationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{violation_id}",
    response_model=ViolationResponse,
    summary="Get a single violation with a fresh snapshot URL",
)
async def get_violation_endpoint(
    violation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ViolationResponse:
    violation = await get_violation(db, violation_id)
    if not violation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation not found")

    fresh_url = None
    if violation.snapshot_key:
        fresh_url = await get_signed_url(violation.snapshot_key)

    return _build_response(violation, fresh_url)


@router.patch(
    "/{violation_id}/resolve",
    response_model=ViolationResponse,
    summary="Mark a violation as resolved or re-open it",
)
async def resolve_violation_endpoint(
    violation_id: str,
    payload: ViolationResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ViolationResponse:
    violation = await resolve_violation(
        db,
        violation_id=violation_id,
        resolved_by_user_id=current_user.id,
        resolved=payload.resolved,
    )
    if not violation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation not found")

    fresh_url = None
    if violation.snapshot_key:
        fresh_url = await get_signed_url(violation.snapshot_key)

    return _build_response(violation, fresh_url)


# ---------------------------------------------------------------------------
# Job status polling
# ---------------------------------------------------------------------------

@jobs_router.get(
    "/{job_id}",
    summary="Poll the status of an async video processing job",
)
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Returns the current status of a video processing job.

    Status values:
      queued    — waiting in ARQ queue
      running   — currently being processed
      complete  — done, violation_count available
      failed:*  — failed with error type
    """
    status_val = await cache.get(f"job:{job_id}:status")
    if status_val is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found or expired",
        )

    result = {}
    if status_val == "complete":
        raw = await cache.get(f"job:{job_id}:result")
        if raw:
            import ast
            try:
                result = ast.literal_eval(raw) if isinstance(raw, str) else raw
            except Exception:
                result = {}

    return {"job_id": job_id, "status": status_val, **result}
