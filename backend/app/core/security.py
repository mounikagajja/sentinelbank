from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from backend.app.core.config import get_settings

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

ROLES = ("analyst", "viewer")


class User(BaseModel):
    username: str
    role: str


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


DEMO_USERS = {
    "analyst": {
        "username": "analyst",
        "role": "analyst",
        "password_hash": hash_password("analyst123"),
    },
    "viewer": {
        "username": "viewer",
        "role": "viewer",
        "password_hash": hash_password("viewer123"),
    },
}


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def authenticate(username: str, password: str) -> User | None:
    record = DEMO_USERS.get(username)
    if record is None or not verify_password(password, record["password_hash"]):
        return None
    return User(username=record["username"], role=record["role"])


def create_access_token(user: User) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.PyJWTError:
        raise credentials_error from None

    username = payload.get("sub")
    role = payload.get("role")
    if username is None or role not in ROLES:
        raise credentials_error
    return User(username=username, role=role)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_analyst(user: CurrentUser) -> User:
    if user.role != "analyst":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the analyst role",
        )
    return user


AnalystUser = Annotated[User, Depends(require_analyst)]
