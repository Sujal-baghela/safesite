"""
Database operations for violations.

All writes invalidate the Redis violation-count cache for the affected site
so the dashboard counter stays accurate within 1 minute.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.models.violation import Violation
from app.schemas.violation import ViolationFilterParams


async def create_violation(
    db: AsyncSession,
    *,
    site_id: str,
    camera_id: str | None,
    violation_type: str,
    confidence_score: float | None,
    snapshot_key: str | None,
    snapshot_url: str | None,
) -> Violation:
    """
    Insert a new violation record and invalidate the site's cached count.

    Returns the newly created Violation ORM object.
    """
    violation = Violation(
        id=str(uuid.uuid4()),
        site_id=site_id,
        camera_id=camera_id,
        type=violation_type,
        confidence_score=confidence_score,
        snapshot_key=snapshot_key,
        snapshot_url=snapshot_url,
    )
    db.add(violation)
    await db.commit()
    await db.refresh(violation)

    # Invalidate cached count so dashboard reflects the new entry quickly
    await cache.delete(cache.key_violations_count(site_id))

    return violation


async def get_violation(db: AsyncSession, violation_id: str) -> Violation | None:
    """Return a single violation by ID, or None."""
    result = await db.execute(
        select(Violation).where(Violation.id == violation_id)
    )
    return result.scalar_one_or_none()


async def list_violations(
    db: AsyncSession,
    filters: ViolationFilterParams,
) -> tuple[list[Violation], int]:
    """
    Return paginated violations filtered by site, camera, type, and date range.

    Returns:
        Tuple of (violations list, total count matching filters).
    """
    query = select(Violation)
    count_query = select(func.count()).select_from(Violation)

    if filters.site_id:
        query = query.where(Violation.site_id == filters.site_id)
        count_query = count_query.where(Violation.site_id == filters.site_id)
    if filters.camera_id:
        query = query.where(Violation.camera_id == filters.camera_id)
        count_query = count_query.where(Violation.camera_id == filters.camera_id)
    if filters.type:
        query = query.where(Violation.type == filters.type)
        count_query = count_query.where(Violation.type == filters.type)
    if filters.resolved is not None:
        query = query.where(Violation.resolved == filters.resolved)
        count_query = count_query.where(Violation.resolved == filters.resolved)
    if filters.start_date:
        query = query.where(Violation.timestamp >= filters.start_date)
        count_query = count_query.where(Violation.timestamp >= filters.start_date)
    if filters.end_date:
        query = query.where(Violation.timestamp <= filters.end_date)
        count_query = count_query.where(Violation.timestamp <= filters.end_date)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    offset = (filters.page - 1) * filters.page_size
    query = (
        query
        .order_by(Violation.timestamp.desc())
        .offset(offset)
        .limit(filters.page_size)
    )
    result = await db.execute(query)
    violations = list(result.scalars().all())

    return violations, total


async def resolve_violation(
    db: AsyncSession,
    violation_id: str,
    resolved_by_user_id: str,
    resolved: bool,
) -> Violation | None:
    """
    Mark a violation as resolved (or re-open it).

    Returns the updated violation, or None if not found.
    """
    result = await db.execute(
        select(Violation).where(Violation.id == violation_id)
    )
    violation = result.scalar_one_or_none()
    if violation is None:
        return None

    violation.resolved = resolved
    violation.resolved_by = resolved_by_user_id if resolved else None
    violation.resolved_at = datetime.utcnow() if resolved else None

    await db.commit()
    await db.refresh(violation)

    # Invalidate count cache — resolved status affects dashboard filters
    await cache.delete(cache.key_violations_count(violation.site_id))

    return violation


async def get_violation_count_for_site(db: AsyncSession, site_id: str) -> int:
    """
    Return total unresolved violation count for a site.
    Result is cached in Redis for 60 seconds.
    """
    cache_key = cache.key_violations_count(site_id)
    cached = await cache.get(cache_key)
    if cached is not None:
        return int(cached)

    result = await db.execute(
        select(func.count())
        .select_from(Violation)
        .where(Violation.site_id == site_id, Violation.resolved == False)  # noqa: E712
    )
    count = result.scalar_one()
    await cache.set(cache_key, count, ttl=60)
    return count
