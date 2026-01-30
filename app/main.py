# Smart Mover Docker - FastAPI Application
# Main entry point for the web application

import os
from pathlib import Path
from typing import Optional

import psutil
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.config_manager import ConfigManager, Settings
from app.runner import ScriptRunner

# Version - update this when making changes
APP_VERSION = "1.2.0"

# Initialize app
app = FastAPI(
    title="Smart Mover",
    description="Intelligently move watched media from cache to array",
    version=APP_VERSION
)

# Configuration
CONFIG_DIR = os.environ.get('CONFIG_DIR', '/config')
config_manager = ConfigManager(config_dir=CONFIG_DIR)
script_runner = ScriptRunner(config_manager)

# Static files and templates
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# --- Request/Response Models ---

class RunRequest(BaseModel):
    dry_run: Optional[bool] = None


class RunResponse(BaseModel):
    success: bool
    message: str
    dry_run: bool
    output: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


class CacheUsageResponse(BaseModel):
    path: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float
    threshold: int
    above_threshold: bool


class LogsResponse(BaseModel):
    content: str
    lines: int


# --- HTML Page Routes ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render dashboard page."""
    settings = config_manager.load()
    runner_status = script_runner.get_status()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "settings": settings,
        "runner_status": runner_status,
        "version": APP_VERSION
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render settings page."""
    settings = config_manager.load()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings,
        "version": APP_VERSION
    })


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Render logs page."""
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "version": APP_VERSION
    })


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Render help page."""
    return templates.TemplateResponse("help.html", {
        "request": request,
        "version": APP_VERSION
    })


# --- API Endpoints ---

@app.get("/api/cache-usage", response_model=CacheUsageResponse)
async def get_cache_usage():
    """Get current cache drive usage statistics."""
    settings = config_manager.load()
    cache_path = settings.cache_drive

    try:
        if os.path.exists(cache_path):
            usage = psutil.disk_usage(cache_path)
            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            percent_used = usage.percent
        else:
            # Return mock data for development/testing
            total_gb = 500.0
            used_gb = 425.0
            free_gb = 75.0
            percent_used = 85.0

        return CacheUsageResponse(
            path=cache_path,
            total_gb=round(total_gb, 2),
            used_gb=round(used_gb, 2),
            free_gb=round(free_gb, 2),
            percent_used=round(percent_used, 1),
            threshold=settings.cache_threshold,
            above_threshold=percent_used >= settings.cache_threshold
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache usage: {str(e)}")


@app.post("/api/run", response_model=RunResponse)
async def run_script(request: RunRequest, background_tasks: BackgroundTasks):
    """Execute the smart mover script."""
    status = script_runner.get_status()

    if status["is_running"]:
        return RunResponse(
            success=False,
            message="Script is already running",
            dry_run=request.dry_run or config_manager.load().dry_run
        )

    # Run synchronously for now (could be made async with background tasks)
    result = script_runner.run(dry_run=request.dry_run)

    return RunResponse(
        success=result.success,
        message="Script completed successfully" if result.success else "Script failed",
        dry_run=result.dry_run,
        output=result.output,
        error=result.error if result.error else None,
        duration_seconds=result.duration_seconds
    )


@app.get("/api/run/status")
async def get_run_status():
    """Get current script execution status."""
    return script_runner.get_status()


class SettingsUpdate(BaseModel):
    """Partial settings update model - all fields optional.

    This enables proper partial updates: only fields explicitly provided
    in the request will be updated. Other fields retain their current values.
    """
    jellyfin_url: Optional[str] = None
    jellyfin_api_key: Optional[str] = None
    jellyfin_user_ids: Optional[str] = None
    cache_threshold: Optional[int] = None
    cache_drive: Optional[str] = None
    array_path: Optional[str] = None
    movies_pool: Optional[str] = None
    tv_pool: Optional[str] = None
    jellyfin_path_prefix: Optional[str] = None
    local_path_prefix: Optional[str] = None
    dry_run: Optional[bool] = None
    debug: Optional[bool] = None
    log_level: Optional[str] = None
    schedule_enabled: Optional[bool] = None
    schedule_cron: Optional[str] = None


@app.post("/api/settings")
async def save_settings(settings_update: SettingsUpdate):
    """Save application settings using partial update pattern.

    Only updates fields that are explicitly provided in the request.
    Fields not included in the request retain their existing values.
    For the API key specifically, an empty string preserves the existing value
    since users never see the actual key (only a masked indicator).
    """
    try:
        # Load existing settings
        current = config_manager.load()
        current_dict = current.model_dump()

        # Get only fields that were explicitly provided in the request
        update_data = settings_update.model_dump(exclude_unset=True)

        # API key handling: empty string means "keep existing" since
        # the UI shows a placeholder when the key is set, not the actual value
        if 'jellyfin_api_key' in update_data and not update_data['jellyfin_api_key']:
            del update_data['jellyfin_api_key']

        # Merge updates with existing settings
        current_dict.update(update_data)
        new_settings = Settings(**current_dict)
        config_manager.save(new_settings)
        return {"success": True, "message": "Settings saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save settings: {str(e)}")


@app.get("/api/settings")
async def get_settings():
    """Get current application settings."""
    settings = config_manager.load()
    # Don't expose API key in full
    settings_dict = settings.model_dump()
    if settings_dict.get('jellyfin_api_key'):
        settings_dict['jellyfin_api_key_set'] = True
        settings_dict['jellyfin_api_key'] = '********'
    else:
        settings_dict['jellyfin_api_key_set'] = False
    return settings_dict


@app.get("/api/logs", response_model=LogsResponse)
async def get_logs(lines: Optional[int] = None, level: Optional[str] = None):
    """Get log file contents."""
    content = config_manager.read_logs(lines=lines, level=level)
    line_count = len(content.splitlines()) if content else 0
    return LogsResponse(content=content, lines=line_count)


@app.get("/api/logs/download")
async def download_logs():
    """Download the full log file."""
    log_file = config_manager.get_log_file()

    if not log_file.exists():
        raise HTTPException(status_code=404, detail="No log file found")

    return FileResponse(
        path=log_file,
        filename="smart_mover.log",
        media_type="text/plain"
    )


@app.delete("/api/logs")
async def clear_logs():
    """Clear the log file."""
    try:
        config_manager.clear_logs()
        return {"success": True, "message": "Logs cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear logs: {str(e)}")


# --- Health Check ---

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": APP_VERSION}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9898)
