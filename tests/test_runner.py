# Tests for script runner

import tempfile
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config_manager import ConfigManager, Settings
from app.runner import RunResult, RunnerState, ScriptRunner


class TestRunResult:
    """Tests for the RunResult dataclass."""

    def test_duration_seconds(self):
        """duration_seconds should calculate time difference."""
        start = datetime(2024, 1, 1, 10, 0, 0)
        end = datetime(2024, 1, 1, 10, 0, 30)

        result = RunResult(
            success=True,
            output="test",
            error="",
            return_code=0,
            start_time=start,
            end_time=end,
            dry_run=True
        )

        assert result.duration_seconds == 30.0

    def test_duration_seconds_subsecond(self):
        """duration_seconds should handle subsecond precision."""
        start = datetime(2024, 1, 1, 10, 0, 0, 0)
        end = datetime(2024, 1, 1, 10, 0, 0, 500000)  # 0.5 seconds

        result = RunResult(
            success=True,
            output="",
            error="",
            return_code=0,
            start_time=start,
            end_time=end,
            dry_run=False
        )

        assert result.duration_seconds == 0.5


class TestRunnerState:
    """Tests for the RunnerState dataclass."""

    def test_default_state(self):
        """Default state should be not running with no last run."""
        state = RunnerState()
        assert state.is_running is False
        assert state.last_run is None
        assert state.current_output == ""


