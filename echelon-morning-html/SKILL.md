---
name: echelon-morning-html
description: Generate ECHELON morning HTML report from markdown and deploy to VPS
---

You are Genie executing the ECHELON morning report. This is the ONLY system sending the morning report — bash cron at 06:45 only generates markdown, you handle HTML + VPS deploy + Telegram.

## Steps

1. Check if today's markdown report exists:
   - Path: `~/.nexus/intel/reports/echelon-morning-$(date +%Y%m%d).md`
   - If missing, wait 2 minutes and retry (bash cron at 06:45 may still be running)
   - If still missing after 2 retries (4 min total), abort and send Telegram error message

2. Read the markdown report content

3. Invoke the **Delphi Pro reporter skill** (NOT the shared-reporter) to generate Tier 2 HTML:
   - Skill location: `~/.claude/plugins/delphi/skills/reporter/SKILL.md`
   - Read that SKILL.md first to get the exact contract
   - Model: claude-sonnet-4-6
   - Pass the markdown report content as `report_markdown`
   - metadata: `{"topic": "ECHELON Morning Brief", "date": "YYYY-MM-DD", "agent": "echelon"}`
   - tier: 2 (Full Report with dark/light toggle, glassmorphism, Chart.js, TOC)
   - deploy_vps: true
   - accent_color: "#58a6ff"

4. The Delphi Pro reporter will:
   - Generate self-contained HTML with glassmorphism dark mode design
   - Include Chart.js visualizations if data available
   - Add share button + OG meta tags
   - Deploy to VPS via scp
   - Return share URL

5. Save local copy: `~/.nexus/intel/reports/echelon-morning-$(date +%Y%m%d).html`

6. Send ONE Telegram notification to Lis (chat 623593648, bot token from keychain `telegram-bot-token-claudemacm4`) using HTML parse mode, format matching scout alerts:

```
☀️ <b>ECHELON Morning Brief</b> YYYY-MM-DD

📊 <b>{signals}</b> signals | <b>{topics}</b> topics | Pipeline: <b>{ok}</b> OK

🎯 <b>Top Actionable:</b>
1. {item1}
2. {item2}
3. {item3}

🔗 <a href="{vps_url}">Open Full Report</a>
```

Extract signals count, topics count, and top 3 actionable items from the markdown file. Get pipeline OK count from `~/.openclaw/logs/echelon-orchestrator.log`.

Use curl:
```bash
curl -sf --max-time 15 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"623593648","text":"...","parse_mode":"HTML","disable_web_page_preview":true}'
```

7. Report: "ECHELON morning delivered. VPS: {url}. Telegram: sent."

## Rules
- Use DELPHI PRO reporter skill (`~/.claude/plugins/delphi/skills/reporter/SKILL.md`), NOT shared-reporter
- Send exactly ONE Telegram message (no duplicates)
- If VPS unreachable: save HTML locally, send Telegram with "[VPS unreachable]" note
- If Telegram fails: log error, do not retry (avoid spam on next run)