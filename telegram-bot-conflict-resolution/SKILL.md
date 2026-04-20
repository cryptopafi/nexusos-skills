---
name: telegram-bot-conflict-resolution
description: Use when multiple Telegram bots conflict with 409 errors — stop-first ordering resolution procedure
---

# Problema
Need independent Telegram channels so no single framework failure kills all access to VPS agents.
# Procedura
1. Stop MacM4 relay FIRST (launchctl unload) to avoid 409 Telegram polling conflict
2. Token swap: extract both tokens (automation bot + macm4 bot), swap in Hermes .env
3. Deploy Bun relay on VPS for @claudeautomationbot: rsync code, patch MacM4 paths (sed /Users/pafi -> /home/pafi), create .env + systemd unit
4. Port Lis personality: system.xml (XML) -> SOUL.md (markdown), backup first
5. Configure Hermes crons: wrapper scripts that source .env (avoid API key in process table)
6. Stop MacM4 proactive LaunchAgents
7. E2E test: independence (stop Hermes, relay still works; stop relay, Hermes still works)
CRITICAL: Check for other services using same bot token (arbitrage-pro.service was the ghost poller).
CRITICAL: OAuth session conflict means relay cant use claude -p while another session is active. SSH is the real debug channel.
# Enforcement Loop
After rewiring: systemctl status hermes-gateway claude-relay. Send test message to both bots. Check gateway.log for response ready.
