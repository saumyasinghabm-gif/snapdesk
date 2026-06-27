@echo off
:: SnapKey Agent Auto-Start Repair
:: Removes old startup entries and recreates them with the current folder paths.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrator privileges.
    echo Please right-click and select "Run as administrator".
    pause
    exit /b 1
)

set "AGENT_DIR=%~dp0"
set "AGENT_DIR=%AGENT_DIR:~0,-1%"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo =========================================================
echo        SnapKey Agent Auto-Start Repair
echo =========================================================
echo.

if not exist "%AGENT_DIR%\snapkey-agent.exe" (
    echo ERROR: snapkey-agent.exe not found in %AGENT_DIR%
    echo Please extract the complete SnapKey agent ZIP before running this file.
    pause
    exit /b 1
)

echo Removing old startup entries...
del "%STARTUP_DIR%\SnapKey Agent.lnk" >nul 2>&1
schtasks /delete /tn "SnapKey Agent" /f >nul 2>&1

echo Recreating startup entries...
call "%AGENT_DIR%\setup-autostart.bat"
