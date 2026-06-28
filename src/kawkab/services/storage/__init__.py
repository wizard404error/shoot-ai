"""Specialised storage classes for Kawkab AI data.
Split from the original StorageService god class.
"""

from kawkab.services.storage.base import BaseStorage
from kawkab.services.storage.match_storage import MatchStorage
from kawkab.services.storage.event_storage import EventStorage
from kawkab.services.storage.player_storage import PlayerStorage
from kawkab.services.storage.feedback_storage import FeedbackStorage
from kawkab.services.storage.clip_storage import ClipStorage
from kawkab.services.storage.profile_storage import ProfileStorage

__all__ = [
    "BaseStorage",
    "MatchStorage",
    "EventStorage",
    "PlayerStorage",
    "FeedbackStorage",
    "ClipStorage",
    "ProfileStorage",
]
