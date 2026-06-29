from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── Auth ──

class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = ""

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    display_name: str
    is_active: bool
    created_at: datetime

class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


# ── Sync ──

class SyncPayload(BaseModel):
    device_id: str
    last_sync_at: Optional[str] = None
    operations: list["SyncOperation"] = []

class SyncOperation(BaseModel):
    op: str  # "create" | "update" | "delete"
    entity_type: str  # "match" | "project" | "scout_report" | "tag"
    entity_id: str
    data: dict = {}

class SyncResponse(BaseModel):
    sync_token: str
    operations: list[SyncOperation] = []
    conflicts: list["ConflictRecord"] = []

class ConflictRecord(BaseModel):
    entity_type: str
    entity_id: str
    local_version: int
    remote_version: int
    local_data: dict
    remote_data: dict


# ── Team ──

class TeamCreate(BaseModel):
    name: str
    description: str = ""

class TeamMember(BaseModel):
    user_id: int
    role: str = "member"  # "owner" | "admin" | "member" | "viewer"

class TeamInvite(BaseModel):
    email: EmailStr
    role: str = "member"

class SharedProject(BaseModel):
    project_id: str
    team_id: int
    permissions: str = "view"  # "view" | "edit" | "admin"


# ── WebSocket ──

class WSMessage(BaseModel):
    type: str  # "edit" | "cursor" | "comment" | "presence"
    project_id: str
    user_id: int
    payload: dict = {}
    timestamp: float = 0.0
