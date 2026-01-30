# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Smart Mover Docker is a Docker-based web application for Unraid that intelligently moves watched media from cache to array based on Jellyfin playback status. It wraps an existing bash script (`scripts/jellyfin_smart_mover.sh`) in a Python FastAPI web interface.

## Build and Run Commands

```bash
# Local development (without Docker)
source venv/bin/activate
pip install -r requirements.txt
python -m app.main
# Access at http://localhost:9898

# Run tests
source venv/bin/activate
pip install pytest pytest-asyncio httpx==0.26.0
pytest tests/

# Build Docker image
docker build -t smart-mover:dev .

# Run Docker container (local testing)
docker run -d --name smart-mover-test -p 9898:9898 \
  -v $(pwd)/config:/config \
  -v /tmp/mock-cache:/mnt/cache:rw \
  -v /tmp/mock-array:/mnt/disk1:rw \
  -e PUID=$(id -u) -e PGID=$(id -g) \
  smart-mover:dev

# View container logs
docker logs -f smart-mover-test

# Tagged release (triggers GitHub Actions CI/CD)
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## Architecture

```
Web Layer (FastAPI + Jinja2)
    ↓
Configuration Manager (app/config_manager.py)
    ↓
Script Runner (app/runner.py) - subprocess wrapper
    ↓
Bash Script (scripts/jellyfin_smart_mover.sh) - core media moving logic
```

The bash script handles:
- Jellyfin API calls to identify watched content
- Path translation between Jellyfin and local filesystem
- Movie moves (entire folder with metadata)
- TV episode moves (S##E## pattern matching with subtitles)
- rsync transfers with verification and cleanup

## Key Conventions

- **Port**: Web UI always on 9898
- **Container paths**: `/mnt/cache` (source), `/mnt/disk1` (destination), `/config` (settings/logs)
- **Config storage**: `/config/settings.json` - JSON file persisted in mounted volume
- **Dry-run default**: Settings should default to `dry_run: true` for safety
- **Dark theme**: Orange accent color `#ff8c00` matching Unraid aesthetic

## Project Management

Tasks are tracked in Notion: [Smart Mover Docker Tasks](https://www.notion.so/2f3fafcc674a80aeb332c5fb4f82c07d)

Development is organized into phases:
- **Phase 1: Setup** - Repository, directory structure, dependencies, bash script
- **Phase 2: Backend** - FastAPI skeleton, config manager, runner, API endpoints
- **Phase 3: Web UI** - HTML templates, CSS, JavaScript, form components
- **Phase 4: Docker** - Dockerfile, compose, entrypoint, Unraid template
- **Phase 5: Testing & Docs** - Unit tests, README, Unraid server testing
- **Phase 6: Release** - Docker Hub, multi-arch builds, Unraid CA submission

## Development Status

**Completed:**
- Phase 1: Setup - Repository structure, bash script integration
- Phase 2: Backend - FastAPI application, config manager with Pydantic validation, script runner with threading
- Phase 3: Web UI - Dashboard, settings, logs, help pages with dark theme
- Phase 4: Docker - Dockerfile, docker-compose.yml, entrypoint script
- Phase 5: Unit tests for config_manager, runner, and API endpoints (81 tests); Tested on Unraid server
- Phase 6 (partial): Docker Hub release at `trrf/smart-mover`

**Remaining:**
- Multi-arch builds
- Unraid Community Applications submission

**Test Coverage:**
- `tests/test_config.py` - Settings model validation, ConfigManager operations
- `tests/test_runner.py` - ScriptRunner execution, state management
- `tests/test_api.py` - All FastAPI endpoints, HTML pages, static files

See the Notion database for detailed task tracking.
