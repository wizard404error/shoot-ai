"""Tests for RBAC middleware."""

from __future__ import annotations

import pytest
from kawkab.core.rbac import (
    RBACMiddleware, Role, ROLE_HIERARCHY, PERMISSION_ROLES, rbac, get_rbac,
)
from fastapi import HTTPException


class TestRBACMiddleware:
    @pytest.fixture
    def middleware(self):
        m = RBACMiddleware()
        m.register_user(1, "admin", Role.ADMIN)
        m.register_user(2, "coach", Role.COACH)
        m.register_user(3, "analyst", Role.ANALYST)
        m.register_user(4, "scout", Role.SCOUT, team="academy")
        m.register_user(5, "viewer", Role.VIEWER)
        return m

    def test_admin_has_all_permissions(self, middleware):
        for perm in PERMISSION_ROLES:
            assert middleware.has_permission(1, perm), f"Admin should have {perm}"

    def test_viewer_only_read(self, middleware):
        assert middleware.has_permission(5, "match:read") is True
        assert middleware.has_permission(5, "match:write") is False
        assert middleware.has_permission(5, "event:read") is True
        assert middleware.has_permission(5, "event:write") is False

    def test_analyst_can_write_events(self, middleware):
        assert middleware.has_permission(3, "event:write") is True
        assert middleware.has_permission(3, "event:read") is True
        assert middleware.has_permission(3, "match:delete") is False

    def test_coach_can_delete(self, middleware):
        assert middleware.has_permission(2, "match:delete") is True
        assert middleware.has_permission(2, "event:delete") is True

    def test_scout_has_recruitment(self, middleware):
        assert middleware.has_permission(4, "recruitment:read") is True
        assert middleware.has_permission(4, "recruitment:write") is True
        assert middleware.has_permission(4, "analysis:run") is False

    def test_unknown_user_has_no_permissions(self, middleware):
        assert middleware.has_permission(99, "match:read") is False

    def test_permission_not_found(self, middleware):
        assert middleware.has_permission(1, "nonexistent:perm") is False

    def test_resource_team_restriction(self, middleware):
        # Analyst (no team) should access any team's data
        assert middleware.has_permission(3, "match:read", "first_team") is True
        # Scout (team=academy) should not access first_team data
        assert middleware.has_permission(4, "match:read", "first_team") is False

    def test_admin_bypasses_team_restriction(self, middleware):
        assert middleware.has_permission(1, "match:read", "any_team") is True

    def test_require_permission_raises(self, middleware):
        with pytest.raises(HTTPException):
            middleware.require_permission(5, "match:write")

    def test_require_permission_passes(self, middleware):
        middleware.require_permission(1, "match:write")

    def test_get_role(self, middleware):
        assert middleware.get_role(1) == Role.ADMIN
        assert middleware.get_role(5) == Role.VIEWER
        assert middleware.get_role(99) is None

    def test_register_user(self, middleware):
        user = middleware.register_user(10, "new", Role.ANALYST)
        assert user["role"] == Role.ANALYST
        assert user["role_level"] == ROLE_HIERARCHY[Role.ANALYST]

    def test_get_user(self, middleware):
        user = middleware.get_user(1)
        assert user is not None
        assert user["username"] == "admin"

    def test_get_user_nonexistent(self, middleware):
        assert middleware.get_user(999) is None

    def test_role_hierarchy(self):
        assert ROLE_HIERARCHY[Role.ADMIN] > ROLE_HIERARCHY[Role.COACH]
        assert ROLE_HIERARCHY[Role.COACH] > ROLE_HIERARCHY[Role.ANALYST]
        assert ROLE_HIERARCHY[Role.ANALYST] > ROLE_HIERARCHY[Role.SCOUT]
        assert ROLE_HIERARCHY[Role.SCOUT] > ROLE_HIERARCHY[Role.VIEWER]

    def test_permission_role_mapping(self):
        assert PERMISSION_ROLES["match:read"] == Role.VIEWER
        assert PERMISSION_ROLES["admin:users"] == Role.ADMIN


class TestRbacSingleton:
    def test_get_rbac_returns_instance(self):
        assert get_rbac() is rbac
        assert isinstance(rbac, RBACMiddleware)
