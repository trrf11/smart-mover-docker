# Feature Comparison: Bash Script vs Docker Web App

## Current Implementation (Bash Script via User Scripts)

### Strengths
✅ Works reliably for technical users
✅ Proven logic for moving files
✅ Multi-user support (space-separated UUIDs)
✅ Smart moving (movies = folder, TV = episode)
✅ Path translation for Docker paths
✅ Dry-run mode
✅ Detailed statistics and logging
✅ Safe transfers with rsync verification

### Weaknesses
❌ Requires manual script editing for configuration
❌ No GUI - CLI only
❌ Must understand bash and Unraid paths
❌ Hard to troubleshoot for non-technical users
❌ No visual feedback during execution
❌ Logs only in file (no web viewer)
❌ Requires User Scripts plugin

### Configuration Method
- Edit script variables directly:
```bash
JELLYFIN_URL="http://localhost:8096"
JELLYFIN_API_KEY="your-key-here"
JELLYFIN_USER_IDS="uuid1 uuid2"
CACHE_THRESHOLD=90
# etc...
```

### Execution Methods
- Manual: Click "Run Script" in User Scripts
- Scheduled: Set cron expression in User Scripts
- Command line: `./jellyfin_smart_mover.sh --dry-run`

---

## New Implementation (Docker Web App)

### Strengths
✅ User-friendly web interface
✅ No script editing required
✅ Visual cache usage display
✅ One-click execution with dry-run toggle
✅ Live log viewing in browser
✅ Settings validation before save
✅ Downloadable logs
✅ No plugins required
✅ All bash script features preserved
✅ Better error messages and troubleshooting

### New Features
🆕 Web-based configuration
🆕 Dashboard with live stats and threshold alerts
🆕 Visual progress indicators
🆕 Log viewer with filtering and copy-to-clipboard
🆕 Settings validation
🆕 Docker isolation
🆕 Easier updates (pull new image)
🆕 Optional scheduling via web UI with next run display
🆕 Version display in UI for debugging

### Configuration Method
- Web form at http://server:9898/settings
- Or Docker environment variables
- Or edit /config/settings.json directly (advanced)

### Execution Methods
- Web UI: Click "Run Now" button on dashboard
- API: `curl -X POST http://server:9898/api/run`
- Scheduled: Configure cron in web UI
- Command line: `docker exec smart-mover /app/scripts/jellyfin_smart_mover.sh`

---

## Feature Parity Checklist

### Core Functionality
| Feature | Bash Script | Docker Web App | Status |
|---------|-------------|----------------|--------|
| Multi-user support | ✅ | ✅ | Preserved |
| Movies: move folder | ✅ | ✅ | Preserved |
| TV: move episode + subs | ✅ | ✅ | Preserved |
| Path translation | ✅ | ✅ | Preserved |
| Cache threshold check | ✅ | ✅ | Preserved |
| Dry-run mode | ✅ | ✅ | Preserved |
| Rsync verification | ✅ | ✅ | Preserved |
| Empty dir cleanup | ✅ | ✅ | Preserved |
| Statistics reporting | ✅ | ✅ | Enhanced |
| Debug logging | ✅ | ✅ | Enhanced |

### Configuration
| Setting | Bash Script | Docker Web App | Notes |
|---------|-------------|----------------|-------|
| Jellyfin URL | Variable | Web form + env | Same |
| API Key | Variable | Web form + env | Same |
| User IDs | Variable | Web form + env | Same format (space-separated) |
| Cache threshold | Variable | Web form + env | Same (percentage) |
| Cache drive path | Variable | Docker volume | Mapped to /mnt/cache |
| Array path | Variable | Docker volume | Mapped to /mnt/disk1 or /mnt/user0 |
| Movies pool | Variable | Web form + env | Same |
| TV pool | Variable | Web form + env | Same |
| Path prefix | Variable | Web form + env | Same |
| Dry-run default | Flag | Web toggle | Configurable default |
| Debug mode | Variable | Web toggle | Same |

### User Experience
| Aspect | Bash Script | Docker Web App | Improvement |
|--------|-------------|----------------|-------------|
| Installation | Copy script to User Scripts | Install via Community Apps | ✅ Easier |
| Configuration | Edit script file | Fill web form | ✅ Much easier |
| Validation | Manual testing | Automatic validation | ✅ Better UX |
| Execution | Click "Run Script" | Click "Run Now" | ✅ Simpler |
| Monitoring | Check log file | View in browser | ✅ More convenient |
| Troubleshooting | Read bash logs | Visual errors + hints | ✅ Better feedback |
| Updates | Copy new script | Pull new image | ✅ Simpler |

