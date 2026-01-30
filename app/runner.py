# Script Runner
# Executes the bash script and captures output

import subprocess
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field

from app.config_manager import ConfigManager


@dataclass
class RunResult:
    """Result of a script execution."""
    success: bool
    output: str
    error: str
    return_code: int
    start_time: datetime
    end_time: datetime
    dry_run: bool

    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()


@dataclass
class RunnerState:
    """Current state of the runner."""
    is_running: bool = False
    last_run: Optional[RunResult] = None
    current_output: str = ""


class ScriptRunner:
    """Executes the smart mover bash script."""

    SCRIPT_PATH = Path("/app/scripts/jellyfin_smart_mover.sh")

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.state = RunnerState()
        self._lock = threading.Lock()

    def run(self, dry_run: Optional[bool] = None, on_output: Optional[Callable[[str], None]] = None) -> RunResult:
        """
        Execute the smart mover script.

        Args:
            dry_run: Override dry_run setting (uses config if None)
            on_output: Callback for real-time output

        Returns:
            RunResult with execution details
        """
        with self._lock:
            if self.state.is_running:
                return RunResult(
                    success=False,
                    output="",
                    error="Script is already running",
                    return_code=-1,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    dry_run=dry_run or self.config.load().dry_run
                )
            self.state.is_running = True
            self.state.current_output = ""

        start_time = datetime.now()
        settings = self.config.load()

        # Get environment variables and apply dry_run override
        env = os.environ.copy()
        env.update(self.config.get_env_vars())

        if dry_run is not None:
            env['DRY_RUN'] = 'true' if dry_run else 'false'
            actual_dry_run = dry_run
        else:
            actual_dry_run = settings.dry_run

        # Log file for persistent output
        log_file = self.config.get_log_file()

        output_lines = []
        error_lines = []

        try:
            # Check if script exists
            if not self.SCRIPT_PATH.exists():
                raise FileNotFoundError(f"Script not found: {self.SCRIPT_PATH}")

            process = subprocess.Popen(
                ['bash', str(self.SCRIPT_PATH)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1
            )

            # Read output in real-time
            def read_stream(stream, lines_list, is_error=False):
                for line in iter(stream.readline, ''):
                    lines_list.append(line)
                    self.state.current_output += line
                    if on_output:
                        on_output(line)
                stream.close()

            stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, output_lines))
            stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, error_lines, True))

            stdout_thread.start()
            stderr_thread.start()

            process.wait()
            stdout_thread.join()
            stderr_thread.join()

            return_code = process.returncode
            success = return_code == 0

        except FileNotFoundError as e:
            error_lines.append(str(e))
            return_code = -1
            success = False
        except Exception as e:
            error_lines.append(f"Unexpected error: {str(e)}")
            return_code = -1
            success = False

        end_time = datetime.now()
        output = ''.join(output_lines)
        error = ''.join(error_lines)

        # Write to log file
        self._write_log(log_file, output, error, start_time, end_time, actual_dry_run, success)

        result = RunResult(
            success=success,
            output=output,
            error=error,
            return_code=return_code,
            start_time=start_time,
            end_time=end_time,
            dry_run=actual_dry_run
        )

        with self._lock:
            self.state.is_running = False
            self.state.last_run = result
            self.state.current_output = ""

        return result

    def _write_log(self, log_file: Path, output: str, error: str,
                   start_time: datetime, end_time: datetime,
                   dry_run: bool, success: bool) -> None:
        """Append run results to log file."""
        mode = "DRY RUN" if dry_run else "LIVE"
        status = "SUCCESS" if success else "FAILED"
        duration = (end_time - start_time).total_seconds()

        log_entry = f"""
{'='*60}
[{start_time.isoformat()}] Smart Mover Run ({mode}) - {status}
Duration: {duration:.1f} seconds
{'='*60}

{output}
"""
        if error:
            log_entry += f"\n--- ERRORS ---\n{error}\n"

        log_entry += f"\n{'='*60}\n"

        with open(log_file, 'a') as f:
            f.write(log_entry)

    def get_status(self) -> dict:
        """Get current runner status."""
        with self._lock:
            last_run_info = None
            if self.state.last_run:
                lr = self.state.last_run
                last_run_info = {
                    "success": lr.success,
                    "dry_run": lr.dry_run,
                    "start_time": lr.start_time.isoformat(),
                    "end_time": lr.end_time.isoformat(),
                    "duration_seconds": lr.duration_seconds,
                    "return_code": lr.return_code
                }

            return {
                "is_running": self.state.is_running,
                "current_output": self.state.current_output,
                "last_run": last_run_info
            }
