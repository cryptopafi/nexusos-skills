---
name: smsads-vertical-scanner
description: Run SMSads P1 Vertical Scanner — score and rank verticals for a market
user_invocable: true
---

# /smsads-vertical-scanner — P1 Vertical Discovery

Score and rank verticals for SMS affiliate marketing in a target market.

## Usage

```
/smsads-vertical-scanner <market> <vertical>
```

Examples:
- `/smsads-vertical-scanner bolivia trading_forex`
- `/smsads-vertical-scanner ecuador app_downloads`

## Input Validation

Before running, validate:
- `market` must be provided and non-empty — if missing, ask: "Which market? (e.g. bolivia, romania, ecuador)"
- `vertical` must be provided and non-empty — if missing, ask: "Which vertical? (e.g. trading_forex, app_downloads, nutra)"
- Both parameters must be plain strings with no spaces (use underscores: `trading_forex` not `trading forex`)
- Do NOT proceed if either parameter is missing — prompt the user instead

## Instructions

1. Parse market and vertical from the user's request.
2. Validate both parameters per Input Validation above. Stop and ask if either is missing.
3. Run:

```bash
cd ~/.nexus/projects/smsads/pipelines && python3 vertical_scanner.py --market {market} --vertical {vertical}
```

4. **On script failure** (non-zero exit code or exception output):
   - Report the exact error to the user
   - Do NOT fabricate results
   - Common causes: missing dependencies (`pip3 install -r requirements.txt`), wrong market code, network timeout
5. Read the generated markdown summary from the JSON output's `summary` field.
6. Present the ranked verticals table in conversation.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| market | Yes | Target market (bolivia, romania, ecuador, burkina_faso, etc.) |
| vertical | Yes | Primary vertical to force-include in ranking |

## Error Contract

| Situation | Behavior |
|-----------|----------|
| Missing `market` | Stop, ask user for market |
| Missing `vertical` | Stop, ask user for vertical |
| Script exits non-zero | Report exact error, do not fabricate results |
| JSON output missing `summary` field | Report parse failure, show raw output |
| Pipeline directory not found | Report path, suggest `cd ~/.nexus/projects/smsads` to verify |
| Empty results / no verticals ranked | Report "no verticals found for {market}" and suggest checking market code |

## Output

- CSV + MD in `~/.nexus/projects/smsads/pipeline-runs/`
- Cortex storage in `business_clickwin` collection

## Edge Cases

- Market code with spaces: normalize to underscores before passing (`"burkina faso"` → `burkina_faso`)
- Vertical already top-ranked: scanner force-includes it regardless — results are still valid
- Script hangs (>120s): kill and report timeout to user
- Pipeline-runs directory missing: script creates it on first run — not an error

## Anti-Examples

- **DO NOT** invent vertical scores if the script fails
- **DO NOT** skip validation and run with empty market/vertical
- **DO NOT** silently swallow script errors and present partial results as complete
- **DO NOT** run with `market` = a country full name like "Bolivia" — use lowercase code `bolivia`