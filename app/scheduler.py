# Scheduler
# Cron-based scheduling for automated runs

import logging
import os
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job

if TYPE_CHECKING:
    from app.runner import ScriptRunner
    from app.config_manager import ConfigManager

logger = logging.getLogger(__name__)


def get_timezone() -> str:
    """Get timezone from TZ environment variable, defaulting to UTC."""
    return os.environ.get("TZ", "UTC")

# Job ID for the scheduled run
SCHEDULED_RUN_JOB_ID = "smart_mover_scheduled_run"


class SmartMoverScheduler:
    """Manages scheduled runs of the smart mover script."""

    def __init__(self, script_runner: "ScriptRunner", config_manager: "ConfigManager"):
        self.script_runner = script_runner
        self.config_manager = config_manager
        self.timezone = get_timezone()
        self.scheduler = BackgroundScheduler(timezone=self.timezone)
        self._started = False

    def start(self) -> None:
        """Start the scheduler and configure the job based on settings."""
        if self._started:
            return

        self.scheduler.start()
        self._started = True
        logger.info(f"Scheduler started (timezone: {self.timezone})")

        # Configure job based on current settings
        self._update_job()

    def stop(self) -> None:
        """Stop the scheduler."""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler stopped")

    def _update_job(self) -> None:
        """Update or remove the scheduled job based on settings."""
        settings = self.config_manager.load()

        # Remove existing job if present
        existing_job = self.scheduler.get_job(SCHEDULED_RUN_JOB_ID)
        if existing_job:
            self.scheduler.remove_job(SCHEDULED_RUN_JOB_ID)
            logger.info("Removed existing scheduled job")

        # Add new job if scheduling is enabled
        if settings.schedule_enabled and settings.schedule_cron:
            try:
                trigger = CronTrigger.from_crontab(settings.schedule_cron)
                self.scheduler.add_job(
                    self._run_scheduled,
                    trigger=trigger,
                    id=SCHEDULED_RUN_JOB_ID,
                    name="Smart Mover Scheduled Run",
                    replace_existing=True
                )
                next_run = self.get_next_run_time()
                logger.info(f"Scheduled job configured with cron '{settings.schedule_cron}', next run: {next_run}")
            except ValueError as e:
                logger.error(f"Invalid cron expression '{settings.schedule_cron}': {e}")

    def update_schedule(self) -> None:
        """Update the schedule based on current settings. Call after settings change."""
        if not self._started:
            return
        self._update_job()

    def _run_scheduled(self) -> None:
        """Execute the scheduled run."""
        settings = self.config_manager.load()
        dry_run = settings.dry_run

        logger.info(f"Starting scheduled run (dry_run={dry_run})")

        # Log to the application log file
        log_file = self.config_manager.get_log_file()
        with open(log_file, 'a') as f:
            f.write(f"\n[{datetime.now().isoformat()}] [INFO] Scheduled run triggered (cron: {settings.schedule_cron})\n")

        try:
            result = self.script_runner.run(dry_run=dry_run)
            if result.success:
                logger.info(f"Scheduled run completed successfully in {result.duration_seconds:.1f}s")
            else:
                logger.error(f"Scheduled run failed with return code {result.return_code}")
        except Exception as e:
            logger.exception(f"Scheduled run encountered an error: {e}")

    def get_next_run_time(self) -> Optional[datetime]:
        """Get the next scheduled run time."""
        job = self.scheduler.get_job(SCHEDULED_RUN_JOB_ID)
        if job:
            return job.next_run_time
        return None

    def is_enabled(self) -> bool:
        """Check if scheduling is enabled and a job is configured."""
        return self.scheduler.get_job(SCHEDULED_RUN_JOB_ID) is not None

    def get_timezone(self) -> str:
        """Get the scheduler's configured timezone."""
        return self.timezone
