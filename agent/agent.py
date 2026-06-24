"""
=============================================================================
SnapKey Remote Access - Local Agent
=============================================================================
Runs on the support operator's local Windows machine. It connects to the
central FastAPI WebSocket endpoint, listens for remote connection commands,
and automates starting AnyDesk with optional unattended credentials.

SECURITY / DESIGN BOUNDARY:
This agent strictly launches the official AnyDesk client. It does NOT bypass,
automate clicking, or screen-scrape AnyDesk confirmation dialogs.
It only uses AnyDesk's native, documented `--with-password` command-line parameter
for unattended access which requires pre-consent and setup on the target machine.
=============================================================================
"""

import os
import sys
import json
import time
import asyncio
import subprocess
import psutil
import websockets

# Retrieve environment configuration or use default safe fallbacks
BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "ws://127.0.0.1:8000/ws/agent")
# AGENT_TOKEN removed - no longer needed

# Well-known Windows installations paths for AnyDesk
COMMON_PATHS = [
    r"C:\Program Files (x86)\AnyDesk\AnyDesk.exe",
    r"C:\Program Files\AnyDesk\AnyDesk.exe",
    r"C:\Users\Public\AnyDesk\AnyDesk.exe",
    r"C:\ProgramData\AnyDesk\AnyDesk.exe",
]


def find_anydesk_from_processes() -> str | None:
    try:
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                if proc.info["name"] and "anydesk" in proc.info["name"].lower():
                    if proc.info["exe"] and os.path.exists(proc.info["exe"]):
                        return proc.info["exe"]
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass
    return None


def find_anydesk_in_common_paths() -> str | None:
    username = os.getenv("USERNAME", "")
    paths = list(COMMON_PATHS)
    if username:
        paths.extend([
            rf"C:\Users\{username}\AppData\Local\AnyDesk\AnyDesk.exe",
            rf"C:\Users\{username}\AppData\Roaming\AnyDesk\AnyDesk.exe",
        ])
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def find_anydesk_in_path() -> str | None:
    try:
        result = subprocess.run(
            ["where", "AnyDesk.exe"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            path = result.stdout.strip().split("\n")[0]
            if path and os.path.exists(path):
                return path
    except Exception:
        pass
    return None


def find_anydesk_path() -> str | None:
    """Discovers the AnyDesk executable on the current system."""
    return (
        find_anydesk_from_processes()
        or find_anydesk_in_common_paths()
        or find_anydesk_in_path()
    )


def is_anydesk_running() -> bool:
    try:
        for proc in psutil.process_iter(["name"]):
            if proc.info["name"] and "anydesk" in proc.info["name"].lower():
                return True
    except Exception:
        pass
    return False


def run_anydesk_connection(anydesk_path: str, anydesk_id: str, password: str | None):
    """
    Spawns AnyDesk and passes the target ID and password.
    If AnyDesk is not running, we open the main window first, then run the link.
    """
    try:
        # Check if AnyDesk is running, start if not
        if not is_anydesk_running():
            print("AnyDesk is not currently running. Starting the main process...")
            subprocess.Popen([anydesk_path])
            time.sleep(2)  # small buffer for the system socket to bind

        print(f"Connecting to AnyDesk ID: {anydesk_id}")

        if password:
            print("Using pre-configured password for automated connection...")
            # Run AnyDesk using standard input stream to safely transfer credentials
            p = subprocess.Popen(
                [anydesk_path, anydesk_id, "--with-password"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Pass password via stdin stream safely without exposing in process parameters
            p.communicate(input=password, timeout=10)
        else:
            print("Connecting without unattended password...")
            subprocess.Popen([anydesk_path, anydesk_id])

    except Exception as e:
        print(f"Failed to execute AnyDesk connection: {e}")


async def listen_for_commands():
    # WebSocket URL without token (token verification removed)
    url = BACKEND_WS_URL
    print("=========================================================")
    print("         SnapKey Remote Access Agent Starting")
    print("=========================================================")
    print(f"Backend WS Endpoint : {BACKEND_WS_URL}")
    print("Agent Status        : Connected (no token required)")
    print("=========================================================")

    while True:
        try:
            async with websockets.connect(url) as websocket:
                print("\n[CONNECTED] Established real-time link with SnapKey Cloud!")
                print("Ready and listening for connections...")
                
                while True:
                    message = await websocket.recv()
                    try:
                        data = json.loads(message)
                        action = data.get("action")
                        
                        if action == "connect":
                            anydesk_id = str(data.get("anydesk_id"))
                            password = data.get("password")
                            
                            anydesk_path = find_anydesk_path()
                            if not anydesk_path:
                                print(f"[ERROR] Received connect request for ID '{anydesk_id}', but AnyDesk.exe was not found locally!")
                                continue
                            
                            run_anydesk_connection(anydesk_path, anydesk_id, password)
                            
                    except json.JSONDecodeError:
                        print(f"[WARN] Non-JSON payload received: {message}")
                    except Exception as e:
                        print(f"[ERROR] Parsing and executing command: {e}")
                        
        except Exception as e:
            print(f"[DISCONNECTED] Connection to server failed: {e}")
            print("Retrying in 5 seconds...")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(listen_for_commands())
    except KeyboardInterrupt:
        print("\nAgent stopped by user.")


# =============================================================================
# WINDOWS AUTOMATIC STARTUP INSTRUCTIONS
# =============================================================================
#
# To ensure this agent runs continuously on your support machines when Windows
# starts up, choose one of the following methods:
#
# METHOD 1: Windows Startup Folder (Easiest)
# ----------------------------------------
# 1. Press Win + R, type "shell:startup", and click OK. This opens the Startup directory.
# 2. Right-click in the folder and select New > Shortcut.
# 3. Enter the command to start your agent, for example:
#    cmd.exe /k "set AGENT_TOKEN=your-token-here&&set BACKEND_WS_URL=wss://your-backend.onrender.com/ws/agent&&python C:\path\to\agent.py"
# 4. Click Next, name your shortcut (e.g. "SnapKey Agent"), and click Finish.
#
# METHOD 2: Windows Task Scheduler (Recommended for production/hidden startup)
# ----------------------------------------------------------------------------
# 1. Press Win + R, type "taskschd.msc" and hit Enter.
# 2. Click "Create Basic Task..." in the Actions pane on the right.
# 3. Name the task "SnapKey Support Agent" and click Next.
# 4. Select Trigger: "When I log on" and click Next.
# 5. Select Action: "Start a program" and click Next.
# 6. In Program/script, enter: pythonw.exe (this executes python silently without opening a terminal window)
#    Or enter "python.exe" if you wish to see the diagnostic logs on-screen.
# 7. In "Add arguments (optional)", enter the absolute path to your script:
#    C:\path\to\agent.py
# 8. In "Start in (optional)", enter the folder path:
#    C:\path\to\
# 9. Click Finish.
# 10. (Optional) To configure Environment Variables such as AGENT_TOKEN or BACKEND_WS_URL:
#     - Right-click the newly created task in the list and select Properties.
#     - Instead of direct execution, you can point the task's program to a batch file (.bat)
#       that sets the environment variables first, then runs the python script:
#
#       @echo off
#       set BACKEND_WS_URL=wss://your-backend.onrender.com/ws/agent
#       set AGENT_TOKEN=your-token-here
#       python C:\path\to\agent.py
#
# =============================================================================