---

## Migration Path for Existing Users

### Step 1: Note Current Settings
Before migrating, document your current configuration:
```bash
# From jellyfin_smart_mover.sh
JELLYFIN_URL="..."
JELLYFIN_API_KEY="..."
JELLYFIN_USER_IDS="..."
CACHE_THRESHOLD=...
CACHE_DRIVE="..."
ARRAY_PATH="..."
MOVIES_POOL="..."
TV_POOL="..."
JELLYFIN_PATH_PREFIX="..."
LOCAL_PATH_PREFIX="..."
```

### Step 2: Install Docker Version
1. Open Unraid web UI
2. Go to Apps tab
3. Search "Smart Mover"
4. Click "Install"
5. Configure paths:
   - Container Path: `/mnt/cache` → Host Path: `/mnt/cache`
   - Container Path: `/mnt/disk1` → Host Path: `/mnt/disk1` (or `/mnt/user0`)
   - Container Path: `/config` → Host Path: `/mnt/user/appdata/smart-mover`
6. Set port: 9898
7. Click "Apply"

### Step 3: Configure via Web UI
1. Open http://your-server:9898
2. Click "Settings"
3. Enter your noted settings
4. Click "Test Connection" (if available)
5. Click "Save Settings"

### Step 4: Test with Dry-Run
1. Go to Dashboard
2. Ensure "Dry-Run" is enabled
3. Click "Run Now"
4. Review output to confirm same behavior
5. Check logs match expectations

### Step 5: Run Live
1. Disable "Dry-Run"
2. Click "Run Now"
3. Verify files moved correctly
4. Compare with previous bash script runs

### Step 6: Disable Old Script
1. Go to User Scripts plugin
2. Disable or delete old script
3. Remove from schedule if scheduled

### Step 7: Optional - Setup Schedule
1. In Docker web UI, configure schedule
2. Or keep manual execution as before

---

## Configuration Mapping

### Bash Variables → Web UI Fields

| Bash Variable | Web UI Field | Section |
|---------------|--------------|---------|
| `JELLYFIN_URL` | Jellyfin Server URL | Jellyfin Connection |
| `JELLYFIN_API_KEY` | API Key | Jellyfin Connection |
| `JELLYFIN_USER_IDS` | User IDs (space-separated) | Jellyfin Connection |
| `CACHE_THRESHOLD` | Cache Threshold (%) | Behavior |
| `CACHE_DRIVE` | Cache Drive Path | Path Configuration |
| `ARRAY_PATH` | Array Destination Path | Path Configuration |
| `MOVIES_POOL` | Movies Pool Name | Path Configuration |
| `TV_POOL` | TV Shows Pool Name | Path Configuration |
| `JELLYFIN_PATH_PREFIX` | Jellyfin Path Prefix | Path Configuration |
| `LOCAL_PATH_PREFIX` | Local Path Prefix | Path Configuration |
| `--dry-run` flag | Dry-Run Mode checkbox | Behavior |
| `DEBUG=true` | Debug Mode checkbox | Behavior |
| N/A | Log Level dropdown | Behavior |
| N/A | Schedule Enabled checkbox | Scheduling |
| N/A | Cron Expression | Scheduling |

### Bash Command → Web UI Action

| Bash Command | Web UI Equivalent |
|--------------|-------------------|
| `./jellyfin_smart_mover.sh` | Click "Run Now" (dry-run disabled) |
| `./jellyfin_smart_mover.sh --dry-run` | Click "Run Now" (dry-run enabled) |
| `cat smart_mover.log` | View "Logs" page |
| `tail -f smart_mover.log` | Logs page with auto-refresh |
| Edit script variables | Edit "Settings" page |
| Check cache: `df -h /mnt/cache` | Dashboard shows cache usage automatically |

---

## Testing Checklist

Before declaring feature parity, verify these scenarios work identically:

### ✅ Scenario 1: Movie Move
- [ ] Detect movie in movies-pool
- [ ] Move entire folder including:
  - [ ] Video file
  - [ ] Subtitle files (.srt, .ass, etc.)
  - [ ] Extra files (NFO, posters, etc.)
- [ ] Preserve folder structure on array
- [ ] Remove empty source folder
- [ ] Log statistics correctly

