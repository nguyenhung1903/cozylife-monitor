#!/usr/bin/env bash

set -e

IMAGE="cozylife-monitor:latest"
CONTAINER="cozylife-monitor"

echo "Building Docker image..."
docker build -t "$IMAGE" .

echo "Removing old container..."
docker rm -f "$CONTAINER" 2>/dev/null || true

echo "Starting new container..."
docker run -d \
    --name "$CONTAINER" \
    -p 8000:8000 \
    --restart unless-stopped \
    --env-file .env \
    "$IMAGE"

echo "Deployment completed!"
