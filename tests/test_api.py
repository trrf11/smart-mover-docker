# Tests for FastAPI endpoints

import os
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

# Set up temp config before any app imports
_temp_dir = tempfile.mkdtemp()
os.environ['CONFIG_DIR'] = _temp_dir
(Path(_temp_dir) / "logs").mkdir(parents=True, exist_ok=True)

from fastapi.testclient import TestClient
from app.main import app, config_manager
from app.config_manager import Settings


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config manager state before each test."""
    # Ensure clean state
    settings_file = config_manager.settings_file
    if settings_file.exists():
        settings_file.unlink()

    log_file = config_manager.get_log_file()
    if log_file.exists():
        log_file.unlink()

    history_file = config_manager.get_history_file()
    if history_file.exists():
        history_file.unlink()

    yield


@pytest.fixture
def client():
    """Create a test client."""
    with TestClient(app) as test_client:
        yield test_client


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestHtmlPages:
    """Tests for HTML page routes."""

    def test_dashboard_returns_html(self, client):
        """Dashboard should return HTML."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_contains_title(self, client):
        """Dashboard should contain page title."""
        response = client.get("/")
        assert "Dashboard" in response.text or "Smart Mover" in response.text

    def test_settings_page_returns_html(self, client):
        """Settings page should return HTML."""
        response = client.get("/settings")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_settings_page_contains_form(self, client):
        """Settings page should contain form elements."""
        response = client.get("/settings")
        assert "form" in response.text.lower()
        assert "jellyfin_url" in response.text

    def test_logs_page_returns_html(self, client):
        """Logs page should return HTML."""
        response = client.get("/logs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


class TestCacheUsageEndpoint:
    """Tests for the cache usage API endpoint."""

    def test_cache_usage_returns_200(self, client):
        """Cache usage endpoint should return 200."""
        response = client.get("/api/cache-usage")
        assert response.status_code == 200

    def test_cache_usage_returns_required_fields(self, client):
        """Cache usage should return all required fields."""
        response = client.get("/api/cache-usage")
        data = response.json()

        assert "path" in data
        assert "total_gb" in data
        assert "used_gb" in data
        assert "free_gb" in data
        assert "percent_used" in data
        assert "threshold" in data
        assert "above_threshold" in data

    def test_cache_usage_values_are_numeric(self, client):
        """Cache usage values should be numeric."""
        response = client.get("/api/cache-usage")
        data = response.json()

        assert isinstance(data["total_gb"], (int, float))
        assert isinstance(data["used_gb"], (int, float))
        assert isinstance(data["free_gb"], (int, float))
        assert isinstance(data["percent_used"], (int, float))
        assert isinstance(data["threshold"], int)
        assert isinstance(data["above_threshold"], bool)


class TestSettingsEndpoints:
    """Tests for the settings API endpoints."""

    def test_get_settings_returns_200(self, client):
        """GET /api/settings should return 200."""
        response = client.get("/api/settings")
        assert response.status_code == 200

    def test_get_settings_returns_defaults(self, client):
        """GET /api/settings should return default values."""
        response = client.get("/api/settings")
        data = response.json()

        assert data["jellyfin_url"] == "http://localhost:8096"
        assert data["cache_threshold"] == 90
        assert data["dry_run"] is True

    def test_get_settings_masks_api_key(self, client):
        """GET /api/settings should mask the API key."""
        # Save settings with API key
        settings = Settings(jellyfin_api_key="secret-key-12345")
        config_manager.save(settings)

        response = client.get("/api/settings")
        data = response.json()

        assert data["jellyfin_api_key"] == "********"
        assert data["jellyfin_api_key_set"] is True

    def test_get_settings_shows_api_key_not_set(self, client):
        """GET /api/settings should indicate when API key is not set."""
        response = client.get("/api/settings")
        data = response.json()

        assert data["jellyfin_api_key_set"] is False

    def test_post_settings_saves_values(self, client):
        """POST /api/settings should save new values."""
        response = client.post("/api/settings", json={
            "jellyfin_url": "http://192.168.1.100:8096",
            "cache_threshold": 85,
            "dry_run": False
        })

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify saved
        settings = config_manager.load()
        assert settings.jellyfin_url == "http://192.168.1.100:8096"
        assert settings.cache_threshold == 85
        assert settings.dry_run is False

    def test_post_settings_partial_update(self, client):
        """POST /api/settings should only update provided fields."""
        # Save initial settings
        initial = Settings(
            jellyfin_url="http://initial:8096",
            cache_threshold=80,
            dry_run=True
        )
        config_manager.save(initial)

        # Update only threshold
        response = client.post("/api/settings", json={
            "cache_threshold": 95
        })

        assert response.status_code == 200

        # Verify only threshold changed
        settings = config_manager.load()
        assert settings.jellyfin_url == "http://initial:8096"
        assert settings.cache_threshold == 95
        assert settings.dry_run is True

    def test_post_settings_preserves_api_key_when_empty(self, client):
        """POST /api/settings should preserve API key when empty string sent."""
        # Save settings with API key
        settings = Settings(jellyfin_api_key="my-secret-key")
        config_manager.save(settings)

        # Update with empty API key
        response = client.post("/api/settings", json={
            "jellyfin_api_key": "",
            "cache_threshold": 75
        })

        assert response.status_code == 200

        # Verify API key preserved
        settings = config_manager.load()
        assert settings.jellyfin_api_key == "my-secret-key"
        assert settings.cache_threshold == 75

    def test_post_settings_updates_api_key_when_provided(self, client):
        """POST /api/settings should update API key when new value provided."""
        # Save settings with API key
        settings = Settings(jellyfin_api_key="old-key")
        config_manager.save(settings)

        # Update with new API key
        response = client.post("/api/settings", json={
            "jellyfin_api_key": "new-key-12345"
        })

        assert response.status_code == 200

        # Verify API key updated
        settings = config_manager.load()
        assert settings.jellyfin_api_key == "new-key-12345"

    def test_post_settings_validates_threshold(self, client):
        """POST /api/settings should validate cache threshold."""
        response = client.post("/api/settings", json={
            "cache_threshold": 150  # Invalid: > 99
        })

        # Should fail validation
        assert response.status_code in [400, 422]


class TestLogsEndpoints:
    """Tests for the logs API endpoints."""

    def test_get_logs_returns_200(self, client):
        """GET /api/logs should return 200."""
        response = client.get("/api/logs")
        assert response.status_code == 200

    def test_get_logs_returns_empty_when_no_file(self, client):
        """GET /api/logs should return empty content when no log file."""
        response = client.get("/api/logs")
        data = response.json()

        assert data["content"] == ""
        assert data["lines"] == 0

    def test_get_logs_returns_content(self, client):
        """GET /api/logs should return log content."""
        # Create log file
        log_file = config_manager.get_log_file()
        log_file.write_text("[INFO] Test log entry\n[ERROR] Error entry\n")

        response = client.get("/api/logs")
        data = response.json()

        assert "[INFO] Test log entry" in data["content"]
        assert "[ERROR] Error entry" in data["content"]
        assert data["lines"] == 2

    def test_get_logs_with_line_limit(self, client):
        """GET /api/logs should respect line limit parameter."""
        # Create log file with multiple lines
        log_file = config_manager.get_log_file()
        log_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        response = client.get("/api/logs?lines=2")
        data = response.json()

        assert data["lines"] == 2

    def test_get_logs_with_level_filter(self, client):
        """GET /api/logs should filter by level parameter."""
        # Create log file
        log_file = config_manager.get_log_file()
        log_file.write_text("[INFO] Info message\n[ERROR] Error message\n[DEBUG] Debug message\n")

        response = client.get("/api/logs?level=ERROR")
        data = response.json()

        assert "[ERROR] Error message" in data["content"]
        assert "[INFO]" not in data["content"]

    def test_delete_logs_returns_200(self, client):
        """DELETE /api/logs should return 200."""
        # Create log file
        log_file = config_manager.get_log_file()
        log_file.write_text("Some logs")

        response = client.delete("/api/logs")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_logs_removes_file(self, client):
        """DELETE /api/logs should remove the log file."""
        # Create log file
        log_file = config_manager.get_log_file()
        log_file.write_text("Some logs")
        assert log_file.exists()

        client.delete("/api/logs")

        assert not log_file.exists()

    def test_download_logs_returns_404_when_no_file(self, client):
        """GET /api/logs/download should return 404 when no log file."""
        response = client.get("/api/logs/download")
        assert response.status_code == 404

    def test_download_logs_returns_file(self, client):
        """GET /api/logs/download should return the log file."""
        # Create log file
        log_file = config_manager.get_log_file()
        log_file.write_text("Download test content")

        response = client.get("/api/logs/download")

        assert response.status_code == 200
        assert "Download test content" in response.text
        assert "text/plain" in response.headers["content-type"]


class TestRunEndpoints:
    """Tests for the run API endpoints."""

    def test_get_run_status_returns_200(self, client):
        """GET /api/run/status should return 200."""
        response = client.get("/api/run/status")
        assert response.status_code == 200

    def test_get_run_status_initial_state(self, client):
        """GET /api/run/status should return initial state."""
        response = client.get("/api/run/status")
        data = response.json()

        assert data["is_running"] is False

    def test_post_run_returns_response(self, client):
        """POST /api/run should return a response."""
        response = client.post("/api/run", json={"dry_run": True})

        # Should return a response (may fail due to missing script, but endpoint works)
        assert response.status_code == 200
        data = response.json()
        assert "started" in data
        assert "dry_run" in data

    def test_post_run_respects_dry_run_flag(self, client):
        """POST /api/run should include dry_run in response."""
        response = client.post("/api/run", json={"dry_run": True})
        data = response.json()

        assert data["dry_run"] is True

        response = client.post("/api/run", json={"dry_run": False})
        data = response.json()

        assert data["dry_run"] is False


class TestStaticFiles:
    """Tests for static file serving."""

    def test_static_css_accessible(self, client):
        """Static CSS files should be accessible."""
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_static_js_accessible(self, client):
        """Static JS files should be accessible."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]


class TestCacheContentsEndpoint:
    """Tests for the cache contents API endpoint."""

    @pytest.fixture
    def cache_dir(self):
        """Create a temp directory with known structure to act as cache drive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files and folders
            os.makedirs(os.path.join(tmpdir, "movies-pool", "Movie A (2024)"))
            os.makedirs(os.path.join(tmpdir, "tv-pool"))
            # Create a file inside movies-pool/Movie A (2024)
            with open(os.path.join(tmpdir, "movies-pool", "Movie A (2024)", "movie.mkv"), 'w') as f:
                f.write("x" * 100)
            # Create a top-level file
            with open(os.path.join(tmpdir, "readme.txt"), 'w') as f:
                f.write("hello")
            yield tmpdir

    def _save_cache_settings(self, cache_path):
        """Helper to save settings with custom cache_drive."""
        settings = Settings(cache_drive=cache_path)
        config_manager.save(settings)

    def test_cache_contents_lists_directory(self, client, cache_dir):
        """Cache contents should list files and folders."""
        self._save_cache_settings(cache_dir)
        response = client.get("/api/cache-contents")
        assert response.status_code == 200
        data = response.json()
        names = [item["name"] for item in data["items"]]
        assert "movies-pool" in names
        assert "tv-pool" in names
        assert "readme.txt" in names

    def test_cache_contents_returns_files_and_folders(self, client, cache_dir):
        """Items should have correct type, size_bytes, and item_count."""
        self._save_cache_settings(cache_dir)
        response = client.get("/api/cache-contents")
        data = response.json()
        items_by_name = {item["name"]: item for item in data["items"]}

        # Folder checks
        movies = items_by_name["movies-pool"]
        assert movies["type"] == "folder"
        assert movies["size_bytes"] >= 100  # contains movie.mkv with 100 bytes
        assert movies["item_count"] >= 1  # at least the subfolder + file

        # File checks
        readme = items_by_name["readme.txt"]
        assert readme["type"] == "file"
        assert readme["size_bytes"] == 5  # "hello"

    def test_cache_contents_sorts_folders_first(self, client, cache_dir):
        """Folders should come before files, alphabetical within type."""
        self._save_cache_settings(cache_dir)
        response = client.get("/api/cache-contents")
        data = response.json()
        types = [item["type"] for item in data["items"]]

        # All folders should come before any files
        folder_done = False
        for t in types:
            if t == "file":
                folder_done = True
            elif t == "folder" and folder_done:
                pytest.fail("Folder appeared after file in listing")

    def test_cache_contents_path_traversal_dotdot(self, client, cache_dir):
        """Path traversal with .. should return 400."""
        self._save_cache_settings(cache_dir)
        response = client.get("/api/cache-contents?path=../../etc")
        assert response.status_code == 400

    def test_cache_contents_path_traversal_absolute(self, client, cache_dir):
        """Absolute path should return 400."""
        self._save_cache_settings(cache_dir)
        response = client.get("/api/cache-contents?path=/etc/passwd")
        assert response.status_code == 400

    def test_cache_contents_nonexistent_path(self, client, cache_dir):
        """Nonexistent path should return 404."""
        self._save_cache_settings(cache_dir)
        response = client.get("/api/cache-contents?path=does-not-exist")
        assert response.status_code == 404

    def test_cache_contents_file_not_dir(self, client, cache_dir):
        """Path pointing to a file should return 400."""
        self._save_cache_settings(cache_dir)
        response = client.get("/api/cache-contents?path=readme.txt")
        assert response.status_code == 400

    def test_cache_contents_empty_path(self, client, cache_dir):
        """Empty path should list root cache directory."""
        self._save_cache_settings(cache_dir)
        response = client.get("/api/cache-contents?path=")
        assert response.status_code == 200
        data = response.json()
        assert data["path"] == "/"
        assert len(data["items"]) > 0


class TestRunHistoryEndpoints:
    """Tests for the run history API endpoints."""

    def test_get_runs_empty(self, client):
        """GET /api/runs with no history should return empty list."""
        response = client.get("/api/runs")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_runs_returns_data(self, client):
        """GET /api/runs should return saved records."""
        config_manager.save_run({"timestamp": "2024-01-01T10:00:00", "success": True})
        config_manager.save_run({"timestamp": "2024-01-01T11:00:00", "success": False})

        response = client.get("/api/runs")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Most recent first
        assert data[0]["success"] is False
        assert data[1]["success"] is True

    def test_get_runs_returns_log_field(self, client):
        """GET /api/runs should include the log field when present."""
        config_manager.save_run({
            "timestamp": "2024-01-01T10:00:00",
            "success": True,
            "files_moved": 1,
            "log": "[1/1] Moving: test\nDone"
        })

        response = client.get("/api/runs")
        data = response.json()
        assert len(data) == 1
        assert "log" in data[0]
        assert "Moving: test" in data[0]["log"]

    def test_delete_runs_clears_history(self, client):
        """DELETE /api/runs should clear all history."""
        config_manager.save_run({"timestamp": "2024-01-01T10:00:00", "success": True})

        response = client.delete("/api/runs")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify empty
        response = client.get("/api/runs")
        assert response.json() == []


class TestScheduleStatusEndpoint:
    """Tests for the schedule status API endpoint."""

    def test_schedule_status_disabled(self, client):
        """Default schedule should be disabled."""
        response = client.get("/api/schedule/status")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

    def test_schedule_status_fields(self, client):
        """Schedule status should include all required fields."""
        response = client.get("/api/schedule/status")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "cron" in data
        assert "timezone" in data
        assert "next_run" in data
        assert "is_active" in data


class TestSecurityHeaders:
    """Tests for security headers middleware."""

    def test_security_headers_present(self, client):
        """Responses should include security headers."""
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_help_page_returns_html(self, client):
        """Help page should return HTML."""
        response = client.get("/help")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_cache_page_returns_html(self, client):
        """Cache page should return HTML."""
        response = client.get("/cache")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
