---
name: travel-monitor
description: Register or check travel bookings for monitoring (delays, cancellations, price drops)
command: /travel-monitor
model: claude-sonnet-4-6
tools: [Read, Write, Bash, mcp__cortex__cortex_store]
---

# /travel-monitor — Booking Monitor

Monitor confirmed bookings for schedule changes, cancellations, and price drops.

## Usage
- `/travel-monitor register PNR ABC123 Turkish Airlines TK1234 May 10`
- `/travel-monitor check`
- `/travel-monitor list`

## Actions

### register
Add a booking to `~/.claude/plugins/travel/resources/state.json` monitored_bookings array.
Use the `register-pnr` skill at `~/.claude/plugins/travel/skills/register-pnr/SKILL.md`.

### check
Poll all active bookings for changes NOW (bypasses the 6h daemon schedule).
Run `python3 ~/.nexus/scripts/travel/change-monitor.py --daemon` via Bash.

### list
Read `~/.claude/plugins/travel/resources/state.json` and display monitored_bookings as a formatted table.

## LaunchAgent
The daemon at `com.nexus.travel-monitor` runs every 6h automatically.
Load it: `launchctl load ~/Library/LaunchAgents/com.nexus.travel-monitor.plist`
