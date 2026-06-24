@echo off
:: SnapKey Agent Starter - Simple configuration for non-technical users
:: Just double-click this file to start the agent

:: Configuration - Edit these lines to match your setup
set BACKEND_WS_URL=ws://localhost:8000/ws/agent
set AGENT_TOKEN=dev-agent-token

:: Start the agent
echo Starting SnapKey Agent...
echo Backend: %BACKEND_WS_URL%
echo Token: %AGENT_TOKEN%
echo.
echo =========================================================
echo          SnapKey Remote Access Agent
echo =========================================================
echo.

:: Run the agent executable
.\dist\agent.exe

:: Keep window open if agent exits
echo.
echo Agent stopped. Press any key to close this window.
pause >nul