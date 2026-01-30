# Smart Mover Docker

A Docker-based web application for Unraid that intelligently moves watched media from cache to array based on Jellyfin playback status.

## Features

- **Web UI Dashboard**: Live cache usage display with threshold alerts and next scheduled run time
- **Settings Management**: Configure all options via web interface
- **Manual & Scheduled Runs**: On-demand execution with cron-based scheduling
- **Smart Move Logic**:
  - Movies: Moves entire folder (video + subtitles + extras)
  - TV Shows: Moves episode files + matching subtitles
- **Dry-Run Mode**: Preview changes before executing
- **Logging**: Configurable log levels with web viewer, copy-to-clipboard, and download
- **Version Display**: Version shown in UI header for easy debugging

## Quick Start

### Docker CLI

```bash
docker run -d \
  --name smart-mover \
  -p 9898:9898 \
  -v /mnt/cache:/mnt/cache:rw \
  -v /mnt/disk1:/mnt/disk1:rw \
  -v /mnt/user/appdata/smart-mover:/config \
  -e PUID=99 \
  -e PGID=100 \
  -e TZ=America/New_York \
  trrf/smart-mover:latest
```

### Docker Compose

```yaml
version: "3.8"
services:
  smart-mover:
    image: trrf/smart-mover:latest
    container_name: smart-mover
    ports:
      - "9898:9898"
    volumes:
      - /mnt/cache:/mnt/cache:rw
      - /mnt/disk1:/mnt/disk1:rw
      - /mnt/user/appdata/smart-mover:/config
    environment:
      - PUID=99
      - PGID=100
      - TZ=America/New_York
    restart: unless-stopped
```

### Unraid Community Applications

Search for "Smart Mover" in the Community Applications tab.

## Configuration

Access the web UI at `http://your-server:9898` and navigate to Settings.

### Required Settings

| Setting | Description |
|---------|-------------|
| Jellyfin URL | Your Jellyfin server URL (e.g., `http://192.168.1.60:8096`) |
| Jellyfin API Key | API key from Jellyfin Admin Dashboard |
| User IDs | Space-separated Jellyfin user IDs to check for playback |
| Cache Drive | Path to cache drive (e.g., `/mnt/cache`) |
| Array Path | Destination path on array (e.g., `/mnt/disk1`) |

### Finding Jellyfin User IDs

There are several ways to find Jellyfin user IDs:

#### Method 1: Admin Dashboard URL

1. Log into Jellyfin as an administrator
2. Go to **Dashboard** → **Users**
3. Click on the user you want to track
4. Look at the URL in your browser - it contains the user ID:
   ```
   http://your-jellyfin:8096/web/index.html#!/useredit.html?userId=a1b2c3d4e5f6g7h8
   ```
   The user ID is the value after `userId=` (e.g., `a1b2c3d4e5f6g7h8`)

#### Method 2: Jellyfin API

Use curl to query the Jellyfin API directly:

```bash
# List all users (requires API key)
curl -s "http://your-jellyfin:8096/Users?api_key=YOUR_API_KEY" | jq '.[] | {Name: .Name, Id: .Id}'
```

Example output:
```json
{
  "Name": "admin",
  "Id": "a1b2c3d4e5f6g7h8"
}
{
  "Name": "family",
  "Id": "i9j0k1l2m3n4o5p6"
}
```

#### Method 3: Browser Developer Tools

1. Log into Jellyfin
2. Open browser Developer Tools (F12)
3. Go to **Network** tab
4. Navigate around Jellyfin (play something, browse library)
5. Look for API requests - many include `userId` parameter

#### Multiple Users

To track multiple users, separate their IDs with spaces in the settings:
```
a1b2c3d4e5f6g7h8 i9j0k1l2m3n4o5p6
```

### Creating a Jellyfin API Key

1. Log into Jellyfin as an administrator
2. Go to **Dashboard** → **API Keys**
3. Click **+** to create a new key
4. Enter a name like "Smart Mover"
5. Copy the generated key (it won't be shown again)

## Volume Mappings

| Container Path | Host Path | Description |
|----------------|-----------|-------------|
| `/mnt/cache` | `/mnt/cache` | Cache drive (read/write) |
| `/mnt/disk1` | `/mnt/disk1` | Array destination |
| `/config` | `/mnt/user/appdata/smart-mover` | App config and logs |

## Path Translation

If your Jellyfin container sees media at a different path than your Unraid server, you need to configure path translation.

### Example Setup

| System | Path |
|--------|------|
| Jellyfin sees | `/media/movies/The Matrix (1999)/` |
| Unraid actual | `/mnt/cache/media/movies/The Matrix (1999)/` |

### Configuration

In Settings, configure:
- **Jellyfin Path Prefix**: `/media` (what Jellyfin reports)
- **Local Path Prefix**: `/mnt/cache/media` (actual Unraid path)

The script will translate paths automatically:
```
Jellyfin reports: /media/movies/The Matrix (1999)/movie.mkv
Translated to:    /mnt/cache/media/movies/The Matrix (1999)/movie.mkv
```

## How It Works

### Move Logic

1. **Check cache usage** - Only proceeds if cache is above the configured threshold
2. **Query Jellyfin** - Gets list of played items for configured users
3. **Filter watched content** - Identifies fully watched movies and TV episodes
4. **Move files**:
   - **Movies**: Entire folder including video, subtitles, artwork, and extras
   - **TV Episodes**: Episode file + matching subtitle files (same S##E## pattern)

### What Gets Moved

| Content Type | What Moves |
|--------------|------------|
| Movies | Entire movie folder (video, subs, artwork, NFO, extras) |
| TV Episodes | Episode file + matching `.srt`, `.ass`, `.sub` files |

### Safety Features

- **Dry-run mode** (default): Shows what would be moved without making changes
- **Verification**: Uses rsync with checksum verification
- **Cleanup**: Only removes source files after successful transfer
- **Logging**: All operations are logged for audit trail

## Troubleshooting

### Common Issues

**Cache usage not displaying:**
- Verify cache drive path is correctly mapped
- Check container logs for errors

**Files not moving:**
- Ensure dry-run mode is disabled
- Verify Jellyfin connection (use Test Connection button)
- Check that user IDs are correct

**Permission errors:**
- Verify PUID/PGID match your Unraid user
- Check volume mount permissions

## License

MIT License

## Credits

Based on the [unraid-smart-mover](https://github.com/trrf11/unraid-smart-mover) bash script.
