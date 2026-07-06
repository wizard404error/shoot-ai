"""Kawkab AI Cloud Server — FastAPI application."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from kawkab.cloud.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from kawkab.cloud.database import get_cloud_db
from kawkab.api.api_v1 import router as api_v1_router
from kawkab.cloud.models import (
    UserRegister,
    UserLogin,
    PasswordChange,
    SyncPayload,
    TeamCreate,
    TeamInvite,
    SharedProject,
    UserOut,
    TokenResponse,
    SyncResponse,
    ConflictRecord,
    SyncOperation,
)

app = FastAPI(title="Kawkab AI Cloud", version="0.1.0")

app.include_router(api_v1_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ──

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


# ── Auth ──

@app.post("/auth/register", response_model=TokenResponse)
def register(body: UserRegister):
    db = get_cloud_db()
    existing = db.execute("SELECT id FROM users WHERE email = ? OR username = ?", (body.email, body.username)).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Email or username already taken")
    pwd_hash = hash_password(body.password)
    cur = db.execute(
        "INSERT INTO users (username, email, password_hash, display_name) VALUES (?, ?, ?, ?)",
        (body.username, body.email, pwd_hash, body.display_name or body.username),
    )
    db.commit()
    user_id = cur.lastrowid
    user = dict(db.execute("SELECT id, username, email, display_name, is_active, created_at FROM users WHERE id = ?", (user_id,)).fetchone())
    token = create_access_token(user_id)
    return TokenResponse(access_token=token, user=UserOut(**user))

@app.post("/auth/login", response_model=TokenResponse)
def login(body: UserLogin):
    db = get_cloud_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (body.email,)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(row["id"])
    user = dict(row)
    del user["password_hash"]
    return TokenResponse(access_token=token, user=UserOut(**user))

@app.get("/auth/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(**user)

@app.post("/auth/change-password")
def change_password(body: PasswordChange, user: dict = Depends(get_current_user)):
    db = get_cloud_db()
    row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
    if not verify_password(body.old_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    db.execute("UPDATE users SET password_hash = ?, updated_at = datetime('now') WHERE id = ?",
               (hash_password(body.new_password), user["id"]))
    db.commit()
    return {"ok": True}


# ── Sync ──

@app.post("/sync/push")
def sync_push(payload: SyncPayload, user: dict = Depends(get_current_user)):
    db = get_cloud_db()
    conflicts = []
    applied = []
    for op in payload.operations:
        existing = db.execute(
            "SELECT version, data FROM projects WHERE id = ? AND owner_id = ?",
            (op.entity_id, user["id"]),
        ).fetchone()
        if existing and op.op == "update":
            local_ver = int(op.data.get("_version", 0))
            if local_ver < existing["version"]:
                conflicts.append(ConflictRecord(
                    entity_type=op.entity_type,
                    entity_id=op.entity_id,
                    local_version=local_ver,
                    remote_version=existing["version"],
                    local_data=op.data,
                    remote_data=json.loads(existing["data"]),
                ))
                continue
        if op.op == "delete":
            db.execute("DELETE FROM projects WHERE id = ? AND owner_id = ?", (op.entity_id, user["id"]))
            db.execute("INSERT INTO sync_log (user_id, device_id, entity_type, entity_id, operation) VALUES (?,?,?,?,?)",
                       (user["id"], payload.device_id, op.entity_type, op.entity_id, "delete"))
            applied.append(op)
        elif op.op in ("create", "update"):
            data_json = json.dumps(op.data, ensure_ascii=False)
            new_ver = existing["version"] + 1 if existing else 1
            db.execute("""INSERT INTO projects (id, name, owner_id, data, version)
                          VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data, version=excluded.version, updated_at=datetime('now')""",
                       (op.entity_id, op.data.get("name", "Untitled"), user["id"], data_json, new_ver))
            db.execute("INSERT INTO sync_log (user_id, device_id, entity_type, entity_id, operation) VALUES (?,?,?,?,?)",
                       (user["id"], payload.device_id, op.entity_type, op.entity_id, op.op))
            applied.append(op)
    db.commit()
    return SyncResponse(sync_token=str(datetime.now(timezone.utc).timestamp()), operations=applied, conflicts=conflicts)

@app.post("/sync/pull")
def sync_pull(payload: SyncPayload, user: dict = Depends(get_current_user)):
    db = get_cloud_db()
    rows = db.execute(
        "SELECT id, name, data, version, updated_at FROM projects WHERE owner_id = ? ORDER BY updated_at DESC LIMIT 100",
        (user["id"],),
    ).fetchall()
    ops = []
    for r in rows:
        data = json.loads(r["data"])
        data["_version"] = r["version"]
        ops.append(SyncOperation(op="update", entity_type="project", entity_id=r["id"], data=data))
    return SyncResponse(sync_token=str(len(rows)), operations=ops)


# ── Teams ──

@app.post("/teams")
def create_team(body: TeamCreate, user: dict = Depends(get_current_user)):
    db = get_cloud_db()
    cur = db.execute("INSERT INTO teams (name, description, owner_id) VALUES (?, ?, ?)",
                     (body.name, body.description, user["id"]))
    db.execute("INSERT INTO team_members (team_id, user_id, role) VALUES (?, ?, 'owner')",
               (cur.lastrowid, user["id"]))
    db.commit()
    return {"ok": True, "team_id": cur.lastrowid}

@app.get("/teams")
def list_teams(user: dict = Depends(get_current_user)):
    db = get_cloud_db()
    rows = db.execute("""SELECT t.*, tm.role FROM teams t
                         JOIN team_members tm ON t.id = tm.team_id
                         WHERE tm.user_id = ? ORDER BY t.name""", (user["id"],)).fetchall()
    return [dict(r) for r in rows]

@app.post("/teams/{team_id}/invite")
def invite_member(team_id: int, body: TeamInvite, user: dict = Depends(get_current_user)):
    db = get_cloud_db()
    owner = db.execute("SELECT role FROM team_members WHERE team_id = ? AND user_id = ?", (team_id, user["id"])).fetchone()
    if not owner or owner["role"] not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    token = str(uuid.uuid4())
    db.execute("INSERT INTO team_invites (team_id, email, role, token) VALUES (?, ?, ?, ?)",
               (team_id, body.email, body.role, token))
    db.commit()
    return {"ok": True, "invite_token": token}

@app.post("/teams/join/{token}")
def accept_invite(token: str, user: dict = Depends(get_current_user)):
    db = get_cloud_db()
    invite = db.execute("SELECT * FROM team_invites WHERE token = ? AND accepted = 0", (token,)).fetchone()
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid or expired invite")
    db.execute("INSERT OR IGNORE INTO team_members (team_id, user_id, role) VALUES (?, ?, ?)",
               (invite["team_id"], user["id"], invite["role"]))
    db.execute("UPDATE team_invites SET accepted = 1 WHERE id = ?", (invite["id"],))
    db.commit()
    return {"ok": True, "team_id": invite["team_id"]}


# ── Shared Projects ──

@app.post("/projects/share")
def share_project(body: SharedProject, user: dict = Depends(get_current_user)):
    db = get_cloud_db()
    project = db.execute("SELECT * FROM projects WHERE id = ?", (body.project_id,)).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["owner_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.execute("UPDATE projects SET is_shared = 1, team_id = ? WHERE id = ?", (body.team_id, body.project_id))
    db.commit()
    return {"ok": True}


# ── WebSocket for real-time collaboration ──

connected_clients: dict[str, list[WebSocket]] = {}

@app.websocket("/ws/{project_id}")
async def ws_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    if project_id not in connected_clients:
        connected_clients[project_id] = []
    connected_clients[project_id].append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Broadcast to other clients in the same project
            for client in connected_clients.get(project_id, []):
                if client != websocket:
                    try:
                        await client.send_text(data)
                    except Exception:
                        pass
    except WebSocketDisconnect:
        connected_clients[project_id] = [c for c in connected_clients.get(project_id, []) if c != websocket]


# ── Run ──

def start(host: str = "0.0.0.0", port: int = 8741):
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    start()
