# Smart Mover Docker
# Intelligently move watched media from cache to array

FROM python:3.11-slim

LABEL maintainer="trrf11"
LABEL description="Smart Mover - Move watched media from cache to array based on Jellyfin playback"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    rsync \
    jq \
    curl \
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
ENV WEB_PORT=7878
ENV TZ=America/New_York

# Expose web UI port
EXPOSE 7878

# Set entrypoint
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
