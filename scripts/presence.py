#!/usr/bin/env python3
"""
Discord Rich Presence for Claude Code
Manages Discord RPC connection and updates presence based on Claude Code activity.
"""

import sys
import os
import json
import time
import atexit
import signal
from pathlib import Path
from datetime import datetime

# Discord Application ID
DISCORD_APP_ID = "1330919293709324449"

# Data directory
if sys.platform == "win32":
    DATA_DIR = Path(os.environ.get("APPDATA", "")) / "cc-discord-rpc"
else:
    DATA_DIR = Path.home() / ".local" / "share" / "cc-discord-rpc"

STATE_FILE = DATA_DIR / "state.json"
PID_FILE = DATA_DIR / "daemon.pid"
LOG_FILE = DATA_DIR / "daemon.log"

# Tool to display name mapping
TOOL_DISPLAY = {
    "Edit": "Editing",
    "Write": "Writing",
    "Read": "Reading",
    "Bash": "Running command",
    "Glob": "Searching files",
    "Grep": "Searching code",
    "Task": "Delegating task",
    "WebFetch": "Fetching web content",
    "WebSearch": "Researching",
}

# Idle timeout in seconds (15 minutes)
IDLE_TIMEOUT = 15 * 60


def log(message: str):
    """Append message to log file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def read_state() -> dict:
    """Read current state from state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def write_state(state: dict):
    """Write state to state file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_daemon_pid() -> int | None:
    """Get PID of running daemon, or None if not running."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is actually running
        if sys.platform == "win32":
            import subprocess
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True
            )
            if str(pid) in result.stdout:
                return pid
        else:
            os.kill(pid, 0)  # Doesn't kill, just checks
            return pid
    except (ValueError, ProcessLookupError, PermissionError, IOError):
        pass
    return None


def write_pid():
    """Write current PID to file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def remove_pid():
    """Remove PID file."""
    try:
        PID_FILE.unlink()
    except IOError:
        pass


def get_project_name() -> str:
    """Get project name from current working directory."""
    cwd = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    return Path(cwd).name


def read_hook_input() -> dict:
    """Read JSON input from stdin (provided by Claude Code hooks)."""
    try:
        if not sys.stdin.isatty():
            data = sys.stdin.read()
            if data.strip():
                return json.loads(data)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def run_daemon():
    """Run the Discord RPC daemon loop."""
    from pypresence import Presence

    log("Daemon starting...")
    write_pid()
    atexit.register(remove_pid)

    # Handle graceful shutdown
    def shutdown(signum, frame):
        log("Received shutdown signal")
        remove_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # Connect to Discord
    rpc = None
    connected = False
    last_sent = {}  # Track last sent state to avoid redundant updates

    while True:
        try:
            # Try to connect if not connected
            if not connected:
                try:
                    rpc = Presence(DISCORD_APP_ID)
                    rpc.connect()
                    connected = True
                    log("Connected to Discord")
                except Exception as e:
                    log(f"Failed to connect to Discord: {e}")
                    time.sleep(5)
                    continue

            # Read current state
            state = read_state()

            if not state:
                time.sleep(1)
                continue

            # Check for idle timeout
            last_update = state.get("last_update", 0)
            if time.time() - last_update > IDLE_TIMEOUT:
                log("Idle timeout reached, clearing presence")
                if rpc:
                    try:
                        rpc.clear()
                    except:
                        pass
                write_state({})
                last_sent = {}
                time.sleep(5)
                continue

            # Update presence
            tool = state.get("tool", "")
            project = state.get("project", "Claude Code")
            session_start = state.get("session_start", int(time.time()))

            details = TOOL_DISPLAY.get(tool, "Working")

            # Only update if something changed
            current = {"details": details, "project": project}
            if current != last_sent:
                log(f"Sending to Discord: {details} on {project}")
                try:
                    rpc.update(
                        state=f"on {project}",
                        details=details,
                        start=session_start,
                        large_image="claude",
                        large_text="Claude Code",
                    )
                    last_sent = current
                except Exception as e:
                    log(f"Failed to update presence: {e}")
                    connected = False
                    rpc = None

            time.sleep(1)

        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"Daemon error: {e}")
            time.sleep(5)

    # Cleanup
    if rpc:
        try:
            rpc.clear()
            rpc.close()
        except:
            pass
    log("Daemon stopped")


def cmd_start():
    """Handle 'start' command - spawn daemon if needed, update state."""
    hook_input = read_hook_input()
    project = hook_input.get("cwd", os.environ.get("CLAUDE_PROJECT_DIR", ""))
    project_name = Path(project).name if project else get_project_name()

    # Update state
    state = read_state()
    now = int(time.time())

    if not state.get("session_start"):
        state["session_start"] = now

    state["project"] = project_name
    state["last_update"] = now
    state["tool"] = ""
    write_state(state)

    # Check if daemon is running
    if get_daemon_pid():
        log("Daemon already running")
        return

    # Spawn daemon in background
    log(f"Starting daemon for project: {project_name}")

    if sys.platform == "win32":
        import subprocess
        # Use pythonw if available for windowless execution
        python_exe = sys.executable
        script_path = Path(__file__).resolve()

        subprocess.Popen(
            [python_exe, str(script_path), "daemon"],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        # Unix: fork and detach
        pid = os.fork()
        if pid == 0:
            # Child process
            os.setsid()
            sys.stdin.close()
            sys.stdout.close()
            sys.stderr.close()
            run_daemon()
            sys.exit(0)


def cmd_update():
    """Handle 'update' command - update current activity."""
    hook_input = read_hook_input()
    tool_name = hook_input.get("tool_name", "")

    state = read_state()
    if not state:
        # No active session, ignore
        return

    state["tool"] = tool_name
    state["last_update"] = int(time.time())
    write_state(state)

    log(f"Updated activity: {tool_name}")


def cmd_stop():
    """Handle 'stop' command - clear presence and stop daemon."""
    log("Stop command received")

    # Clear state
    write_state({})

    # Kill daemon if running
    pid = get_daemon_pid()
    if pid:
        try:
            if sys.platform == "win32":
                import subprocess
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                             capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
            log(f"Stopped daemon (PID {pid})")
        except Exception as e:
            log(f"Failed to stop daemon: {e}")

    remove_pid()


def cmd_status():
    """Handle 'status' command - show current status."""
    pid = get_daemon_pid()
    state = read_state()

    if pid:
        print(f"Daemon running (PID {pid})")
    else:
        print("Daemon not running")

    if state:
        print(f"Project: {state.get('project', 'Unknown')}")
        print(f"Last tool: {state.get('tool', 'None')}")
        last_update = state.get("last_update", 0)
        if last_update:
            ago = int(time.time() - last_update)
            print(f"Last update: {ago}s ago")
    else:
        print("No active session")


def main():
    if len(sys.argv) < 2:
        print("Usage: presence.py <start|update|stop|status|daemon>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        cmd_start()
    elif command == "update":
        cmd_update()
    elif command == "stop":
        cmd_stop()
    elif command == "status":
        cmd_status()
    elif command == "daemon":
        run_daemon()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
