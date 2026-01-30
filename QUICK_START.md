# Quick Start Guide for Claude Code

> **Development Environment**: MacBook (local development)  
> **Testing Environment**: Unraid server "Nelly" at 192.168.1.60  
> **Approach**: Build and test locally, deploy to Unraid when ready

## Prerequisites

Make sure you have these installed on your MacBook:
- **Homebrew**: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- **Python 3.11+**: `brew install python@3.11`
- **Docker Desktop**: Download from docker.com or `brew install --cask docker`
- **Git**: Pre-installed on macOS (check with `git --version`)
- **GitHub CLI** (optional): `brew install gh`

## Initial Setup Commands

Run these commands in order to set up the project on your MacBook:

```bash
# 1. Navigate to your development directory
cd ~/Developer  # or wherever you keep your projects
# If you don't have a Developer folder:
mkdir -p ~/Developer && cd ~/Developer

# 2. Install GitHub CLI (if not already installed)
brew install gh
gh auth login  # Follow prompts to authenticate

# 3. Create GitHub repository
gh repo create smart-mover-docker --public --description "Docker-based Smart Mover for Unraid with Web UI"

# 4. Clone the empty repository
git clone https://github.com/trrf11/smart-mover-docker.git
cd smart-mover-docker

# 5. Create directory structure
mkdir -p app/{static/{css,js},templates}
mkdir -p scripts
mkdir -p config/logs
mkdir -p tests/mock_jellyfin
mkdir -p .github/workflows

# 6. Copy existing bash script from old repo
curl -o scripts/jellyfin_smart_mover.sh https://raw.githubusercontent.com/trrf/unraid-smart-mover/main/jellyfin_smart_mover.sh
chmod +x scripts/jellyfin_smart_mover.sh

# 7. Create initial Git files
touch .gitignore .dockerignore README.md

# 8. Initial git commit
git add .
git commit -m "Initial project structure"
git push origin main

# 9. Create Python virtual environment
python3 -m venv venv
source venv/bin/activate  # Run this each time you start working

# 10. Install Python dependencies (after creating requirements.txt)
pip install -r requirements.txt
```

## Files to Create (In Order)

### Phase 1: Core Setup
1. `.gitignore` - Standard Python/Docker ignores
2. `.dockerignore` - Exclude unnecessary files from image
3. `requirements.txt` - Python dependencies
4. `README.md` - Initial documentation

### Phase 2: Backend
5. `app/__init__.py` - Package init
6. `app/main.py` - FastAPI application
7. `app/config_manager.py` - Settings management
8. `app/runner.py` - Script executor
9. `app/jellyfin_client.py` - Jellyfin API wrapper (optional)

### Phase 3: Frontend
10. `app/static/css/style.css` - Main stylesheet
11. `app/static/js/app.js` - Frontend JavaScript
12. `app/templates/base.html` - Base template
13. `app/templates/dashboard.html` - Dashboard page
14. `app/templates/settings.html` - Settings page

### Phase 4: Docker
15. `Dockerfile` - Container definition
16. `scripts/entrypoint.sh` - Startup script
17. `docker-compose.yml` - Local testing

### Phase 5: Testing & Docs
18. `tests/test_config.py` - Unit tests
19. `tests/test_runner.py` - Unit tests
20. `unraid-template.xml` - Unraid CA template
21. Update `README.md` - Complete documentation

## Development Workflow

```bash
# Activate virtual environment (do this when starting work)
cd ~/Developer/smart-mover-docker
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run FastAPI locally (without Docker) for development
python -m app.main
# Access at http://localhost:9898

# In another terminal, watch for file changes (optional)
# Install watchdog if you want auto-reload:
pip install watchdog
# FastAPI has auto-reload built in with: uvicorn app.main:app --reload

# Build Docker image
docker build -t smart-mover:dev .

# Run Docker container locally
docker run -d \
  --name smart-mover-test \
  -p 9898:9898 \
  -v $(pwd)/config:/config \
  -e PUID=1000 \
  -e PGID=1000 \
  smart-mover:dev

# View logs
docker logs -f smart-mover-test

# Stop and remove
docker stop smart-mover-test && docker rm smart-mover-test

# For testing with mock paths (since you don't have /mnt/cache on MacBook)
mkdir -p /tmp/mock-cache /tmp/mock-array
docker run -d \
  --name smart-mover-test \
  -p 9898:9898 \
  -v $(pwd)/config:/config \
  -v /tmp/mock-cache:/mnt/cache:rw \
  -v /tmp/mock-array:/mnt/disk1:rw \
  -e PUID=$(id -u) \
  -e PGID=$(id -g) \
  smart-mover:dev
```

## Testing on Unraid (Nelly)

```bash
# 1. Build and push to Docker Hub
docker build -t trrf/smart-mover:dev .
docker push trrf/smart-mover:dev

# 2. SSH to Unraid server
ssh root@192.168.1.60

# 3. Pull and run (or use Unraid Docker UI)
docker pull trrf/smart-mover:dev
docker run -d \
  --name=smart-mover \
  -p 9898:9898 \
  -v /mnt/user/appdata/smart-mover:/config \
  -v /mnt/cache:/mnt/cache:rw \
  -v /mnt/disk1:/mnt/disk1:rw \
  -e PUID=99 \
  -e PGID=100 \
  -e TZ=America/New_York \
  trrf/smart-mover:dev

# 4. Access web UI
# Open browser: http://192.168.1.60:9898
```

