#!/bin/bash
set -e

echo "Create Docker Image..."
docker build -t maps-converter .

echo "Delete old docker container (when necessary)..."
docker rm -f maps-converter-container 2>/dev/null || true

echo "Start Docker Container..."
docker run -d \
  --name maps-converter-container \
  -p 8080:8080 \
  -v "$(pwd)/tile_cache:/app/tile_cache" \
  -v "$(pwd)/logs:/app/logs" \
  --restart unless-stopped \
  maps-converter

echo "Server runs on: http://localhost:8080"
