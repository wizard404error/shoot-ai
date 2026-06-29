from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CollabUser:
    id: int = 0
    username: str = ""
    display_name: str = ""
    role: str = "analyst"  # admin, coach, analyst, scout
    created_at: str = ""

    def to_dict(self):
        return {"id": self.id, "username": self.username, "display_name": self.display_name, "role": self.role}


@dataclass
class Comment:
    id: int = 0
    match_id: int = 0
    event_id: int = 0
    user_id: int = 0
    username: str = ""
    text: str = ""
    created_at: str = ""

    def to_dict(self):
        return {"id": self.id, "match_id": self.match_id, "event_id": self.event_id, "user_id": self.user_id, "username": self.username, "text": self.text, "created_at": self.created_at}


@dataclass
class ActivityEntry:
    id: int = 0
    user_id: int = 0
    username: str = ""
    action: str = ""  # "analyze", "comment", "export", "import", "tag", "review"
    description: str = ""
    match_id: int = 0
    created_at: str = ""

    def to_dict(self):
        return {"id": self.id, "user_id": self.user_id, "username": self.username, "action": self.action, "description": self.description, "match_id": self.match_id, "created_at": self.created_at}


class CollaborationService:
    def __init__(self):
        self._users: dict[int, CollabUser] = {}
        self._comments: list[Comment] = []
        self._activities: list[ActivityEntry] = []
        self._next_user_id = 1
        self._next_comment_id = 1
        self._next_activity_id = 1
        self._add_default_users()

    def _add_default_users(self):
        self._users[0] = CollabUser(id=0, username="admin", display_name="Head Coach", role="admin", created_at=datetime.now().isoformat())
        self._users[1] = CollabUser(id=1, username="analyst1", display_name="Video Analyst", role="analyst", created_at=datetime.now().isoformat())
        self._next_user_id = 2

    def create_user(self, username: str, display_name: str, role: str = "analyst") -> str:
        try:
            for u in self._users.values():
                if u.username == username:
                    return json.dumps({"error": "Username already exists"})
            uid = self._next_user_id
            self._next_user_id += 1
            user = CollabUser(id=uid, username=username, display_name=display_name, role=role, created_at=datetime.now().isoformat())
            self._users[uid] = user
            self._add_activity(uid, username, "user_created", f"User {username} created")
            return json.dumps({"user": user.to_dict(), "ok": True})
        except Exception as e:
            logger.error(f"create_user failed: {e}")
            return json.dumps({"error": str(e)})

    def get_users(self) -> str:
        try:
            return json.dumps({"users": [u.to_dict() for u in self._users.values()], "total": len(self._users)})
        except Exception as e:
            logger.error(f"get_users failed: {e}")
            return json.dumps({"error": str(e)})

    def delete_user(self, user_id: int) -> str:
        try:
            if user_id in self._users and user_id > 1:
                del self._users[user_id]
                return json.dumps({"ok": True})
            return json.dumps({"error": "User not found or cannot delete default users"})
        except Exception as e:
            logger.error(f"delete_user failed: {e}")
            return json.dumps({"error": str(e)})

    def add_comment(self, match_id: int, event_id: int, user_id: int, text: str) -> str:
        try:
            cid = self._next_comment_id
            self._next_comment_id += 1
            username = self._users.get(user_id, CollabUser(username="unknown")).username
            comment = Comment(id=cid, match_id=match_id, event_id=event_id, user_id=user_id, username=username, text=text, created_at=datetime.now().isoformat())
            self._comments.append(comment)
            self._add_activity(user_id, username, "comment", f"Commented on match {match_id}", match_id)
            return json.dumps({"comment": comment.to_dict(), "ok": True})
        except Exception as e:
            logger.error(f"add_comment failed: {e}")
            return json.dumps({"error": str(e)})

    def get_comments(self, match_id: int, event_id: int = 0) -> str:
        try:
            results = [c for c in self._comments if c.match_id == match_id and (event_id == 0 or c.event_id == event_id)]
            return json.dumps({"comments": [c.to_dict() for c in results], "total": len(results)})
        except Exception as e:
            logger.error(f"get_comments failed: {e}")
            return json.dumps({"error": str(e)})

    def delete_comment(self, comment_id: int) -> str:
        try:
            self._comments = [c for c in self._comments if c.id != comment_id]
            return json.dumps({"ok": True})
        except Exception as e:
            logger.error(f"delete_comment failed: {e}")
            return json.dumps({"error": str(e)})

    def export_project(self, match_data: dict) -> str:
        try:
            project = {
                "version": "0.13.0",
                "type": "kawkab_project",
                "exported_at": datetime.now().isoformat(),
                "match": match_data,
                "comments": [c.to_dict() for c in self._comments if c.match_id == match_data.get("id")],
            }
            return json.dumps({"project": project, "ok": True})
        except Exception as e:
            logger.error(f"export_project failed: {e}")
            return json.dumps({"error": str(e)})

    def import_project(self, project_json: str) -> str:
        try:
            data = json.loads(project_json) if isinstance(project_json, str) else project_json
            if data.get("type") != "kawkab_project":
                return json.dumps({"error": "Invalid project format"})
            match = data.get("match", {})
            for c_data in data.get("comments", []):
                comment = Comment(
                    id=self._next_comment_id, match_id=match.get("id", 0),
                    event_id=c_data.get("event_id", 0), user_id=0,
                    username=c_data.get("username", "imported"), text=c_data.get("text", ""),
                    created_at=c_data.get("created_at", datetime.now().isoformat()),
                )
                self._next_comment_id += 1
                self._comments.append(comment)
            self._add_activity(0, "system", "import", f"Imported project for match {match.get('id', '?')}", match.get("id", 0))
            return json.dumps({"match": match, "comments_imported": len(data.get("comments", [])), "ok": True})
        except Exception as e:
            logger.error(f"import_project failed: {e}")
            return json.dumps({"error": str(e)})

    def get_activity_feed(self, limit: int = 50) -> str:
        try:
            feed = sorted(self._activities, key=lambda a: a.created_at, reverse=True)[:limit]
            return json.dumps({"activities": [a.to_dict() for a in feed], "total": len(feed)})
        except Exception as e:
            logger.error(f"get_activity_feed failed: {e}")
            return json.dumps({"error": str(e)})

    def _add_activity(self, user_id: int, username: str, action: str, description: str, match_id: int = 0):
        aid = self._next_activity_id
        self._next_activity_id += 1
        entry = ActivityEntry(id=aid, user_id=user_id, username=username, action=action, description=description, match_id=match_id, created_at=datetime.now().isoformat())
        self._activities.append(entry)
