@echo off
echo Fixing Backend Logging Issues...

REM Stop any existing backend processes
echo Stopping backend processes...
taskkill /f /im python.exe 2>nul
taskkill /f /im uvicorn.exe 2>nul

REM Wait a moment for processes to fully stop
timeout /t 2 /nobreak >nul

REM Clean up potentially locked log files
echo Cleaning up log files...
cd /d "C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\backend"

REM Remove or rename locked log files if they exist
if exist "logs\database.log.1" del "logs\database.log.1" 2>nul
if exist "logs\platform.log.1" del "logs\platform.log.1" 2>nul
if exist "logs\platform_master.log.1" del "logs\platform_master.log.1" 2>nul
if exist "logs\agents.log.1" del "logs\agents.log.1" 2>nul

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir "logs"

echo Log cleanup complete!

REM Optional: Start the backend with the fixed logging
echo Starting backend with fixed logging...
python -m app.main

pause
