# Configuration Manager
# Handles loading, saving, and validating settings

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    """Application settings schema."""
    jellyfin_url: str = Field(default="http://localhost:8096")
    jellyfin_api_key: str = Field(default="")
    jellyfin_user_ids: str = Field(default="")
    cache_threshold: int = Field(default=90, ge=1, le=99)
    cache_drive: str = Field(default="/mnt/cache")
    array_path: str = Field(default="/mnt/disk1")
    movies_pool: str = Field(default="movies-pool")
    tv_pool: str = Field(default="tv-pool")
    jellyfin_path_prefix: str = Field(default="/media/media")
    local_path_prefix: str = Field(default="/mnt/cache/media")
    dry_run: bool = Field(default=True)
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    schedule_enabled: bool = Field(default=False)
    schedule_cron: str = Field(default="0 */6 * * *")

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = ['DEBUG', 'INFO', 'ERROR']
        if v.upper() not in allowed:
            raise ValueError(f'log_level must be one of {allowed}')
        return v.upper()

    @field_validator('jellyfin_url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        if v and not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError('jellyfin_url must start with http:// or https://')
        return v.rstrip('/')


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_dir: str = "/config"):
        self.config_dir = Path(config_dir)
        self.settings_file = self.config_dir / "settings.json"
        self.logs_dir = self.config_dir / "logs"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create config and logs directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> Settings:
        """Load settings from file, returning defaults if not found."""
        if not self.settings_file.exists():
            return Settings()

        try:
            with open(self.settings_file, 'r') as f:
                data = json.load(f)
            return Settings(**data)
        except (json.JSONDecodeError, ValueError):
            return Settings()

    def save(self, settings: Settings) -> None:
        """Save settings to file."""
        with open(self.settings_file, 'w') as f:
            json.dump(settings.model_dump(), f, indent=2)

    def update(self, **kwargs) -> Settings:
        """Update specific settings and save."""
        current = self.load()
        updated_data = current.model_dump()
        updated_data.update(kwargs)
        new_settings = Settings(**updated_data)
        self.save(new_settings)
        return new_settings

    def get_env_vars(self) -> dict:
        """Generate environment variables for bash script."""
        settings = self.load()
        return {
            'JELLYFIN_URL': settings.jellyfin_url,
            'JELLYFIN_API_KEY': settings.jellyfin_api_key,
            'USER_IDS': settings.jellyfin_user_ids,
            'CACHE_THRESHOLD': str(settings.cache_threshold),
            'CACHE_DRIVE': settings.cache_drive,
            'ARRAY_PATH': settings.array_path,
            'MOVIES_POOL': settings.movies_pool,
            'TV_POOL': settings.tv_pool,
            'JELLYFIN_PATH_PREFIX': settings.jellyfin_path_prefix,
            'LOCAL_PATH_PREFIX': settings.local_path_prefix,
            'DRY_RUN': 'true' if settings.dry_run else 'false',
            'DEBUG': 'true' if settings.debug else 'false',
        }

    def get_log_file(self) -> Path:
        """Get path to the main log file."""
        return self.logs_dir / "smart_mover.log"

    def read_logs(self, lines: Optional[int] = None, level: Optional[str] = None) -> str:
        """Read log file contents, optionally filtering by level."""
        log_file = self.get_log_file()
        if not log_file.exists():
            return ""

        with open(log_file, 'r') as f:
            content = f.readlines()

        if level and level != 'ALL':
            content = [line for line in content if f'[{level}]' in line]

        if lines:
            content = content[-lines:]

        return ''.join(content)

    def clear_logs(self) -> None:
        """Clear the log file."""
        log_file = self.get_log_file()
        if log_file.exists():
            log_file.unlink()

    # Run History Management
    def get_history_file(self) -> Path:
        """Get path to the run history file."""
        return self.config_dir / "run_history.json"

    def save_run(self, run_record: dict) -> None:
        """Save a run record to history."""
        history = self.load_run_history()
        history.insert(0, run_record)
        # Keep only the last 50 runs
        history = history[:50]
        with open(self.get_history_file(), 'w') as f:
            json.dump(history, f, indent=2)

    def load_run_history(self) -> List[dict]:
        """Load run history from file."""
        history_file = self.get_history_file()
        if not history_file.exists():
            return []
        try:
            with open(history_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return []

    def clear_run_history(self) -> None:
        """Clear the run history."""
        history_file = self.get_history_file()
        if history_file.exists():
            history_file.unlink()
