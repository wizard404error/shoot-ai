from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kawkab.cloud.database import get_cloud_db

_jwt_secret: str | None = None

def _get_jwt_secret() -> str:
    global _jwt_secret
    if _jwt_secret is not None:
        return _jwt_secret
    val = os.environ.get("KAWKAB_JWT_SECRET")
    if not val:
        raise RuntimeError(
            "KAWKAB_JWT_SECRET environment variable is not set. "
            "Generate a strong secret (e.g., `python -c \"import secrets; print(secrets.token_hex(32))\"`) "
            "and export KAWKAB_JWT_SECRET before starting the cloud server."
        )
    _jwt_secret = val
    return val

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"{salt}${pwd_hash.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, pwd_hash = stored.split("$", 1)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
        return hmac.compare_digest(computed.hex(), pwd_hash)
    except (ValueError, AttributeError):
        return False


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, _get_jwt_secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _get_jwt_secret(), algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    db = get_cloud_db()
    user = db.execute("SELECT id, username, email, display_name, is_active, created_at FROM users WHERE id = ?", (int(payload["sub"]),)).fetchone()
    if user is None or not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return dict(user)
