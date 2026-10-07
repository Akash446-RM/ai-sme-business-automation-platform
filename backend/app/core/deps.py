"""Shared FastAPI dependencies for authentication and authorisation."""

from __future__ import annotations

from typing import Annotated, Callable, Iterable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_access_token
from app.models.enums import UserRole
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False
)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> User:
    """Resolve the authenticated user from the bearer token."""
    if not token:
        raise AuthenticationError("Authentication credentials were not provided.")

    payload = decode_access_token(token)
    user = db.query(User).filter(User.email == payload["sub"]).first()
    if user is None:
        raise AuthenticationError("The account linked to this token no longer exists.")
    if not user.is_active:
        raise AuthenticationError("This account has been deactivated.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole | str) -> Callable[[User], User]:
    """Build a dependency that allows only the supplied roles."""
    allowed: set[str] = {str(role) for role in roles}

    def _dependency(current_user: CurrentUser) -> User:
        if str(current_user.role) not in allowed:
            raise AuthorizationError(
                "Your role does not permit this action.",
                {"required_roles": sorted(allowed), "your_role": str(current_user.role)},
            )
        return current_user

    return _dependency


def roles_of(*roles: Iterable[UserRole]) -> set[str]:  # pragma: no cover - helper
    return {str(role) for group in roles for role in group}


# Common role gates
require_owner = require_roles(UserRole.OWNER)
require_manager = require_roles(UserRole.OWNER, UserRole.MANAGER)
require_staff = require_roles(UserRole.OWNER, UserRole.MANAGER, UserRole.STAFF)

ManagerUser = Annotated[User, Depends(require_manager)]
OwnerUser = Annotated[User, Depends(require_owner)]
