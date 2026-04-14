# weekly-report

description: Generate and send weekly/monthly business intelligence summaries from Cortex collections to Telegram.
trigger: When user asks for weekly/monthly intelligence summaries or business trend report.
steps:
1. Weekly: run `bash ~/.openclaw/scripts/weekly-intelligence-report.sh`.
2. Monthly: run `bash ~/.openclaw/scripts/monthly-intelligence-report.sh`.
3. Verify logs in `~/.openclaw/logs/weekly-report.log` and `~/.openclaw/logs/monthly-report.log`.

output_format:
- Telegram summary grouped by business with top items, alert count, and trend direction.
- Message trimmed to Telegram-safe length (<4000 chars).

examples:
- `bash ~/.openclaw/scripts/weekly-intelligence-report.sh`
- `bash ~/.openclaw/scripts/monthly-intelligence-report.sh`
