#!/bin/bash
# Quick start / restart all services
cd "$(dirname "$0")/.."
docker compose up -d --build
echo "✅ All services started"
docker compose ps
