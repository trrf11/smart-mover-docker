# Smart Mover Docker

A Docker-based web application for Unraid that intelligently moves watched media from cache to array based on Jellyfin playback status.

## Features

- **Web UI Dashboard**: Live cache usage display, run status, and quick stats
- **Settings Management**: Configure all options via web interface
- **Manual & Scheduled Runs**: On-demand execution with optional scheduling
- **Smart Move Logic**:
  - Movies: Moves entire folder (video + subtitles + extras)
  - TV Shows: Moves episode files + matching subtitles
- **Dry-Run Mode**: Preview changes before executing
- **Logging**: Configurable log levels with web viewer and download

## Quick Start

### Docker CLI

```bash
docker run -d \
  --name smart-mover \
  -p 7878:7878 \
  -v /mnt/cache:/mnt/cache:rw \
  -v /mnt/disk1:/mnt/disk1:rw \
  -v /mnt/user/appdata/smart-mover:/config \
  -e PUID=99 \
  -e PGID=100 \
  -e TZ=America/New_York \
  trrf11/smart-mover-docker:latest
```

### Docker Compose

```yaml
version: "3.8"
services:
  smart-mover:
    image: trrf11/smart-mover-docker:latest
    container_name: smart-mover
    ports:
      - "7878:7878"
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

Access the web UI at `http://your-server:7878` and navigate to Settings.

### Required Settings

| Setting | Description |
|---------|-------------|
| Jellyfin URL | Your Jellyfin server URL (e.g., `http://192.168.1.60:8096`) |
| Jellyfin API Key | API key from Jellyfin Admin Dashboard |
| User IDs | Space-separated Jellyfin user IDs to check for playback |
| Cache Drive | Path to cache drive (e.g., `/mnt/cache`) |
| Array Path | Destination path on array (e.g., `/mnt/disk1`) |

### Finding Jellyfin User IDs

1. Go to Jellyfin Admin Dashboard
2. Navigate to Users
3. Click on a user
4. The User ID is in the URL: `...userId=<USER_ID>`

## Volume Mappings

| Container Path | Host Path | Description |
|----------------|-----------|-------------|
| `/mnt/cache` | `/mnt/cache` | Cache drive (read/write) |
| `/mnt/disk1` | `/mnt/disk1` | Array destination |
| `/config` | `/mnt/user/appdata/smart-mover` | App config and logs |

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