### ✅ Scenario 2: TV Episode Move
- [ ] Detect episode in tv-pool
- [ ] Extract S##E## pattern
- [ ] Move video file
- [ ] Find and move matching subtitle files
- [ ] Preserve directory structure
- [ ] Remove empty season/show folders if empty
- [ ] Log statistics correctly

### ✅ Scenario 3: Path Translation
- [ ] Jellyfin reports path: `/media/media/movies-pool/Movie/movie.mkv`
- [ ] Translate to local: `/mnt/cache/media/movies-pool/Movie/movie.mkv`
- [ ] Move to array: `/mnt/disk1/media/movies-pool/Movie/movie.mkv`
- [ ] Verify path exists at each step

### ✅ Scenario 4: Multi-User Support
- [ ] User A watches Movie X
- [ ] User B watches Movie Y
- [ ] Both movies marked as played
- [ ] Script moves both movies
- [ ] De-duplicates if both watched same movie

### ✅ Scenario 5: Cache Threshold
- [ ] Cache at 85%, threshold 90% → No action
- [ ] Cache at 92%, threshold 90% → Process played items
- [ ] Display matches actual disk usage

### ✅ Scenario 6: Dry-Run Mode
- [ ] Enable dry-run
- [ ] Run mover
- [ ] No files actually moved
- [ ] Output shows what WOULD be moved
- [ ] Statistics show predicted moves

### ✅ Scenario 7: Error Handling
- [ ] Invalid API key → Clear error message
- [ ] Invalid user ID → Clear error message
- [ ] Cache drive not mounted → Clear error message
- [ ] Array drive not writable → Clear error message
- [ ] Jellyfin server unreachable → Clear error message

---

## Known Differences (Intentional)

These are intentional improvements over the bash version:

1. **Configuration Storage**: 
   - Bash: Variables in script file
   - Docker: JSON file in /config volume
   - **Why**: Persists across updates, easier to backup

2. **Log Location**:
   - Bash: Same directory as script
   - Docker: /config/logs/ volume
   - **Why**: Persists across container restarts

3. **Execution Interface**:
   - Bash: User Scripts plugin UI
   - Docker: Custom web UI
   - **Why**: More user-friendly, no plugin required

4. **Updates**:
   - Bash: Copy new script file
   - Docker: Pull new image
   - **Why**: Easier, no manual file management

5. **Isolation**:
   - Bash: Runs directly on host
   - Docker: Runs in container
   - **Why**: Better security, easier troubleshooting

---

## Backwards Compatibility Notes

### ✅ Fully Compatible
- All configuration values work the same
- Same Jellyfin API calls
- Same file move logic
- Same path translation
- Same statistics format

### ℹ️ Different but Equivalent
- Configuration method (web UI vs script editing)
- Execution method (web button vs User Scripts)
- Log viewing (web UI vs file reading)

### ⚠️ Not Applicable
- User Scripts plugin dependency (Docker doesn't need it)
- Direct script execution (use web UI or API instead)

---

## For Developers: Code Architecture

### Bash Script (Current)
```
jellyfin_smart_mover.sh (1 file, ~1500 lines)
├── Configuration variables
├── Logging functions
├── Jellyfin API functions
├── File moving functions
├── Main execution logic
└── Summary reporting
```

### Docker App (New)
```
Docker Container
├── Web Layer (Python/FastAPI)
│   ├── app/main.py - HTTP endpoints
│   ├── app/config_manager.py - Settings
│   ├── app/runner.py - Script executor
│   └── app/templates/ - HTML UI
├── Engine Layer (Bash)
│   └── scripts/jellyfin_smart_mover.sh - Original logic
└── Storage Layer
    └── /config/settings.json - Persisted config
```

### Why This Architecture?
1. **Separation of concerns**: Web UI separate from move logic
2. **Reusability**: Bash script can still be run standalone
3. **Testability**: Each layer can be tested independently
4. **Maintainability**: Updates to UI don't affect move logic
5. **Progressive enhancement**: Start with bash, add features to web layer

---

## Summary

The Docker web app **preserves 100% of bash script functionality** while adding:
- User-friendly web interface
- Visual feedback and monitoring
- Better error messages
- Easier installation and updates
- No User Scripts plugin dependency

**All core moving logic remains unchanged** - the bash script is called by the web layer with the same parameters it would receive from User Scripts.

Users can migrate with confidence knowing the underlying file operations work identically.
