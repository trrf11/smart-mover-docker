# Tests for scheduler

import tempfile
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.config_manager import ConfigManager, Settings
from app.runner import ScriptRunner, RunResult
from app.scheduler import get_timezone, SmartMoverScheduler, SCHEDULED_RUN_JOB_ID


class TestGetTimezone:
    """Tests for the get_timezone function."""

    def test_timezone_from_env(self, monkeypatch):
        """get_timezone should return TZ env var when set."""
        monkeypatch.setenv("TZ", "America/New_York")
        assert get_timezone() == "America/New_York"

    def test_timezone_defaults_to_utc(self, monkeypatch):
        """get_timezone should default to UTC when TZ is not set."""
        monkeypatch.delenv("TZ", raising=False)
        assert get_timezone() == "UTC"


class TestSmartMoverScheduler:
    """Tests for the SmartMoverScheduler class."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create a temporary config directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Create a ConfigManager with temporary directory."""
        return ConfigManager(config_dir=temp_config_dir)

    @pytest.fixture
    def runner(self, config_manager):
        """Create a ScriptRunner."""
        return ScriptRunner(config_manager)

    @pytest.fixture
    def sched(self, runner, config_manager):
        """Create a SmartMoverScheduler and ensure cleanup."""
        s = SmartMoverScheduler(runner, config_manager)
        yield s
        if s._started:
            s.stop()

    def test_init(self, sched):
        """Scheduler should be created but not started."""
        assert sched._started is False
        assert sched.scheduler is not None

    def test_start(self, sched, config_manager):
        """start() should start the scheduler."""
        # Save default settings (schedule_enabled=False) so _update_job doesn't fail
        config_manager.save(Settings())
        sched.start()
        assert sched._started is True

    def test_start_idempotent(self, sched, config_manager):
        """Calling start() twice should not error."""
        config_manager.save(Settings())
        sched.start()
        sched.start()  # Should not raise
        assert sched._started is True

    def test_stop(self, sched, config_manager):
        """stop() should stop the scheduler."""
        config_manager.save(Settings())
        sched.start()
        assert sched._started is True
        sched.stop()
        assert sched._started is False

    def test_stop_when_not_started(self, sched):
        """stop() when not started should not error."""
        sched.stop()  # Should not raise
        assert sched._started is False

    def test_update_job_enabled_valid_cron(self, sched, config_manager):
        """Job should be added when schedule_enabled=True with valid cron."""
        config_manager.save(Settings(schedule_enabled=True, schedule_cron="0 2 * * *"))
        sched.start()
        job = sched.scheduler.get_job(SCHEDULED_RUN_JOB_ID)
        assert job is not None

    def test_update_job_disabled(self, sched, config_manager):
        """No job should exist when schedule_enabled=False."""
        config_manager.save(Settings(schedule_enabled=False))
        sched.start()
        job = sched.scheduler.get_job(SCHEDULED_RUN_JOB_ID)
        assert job is None

    def test_update_job_invalid_cron(self, sched, config_manager):
        """Invalid cron should log error and not add job."""
        config_manager.save(Settings(schedule_enabled=True, schedule_cron="invalid cron"))
        sched.start()
        job = sched.scheduler.get_job(SCHEDULED_RUN_JOB_ID)
        assert job is None

    def test_update_schedule_when_started(self, sched, config_manager):
        """update_schedule() when started should call _update_job."""
        config_manager.save(Settings(schedule_enabled=False))
        sched.start()
        assert sched.scheduler.get_job(SCHEDULED_RUN_JOB_ID) is None

        # Enable schedule and update
        config_manager.save(Settings(schedule_enabled=True, schedule_cron="0 3 * * *"))
        sched.update_schedule()
        job = sched.scheduler.get_job(SCHEDULED_RUN_JOB_ID)
        assert job is not None

    def test_update_schedule_when_not_started(self, sched, config_manager):
        """update_schedule() when not started should be a no-op."""
        config_manager.save(Settings(schedule_enabled=True, schedule_cron="0 3 * * *"))
        sched.update_schedule()  # Should not raise, should not add job
        job = sched.scheduler.get_job(SCHEDULED_RUN_JOB_ID)
        assert job is None

    def test_get_next_run_time_with_job(self, sched, config_manager):
        """get_next_run_time() should return a datetime when job is scheduled."""
        config_manager.save(Settings(schedule_enabled=True, schedule_cron="0 2 * * *"))
        sched.start()
        next_run = sched.get_next_run_time()
        assert isinstance(next_run, datetime)

    def test_get_next_run_time_no_job(self, sched, config_manager):
        """get_next_run_time() should return None when no job."""
        config_manager.save(Settings(schedule_enabled=False))
        sched.start()
        assert sched.get_next_run_time() is None

    def test_is_enabled_with_job(self, sched, config_manager):
        """is_enabled() should return True when job is configured."""
        config_manager.save(Settings(schedule_enabled=True, schedule_cron="0 2 * * *"))
        sched.start()
        assert sched.is_enabled() is True

    def test_is_enabled_no_job(self, sched, config_manager):
        """is_enabled() should return False when no job."""
        config_manager.save(Settings(schedule_enabled=False))
        sched.start()
        assert sched.is_enabled() is False

    def test_get_timezone_method(self, sched):
        """get_timezone() should return the configured timezone."""
        tz = sched.get_timezone()
        assert isinstance(tz, str)
        assert len(tz) > 0

    def test_run_scheduled_success(self, sched, config_manager, temp_config_dir):
        """_run_scheduled should call runner.run() and log on success."""
        config_manager.save(Settings(dry_run=True))
        mock_result = RunResult(
            success=True,
            output="Done",
            error="",
            return_code=0,
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 0, 30),
            dry_run=True
        )
        with patch.object(sched.script_runner, 'run', return_value=mock_result) as mock_run:
            sched._run_scheduled()
            mock_run.assert_called_once_with(dry_run=True)

        # Verify log file was written
        log_file = config_manager.get_log_file()
        assert log_file.exists()
        log_content = log_file.read_text()
        assert "Scheduled run triggered" in log_content

    def test_run_scheduled_failure(self, sched, config_manager, temp_config_dir):
        """_run_scheduled should handle runner.run() failure."""
        config_manager.save(Settings(dry_run=False))
        mock_result = RunResult(
            success=False,
            output="",
            error="Script failed",
            return_code=1,
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 0, 5),
            dry_run=False
        )
        with patch.object(sched.script_runner, 'run', return_value=mock_result) as mock_run:
            sched._run_scheduled()
            mock_run.assert_called_once_with(dry_run=False)
