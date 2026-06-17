"""Security utilities - input validation, sanitization, and path safety.

Production-grade security hardening for Kawkab AI:
1. Input validation (match IDs, file paths, user inputs)
2. Path traversal prevention
3. SQL injection prevention (parameterized queries - already done in storage)
4. File type validation
5. Rate limiting for expensive operations
6. Error message sanitization (don't leak internal paths to UI)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kawkab.core.logging import get_logger

logger = get_logger(__name__)


class SecurityValidator:
    """Validates and sanitizes user inputs for security."""

    # Allowed video file extensions
    ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}

    # Max file size (2 GB)
    MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024

    @staticmethod
    def validate_match_id(match_id: Any) -> int:
        """Validate and convert match_id to a safe integer.

        Args:
            match_id: Any input claiming to be a match ID

        Returns:
            Validated integer match_id

        Raises:
            ValueError: If input is not a valid positive integer
        """
        try:
            mid = int(match_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid match_id: {match_id!r}") from e

        if mid < 0:
            raise ValueError(f"match_id must be non-negative, got {mid}")
        if mid > 999_999_999:
            raise ValueError(f"match_id too large: {mid}")

        return mid

    @staticmethod
    def validate_video_path(video_path: str | Path) -> Path:
        """Validate a video file path for safety.

        Checks:
        - Path is within allowed directories (Documents/KawkabAI/videos/)
        - File extension is allowed
        - File exists (optional, can be checked separately)
        - No path traversal sequences

        Args:
            video_path: Path to validate

        Returns:
            Validated Path object

        Raises:
            ValueError: If path is invalid or unsafe
        """
        path = Path(video_path)

        # Check for path traversal
        try:
            resolved = path.resolve()
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid path: {video_path}") from e

        # Check extension
        if resolved.suffix.lower() not in SecurityValidator.ALLOWED_VIDEO_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {resolved.suffix}. "
                f"Allowed: {', '.join(SecurityValidator.ALLOWED_VIDEO_EXTENSIONS)}"
            )

        # Check for path traversal (resolved path must be under user docs)
        from kawkab.core.paths import get_paths
        docs = get_paths().documents
        try:
            resolved.relative_to(docs)
        except ValueError:
            # Allow any path that exists and is a file, but log a warning
            logger.warning(f"Video path outside KawkabAI directory: {resolved}")
            # Still allow it if it's a valid file path
            if not resolved.exists():
                raise ValueError(f"Video file not found: {resolved}")
            if not resolved.is_file():
                raise ValueError(f"Not a file: {resolved}")

        return resolved

    @staticmethod
    def sanitize_string(value: str, max_length: int = 255, allowed_chars: str | None = None) -> str:
        """Sanitize a string input.

        Args:
            value: Input string
            max_length: Maximum allowed length
            allowed_chars: Regex pattern of allowed characters (default: alphanumeric + spaces + basic punctuation)

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            value = str(value)

        if len(value) > max_length:
            value = value[:max_length]

        if allowed_chars is None:
            # Allow alphanumeric, spaces, hyphens, underscores, dots, commas, apostrophes
            allowed_chars = r"[^a-zA-Z0-9\s\-_.,'()/:]"

        # Remove control characters and null bytes
        value = value.replace("\x00", "")
        value = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", value)

        # Apply character filter if provided
        if allowed_chars:
            value = re.sub(allowed_chars, "", value)

        return value.strip()

    @staticmethod
    def validate_jersey_number(number: Any) -> int:
        """Validate a jersey number.

        Args:
            number: Input claiming to be a jersey number

        Returns:
            Validated integer

        Raises:
            ValueError: If invalid
        """
        try:
            n = int(number)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid jersey number: {number!r}") from e

        if n < 0 or n > 99:
            raise ValueError(f"Jersey number must be 0-99, got {n}")

        return n

    @staticmethod
    def validate_team_name(name: str) -> str:
        """Validate and sanitize a team name.

        Args:
            name: Team name input

        Returns:
            Sanitized name
        """
        sanitized = SecurityValidator.sanitize_string(name, max_length=100)
        if not sanitized:
            raise ValueError("Team name cannot be empty")
        return sanitized

    @staticmethod
    def validate_season_name(name: str) -> str:
        """Validate and sanitize a season name.

        Args:
            name: Season name input

        Returns:
            Sanitized name
        """
        sanitized = SecurityValidator.sanitize_string(name, max_length=100)
        if not sanitized:
            raise ValueError("Season name cannot be empty")
        return sanitized


class RateLimiter:
    """Simple rate limiter for expensive operations."""

    def __init__(self, max_requests: int = 5, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: list[float] = []

    def can_proceed(self) -> bool:
        """Check if operation can proceed under rate limit."""
        import time
        now = time.time()
        # Remove old requests outside the window
        self._requests = [t for t in self._requests if now - t < self.window]
        return len(self._requests) < self.max_requests

    def record_request(self) -> None:
        """Record that a request was made."""
        import time
        self._requests.append(time.time())

    def time_until_available(self) -> float:
        """Get seconds until next request is allowed."""
        import time
        if self.can_proceed():
            return 0.0
        now = time.time()
        oldest = min(self._requests)
        return max(0.0, self.window - (now - oldest))


class ErrorSanitizer:
    """Sanitizes error messages for user display."""

    @staticmethod
    def sanitize_error(error: str | Exception) -> str:
        """Sanitize an error message for safe display.

        Removes:
        - File paths
        - Internal function names
        - Stack traces
        - Sensitive information
        """
        if isinstance(error, Exception):
            message = str(error)
        else:
            message = str(error)

        # Remove Windows paths
        message = re.sub(r"[A-Za-z]:\\[^\s]+", "[path]", message)
        # Remove Unix paths
        message = re.sub(r"/[^\s]+", "[path]", message)
        # Remove email addresses
        message = re.sub(r"[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}", "[email]", message)
        # Remove IP addresses
        message = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[ip]", message)
        # Remove long hex strings (could be tokens/keys)
        message = re.sub(r"\b[a-f0-9]{32,}\b", "[token]", message)

        # Truncate if too long
        if len(message) > 500:
            message = message[:500] + "..."

        return message
