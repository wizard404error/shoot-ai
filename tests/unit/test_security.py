"""Tests for security validation utilities."""

from pathlib import Path
import pytest
from kawkab.core.security import SecurityValidator, ErrorSanitizer, RateLimiter


class TestSecurityValidator:
    """Test input validation utilities."""

    def test_validate_match_id_valid(self):
        assert SecurityValidator.validate_match_id(42) == 42
        assert SecurityValidator.validate_match_id("123") == 123
        assert SecurityValidator.validate_match_id(0) == 0

    def test_validate_match_id_invalid(self):
        with pytest.raises(ValueError, match="Invalid match_id"):
            SecurityValidator.validate_match_id("abc")
        with pytest.raises(ValueError, match="Invalid match_id"):
            SecurityValidator.validate_match_id(None)
        with pytest.raises(ValueError, match="match_id must be non-negative"):
            SecurityValidator.validate_match_id(-1)
        with pytest.raises(ValueError, match="match_id too large"):
            SecurityValidator.validate_match_id(1_000_000_000)

    def test_validate_jersey_number(self):
        assert SecurityValidator.validate_jersey_number(7) == 7
        assert SecurityValidator.validate_jersey_number(99) == 99
        assert SecurityValidator.validate_jersey_number(0) == 0
        with pytest.raises(ValueError, match="must be 0-99"):
            SecurityValidator.validate_jersey_number(-1)
        with pytest.raises(ValueError, match="must be 0-99"):
            SecurityValidator.validate_jersey_number(100)
        with pytest.raises(ValueError, match="Invalid jersey number"):
            SecurityValidator.validate_jersey_number("abc")

    def test_sanitize_string(self):
        assert SecurityValidator.sanitize_string("hello") == "hello"
        assert SecurityValidator.sanitize_string("  hello  ") == "hello"
        assert SecurityValidator.sanitize_string("a" * 300, max_length=10) == "a" * 10
        assert SecurityValidator.sanitize_string("hello\x00world") == "helloworld"
        assert SecurityValidator.sanitize_string("hello<script>world") == "helloscriptworld"
        assert SecurityValidator.sanitize_string("test@#$%world") == "testworld"

    def test_validate_team_name(self):
        assert SecurityValidator.validate_team_name("Team A") == "Team A"
        with pytest.raises(ValueError, match="cannot be empty"):
            SecurityValidator.validate_team_name("")
        with pytest.raises(ValueError, match="cannot be empty"):
            SecurityValidator.validate_team_name("   ")

    def test_validate_video_path(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_text("dummy")
        result = SecurityValidator.validate_video_path(str(video))
        assert result == video

    def test_validate_video_path_unsupported_extension(self, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_text("dummy")
        with pytest.raises(ValueError, match="Unsupported file type"):
            SecurityValidator.validate_video_path(str(txt))


class TestErrorSanitizer:
    """Test error message sanitization."""

    def test_sanitize_error_removes_paths(self):
        error = "Failed to load C:\\Users\\Test\\video.mp4"
        sanitized = ErrorSanitizer.sanitize_error(error)
        assert "[path]" in sanitized
        assert "C:\\Users" not in sanitized

    def test_sanitize_error_removes_ips(self):
        error = "Connection failed to 192.168.1.1:8080"
        sanitized = ErrorSanitizer.sanitize_error(error)
        assert "[ip]" in sanitized
        assert "192.168.1.1" not in sanitized

    def test_sanitize_error_removes_emails(self):
        error = "Contact admin@example.com for help"
        sanitized = ErrorSanitizer.sanitize_error(error)
        assert "[email]" in sanitized
        assert "admin@example.com" not in sanitized

    def test_sanitize_error_truncates(self):
        error = "x" * 1000
        sanitized = ErrorSanitizer.sanitize_error(error)
        assert len(sanitized) <= 503  # 500 + "..."


class TestRateLimiter:
    """Test rate limiting."""

    def test_rate_limiter_allows_requests(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60.0)
        assert limiter.can_proceed() is True
        limiter.record_request()
        assert limiter.can_proceed() is True
        limiter.record_request()
        assert limiter.can_proceed() is True
        limiter.record_request()
        assert limiter.can_proceed() is False

    def test_rate_limiter_time_until_available(self):
        limiter = RateLimiter(max_requests=1, window_seconds=1.0)
        limiter.record_request()
        assert limiter.can_proceed() is False
        assert limiter.time_until_available() > 0.0

    def test_rate_limiter_resets_after_window(self):
        import time
        limiter = RateLimiter(max_requests=1, window_seconds=0.1)
        limiter.record_request()
        assert limiter.can_proceed() is False
        time.sleep(0.15)
        assert limiter.can_proceed() is True
