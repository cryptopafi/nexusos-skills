---
name: slack
description: Interact with Slack workspaces using browser automation. Use when the user needs to check unread channels, navigate Slack, send messages, extract data, find information, search conversations, or automate any Slack task. Triggers include "check my Slack", "what channels have unreads", "send a message to", "search Slack for", "extract from Slack", "find who said", or any task requiring programmatic Slack interaction.
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*)
---

# Slack Automation

Interact with Slack workspaces to check messages, extract data, and automate common tasks.

## Anti-Examples

Do NOT use this skill when:
- User wants to send a Slack message via API/webhook (use curl with Slack webhook URL instead)
- User wants to configure Slack notifications or workspace settings (direct them to Slack admin UI)
- User asks about Slack API tokens or OAuth (this skill uses browser automation, not the API)

## Input Validation

Before executing any Slack automation:
1. Verify `agent-browser` is installed: `which agent-browser || npx agent-browser --version`
2. Verify a browser session is available on port 9222: `agent-browser connect 9222` (if fails, instruct user to open Slack in Chrome with `--remote-debugging-port=9222`)
3. Verify Slack is loaded: after connect, run `agent-browser get url` and confirm it contains `app.slack.com`

If any check fails, report the specific failure and stop. Do not proceed with stale or missing sessions.

## Quick Start

```bash
# Connect to existing Slack browser session on port 9222
agent-browser connect 9222

# Or open Slack if not already running
agent-browser open https://app.slack.com
```

Then take a snapshot to see what's available:

```bash
agent-browser snapshot -i
```

## Core Workflow

1. **Connect/Navigate**: Open or connect to Slack
2. **Snapshot**: Get interactive elements with refs (`@e1`, `@e2`, etc.)
3. **Navigate**: Click tabs, expand sections, or navigate to specific channels
4. **Extract/Interact**: Read data or perform actions
5. **Screenshot**: Capture evidence of findings

```bash
# Example: Check unread channels
agent-browser connect 9222
agent-browser snapshot -i
# Look for "More unreads" button in snapshot output
# Click the ref shown for that button (refs vary per session)
agent-browser click @e21
agent-browser screenshot slack-unreads.png
```

## Output Contract

Every Slack automation MUST produce:
1. **Screenshot** (`.png`): visual proof of the final state
2. **Text summary**: structured text describing what was found/done
3. **Status**: `SUCCESS` (task completed), `PARTIAL` (some data retrieved but not all), or `FAILED` (could not complete)

Format for text output:
```
SLACK_RESULT:
  status: SUCCESS|PARTIAL|FAILED
  workspace: <workspace name>
  action: <what was done>
  findings: <structured data or summary>
  screenshot: <path to screenshot>
```

## Common Tasks

### Checking Unread Messages

```bash
agent-browser connect 9222
agent-browser snapshot -i

# IMPORTANT: Element refs (@eN) change between sessions.
# Always snapshot first, then find the correct ref by label text.
# Look for these labels in snapshot output:
#   "Home" tab, "DMs" tab, "Activity" tab, "Search" button, "More unreads"

# Navigate to Activity tab (find ref for "Activity" in snapshot)
agent-browser click @e_activity_ref
agent-browser wait 1000
agent-browser screenshot activity-unreads.png

# Or check DMs tab
agent-browser click @e_dms_ref
agent-browser screenshot dms.png

# Or expand "More unreads" in sidebar
agent-browser click @e_unreads_ref
agent-browser wait 500
agent-browser screenshot expanded-unreads.png
```

### Navigating to a Channel

```bash
agent-browser snapshot -i

# Find channel name in the snapshot output, note its @eN ref
agent-browser click @e_channel_ref
agent-browser wait 2000  # max wait for channel load
agent-browser screenshot channel.png
```

### Finding Messages/Threads

```bash
agent-browser snapshot -i
# Find the Search button ref in snapshot output
agent-browser click @e_search_ref
agent-browser fill @e_search_input "keyword"
agent-browser press Enter
agent-browser wait 3000  # max wait for search results
agent-browser screenshot search-results.png
```

### Extracting Channel Information

