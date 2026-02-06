# Tests for configuration manager

import json
import tempfile
import pytest
from pathlib import Path
from pydantic import ValidationError

from app.config_manager import Settings, ConfigManager


class TestSettings:
    """Tests for the Settings model."""

    def test_default_values(self):
        """Settings should have sensible defaults."""
        settings = Settings()
        assert settings.jellyfin_url == "http://localhost:8096"
        assert settings.jellyfin_api_key == ""
        assert settings.cache_threshold == 90
        assert settings.cache_drive == "/mnt/cache"
        assert settings.array_path == "/mnt/disk1"
        assert settings.dry_run is True
        assert settings.debug is False
        assert settings.log_level == "INFO"

    def test_custom_values(self):
        """Settings should accept custom values."""
        settings = Settings(
            jellyfin_url="http://192.168.1.100:8096",
            jellyfin_api_key="test-key-123",
            cache_threshold=85,
            dry_run=False
        )
        assert settings.jellyfin_url == "http://192.168.1.100:8096"
        assert settings.jellyfin_api_key == "test-key-123"
        assert settings.cache_threshold == 85
        assert settings.dry_run is False

    def test_url_validation_http(self):
        """URL should accept http://."""
        settings = Settings(jellyfin_url="http://example.com:8096")
        assert settings.jellyfin_url == "http://example.com:8096"

    def test_url_validation_https(self):
        """URL should accept https://."""
        settings = Settings(jellyfin_url="https://example.com:8096")
        assert settings.jellyfin_url == "https://example.com:8096"

    def test_url_validation_strips_trailing_slash(self):
        """URL should strip trailing slashes."""
        settings = Settings(jellyfin_url="http://example.com:8096/")
        assert settings.jellyfin_url == "http://example.com:8096"

    def test_url_validation_invalid(self):
        """URL should reject invalid URLs."""
        with pytest.raises(ValidationError):
            Settings(jellyfin_url="not-a-valid-url")

    def test_cache_threshold_range_valid(self):
        """Cache threshold should accept values 1-99."""
        for value in [1, 50, 99]:
            settings = Settings(cache_threshold=value)
            assert settings.cache_threshold == value

    def test_cache_threshold_too_low(self):
        """Cache threshold should reject values below 1."""
        with pytest.raises(ValidationError):
            Settings(cache_threshold=0)

    def test_cache_threshold_too_high(self):
        """Cache threshold should reject values above 99."""
        with pytest.raises(ValidationError):
            Settings(cache_threshold=100)

    def test_log_level_validation_valid(self):
        """Log level should accept INFO, DEBUG, ERROR."""
        for level in ['INFO', 'DEBUG', 'ERROR']:
            settings = Settings(log_level=level)
            assert settings.log_level == level

    def test_log_level_validation_case_insensitive(self):
        """Log level should be case-insensitive."""
        settings = Settings(log_level='info')
        assert settings.log_level == 'INFO'

    def test_log_level_validation_invalid(self):
        """Log level should reject invalid values."""
        with pytest.raises(ValidationError):
            Settings(log_level='INVALID')


