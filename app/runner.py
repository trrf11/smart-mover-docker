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
    current_status: str = ""


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
            self.state.current_status = "Starting..."

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
        log_file_lock = threading.Lock()

        output_lines = []
        error_lines = []

        # Open log file and write header immediately
        mode = "DRY RUN" if actual_dry_run else "LIVE"
        log_handle = open(log_file, 'a')
        log_handle.write(f"\n{'='*60}\n")
        log_handle.write(f"[{start_time.isoformat()}] Smart Mover Run ({mode}) - RUNNING\n")
        log_handle.write(f"{'='*60}\n\n")
        log_handle.flush()

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

            # Read output in real-time and stream to log file
            def read_stream(stream, lines_list, is_error=False):
                for line in iter(stream.readline, ''):
                    lines_list.append(line)
                    self.state.current_output += line
                    # Parse STATUS: lines for current status
                    if line.startswith("STATUS: "):
                        self.state.current_status = line[8:].strip()
                    # Write to log file immediately (skip STATUS lines)
                    if not line.startswith("STATUS: "):
                        with log_file_lock:
                            log_handle.write(line)
                            log_handle.flush()
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
            log_handle.write(f"ERROR: {e}\n")
            return_code = -1
            success = False
        except Exception as e:
            error_lines.append(f"Unexpected error: {str(e)}")
            log_handle.write(f"ERROR: Unexpected error: {str(e)}\n")
            return_code = -1
            success = False

        end_time = datetime.now()
        output = ''.join(output_lines)
        error = ''.join(error_lines)

        # Write footer to log file
        status = "SUCCESS" if success else "FAILED"
        duration = (end_time - start_time).total_seconds()
        if error and success:  # Has stderr but didn't fail
            log_handle.write(f"\n--- STDERR ---\n{error}")
        log_handle.write(f"\n{'='*60}\n")
        log_handle.write(f"Completed: {status} in {duration:.1f} seconds\n")
        log_handle.write(f"{'='*60}\n")
        log_handle.close()

        result = RunResult(
            success=success,
            output=output,
            error=error,
            return_code=return_code,
            start_time=start_time,
            end_time=end_time,
            dry_run=actual_dry_run
        )

        # Count files moved from output
        files_moved = self._count_files_moved(output)

        # Filter STATUS lines from log output for storage
        log_output = '\n'.join(
            line for line in output.split('\n')
            if not line.startswith("STATUS: ")
        ).strip()

        # Save to run history
        run_record = {
            "timestamp": start_time.isoformat(),
            "dry_run": actual_dry_run,
            "success": success,
            "duration_seconds": round(duration, 1),
            "files_moved": files_moved,
            "log": log_output
        }
        self.config.save_run(run_record)

        with self._lock:
            self.state.is_running = False
            self.state.last_run = result
            self.state.current_output = ""
            self.state.current_status = ""

        return result

    def _count_files_moved(self, output: str) -> int:
        """Count number of files moved from script output."""
        count = 0
        for line in output.split('\n'):
            # Skip STATUS: lines to avoid double-counting
            if line.startswith("STATUS: "):
                continue
            # Look for rsync success lines or move confirmations
            if 'Moving:' in line or 'Moved:' in line:
                count += 1
            elif '[DRY RUN] Would move:' in line:
                count += 1
        return count

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
                "current_status": self.state.current_status,
                "last_run": last_run_info
            }
