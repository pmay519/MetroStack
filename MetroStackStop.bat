@echo off
SETLOCAL EnableDelayedExpansion

:: MetroStack Stop Script
:: Gracefully stops all services

echo ==================================================================
echo                      STOPPING METROSTACK                         
echo ==================================================================
echo.

echo - Stopping Docker containers... 
docker-compose down 

echo - Stopping any local frontend processes... 
:: This kills any local node processes started by the Start script 
taskkill /F /IM node.exe /T 2>nul 

echo.
echo ^[V^] All services stopped [cite: 16]
echo.
echo - To remove all data (CAUTION: deletes database): [cite: 16]
echo     docker-compose down -v [cite: 16]
echo.
pause [cite: 17]