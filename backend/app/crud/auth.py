"""Database operations for authentication."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Return User matching email, or None."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    """Return User matching id, or None."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: RegisterRequest) -> User:
    """
    Insert a new user with a hashed password.

    Args:
        db: Async database session.
        data: Validated registration payload.

    Returns:
        Newly created User ORM object.
    """
    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole.COMPANY_ADMIN.value,  # first user of a company is admin
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
