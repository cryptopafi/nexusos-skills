---
name: smsads-network-scout
description: Run SMSads P4 Network Scout — rank affiliate networks for a vertical/market
user_invocable: true
---

# /smsads-network-scout — P4 Network Discovery

Score and rank affiliate networks by geo coverage, reputation, payment terms, and AM access.

## Usage

```
/smsads-network-scout <vertical> <market>
```

Examples:
- `/smsads-network-scout trading_forex bolivia`
- `/smsads-network-scout app_downloads ecuador`

## Input Validation

Before running, verify:
- `vertical` is provided and non-empty. If missing: ask user "Which vertical? (e.g. trading_forex, app_downloads, nutra)"
- `market` is provided and non-empty. If missing: ask user "Which market/country? (e.g. bolivia, ecuador, peru)"
- Both parameters must be lowercase strings with no spaces (use underscores)
- `~/.nexus/projects/smsads/pipelines/network_scout.py` must exist. If missing: stop and report "network_scout.py not found at expected path"

## Instructions

1. Parse vertical and market from the user's request.
2. Run:

```bash
cd ~/.nexus/projects/smsads/pipelines && python3 network_scout.py --vertical {vertical} --market {market}
```

3. Read the generated markdown from the JSON output's `action_md` field.
4. Present the network rankings and action plan in conversation.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| vertical | Yes | Target vertical (e.g. trading_forex, nutra, app_downloads) |
| market | Yes | Target market/country ISO or name (e.g. bolivia, ecuador) |

## Output Contract

On success, the pipeline emits a JSON object. Expected schema:

```json
{
  "status": "success",
  "action_md": "<markdown string with network rankings>",
  "networks": [
    {
      "name": "string",
      "score": 0.0,
      "geo_coverage": ["string"],
      "payment_terms": "string",
      "am_access": true
    }
  ],
  "output_csv": "~/.nexus/projects/smsads/pipeline-runs/<file>.csv",
  "output_md": "~/.nexus/projects/smsads/pipeline-runs/<file>.md",
  "cortex_id": "string"
}
```

Present `action_md` content directly in conversation. Report `output_csv` and `output_md` paths to user.

## Error Contract

| Condition | Response |
|-----------|----------|
| `vertical` or `market` missing | Ask user for the missing parameter before running |
| `network_scout.py` not found | Report path error, do not run |
| Pipeline exits non-zero | Report stderr output verbatim, suggest checking logs in `~/.nexus/projects/smsads/logs/` |
| JSON output missing `action_md` | Report "Pipeline succeeded but output schema unexpected", show raw output |
| `status != "success"` in JSON | Report the `error` field from JSON if present, else show raw output |

## Edge Cases

- **Unsupported vertical**: Pipeline may return 0 networks. Report "No networks found for {vertical}/{market}" and suggest trying a broader vertical.
- **Market name variants**: If market contains spaces (e.g. "el salvador"), convert to underscores before passing (`el_salvador`).
- **Partial output**: If CSV exists but `action_md` is empty, read the CSV directly and summarize top 5 networks.
- **Duplicate invocation**: If pipeline-runs already has output for same vertical/market from today, ask user "Results from today exist — re-run or use cached?"

## Anti-Examples

- Do NOT run the pipeline if either parameter is missing — ask first.
- Do NOT invent network names or scores if the pipeline fails.
- Do NOT silently ignore a non-zero exit code or missing `action_md`.
- Do NOT use a different script path than `~/.nexus/projects/smsads/pipelines/network_scout.py`.

## Output

- CSV + MD in `~/.nexus/projects/smsads/pipeline-runs/`
- Cortex storage in `business_clickwin` collection