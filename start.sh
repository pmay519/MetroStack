#!/bin/bash

# MetroStack Quick Start Script
# Starts the full stack in development mode

set -e  # Exit on error

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    METROSTACK QUICK START                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
echo "→ Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "✗ Docker not found. Please install Docker Desktop."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "✗ Docker Compose not found. Please install Docker Compose."
    exit 1
fi

echo "✓ Docker found"
echo "✓ Docker Compose found"
echo ""

# Start backend services
echo "→ Starting backend services (PostgreSQL, Redis, FastAPI)..."
docker-compose up -d db redis api

# Wait for database to be ready
echo "→ Waiting for PostgreSQL to be ready..."
sleep 5

# Run database migrations
echo "→ Running database migrations..."
docker-compose exec -T api alembic upgrade head

echo "✓ Backend services started"
echo ""

# Check if Node.js is available for local frontend dev
if command -v node &> /dev/null; then
    echo "→ Node.js found - starting frontend locally..."
    cd frontend
    
    if [ ! -d "node_modules" ]; then
        echo "→ Installing frontend dependencies..."
        npm install
    fi
    
    echo "→ Starting Vite dev server..."
    npm run dev &
    FRONTEND_PID=$!
    cd ..
    
    echo "✓ Frontend started (PID: $FRONTEND_PID)"
else
    echo "→ Node.js not found - starting frontend in Docker..."
    docker-compose up -d frontend
    echo "✓ Frontend container started"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                       SERVICES RUNNING                         ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  Frontend:  http://localhost:3000                              ║"
echo "║  Backend:   http://localhost:8000                              ║"
echo "║  API Docs:  http://localhost:8000/docs                         ║"
echo "║  pgAdmin:   http://localhost:5050                              ║"
echo "║             (login: admin@metrostack.local / admin)            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "→ To stop services:"
echo "    docker-compose down"
echo ""
echo "→ To view logs:"
echo "    docker-compose logs -f"
echo ""
echo "→ Ready to use! Open http://localhost:3000 in your browser."
