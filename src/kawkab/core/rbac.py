"""Role-based access control — permissions, roles, and authorization middleware."""

from __future__ import annotations

from enum import Enum
from typing import Any


class Role(str, Enum):
    ADMIN = "admin"
    COACH = "coach"
    ANALYST = "analyst"
    SCOUT = "scout"
    VIEWER = "viewer"


ROLE_HIERARCHY: dict[Role, int] = {
    Role.ADMIN: 100,
    Role.COACH: 80,
    Role.ANALYST: 60,
    Role.SCOUT: 50,
    Role.VIEWER: 30,
}

PERMISSION_ROLES: dict[str, Role] = {
    "match:read": Role.VIEWER,
    "match:write": Role.ANALYST,
    "match:delete": Role.COACH,
    "event:read": Role.VIEWER,
    "event:write": Role.ANALYST,
    "event:delete": Role.COACH,
    "player:read": Role.VIEWER,
    "player:write": Role.ANALYST,
    "analysis:read": Role.VIEWER,
    "analysis:run": Role.ANALYST,
    "tag:read": Role.VIEWER,
    "tag:write": Role.ANALYST,
    "tag:delete": Role.COACH,
    "admin:users": Role.ADMIN,
    "admin:settings": Role.ADMIN,
    "recruitment:read": Role.SCOUT,
    "recruitment:write": Role.SCOUT,
    "medical:read": Role.COACH,
    "medical:write": Role.COACH,
    "export:data": Role.ANALYST,
    "export:video": Role.COACH,
}


class RBACMiddleware:
    def __init__(self):
        self._users: dict[int, dict] = {}

    def register_user(self, user_id: int, username: str, role: Role, team: str = "") -> dict:
        user = {
            "id": user_id,
            "username": username,
            "role": role,
            "role_level": ROLE_HIERARCHY.get(role, 0),
            "team": team,
        }
        self._users[user_id] = user
        return user

    def get_user(self, user_id: int) -> dict | None:
        return self._users.get(user_id)

    def has_permission(self, user_id: int, permission: str, resource_team: str = "") -> bool:
        user = self._users.get(user_id)
        if not user:
            return False
        required_role = PERMISSION_ROLES.get(permission)
        if required_role is None:
            return False
        if user["role_level"] >= ROLE_HIERARCHY.get(required_role, 0):
            if resource_team and user["team"] and user["team"] != resource_team:
                if user["role_level"] < ROLE_HIERARCHY[Role.ADMIN]:
                    return False
            return True
        return False

    def require_permission(self, user_id: int, permission: str, resource_team: str = ""):
        if not self.has_permission(user_id, permission, resource_team):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")

    def get_role(self, user_id: int) -> Role | None:
        user = self._users.get(user_id)
        return user["role"] if user else None


rbac = RBACMiddleware()


def get_rbac() -> RBACMiddleware:
    return rbac
