# cc-discord-rpc

Claude Code plugin that displays your coding activity as Discord Rich Presence.

## Features

- Shows current activity (Editing, Reading, Running, etc.)
- Displays project name
- Elapsed time counter
- Auto-starts when Claude Code session begins
- Auto-clears after 15 minutes of inactivity

## Prerequisites

- Python 3.10+
- Discord desktop app running
- pypresence library

## Installation

1. Install pypresence:
   ```bash
   pip install pypresence
   ```

2. Copy this plugin to your Claude Code plugins directory:
   ```bash
   # Option 1: Project-level (just this project)
   cp -r cc-discord-rpc /path/to/your/project/.claude-plugins/

   # Option 2: Global plugins
   cp -r cc-discord-rpc ~/.claude/plugins/
   ```

3. Restart Claude Code

## Discord Setup

The plugin uses Discord Application ID `1330919293709324449`. To use your own:

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Copy the Application ID
4. Edit `scripts/presence.py` and update `DISCORD_APP_ID`
5. Upload assets (optional): Add a "claude" image in Rich Presence > Art Assets

## How It Works

The plugin uses Claude Code hooks:

- **SessionStart**: Spawns the Discord RPC daemon
- **PreToolUse**: Updates activity (Edit, Bash, Read, etc.)
- **Stop**: Clears presence and stops daemon

## Files

```
cc-discord-rpc/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── hooks/
│   └── hooks.json           # Hook definitions
├── scripts/
│   ├── presence.py          # Discord RPC manager
│   └── requirements.txt     # Python dependencies
├── README.md
├── SPEC.md
└── CLAUDE.md
```

## Manual Control

You can also control the presence manually:

```bash
# Check status
python scripts/presence.py status

# Stop presence
python scripts/presence.py stop
```

## Troubleshooting

**Presence not showing:**
- Make sure Discord desktop app is running
- Check if pypresence is installed: `pip show pypresence`
- Check logs: `%APPDATA%/cc-discord-rpc/daemon.log` (Windows)

**"Could not connect" errors:**
- Discord must be running before Claude Code starts
- Try restarting Discord

**Multiple sessions:**
- Currently only supports one Claude Code session at a time

## License

MIT
