@echo off
:: SnapKey Agent Starter - Simple configuration for non-technical users
:: This file can be used to start the agent manually or automatically

:: Configuration - Fixed backend URL (no editing needed)
set BACKEND_WS_URL=wss://snapdesk-backend.onrender.com/ws/agent
if not defined SUPPORT_AGENT_ID set "SUPPORT_AGENT_ID=%COMPUTERNAME%"
set "AGENT_DIR=%~dp0"
set "AGENT_EXE=%AGENT_DIR%snapkey-agent.exe"

if not exist "%AGENT_EXE%" (
    echo ERROR: snapkey-agent.exe was not found next to this starter file.
    echo Expected location: %AGENT_EXE%
    echo.
    echo Please extract the complete SnapKey agent ZIP before running this file.
    pause
    exit /b 1
)

:: Check if we're running in auto-start mode (no console window)
if "%1"=="--auto" (
    :: Auto-start mode - run silently in background
    start "" /MIN "%AGENT_EXE%"
    exit /b 0
) else (
    :: Manual start mode - show console window
    echo Starting SnapKey Agent...
    echo Backend: %BACKEND_WS_URL%
    echo Support Agent ID: %SUPPORT_AGENT_ID%
    echo.
    echo =========================================================
    echo          SnapKey Remote Access Agent
    echo =========================================================
    echo.

    :: Run the agent executable
    "%AGENT_EXE%"

    :: Keep window open if agent exits
    echo.
    echo Agent stopped. Press any key to close this window.
    pause >nul
)
