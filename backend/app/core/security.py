"""Password hashing and JSON Web Token helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import AuthenticationError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TOKEN_TYPE = "bearer"


def hash_password(plain_password: str) -> str:
    """Return a salted bcrypt hash for the supplied password."""
    # bcrypt only considers the first 72 bytes; truncate explicitly so long
    # passwords fail predictably rather than raising inside the library.
    return _pwd_context.hash(plain_password[:72])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a stored hash."""
    try:
        return _pwd_context.verify(plain_password[:72], hashed_password)
    except ValueError:
        return False


def create_access_token(
    subject: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: Dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expire.timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT, raising AuthenticationError when invalid."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired authentication token.") from exc
    if payload.get("type") != "access":
        raise AuthenticationError("Unsupported token type.")
    if not payload.get("sub"):
        raise AuthenticationError("Token is missing a subject.")
    return payload
