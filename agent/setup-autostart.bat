@echo off
:: SnapKey Agent Auto-Start Setup
:: This script configures the agent to run automatically when Windows starts.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrator privileges.
    echo Please right-click and select "Run as administrator".
    pause
    exit /b 1
)

set "AGENT_DIR=%~dp0"
set "AGENT_DIR=%AGENT_DIR:~0,-1%"

echo =========================================================
echo        SnapKey Agent Auto-Start Setup
echo =========================================================
echo.

if not exist "%AGENT_DIR%\snapkey-agent.exe" (
    echo ERROR: snapkey-agent.exe not found in %AGENT_DIR%
    echo Please make sure the agent executable is in the same folder as this script.
    pause
    exit /b 1
)

echo Checking backend connectivity to wss://snapdesk-backend.onrender.com...
ping -n 2 -w 1000 snapdesk-backend.onrender.com >nul 2>&1
if %errorlevel% equ 0 (
    echo Backend is reachable
) else (
    echo Could not verify backend connectivity - may need internet connection
)
echo.

set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
echo Creating startup shortcut in %STARTUP_DIR%...

(
    echo Set WshShell = WScript.CreateObject("WScript.Shell"^)
    echo Set Shortcut = WshShell.CreateShortcut("%STARTUP_DIR%\SnapKey Agent.lnk"^)
    echo Shortcut.TargetPath = "%AGENT_DIR%\SnapKey-Agent-Starter.bat"
    echo Shortcut.Arguments = "--auto"
    echo Shortcut.WorkingDirectory = "%AGENT_DIR%"
    echo Shortcut.WindowStyle = 7
    echo Shortcut.Description = "SnapKey Remote Access Agent - Auto-start"
    echo Shortcut.Save
) > "%TEMP%\create_shortcut.vbs"

cscript //nologo "%TEMP%\create_shortcut.vbs"
del "%TEMP%\create_shortcut.vbs"

echo Creating Task Scheduler entry for SnapKey Agent...
schtasks /delete /tn "SnapKey Agent" /f >nul 2>&1
schtasks /create /tn "SnapKey Agent" /tr "\"%AGENT_DIR%\SnapKey-Agent-Starter.bat\" --auto" /sc onlogon /rl highest /f
set "TASK_RESULT=%errorlevel%"

if "%TASK_RESULT%"=="0" (
    echo.
    echo SUCCESS! SnapKey Agent is now configured to auto-start when Windows starts.
    echo.
    echo What was configured:
    echo 1. Startup folder shortcut - runs when user logs in
    echo 2. Task Scheduler entry - runs at Windows startup
    echo.
    echo The agent will now automatically start in the background when:
    echo - The computer boots up
    echo - Any user logs in to Windows
    echo.
    echo You can test it now by running: SnapKey-Agent-Starter.bat --auto
    echo.
) else (
    echo.
    echo WARNING: Could not create Task Scheduler entry.
    echo But the startup folder shortcut was created successfully.
    echo The agent will start when the user logs in.
    echo.
)

echo Setup complete. You can close this window.
pause
