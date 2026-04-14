# business-alerts

description: Run rule-based business alert detection with 13 rules per business, 6h cooldown, and Telegram escalation.
trigger: When user asks to check business alerts, detect critical market/regulatory changes, or run alert monitoring.
steps:
1. Choose config: `~/.openclaw/intelligence/{business}-config.json`.
2. Run checker: `python3 ~/.openclaw/scripts/alert-checker.py <config> --verbose`.
3. Optional digest send for queued INFO/WARNING: `python3 ~/.openclaw/scripts/alert-checker.py <config> --send-digest`.
4. Review state in `~/.openclaw/intelligence/alert-state.json`.

output_format:
- Runtime status line with checked/triggered/sent counters.
- CRITICAL alerts are immediate Telegram messages.
- INFO/WARNING alerts are queued for digest send.

examples:
- `python3 ~/.openclaw/scripts/alert-checker.py ~/.openclaw/intelligence/albastru-config.json --verbose`
- `python3 ~/.openclaw/scripts/alert-checker.py ~/.openclaw/intelligence/ai-b2b-config.json --send-digest`
