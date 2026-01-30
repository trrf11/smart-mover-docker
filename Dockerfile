# Smart Mover Docker
# Intelligently move watched media from cache to array

FROM python:3.11-slim

LABEL maintainer="timfokker"
LABEL description="Smart Mover - Move watched media from cache to array based on Jellyfin playback"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    rsync \
    jq \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app/ ./app/
COPY scripts/ ./scripts/

# Make scripts executable
RUN chmod +x /app/scripts/*.sh

# Create config directory
RUN mkdir -p /config/logs

# Environment variables
ENV PUID=99
ENV PGID=100
ENV WEB_PORT=9898
ENV TZ=America/New_York

# Expose web UI port
EXPOSE 9898

# Set entrypoint
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