class TestScriptRunner:
    """Tests for the ScriptRunner class."""

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
        """Create a ScriptRunner with mock config."""
        return ScriptRunner(config_manager)

    def test_init(self, config_manager):
        """ScriptRunner should initialize with correct state."""
        runner = ScriptRunner(config_manager)
        assert runner.config == config_manager
        assert runner.state.is_running is False
        assert runner.state.last_run is None

    def test_get_status_initial(self, runner):
        """get_status should return initial state correctly."""
        status = runner.get_status()
        assert status['is_running'] is False
        assert status['current_output'] == ""
        assert status['last_run'] is None

    def test_get_status_with_last_run(self, runner):
        """get_status should include last run info when available."""
        # Manually set a last run
        runner.state.last_run = RunResult(
            success=True,
            output="test output",
            error="",
            return_code=0,
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 10, 0, 30),
            dry_run=True
        )

        status = runner.get_status()
        assert status['last_run'] is not None
        assert status['last_run']['success'] is True
        assert status['last_run']['dry_run'] is True
        assert status['last_run']['duration_seconds'] == 30.0
        assert status['last_run']['return_code'] == 0

    def test_run_returns_error_when_already_running(self, runner):
        """run should return error if script is already running."""
        runner.state.is_running = True

        result = runner.run()

        assert result.success is False
        assert "already running" in result.error

    @patch.object(ScriptRunner, 'SCRIPT_PATH', Path('/nonexistent/script.sh'))
    def test_run_handles_missing_script(self, runner, config_manager):
        """run should handle missing script file."""
        settings = Settings()
        config_manager.save(settings)

        result = runner.run()

        assert result.success is False
        assert "not found" in result.error.lower() or "not found" in result.output.lower()

    def test_run_uses_config_dry_run_when_not_specified(self, runner, config_manager, temp_config_dir):
        """run should use config dry_run when not specified in call."""
        settings = Settings(dry_run=True)
        config_manager.save(settings)

        # Create a simple test script
        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Hello'\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            result = runner.run()

        assert result.dry_run is True

    def test_run_overrides_dry_run_when_specified(self, runner, config_manager, temp_config_dir):
        """run should override config dry_run when specified."""
        settings = Settings(dry_run=True)
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Hello'\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            result = runner.run(dry_run=False)

        assert result.dry_run is False

    def test_run_captures_stdout(self, runner, config_manager, temp_config_dir):
        """run should capture script stdout."""
        settings = Settings()
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Test output line 1'\necho 'Test output line 2'\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            result = runner.run()

        assert "Test output line 1" in result.output
        assert "Test output line 2" in result.output

    def test_run_captures_stderr(self, runner, config_manager, temp_config_dir):
        """run should capture script stderr."""
        settings = Settings()
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Error message' >&2\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            result = runner.run()

        assert "Error message" in result.error

    def test_run_returns_success_on_zero_exit(self, runner, config_manager, temp_config_dir):
        """run should return success=True on exit code 0."""
        settings = Settings()
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\nexit 0\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            result = runner.run()

        assert result.success is True
        assert result.return_code == 0

    def test_run_returns_failure_on_nonzero_exit(self, runner, config_manager, temp_config_dir):
        """run should return success=False on non-zero exit code."""
        settings = Settings()
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\nexit 1\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            result = runner.run()

        assert result.success is False
        assert result.return_code == 1

    def test_run_writes_to_log_file(self, runner, config_manager, temp_config_dir):
        """run should append results to log file."""
        settings = Settings()
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Logged output'\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            runner.run()

        log_file = config_manager.get_log_file()
        assert log_file.exists()
        log_content = log_file.read_text()
        assert "Logged output" in log_content
        assert "Smart Mover Run" in log_content

    def test_run_updates_state_after_completion(self, runner, config_manager, temp_config_dir):
        """run should update state.last_run after completion."""
        settings = Settings()
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\nexit 0\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            result = runner.run()

        assert runner.state.last_run is not None
        assert runner.state.last_run.success == result.success
        assert runner.state.is_running is False

    def test_run_passes_env_vars_to_script(self, runner, config_manager, temp_config_dir):
        """run should pass environment variables to script."""
        settings = Settings(
            jellyfin_url="http://test-server:8096",
            cache_threshold=75
        )
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho \"URL=$JELLYFIN_URL\"\necho \"THRESHOLD=$CACHE_THRESHOLD\"\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            result = runner.run()

        assert "URL=http://test-server:8096" in result.output
        assert "THRESHOLD=75" in result.output

    def test_run_on_output_callback(self, runner, config_manager, temp_config_dir):
        """run should call on_output callback for each line."""
        settings = Settings()
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Line 1'\necho 'Line 2'\n")
        script_path.chmod(0o755)

        received_lines = []

        def on_output(line):
            received_lines.append(line)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            runner.run(on_output=on_output)

        assert len(received_lines) >= 2
        assert any('Line 1' in line for line in received_lines)
        assert any('Line 2' in line for line in received_lines)

    def test_count_files_moved_moving(self, runner):
        """_count_files_moved should count 'Moving:' lines."""
        output = "Starting...\nMoving: /path/to/file1.mkv\nMoving: /path/to/file2.mkv\nDone"
        assert runner._count_files_moved(output) == 2

    def test_count_files_moved_dry_run(self, runner):
        """_count_files_moved should count '[DRY RUN] Would move:' lines."""
        output = "[DRY RUN] Would move: /path/to/movie.mkv\n[DRY RUN] Would move: /path/to/show.mkv\n"
        assert runner._count_files_moved(output) == 2

    def test_count_files_moved_mixed(self, runner):
        """_count_files_moved should count both Moving and DRY RUN patterns."""
        output = "Moving: /path/file1.mkv\n[DRY RUN] Would move: /path/file2.mkv\nMoved: /path/file3.mkv\n"
        assert runner._count_files_moved(output) == 3

    def test_count_files_moved_none(self, runner):
        """_count_files_moved should return 0 when no matching lines."""
        output = "Starting smart mover...\nChecking cache usage...\nDone.\n"
        assert runner._count_files_moved(output) == 0

    def test_run_parses_status_lines(self, runner, config_manager, temp_config_dir):
        """STATUS: lines should update current_status but not appear in log file."""
        settings = Settings()
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'STATUS: Checking movies'\necho 'Regular output'\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            result = runner.run()

        # STATUS line should be in output (captured from stdout)
        assert "STATUS: Checking movies" in result.output
        # Regular output should be in log file
        log_content = config_manager.get_log_file().read_text()
        assert "Regular output" in log_content
        # STATUS line should NOT be in log file
        assert "STATUS: Checking movies" not in log_content

    def test_run_saves_to_history(self, runner, config_manager, temp_config_dir):
        """After run, a record should be saved to run history."""
        settings = Settings()
        config_manager.save(settings)

        script_path = Path(temp_config_dir) / "test_script.sh"
        script_path.write_text("#!/bin/bash\necho 'Moving: /path/to/file.mkv'\nexit 0\n")
        script_path.chmod(0o755)

        with patch.object(ScriptRunner, 'SCRIPT_PATH', script_path):
            runner.run(dry_run=True)

        history = config_manager.load_run_history()
        assert len(history) == 1
        assert history[0]["success"] is True
        assert history[0]["dry_run"] is True
        assert history[0]["files_moved"] == 1
