---
name: electron
description: Automate Electron desktop apps (VS Code, Slack, Discord, Figma, Notion, Spotify, etc.) using agent-browser via Chrome DevTools Protocol. Use when the user needs to interact with an Electron app, automate a desktop app, connect to a running app, control a native app, or test an Electron application. Triggers include "automate Slack app", "control VS Code", "interact with Discord app", "test this Electron app", "connect to desktop app", or any task requiring automation of a native Electron application.
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*)
---

# Electron App Automation

Automate any Electron desktop app using agent-browser. Electron apps are built on Chromium and expose a Chrome DevTools Protocol (CDP) port that agent-browser can connect to, enabling the same snapshot-interact workflow used for web pages.

## Anti-Examples

Do NOT trigger this skill when:
- The user wants to automate a **web browser** (use agent-browser directly without Electron setup)
- The user wants to scrape a **website** (use agent-browser or apify skills)
- The app is **not Electron-based** (e.g., native Swift/AppKit macOS apps, Qt apps — CDP will not work)
- The user wants to automate a **CLI tool** (use Bash directly)
- The request is about **building** an Electron app, not automating one

## Input Validation

Before proceeding, verify:

| Input | Required | Valid Values | Fail Action |
|-------|----------|--------------|-------------|
| App name / path | Yes | Known Electron app or explicit `.app`/`.exe` path | Ask user to confirm the app is Electron-based |
| CDP port | No | 1024–65535, not already in use | Default to 9222; if in use, suggest next free port |
| Platform | Auto-detected | `darwin`, `linux`, `win32` | Use `uname` / `$OSTYPE` to detect; fail if unsupported |
| Session name | No | Alphanumeric string | Default to app name |

If the app name is ambiguous, run `ls /Applications | grep -i "<name>"` on macOS before attempting `open -a`.

## Core Workflow

1. **Launch** the Electron app with remote debugging enabled
2. **Connect** agent-browser to the CDP port
3. **Snapshot** to discover interactive elements
4. **Interact** using element refs
5. **Re-snapshot** after navigation or state changes

```bash
# Launch an Electron app with remote debugging
open -a "Slack" --args --remote-debugging-port=9222

# Connect agent-browser to the app
agent-browser connect 9222

# Standard workflow from here
agent-browser snapshot -i
agent-browser click @e5
agent-browser screenshot slack-desktop.png
```

## Launching Electron Apps with CDP

Every Electron app supports the `--remote-debugging-port` flag since it's built into Chromium.

### macOS

```bash
# Slack
open -a "Slack" --args --remote-debugging-port=9222

# VS Code
open -a "Visual Studio Code" --args --remote-debugging-port=9223

# Discord
open -a "Discord" --args --remote-debugging-port=9224

# Figma
open -a "Figma" --args --remote-debugging-port=9225

# Notion
open -a "Notion" --args --remote-debugging-port=9226

# Spotify
open -a "Spotify" --args --remote-debugging-port=9227
```

### Linux

```bash
slack --remote-debugging-port=9222
code --remote-debugging-port=9223
discord --remote-debugging-port=9224
```

### Windows

```bash
"C:\Users\%USERNAME%\AppData\Local\slack\slack.exe" --remote-debugging-port=9222
"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe" --remote-debugging-port=9223
```

**Important:** If the app is already running, quit it first, then relaunch with the flag. The `--remote-debugging-port` flag must be present at launch time.

## Connecting

```bash
# Connect to a specific port
agent-browser connect 9222

# Or use --cdp on each command
agent-browser --cdp 9222 snapshot -i

# Auto-discover a running Chromium-based app
agent-browser --auto-connect snapshot -i
```

After `connect`, all subsequent commands target the connected app without needing `--cdp`.

## Tab Management

Electron apps often have multiple windows or webviews. Use tab commands to list and switch between them:

```bash
# List all available targets (windows, webviews, etc.)
agent-browser tab

# Switch to a specific tab by index
agent-browser tab 2

# Switch by URL pattern
agent-browser tab --url "*settings*"
```

## Common Patterns

### Inspect and Navigate an App

```bash
open -a "Slack" --args --remote-debugging-port=9222
sleep 3  # Wait for app to start
agent-browser connect 9222
agent-browser snapshot -i
# Read the snapshot output to identify UI elements
agent-browser click @e10  # Navigate to a section
agent-browser snapshot -i  # Re-snapshot after navigation
```

### Take Screenshots of Desktop Apps

```bash
agent-browser connect 9222
agent-browser screenshot app-state.png
agent-browser screenshot --full full-app.png
agent-browser screenshot --annotate annotated-app.png
```

### Extract Data from a Desktop App

```bash
agent-browser connect 9222
agent-browser snapshot -i
agent-browser get text @e5
agent-browser snapshot --json > app-state.json
```

