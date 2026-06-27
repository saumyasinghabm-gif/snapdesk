@echo off
:: SnapKey Agent Starter - Simple configuration for non-technical users
:: This file can be used to start the agent manually or automatically

:: Configuration - Fixed backend URL (no editing needed)
set BACKEND_WS_URL=wss://snapdesk-backend.onrender.com/ws/agent
if not defined SUPPORT_AGENT_ID set "SUPPORT_AGENT_ID=%COMPUTERNAME%"

:: Check if we're running in auto-start mode (no console window)
if "%1"=="--auto" (
    :: Auto-start mode - run silently in background
    start "" /B .\snapkey-agent.exe
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
    .\snapkey-agent.exe

    :: Keep window open if agent exits
    echo.
    echo Agent stopped. Press any key to close this window.
    pause >nul
)