class TestConfigManager:
    """Tests for the ConfigManager class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create a ConfigManager with temporary directory."""
        return ConfigManager(config_dir=temp_config_dir)

    def test_init_creates_directories(self, temp_config_dir):
        """ConfigManager should create config and logs directories."""
        config_manager = ConfigManager(config_dir=temp_config_dir)
        assert Path(temp_config_dir).exists()
        assert (Path(temp_config_dir) / "logs").exists()

    def test_load_returns_defaults_when_no_file(self, config_manager):
        """Load should return defaults when no settings file exists."""
        settings = config_manager.load()
        assert isinstance(settings, Settings)
        assert settings.jellyfin_url == "http://localhost:8096"

    def test_save_creates_file(self, config_manager, temp_config_dir):
        """Save should create settings file."""
        settings = Settings(jellyfin_url="http://test:8096")
        config_manager.save(settings)

        settings_file = Path(temp_config_dir) / "settings.json"
        assert settings_file.exists()

    def test_save_and_load_roundtrip(self, config_manager):
        """Saved settings should be loadable."""
        original = Settings(
            jellyfin_url="http://192.168.1.50:8096",
            jellyfin_api_key="my-secret-key",
            cache_threshold=75,
            dry_run=False
        )
        config_manager.save(original)
        loaded = config_manager.load()

        assert loaded.jellyfin_url == original.jellyfin_url
        assert loaded.jellyfin_api_key == original.jellyfin_api_key
        assert loaded.cache_threshold == original.cache_threshold
        assert loaded.dry_run == original.dry_run

    def test_update_partial_settings(self, config_manager):
        """Update should only change specified fields."""
        # Save initial settings
        initial = Settings(jellyfin_url="http://initial:8096", cache_threshold=80)
        config_manager.save(initial)

        # Update only cache_threshold
        updated = config_manager.update(cache_threshold=90)

        assert updated.cache_threshold == 90
        assert updated.jellyfin_url == "http://initial:8096"

    def test_update_persists_changes(self, config_manager):
        """Update should persist changes to disk."""
        initial = Settings()
        config_manager.save(initial)

        config_manager.update(jellyfin_url="http://updated:8096")

        # Load fresh from disk
        loaded = config_manager.load()
        assert loaded.jellyfin_url == "http://updated:8096"

    def test_get_env_vars(self, config_manager):
        """get_env_vars should return correct environment variables."""
        settings = Settings(
            jellyfin_url="http://test:8096",
            jellyfin_api_key="test-key",
            jellyfin_user_ids="user1 user2",
            cache_threshold=85,
            dry_run=False
        )
        config_manager.save(settings)

        env_vars = config_manager.get_env_vars()

        assert env_vars['JELLYFIN_URL'] == "http://test:8096"
        assert env_vars['JELLYFIN_API_KEY'] == "test-key"
        assert env_vars['USER_IDS'] == "user1 user2"
        assert env_vars['CACHE_THRESHOLD'] == "85"
        assert env_vars['DRY_RUN'] == "false"

    def test_get_env_vars_dry_run_true(self, config_manager):
        """DRY_RUN env var should be 'true' when dry_run is True."""
        settings = Settings(dry_run=True)
        config_manager.save(settings)

        env_vars = config_manager.get_env_vars()
        assert env_vars['DRY_RUN'] == "true"

    def test_get_log_file(self, config_manager, temp_config_dir):
        """get_log_file should return correct path."""
        log_file = config_manager.get_log_file()
        expected = Path(temp_config_dir) / "logs" / "smart_mover.log"
        assert log_file == expected

    def test_read_logs_empty_when_no_file(self, config_manager):
        """read_logs should return empty string when no log file."""
        content = config_manager.read_logs()
        assert content == ""

    def test_read_logs_returns_content(self, config_manager, temp_config_dir):
        """read_logs should return log file content."""
        log_file = Path(temp_config_dir) / "logs" / "smart_mover.log"
        log_file.write_text("[INFO] Test log line 1\n[ERROR] Test log line 2\n")

        content = config_manager.read_logs()
        assert "[INFO] Test log line 1" in content
        assert "[ERROR] Test log line 2" in content

    def test_read_logs_with_line_limit(self, config_manager, temp_config_dir):
        """read_logs should respect line limit."""
        log_file = Path(temp_config_dir) / "logs" / "smart_mover.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        content = config_manager.read_logs(lines=2)
        lines = content.strip().split('\n')
        assert len(lines) == 2
        assert "Line 4" in content
        assert "Line 5" in content

    def test_read_logs_with_level_filter(self, config_manager, temp_config_dir):
        """read_logs should filter by log level."""
        log_file = Path(temp_config_dir) / "logs" / "smart_mover.log"
        log_file.write_text("[INFO] Info message\n[ERROR] Error message\n[DEBUG] Debug message\n")

        content = config_manager.read_logs(level='ERROR')
        assert "[ERROR] Error message" in content
        assert "[INFO]" not in content
        assert "[DEBUG]" not in content

    def test_clear_logs(self, config_manager, temp_config_dir):
        """clear_logs should delete log file."""
        log_file = Path(temp_config_dir) / "logs" / "smart_mover.log"
        log_file.write_text("Some log content")
        assert log_file.exists()

        config_manager.clear_logs()
        assert not log_file.exists()

    def test_clear_logs_no_error_when_no_file(self, config_manager):
        """clear_logs should not error when no log file exists."""
        config_manager.clear_logs()  # Should not raise

    def test_load_handles_invalid_json(self, config_manager, temp_config_dir):
        """Load should return defaults on invalid JSON."""
        settings_file = Path(temp_config_dir) / "settings.json"
        settings_file.write_text("not valid json {{{")

        settings = config_manager.load()
        assert settings == Settings()

    def test_load_handles_invalid_data(self, config_manager, temp_config_dir):
        """Load should return defaults on invalid data."""
        settings_file = Path(temp_config_dir) / "settings.json"
        settings_file.write_text('{"cache_threshold": 150}')  # Invalid value

        settings = config_manager.load()
        assert settings == Settings()


