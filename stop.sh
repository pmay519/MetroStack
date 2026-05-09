#!/bin/bash

# MetroStack Stop Script
# Gracefully stops all services

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    STOPPING METROSTACK                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

echo "→ Stopping Docker containers..."
docker-compose down

echo "→ Stopping any local frontend processes..."
pkill -f "vite" 2>/dev/null || true
pkill -f "npm run dev" 2>/dev/null || true

echo ""
echo "✓ All services stopped"
echo ""
echo "→ To remove all data (CAUTION: deletes database):"
echo "    docker-compose down -v"
