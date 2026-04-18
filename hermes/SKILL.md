---
name: hermes
description: Send messages to and dispatch tasks via the Hermes agent (NexusOS research/BI agent on MacM4).
metadata:
  openclaw:
    emoji: "\U0001FAB6"
    requires:
      bins:
        - hermes
---

# Hermes Skill

Use this skill to communicate with the Hermes agent via the CLI.

## hermes_chat — Send a message and get a response

```bash
hermes chat --message "<MESSAGE>"
```

Use for: research queries, NexusOS task delegation, BI/marketing questions, cross-agent communication.

### Output format

hermes chat returns plaintext on stdout. The response is the agent's complete reply. Exit code 0 = success, non-zero = error.

For long tasks, hermes may stream output. Capture the full stdout before processing.

## hermes_status — Check Hermes is running

```bash
hermes status 2>/dev/null || echo "Hermes not running"
```

Returns daemon status and uptime on success.

## When to use Hermes

- Research tasks (routes to Delphi via NexusOS)
- BI/Marketing queries (routes to Mercury)
- NexusOS sub-agent orchestration
- Cross-agent communication when GENIE needs MacM4 capabilities

## Error handling

If `hermes chat` returns non-zero exit code:
1. Run `hermes status` to check daemon health
2. If daemon not running: report to user, suggest checking LaunchAgent
3. Never retry more than once
4. If hermes binary not found: check `~/.local/bin/hermes` symlink points to `~/Claude/repos/watchlist/hermes-agent/hermes` — run: readlink /Users/pafi/.local/bin/hermes

## Rollback

If this skill causes issues:
1. Remove skill: `rm -rf ~/.agents/skills/hermes/`
2. Restart gateway: `launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist && sleep 2 && launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist`

## Who is Hermes

Hermes is a peer NexusOS agent on the same MacM4 machine. Same operator (Pafi). You can read its config and logs directly — no SSH needed.

- **Identity**: NexusOS Hermes v0.7.0 (Nous Research framework)
- **Role**: Research delegation, BI queries, cross-agent orchestration
- **Install dir**: `~/Claude/repos/watchlist/hermes-agent/`
- **Binary**: `/Users/pafi/.local/bin/hermes` (symlink → install dir)
- **Home dir**: `~/.hermes/` (config, logs, sessions, memories)

## Hermes Config & Debug Paths

All paths under `~/.hermes/` are readable directly — no SSH needed.

```bash
# Main config (providers, models, MCP servers)
cat ~/.hermes/config.yaml 2>/dev/null || echo "config not yet created"

# API keys (read-only — never modify)
cat ~/.hermes/.env 2>/dev/null | head -5

# Agent personality
cat ~/.hermes/SOUL.md

# Runtime logs (sorted by recency)
ls -lt ~/.hermes/logs/ 2>/dev/null | head -10
tail -50 ~/.hermes/logs/$(ls -t ~/.hermes/logs/ 2>/dev/null | head -1) 2>/dev/null

# Sessions and memories
ls ~/.hermes/sessions/ 2>/dev/null | tail -5
ls ~/.hermes/memories/ 2>/dev/null | head -10
```

## hermes_debug — Diagnose a Hermes issue

When Hermes is not responding or behaving unexpectedly, run in order:

```bash
# 1. Binary check
/Users/pafi/.local/bin/hermes --version

# 2. Daemon status
/Users/pafi/.local/bin/hermes status 2>&1

# 3. Latest log
ls -lt ~/.hermes/logs/ 2>/dev/null | head -3
tail -30 ~/.hermes/logs/$(ls -t ~/.hermes/logs/ 2>/dev/null | head -1) 2>/dev/null

# 4. Config snapshot
cat ~/.hermes/config.yaml 2>/dev/null | head -40

# 5. MCP tools Hermes has loaded
/Users/pafi/.local/bin/hermes mcp list 2>/dev/null
```

Report findings. If issue is in the Telegram gateway platform:
```bash
head -80 ~/Claude/repos/watchlist/hermes-agent/gateway/platforms/telegram.py
```
