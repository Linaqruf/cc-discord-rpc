#!/usr/bin/env python3
"""
Statusline script for Claude Code - updates Discord RPC state with token/cost data.

This script is called by Claude Code's statusline feature every ~300ms.
It reads token/cost data from stdin (JSON) and writes to state.json for the daemon.

Setup in ~/.claude/settings.json:
{
  "statusLine": {
    "type": "command",
    "command": "python /path/to/cc-discord-rpc/scripts/statusline.py"
  }
}
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Data directory (same as presence.py)
if sys.platform == "win32":
    DATA_DIR = Path(os.environ.get("APPDATA", "")) / "cc-discord-rpc"
else:
    DATA_DIR = Path.home() / ".local" / "share" / "cc-discord-rpc"

STATE_FILE = DATA_DIR / "state.json"
LOG_FILE = DATA_DIR / "daemon.log"


def log(message: str):
    """Append message to log file."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [statusline] {message}\n")
    except OSError:
        pass


def read_state() -> dict:
    """Read current state from state file."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def write_state(state: dict):
    """Write state to state file."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as e:
        log(f"Warning: Could not write state: {e}")


def format_tokens(count: int) -> str:
    """Format token count for display (e.g., 12.5k, 1.2M)."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    elif count >= 1000:
        return f"{count / 1000:.1f}k"
    return str(count)


def main():
    """Main statusline handler."""
    # Read JSON from stdin (Claude Code statusline data)
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Output empty statusline on error
        print("")
        return

    # Extract model info
    model_info = data.get("model", {})
    model_display = model_info.get("display_name", "")
    model_id = model_info.get("id", "")

    # Extract cost info
    cost_info = data.get("cost", {})
    total_cost = cost_info.get("total_cost_usd", 0.0)

    # Extract token info
    context = data.get("context_window", {})
    total_input = context.get("total_input_tokens", 0)
    total_output = context.get("total_output_tokens", 0)

    # Current usage has cache info
    current_usage = context.get("current_usage") or {}
    cache_read = current_usage.get("cache_read_input_tokens", 0)
    cache_write = current_usage.get("cache_creation_input_tokens", 0)

    # Calculate simple cost estimate (input + output at base rates)
    # This is an approximation since statusline doesn't provide it
    simple_tokens = total_input + total_output
    # Rough estimate: assume average $4/M input, $12/M output (mid-tier pricing)
    simple_cost = (total_input * 4 + total_output * 12) / 1_000_000

    # Update state.json with token data (merge with existing hook data)
    state = read_state()
    if state:  # Only update if session exists (started by hook)
        # Update model if we have it
        if model_display:
            state["model"] = model_display
        if model_id:
            state["model_id"] = model_id

        # Update tokens
        state["tokens"] = {
            "input": total_input,
            "output": total_output,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "cost": total_cost,
            "simple_cost": simple_cost,
        }

        # Mark statusline update time
        state["statusline_update"] = int(datetime.now().timestamp())

        write_state(state)

    # Output statusline for Claude Code UI
    # This appears at the bottom of the Claude Code interface
    total_tokens = total_input + total_output
    if total_tokens > 0:
        tokens_str = format_tokens(total_tokens)
        cost_str = f"${total_cost:.2f}" if total_cost >= 0.01 else f"${total_cost:.3f}"
        print(f"[{model_display}] {tokens_str} | {cost_str}")
    elif model_display:
        print(f"[{model_display}]")
    else:
        print("")


if __name__ == "__main__":
    main()