## Key Configuration Values

### For Development (MacBook)
- **Jellyfin URL**: http://192.168.1.60:8096 (Jellyfin on Nelly)
- **Cache Path**: Use mock paths like `/tmp/mock-cache`
- **Array Path**: Use mock paths like `/tmp/mock-array`
- **Note**: Since MacBook doesn't have /mnt/cache, use temp directories for testing
- **Testing**: Can test web UI and logic, but actual file moves should be tested on Nelly

### For Production (Nelly)
- **Jellyfin URL**: http://localhost:8096 (if Jellyfin on same server)
- **Cache Path**: /mnt/cache
- **Array Path**: /mnt/disk1 or /mnt/user0
- **Movies Pool**: movies-pool
- **TV Pool**: tv-pool

## Notion Database Setup

1. Create new database in Notion
2. Add these properties:
   - Task Name (Title)
   - Category (Select: Setup, Backend, Frontend, Docker, Testing, Documentation, Release)
   - Priority (Select: High, Medium, Low)
   - Status (Select: Not Started, In Progress, Blocked, Testing, Done)
   - Estimated Hours (Number)
   - Actual Hours (Number)
   - Dependencies (Text)
   - Notes (Text)
   - Due Date (Date)
   - Assignee (Person)

3. Import CSV:
   - Click "..." menu in database
   - Select "Import"
   - Choose "CSV"
   - Upload `NOTION_TASKS.csv`

4. Create views:
   - Board view by Status
   - Table view by Category
   - Timeline view by Due Date
   - Calendar view by Due Date

## Git Workflow

```bash
# Create feature branch
git checkout -b feature/dashboard-ui

# Make changes, commit frequently
git add .
git commit -m "Add dashboard UI with cache display"

# Push to remote
git push origin feature/dashboard-ui

# Merge to main when ready
git checkout main
git merge feature/dashboard-ui
git push origin main

# Tag releases
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## Debugging Tips

```bash
# Check Docker container status
docker ps -a | grep smart-mover

# View real-time logs
docker logs -f smart-mover-test

# Exec into container
docker exec -it smart-mover-test /bin/bash

# Check mounted volumes
docker exec smart-mover-test ls -la /config
docker exec smart-mover-test ls -la /mnt/cache

# Test API endpoints
curl http://localhost:9898/health
curl http://localhost:9898/api/cache-usage
```

## Common Issues & Solutions

### Port already in use
```bash
# Find what's using port 7878 (macOS)
lsof -i :9898
# Or use different port
docker run -p 7879:9898 ...
```

### Permission denied on volumes
```bash
# Check PUID/PGID match your user
id -u  # Should match PUID
id -g  # Should match PGID
```

### Bash script not executing
```bash
# Make sure it's executable
chmod +x scripts/jellyfin_smart_mover.sh
# Rebuild Docker image after changes
docker build -t smart-mover:dev --no-cache .
```

## Getting Started on MacBook

### First Time Setup
```bash
# 1. Make sure you have these installed:
brew --version  # If not: install Homebrew first
python3 --version  # Should be 3.11+
docker --version  # If not: install Docker Desktop
git --version  # Should be pre-installed on macOS

# 2. Open Terminal and navigate to your projects folder
cd ~/Developer  # or mkdir -p ~/Developer && cd ~/Developer

# 3. Have CLAUDE_CODE_PROMPT.md ready in this directory
# You can download it or have it open in your editor

# 4. Start Claude Code (via VS Code with Continue extension or Cursor)
# Point it to CLAUDE_CODE_PROMPT.md and begin!
```

### Development Session Workflow
```bash
# Each time you start working:
cd ~/Developer/smart-mover-docker
source venv/bin/activate  # Activate Python virtual environment

# Make sure Docker Desktop is running
open -a Docker  # Start Docker Desktop if not running

# Run the app locally for testing
python -m app.main  # Access at http://localhost:9898

# When done:
deactivate  # Deactivate virtual environment
```

### Testing on Nelly (When Ready)
```bash
# 1. Build and tag for Docker Hub
docker build -t trrf/smart-mover:dev .

# 2. Push to Docker Hub (requires login)
docker login
docker push trrf/smart-mover:dev

# 3. SSH to Nelly and pull
ssh root@192.168.1.60
docker pull trrf/smart-mover:dev
# Then install via Unraid Docker UI or command line
```

## Next Steps

1. Read `CLAUDE_CODE_PROMPT.md` fully
2. Import `NOTION_TASKS.csv` into Notion database
3. Start with Phase 1 tasks (Setup category)
4. Work through tasks in dependency order
5. Test frequently (after each major component)
6. Update Notion as you complete tasks
7. Commit to Git regularly

## Resources

- **Main prompt**: `CLAUDE_CODE_PROMPT.md`
- **Tasks**: `NOTION_TASKS.csv`
- **Existing repo**: https://github.com/trrf11/unraid-smart-mover
- **Unraid forums**: https://forums.unraid.net/
- **FastAPI docs**: https://fastapi.tiangolo.com/

---

**Ready to start?** Begin with creating the GitHub repo and directory structure!
