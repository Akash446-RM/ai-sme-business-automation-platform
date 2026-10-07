"""Authentication and user account business logic."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserRead, UserUpdate

logger = logging.getLogger(__name__)


class AuthService:
    """Owns every rule about accounts, credentials and tokens."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- queries ----------------------------------------------------------
    def get_by_email(self, email: str) -> Optional[User]:
        normalised = email.strip().lower()
        return self.db.execute(
            select(User).where(func.lower(User.email) == normalised)
        ).scalar_one_or_none()

    def get_by_id(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} was not found.")
        return user

    def list_users(self) -> List[User]:
        return list(self.db.execute(select(User).order_by(User.id)).scalars())

    def count_users(self) -> int:
        return int(self.db.execute(select(func.count(User.id))).scalar_one())

    # -- commands ---------------------------------------------------------
    def register(self, payload: UserCreate, *, allow_owner: bool = False) -> User:
        """Create a new account.

        The very first account created on a fresh installation always becomes
        the owner so the platform is usable immediately.
        """
        if self.get_by_email(payload.email):
            raise ConflictError("An account with this email address already exists.")

        role = payload.role
        if self.count_users() == 0:
            role = UserRole.OWNER
        elif role == UserRole.OWNER and not allow_owner:
            raise ValidationError("Only an existing owner can create another owner account.")

        user = User(
            email=payload.email.strip().lower(),
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            role=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info("Registered user %s with role %s", user.email, user.role)
        return user

    def authenticate(self, email: str, password: str) -> User:
        """Validate credentials and return the matching active user."""
        user = self.get_by_email(email)
        # Always run a hash comparison so timing does not reveal account existence.
        reference_hash = user.hashed_password if user else hash_password("invalid-placeholder-1")
        password_ok = verify_password(password, reference_hash)

        if user is None or not password_ok:
            raise AuthenticationError("Incorrect email or password.")
        if not user.is_active:
            raise AuthenticationError("This account has been deactivated.")

        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(user)
        return user

    def issue_token(self, user: User) -> Token:
        """Build the token response for an authenticated user."""
        access_token = create_access_token(subject=user.email, role=str(user.role))
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserRead.model_validate(user),
        )

    def login(self, email: str, password: str) -> Token:
        return self.issue_token(self.authenticate(email, password))

    def update_user(self, user_id: int, payload: UserUpdate) -> User:
        user = self.get_by_id(user_id)
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("The current password is incorrect.")
        if current_password == new_password:
            raise ValidationError("The new password must differ from the current password.")
        user.hashed_password = hash_password(new_password)
        self.db.commit()
        logger.info("Password changed for %s", user.email)

    def deactivate(self, user_id: int, acting_user: User) -> User:
        if user_id == acting_user.id:
            raise ValidationError("You cannot deactivate your own account.")
        user = self.get_by_id(user_id)
        user.is_active = False
        self.db.commit()
        self.db.refresh(user)
        return user
