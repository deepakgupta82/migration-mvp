@echo off
REM =====================================================================================
REM Nagarro AgentiMigrate Platform - Windows Stop Script
REM =====================================================================================

echo 🛑 Stopping Nagarro AgentiMigrate Platform
echo ==========================================

REM Determine Docker Compose command
docker compose version >nul 2>&1
if %errorlevel% equ 0 (
    set DOCKER_COMPOSE=docker compose
) else (
    set DOCKER_COMPOSE=docker-compose
)

if "%1"=="--soft" goto soft_stop
if "%1"=="--hard" goto hard_stop
if "%1"=="--reset" goto reset_stop
if "%1"=="--help" goto show_help

REM Interactive mode
echo Select stop option:
echo 1) Soft stop (containers only)
echo 2) Standard stop (remove containers)
echo 3) Hard reset (remove containers and data)
echo.
set /p choice="Enter choice (1-3): "

if "%choice%"=="1" goto soft_stop
if "%choice%"=="2" goto hard_stop
if "%choice%"=="3" goto reset_confirm
goto invalid_choice

:soft_stop
echo 🔄 Soft stop (containers only)...
%DOCKER_COMPOSE% stop
goto end

:hard_stop
echo 🛑 Standard stop (remove containers)...
%DOCKER_COMPOSE% down --remove-orphans
goto end

:reset_confirm
echo ⚠️  WARNING: This will remove all data including projects and uploads!
set /p confirm="Are you sure? (y/N): "
if /i "%confirm%"=="y" goto reset_stop
echo ❌ Reset cancelled
goto end

:reset_stop
echo 💥 Full reset (remove containers and volumes)...
%DOCKER_COMPOSE% down -v --remove-orphans
echo 🧹 Cleaning up Docker system...
docker system prune -f
goto end

:show_help
echo Usage: %0 [option]
echo.
echo Options:
echo   --soft    Stop containers only (data preserved)
echo   --hard    Remove containers (data preserved)
echo   --reset   Remove containers and all data
echo   --help    Show this help message
echo.
echo If no option is provided, interactive mode will be used.
goto end

:invalid_choice
echo ❌ Invalid choice
goto end

:end
echo.
echo ✅ Platform stopped successfully!
echo.
echo 📋 Next steps:
echo   🚀 To restart: build-optimized.bat
echo   🏥 To check status: health-check.bat
echo   📊 To view Docker usage: docker system df
echo.
pause