```bash
# Get list of all visible channels as JSON
agent-browser snapshot --json > slack-snapshot.json

# Parse for channel names and metadata
# Look for treeitem elements with level=2 (sub-channels under sections)
```

### Taking Notes/Capturing State

```bash
# Take annotated screenshot (shows element numbers)
agent-browser screenshot --annotate slack-state.png

# Get current URL for reference
agent-browser get url

# Get page title
agent-browser get title
```

## Element Reference Strategy

Element refs (`@eN`) are **session-specific** and change every time a new snapshot is taken or the page re-renders. Never hardcode refs.

**Correct pattern:**
1. Run `agent-browser snapshot -i`
2. Parse output to find the element by its **label text** (e.g., "Activity", "Home", "Search")
3. Use the ref shown next to that label

**Example:** To find the Activity tab:
```bash
SNAPSHOT=$(agent-browser snapshot -i)
# Look for line containing "Activity" and extract its @eN ref
ACTIVITY_REF=$(echo "$SNAPSHOT" | grep -i "activity" | grep -oE '@e[0-9]+' | head -1)
agent-browser click "$ACTIVITY_REF"
```

## Sidebar Structure

```
- Threads
- Huddles
- Drafts & sent
- Directories
- [Section Headers - External connections, Starred, Channels, etc.]
  - [Channels listed as treeitems]
- Direct Messages
  - [DMs listed]
- Apps
  - [App shortcuts]
- [More unreads] button (toggles unread channels list)
```

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| No browser session on port 9222 | Report error: "No Slack session found. Open Slack in Chrome with --remote-debugging-port=9222" |
| Slack shows login page | Report: "Slack session expired. User must log in manually." Do not attempt login. |
| Channel has no messages | Screenshot empty channel, report "Channel empty or no visible messages" |
| Snapshot returns no interactive elements | Retry once after `wait 2000`. If still empty, report "Page not fully loaded" |
| Search returns no results | Screenshot the "no results" state, report as PARTIAL |
| Element ref not found after click | Re-snapshot and retry with updated ref. Max 2 retries. |
| Sidebar too long to show all channels | Use `agent-browser scroll down 300 --selector ".p-sidebar"` to reveal more channels |

## Error Contract

| Error | Cause | Recovery |
|-------|-------|----------|
| `agent-browser: command not found` | CLI not installed | `npm install -g agent-browser` or use `npx agent-browser` |
| `connect ECONNREFUSED 9222` | No browser session available | Instruct user to open Slack in Chrome with remote debugging flag |
| `timeout waiting for networkidle` | Slack loading slowly or hanging | Retry with `wait 3000`. If still fails, proceed with current state and note partial results |
| `element @eN not found` | Ref changed after page re-render | Re-snapshot, find element by label text, use new ref |
| `snapshot returned empty` | Page not loaded or wrong tab focused | `agent-browser get url` to verify Slack is loaded. If not, reconnect. |

## Best Practices

- **Connect to existing sessions**: Use `agent-browser connect 9222` if Slack is already open
- **Snapshot before every click**: Always `snapshot -i` to get current refs
- **Re-snapshot after navigation**: Refs change after page transitions
- **Use JSON snapshots for parsing**: `snapshot --json` for machine-readable output
- **Pace interactions**: Add `wait 1000` between rapid interactions
- **Never hardcode element refs**: Always discover refs from snapshot output by label text
- **Max wait time**: Never wait more than 5000ms for any single operation. If not loaded by then, report partial results.

## Limitations

- **No Slack API**: Browser automation only. No OAuth, webhooks, or bot tokens needed.
- **Session-specific**: Screenshots and snapshots are tied to the current browser session.
- **Rate limiting**: Slack may throttle rapid interactions. Add delays between commands.
- **Workspace-specific**: Interacts with the logged-in workspace only.
- **Cannot send messages without user confirmation**: Always confirm with user before sending any message.

## Debugging

```bash
# Check console for errors
agent-browser console
agent-browser errors

# Include cursor-interactive divs in snapshot
agent-browser snapshot -i -C

# Get current page state
agent-browser get url
agent-browser get title
agent-browser screenshot page-state.png
```
