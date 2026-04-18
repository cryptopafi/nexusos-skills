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
4. If hermes binary not found: check `~/.local/bin/hermes` symlink points to `~/Claude/repos/hermes-agent/hermes`

## Rollback

If this skill causes issues:
1. Remove skill: `rm -rf ~/.agents/skills/hermes/`
2. Restart gateway: `launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist && sleep 2 && launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist`
