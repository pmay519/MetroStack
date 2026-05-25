@echo off
title MetroStack - Master Launcher
color 0A

echo.
echo  ============================================================
echo   MetroStack - Local AI Crew Launcher
echo   Junior Coder  ^| Port 8080  (Qwen Coder Server)
echo   Senior Reasoner ^| Port 8081 (DeepSeek Coder Server)
echo  ============================================================
echo.

:: ----------------------------------------------------------------
:: STEP 1 - Start Junior Coder server (port 8080) in foreground window
::          Removed /MIN so you can see Layer 2 token processing
:: ----------------------------------------------------------------
echo [1/4] Starting Junior Coder server on port 8080...
start "ISAAC - Junior" cmd /c ^
    "cd /d C:\AI\llama.cpp && llama-server.exe -m C:\AI\llama.cpp\models\llama-3.2-3b-instruct-q4_k_m.gguf -c 8192 --port 8080 --host 127.0.0.1"

:: ----------------------------------------------------------------
:: STEP 2 - Start Senior Reasoner server (port 8081) in foreground window
::          Removed /MIN so you can see Layer 2 prompt evaluation
:: ----------------------------------------------------------------
echo [2/4] Starting Senior Reasoner server on port 8081...
start "DANTE - Senior" cmd /c ^
    "cd /d C:\AI\llama.cpp && llama-server.exe -m C:\AI\llama.cpp\models\stable-code-3b.Q4_K_M.gguf -c 8192 --port 8081 --host 127.0.0.1"

:: ----------------------------------------------------------------
:: STEP 3 - Wait for both servers to become ready
::          Uses netstat to check TCP LISTENING state - works on all
::          Windows versions without PowerShell 7 dependency.
:: ----------------------------------------------------------------
echo [3/4] Waiting for servers to become ready...
echo       (Polling ports 8080 and 8081 - up to 240 seconds)
echo.

set /a ATTEMPTS=0
set /a MAX_ATTEMPTS=24

:WAIT_LOOP
    set /a ATTEMPTS+=1
    if %ATTEMPTS% GTR %MAX_ATTEMPTS% (
        echo.
        echo [ERROR] Servers did not become ready within 240 seconds.
        echo.
        echo   Diagnostics:
        netstat -an | findstr ":8080 " | findstr "LISTENING" >nul 2>&1
        if errorlevel 1 (echo   Port 8080 ^(Junior^)  : NOT listening) else (echo   Port 8080 ^(Junior^)  : OK - listening)
        netstat -an | findstr ":8081 " | findstr "LISTENING" >nul 2>&1
        if errorlevel 1 (echo   Port 8081 ^(Senior^)  : NOT listening) else (echo   Port 8081 ^(Senior^)  : OK - listening)
        echo.
        echo   Check the server windows for error messages.
        pause
        exit /b 1
    )

    :: Check port 8080 - Junior Coder (Qwen Coder Server)
    netstat -an | findstr ":8080 " | findstr "LISTENING" >nul 2>&1
    set JUNIOR_OK=%ERRORLEVEL%

    :: Check port 8081 - Senior Reasoner (DeepSeek Coder Server)
    netstat -an | findstr ":8081 " | findstr "LISTENING" >nul 2>&1
    set SENIOR_OK=%ERRORLEVEL%

    :: Report individual status each attempt
    if %JUNIOR_OK%==0 (set JUNIOR_STATUS=READY) else (set JUNIOR_STATUS=waiting...)
    if %SENIOR_OK%==0 (set SENIOR_STATUS=READY) else (set SENIOR_STATUS=waiting...)
    echo   Attempt %ATTEMPTS%/%MAX_ATTEMPTS%  ^|  8080 Junior: %JUNIOR_STATUS%  ^|  8081 Senior: %SENIOR_STATUS%

    if %JUNIOR_OK%==0 if %SENIOR_OK%==0 goto SERVERS_READY

    timeout /t 5 /nobreak >nul
goto WAIT_LOOP

:SERVERS_READY
echo.
echo  [OK] Both servers are online and ready.
echo.

:: ----------------------------------------------------------------
:: STEP 4 - Launch metro_crew.py
::          Force UTF-8 so CrewAI/AgentOps emoji in logs don't crash
::          the cp1252 Windows terminal codepage.
:: ----------------------------------------------------------------
echo [4/4] Launching metro_crew.py...
echo.

:: Switch terminal to UTF-8 (codepage 65001) for this session only
chcp 65001 >nul

:: Tell Python stdout/stderr to use UTF-8 regardless of terminal locale
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set METROSTACK=C:\Users\%USERNAME%\Desktop\MetroStack

cd /d %METROSTACK%
call %METROSTACK%\venv\Scripts\activate.bat

python %METROSTACK%\metro_crew.py

echo.
echo  ============================================================
echo   MetroStack crew execution complete.
echo   Server windows remain open.
echo   Close them manually when done, or run MetroStackStop.bat
echo  ============================================================
echo.
pause