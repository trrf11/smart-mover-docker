#!/bin/bash
set -e

# Smart Mover Docker - Entrypoint Script

# Set default values
PUID=${PUID:-99}
PGID=${PGID:-100}
WEB_PORT=${WEB_PORT:-7878}

echo "Starting Smart Mover..."
echo "PUID: $PUID"
echo "PGID: $PGID"
echo "Web Port: $WEB_PORT"

# Create config directories if they don't exist
mkdir -p /config/logs

# Set ownership
chown -R "$PUID:$PGID" /config

# Start the web application
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$WEB_PORT"
