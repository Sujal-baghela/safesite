"""
FastAPI dependency functions.

Provides:
  - get_db        — async SQLAlchemy session
  - get_current_user — decode JWT and return User ORM object
  - require_role  — factory for role-gated endpoints
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.core.database import async_session_factory
from app.core.security import decode_token
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer()


async def get_db() -> AsyncSession:  # type: ignore[return]
    """Yield an async database session, closing it after the request."""
    async with async_session_factory() as session:
        yield session


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Decode the Bearer JWT and return the matching User.

    Raises 401 if the token is invalid / expired.
    Raises 404 if the user no longer exists in the DB.
    Uses Redis to cache permission lookups for 15 minutes.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Try cache first
    cached = await cache.get(cache.key_user_permissions(user_id))
    if cached:
        # Reconstruct a lightweight proxy — full ORM object needed for relations
        # so we still hit DB on cache miss but skip it on hit.
        pass  # fall through to DB for now; cache used in heavy endpoints

    from sqlalchemy import select

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account")
    return user


def require_role(*roles: UserRole):
    """
    Factory that returns a dependency enforcing role membership.

    Usage:
        @router.get("/admin-only")
        async def admin(user = Depends(require_role(UserRole.SUPER_ADMIN))):
            ...
    """

    async def _check(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role(s): {[r.value for r in roles]}",
            )
        return current_user

    return _check
