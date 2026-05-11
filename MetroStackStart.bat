@echo off
SETLOCAL EnableDelayedExpansion

:: MetroStack Quick Start Script for Windows
:: Starts the full stack in development mode

echo ==================================================================
echo                      METROSTACK QUICK START                      
echo ==================================================================
echo.

:: Check prerequisites
echo - Checking prerequisites...

where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo X Docker not found. Please install Docker Desktop.
    exit /b 1
)

where docker-compose >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo X Docker Compose not found. Please install Docker Compose.
    exit /b 1
)

echo ^[V^] Docker found
echo ^[V^] Docker Compose found
echo.

:: Start backend services
echo - Starting backend services (PostgreSQL, Redis, FastAPI)...
docker-compose up -d db redis api

:: Wait for database to be ready (timeout is the Windows equivalent of sleep)
echo - Waiting for PostgreSQL to be ready...
timeout /t 5 /nobreak >nul

:: Run database migrations
echo - Running database migrations...
docker-compose exec -T api alembic upgrade head

echo ^[V^] Backend services started
echo.

:: Check if Node.js is available for local frontend dev
where node >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo - Node.js found - starting frontend locally...
    pushd frontend
    
    if not exist "node_modules\" (
        echo - Installing frontend dependencies...
        call npm install
    )
    
    echo - Starting Vite dev server...
    :: Starts the process in the background
    start /b npm run dev
    popd
    
    echo ^[V^] Frontend started locally
) else (
    echo - Node.js not found - starting frontend in Docker...
    docker-compose up -d frontend
    echo ^[V^] Frontend container started
)

echo.
echo ==================================================================
echo                        SERVICES RUNNING                         
echo ==================================================================
echo   Frontend:  http://localhost:3000                              
echo   Backend:   http://localhost:8000                              
echo   API Docs:  http://localhost:8000/docs                         
echo   pgAdmin:   http://localhost:5050                              
echo              (login: admin@metrostack.local / admin)            
echo ==================================================================
echo.
echo - To stop services:
echo     docker-compose down
echo.
echo - To view logs:
echo     docker-compose logs -f
echo.
echo - Ready to use! Open http://localhost:3000 in your browser.

pause