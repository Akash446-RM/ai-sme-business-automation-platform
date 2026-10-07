"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated, List

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import CurrentUser, DbSession, require_manager, require_owner
from app.models.user import User
from app.schemas.auth import (
    PasswordChange,
    Token,
    UserCreate,
    UserLogin,
    UserRead,
    UserUpdate,
)
from app.schemas.common import Message
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register an account (first account becomes the owner)",
)
def register(payload: UserCreate, db: DbSession) -> UserRead:
    service = AuthService(db)
    user = service.register(payload)
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token, summary="Login with email and password")
def login(payload: UserLogin, db: DbSession) -> Token:
    return AuthService(db).login(payload.email, payload.password)


@router.post(
    "/token",
    response_model=Token,
    summary="OAuth2 password flow (used by the interactive docs)",
)
def login_oauth2(
    db: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    return AuthService(db).login(form_data.username, form_data.password)


@router.get("/me", response_model=UserRead, summary="Current authenticated user")
def read_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.post("/change-password", response_model=Message, summary="Change own password")
def change_password(
    payload: PasswordChange, db: DbSession, current_user: CurrentUser
) -> Message:
    AuthService(db).change_password(
        current_user, payload.current_password, payload.new_password
    )
    return Message(message="Password updated successfully.")


@router.get(
    "/users",
    response_model=List[UserRead],
    dependencies=[Depends(require_manager)],
    summary="List platform users",
)
def list_users(db: DbSession) -> List[UserRead]:
    return [UserRead.model_validate(user) for user in AuthService(db).list_users()]


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user account (owner only)",
)
def create_user(
    payload: UserCreate,
    db: DbSession,
    _: Annotated[User, Depends(require_owner)],
) -> UserRead:
    return UserRead.model_validate(AuthService(db).register(payload, allow_owner=True))


@router.patch(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Update a user account (owner only)",
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: DbSession,
    _: Annotated[User, Depends(require_owner)],
) -> UserRead:
    return UserRead.model_validate(AuthService(db).update_user(user_id, payload))


@router.delete(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Deactivate a user account (owner only)",
)
def deactivate_user(
    user_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_owner)],
) -> UserRead:
    return UserRead.model_validate(AuthService(db).deactivate(user_id, current_user))
