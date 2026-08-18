"""Auth bridge handler — login, logout, user management, audit log."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta

from kawkab.core.logging import get_logger
from kawkab.core.security import ErrorSanitizer

logger = get_logger(__name__)


def _hash_str(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _hash_password(password: str) -> str:
    salt = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
    return f"{salt}${pwd_hash.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, pwd_hash = stored.split("$", 1)
        computed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000)
        return secrets.compare_digest(computed.hex(), pwd_hash)
    except (ValueError, AttributeError):
        return False


class AuthHandler:
    """Handles authentication and authorization for Bridge."""

    def __init__(self, bridge, services, rate_limiter=None):
        self._bridge = bridge
        self._services = services
        self._rate_limiter = rate_limiter
        self._default_admin_created = False

    @property
    def storage_service(self):
        return self._services.get("storage_service")

    def _ensure_admin(self):
        """Create default admin on first run if no users exist."""
        if self._default_admin_created:
            return
        svc = self.storage_service
        if svc is None:
            return
        try:
            import asyncio
            user = asyncio.run(svc.get_user_by_username("admin"))
            if user is None:
                pwd_hash = _hash_password("admin123")
                asyncio.run(svc.create_user("admin", pwd_hash, "admin", "admin@kawkab.ai", "Admin"))
                logger.info("Created default admin user (admin/admin123)")
            self._default_admin_created = True
        except Exception as e:
            logger.warning(f"Could not create default admin: {e}")

    def login(self, username: str, password: str) -> str:
        """Authenticate user and return session token."""
        try:
            svc = self.storage_service
            if svc is None:
                return json.dumps({"error": "Storage unavailable"})
            self._ensure_admin()

            import asyncio
            user = asyncio.run(svc.get_user_by_username(username))
            if user is None:
                return json.dumps({"error": "Invalid username or password"})

            if user.get("is_locked"):
                return json.dumps({"error": "Account locked. Try again later."})
            if not user.get("is_active"):
                return json.dumps({"error": "Account deactivated."})

            if not _verify_password(password, user.get("password_hash", "")):
                remaining = asyncio.run(svc.record_failed_login(username))
                msg = "Invalid password"
                if remaining > 0:
                    msg += f" ({remaining} attempts remaining)"
                return json.dumps({"error": msg})

            asyncio.run(svc.update_user_login(user["id"]))

            token_raw = secrets.token_hex(32)
            token_hash = _hash_str(token_raw)
            expires = (datetime.now(UTC) + timedelta(days=7)).isoformat()
            asyncio.run(svc.save_session(user["id"], token_hash, expires))
            asyncio.run(svc.audit_log(user["id"], username, "login", "auth", "session"))

            return json.dumps({
                "success": True,
                "token": token_raw,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "display_name": user.get("display_name", ""),
                    "role": user["role"],
                    "team": user.get("team", ""),
                    "email": user.get("email", ""),
                }
            })
        except Exception as e:
            logger.error(f"login failed: {e}")
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def logout(self, token: str) -> str:
        """Invalidate user session."""
        try:
            svc = self.storage_service
            if svc is None:
                return json.dumps({"error": "Storage unavailable"})
            import asyncio
            token_hash = _hash_str(token)
            asyncio.run(svc.delete_session(token_hash))
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def get_current_user(self, token: str) -> str:
        """Get current user from session token."""
        try:
            if not token:
                return json.dumps({"error": "Not authenticated"})
            svc = self.storage_service
            if svc is None:
                return json.dumps({"error": "Storage unavailable"})
            import asyncio
            token_hash = _hash_str(token)
            user = asyncio.run(svc.validate_session(token_hash))
            if user is None:
                return json.dumps({"error": "Session expired or invalid"})
            return json.dumps({"success": True, "user": dict(user)})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def change_password(self, token: str, old_password: str, new_password: str) -> str:
        """Change password for authenticated user."""
        try:
            svc = self.storage_service
            if svc is None:
                return json.dumps({"error": "Storage unavailable"})
            import asyncio
            token_hash = _hash_str(token)
            user = asyncio.run(svc.validate_session(token_hash))
            if user is None:
                return json.dumps({"error": "Not authenticated"})
            full = asyncio.run(svc.get_user_by_id(user["id"]))
            if full is None:
                return json.dumps({"error": "User not found"})
            if not _verify_password(old_password, full.get("password_hash", "")):
                return json.dumps({"error": "Current password is incorrect"})
            if len(new_password) < 6:
                return json.dumps({"error": "New password must be at least 6 characters"})
            new_hash = _hash_password(new_password)
            asyncio.run(svc.change_password(user["id"], new_hash))
            asyncio.run(svc.audit_log(user["id"], user["username"], "change_password", "auth", "password"))
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def get_audit_log(self, token: str, limit: str = "50") -> str:
        """Get audit log (admin only)."""
        try:
            svc = self.storage_service
            if svc is None:
                return json.dumps({"error": "Storage unavailable"})
            import asyncio
            token_hash = _hash_str(token)
            user = asyncio.run(svc.validate_session(token_hash))
            if user is None:
                return json.dumps({"error": "Not authenticated"})
            if user["role"] != "admin":
                return json.dumps({"error": "Admin only"})
            lim = max(1, min(200, int(limit)))
            events = asyncio.run(svc.get_audit_log(limit=lim))
            return json.dumps({"success": True, "events": events})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})

    def list_users(self, token: str) -> str:
        """List all users (admin only)."""
        try:
            svc = self.storage_service
            if svc is None:
                return json.dumps({"error": "Storage unavailable"})
            import asyncio
            token_hash = _hash_str(token)
            user = asyncio.run(svc.validate_session(token_hash))
            if user is None:
                return json.dumps({"error": "Not authenticated"})
            if user["role"] != "admin":
                return json.dumps({"error": "Admin only"})
            users_list = asyncio.run(svc.get_all_users())
            return json.dumps({"success": True, "users": users_list})
        except Exception as e:
            return json.dumps({"error": ErrorSanitizer.sanitize_error(e)})