class TestConfigManagerRunHistory:
    """Tests for ConfigManager run history methods."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create a ConfigManager with temporary directory."""
        return ConfigManager(config_dir=temp_config_dir)

    def test_get_history_file_path(self, config_manager, temp_config_dir):
        """get_history_file should return config_dir/run_history.json."""
        expected = Path(temp_config_dir) / "run_history.json"
        assert config_manager.get_history_file() == expected

    def test_save_run_creates_file(self, config_manager, temp_config_dir):
        """First save_run should create the history file."""
        history_file = Path(temp_config_dir) / "run_history.json"
        assert not history_file.exists()

        config_manager.save_run({"timestamp": "2024-01-01T10:00:00", "success": True})
        assert history_file.exists()

    def test_save_run_prepends_record(self, config_manager):
        """Newest record should be first in the list."""
        config_manager.save_run({"id": 1, "timestamp": "2024-01-01T10:00:00"})
        config_manager.save_run({"id": 2, "timestamp": "2024-01-01T11:00:00"})

        history = config_manager.load_run_history()
        assert history[0]["id"] == 2
        assert history[1]["id"] == 1

    def test_save_run_truncates_at_50(self, config_manager):
        """History should be truncated to 50 records."""
        for i in range(51):
            config_manager.save_run({"id": i, "timestamp": f"2024-01-01T{i:02d}:00:00"})

        history = config_manager.load_run_history()
        assert len(history) == 50
        # Most recent (id=50) should be first
        assert history[0]["id"] == 50

    def test_load_run_history_empty(self, config_manager):
        """load_run_history should return empty list when no file."""
        assert config_manager.load_run_history() == []

    def test_load_run_history_returns_data(self, config_manager):
        """Saved records should be loadable."""
        record = {"timestamp": "2024-01-01T10:00:00", "success": True, "duration_seconds": 5.0}
        config_manager.save_run(record)

        history = config_manager.load_run_history()
        assert len(history) == 1
        assert history[0]["success"] is True
        assert history[0]["duration_seconds"] == 5.0

    def test_load_run_history_invalid_json(self, config_manager, temp_config_dir):
        """Corrupt history file should return empty list."""
        history_file = Path(temp_config_dir) / "run_history.json"
        history_file.write_text("not valid json {{{")

        assert config_manager.load_run_history() == []

    def test_clear_run_history(self, config_manager, temp_config_dir):
        """clear_run_history should delete the history file."""
        config_manager.save_run({"timestamp": "2024-01-01T10:00:00"})
        history_file = Path(temp_config_dir) / "run_history.json"
        assert history_file.exists()

        config_manager.clear_run_history()
        assert not history_file.exists()

    def test_clear_run_history_no_error_when_missing(self, config_manager):
        """clear_run_history should not error when no file exists."""
        config_manager.clear_run_history()  # Should not raise
