@echo off
:: Test script to verify auto-start functionality
echo Testing SnapKey Agent Auto-Start Configuration...

:: Test 1: Check if batch file supports --auto argument
echo.
echo Test 1: Checking batch file syntax...
call SnapKey-Agent-Starter.bat --auto
if %errorlevel% equ 0 (
    echo ✅ Batch file supports --auto argument
) else (
    echo ❌ Batch file does not support --auto argument
)

:: Test 2: Verify required files exist
echo.
echo Test 2: Checking required files...
if exist "snapkey-agent.exe" (
    echo ✅ snapkey-agent.exe found
) else (
    echo ❌ snapkey-agent.exe missing
)

if exist "SnapKey-Agent-Starter.bat" (
    echo ✅ SnapKey-Agent-Starter.bat found
) else (
    echo ❌ SnapKey-Agent-Starter.bat missing
)

if exist "Setup-AutoStart.bat" (
    echo ✅ Setup-AutoStart.bat found
) else (
    echo ❌ Setup-AutoStart.bat missing
)

echo.
echo Test complete. Check the results above.
echo.
echo To set up auto-start for real use:
echo 1. Edit SnapKey-Agent-Starter.bat with your backend URL and token
echo 2. Run Setup-AutoStart.bat as administrator
echo 3. Restart your computer to test auto-start
pause