### Fill Forms in Desktop Apps

```bash
agent-browser connect 9222
agent-browser snapshot -i
agent-browser fill @e3 "search query"
agent-browser press Enter
agent-browser wait 1000
agent-browser snapshot -i
```

### Run Multiple Apps Simultaneously

Use named sessions to control multiple Electron apps at the same time:

```bash
# Connect to Slack
agent-browser --session slack connect 9222

# Connect to VS Code
agent-browser --session vscode connect 9223

# Interact with each independently
agent-browser --session slack snapshot -i
agent-browser --session vscode snapshot -i
```

## Color Scheme

Playwright overrides the color scheme to `light` by default when connecting via CDP. To preserve dark mode:

```bash
agent-browser connect 9222
agent-browser --color-scheme dark snapshot -i
```

Or set it globally:

```bash
AGENT_BROWSER_COLOR_SCHEME=dark agent-browser connect 9222
```

## Edge Cases

| Scenario | Symptom | Resolution |
|----------|---------|------------|
| App already running without CDP flag | `Connection refused` on connect | Quit app, relaunch with `--remote-debugging-port` |
| Port already in use | `EADDRINUSE` or silent failure | `lsof -i :9222` to find conflict; use a different port |
| App has no visible Electron window yet | Empty snapshot or no targets | `sleep 3` after launch; retry connect |
| Multiple webviews (e.g. embedded browser inside app) | Wrong content in snapshot | `agent-browser tab` to list targets; switch to correct one |
| App uses custom input components | `fill` has no effect | Use `agent-browser keyboard inserttext "text"` instead |
| Non-Electron native app | CDP port never opens | Confirm with `lsof -i :9222` after launch; escalate to user |
| App updates itself on launch | Port changes between sessions | Always re-run connect after app restart |
| Dark mode bleeding from OS theme | UI renders incorrectly in screenshots | Set `--color-scheme dark` or `AGENT_BROWSER_COLOR_SCHEME=dark` |

## Output Contract

A successful automation session produces one or more of:

- **Snapshot text** (`agent-browser snapshot -i`): structured list of interactive elements with `@eN` refs, one per line
- **Screenshot file**: PNG at the specified path, confirmed by zero exit code
- **Extracted text** (`agent-browser get text @eN`): raw string content of the element
- **JSON state** (`agent-browser snapshot --json`): full accessibility tree as JSON written to stdout or file

All commands exit `0` on success. Non-zero exit codes indicate failure (see Error Contract). Snapshot refs (`@eN`) are **session-scoped** — they reset after re-snapshot; never reuse a ref across snapshot calls.

## Error Contract

| Exit Code / Error | Meaning | Recovery |
|-------------------|---------|----------|
| `Connection refused` (exit 1) | App not running or CDP port not open | Relaunch app with `--remote-debugging-port=NNNN` |
| `Timeout waiting for target` | App launched but webview not ready | Add `sleep 3` before connect; retry |
| `No element found: @eN` | Stale ref after UI change | Re-snapshot and resolve new ref |
| `EADDRINUSE` | Chosen port already bound | Pick a different port (9222–9230 range) |
| `open: Application not found` (macOS) | App name mismatch | Run `ls /Applications | grep -i "<name>"` to confirm |
| `Permission denied` | Agent-browser binary not executable | `chmod +x $(which agent-browser)` |
| Non-zero exit, no message | Generic agent-browser failure | Re-run with `--debug` flag to surface CDP error details |

On any unrecoverable error, report the exact command, exit code, and stderr to the user before stopping.

## Troubleshooting

### "Connection refused" or "Cannot connect"

- Make sure the app was launched with `--remote-debugging-port=NNNN`
- If the app was already running, quit and relaunch with the flag
- Check that the port isn't in use by another process: `lsof -i :9222`

### App launches but connect fails

- Wait a few seconds after launch before connecting (`sleep 3`)
- Some apps take time to initialize their webview

### Elements not appearing in snapshot

- The app may use multiple webviews. Use `agent-browser tab` to list targets and switch to the right one
- Use `agent-browser snapshot -i -C` to include cursor-interactive elements (divs with onclick handlers)

### Cannot type in input fields

- Try `agent-browser keyboard type "text"` to type at the current focus without a selector
- Some Electron apps use custom input components; use `agent-browser keyboard inserttext "text"` to bypass key events

## Supported Apps

Any app built on Electron works, including:

- **Communication:** Slack, Discord, Microsoft Teams, Signal, Telegram Desktop
- **Development:** VS Code, GitHub Desktop, Postman, Insomnia
- **Design:** Figma, Notion, Obsidian
- **Media:** Spotify, Tidal
- **Productivity:** Todoist, Linear, 1Password

If an app is built with Electron, it supports `--remote-debugging-port` and can be automated with agent-browser.