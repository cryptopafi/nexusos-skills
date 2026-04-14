---
name: smsads-offer-finder
description: Run SMSads P2 Offer Finder — rank affiliate offers for a vertical/market
user_invocable: true
---

# /smsads-offer-finder — P2 Product Finder

Rank affiliate offers by EC/1K, saturation, and payment terms for a given vertical and market.

## Usage

```
/smsads-offer-finder <vertical> <market> [--networks n1,n2,...]
```

Examples:
- `/smsads-offer-finder trading_forex bolivia`
- `/smsads-offer-finder app_downloads ecuador --networks clickdealer,mobidea`

## Anti-Examples (do NOT do these)

- `/smsads-offer-finder trading_forex` — missing market, will fail validation
- `/smsads-offer-finder "" bolivia` — empty vertical is invalid
- `/smsads-offer-finder trading forex bolivia` — vertical must use underscores, not spaces
- Running without checking for a concurrent pipeline-run lock — causes corrupted output files

## Input Validation

Before running the pipeline, verify:

1. `vertical` is non-empty and contains only `[a-z0-9_]` characters (no spaces, no special chars)
2. `market` is non-empty and contains only `[a-z0-9_]` characters
3. If `--networks` provided: each network slug matches `[a-z0-9_-]+`; reject unknowns not in the known set (clickdealer, mobidea, maxbounty, adcombo, cpamatica)
4. If any validation fails: stop, report the exact invalid value and the rule it broke, and do NOT run the pipeline

## Instructions

1. Parse vertical, market, and optional networks from the user's request.
2. Validate all inputs per the Input Validation section above.
3. Check for a concurrent-write lock before running:

```bash
LOCK=~/.nexus/projects/smsads/pipeline-runs/.offer-finder.lock
if [ -f "$LOCK" ]; then
  echo "ERROR: Another offer-finder run is active (lock: $LOCK). Wait or remove stale lock."
  exit 1
fi
touch "$LOCK"
trap "rm -f $LOCK" EXIT
```

4. Run:

```bash
cd ~/.nexus/projects/smsads/pipelines && python3 offer_finder.py --vertical {vertical} --market {market} [--networks {networks}]
```

5. Read the generated markdown from the JSON output's `ranked_md` field.
6. Present the ranked offers table and launch plan in conversation.
7. Lock is auto-released on exit (trap above). If the script crashes, manually remove `~/.nexus/projects/smsads/pipeline-runs/.offer-finder.lock`.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| vertical | Yes | Vertical to find offers for (snake_case, e.g. `trading_forex`) |
| market | Yes | Target market (snake_case, e.g. `bolivia`) |
| networks | No | Comma-separated network filter (default: all 5 networks) |

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| No offers returned for vertical+market | Report "0 offers found" — do NOT hallucinate alternatives |
| Network slug not in known set | Fail validation before running pipeline |
| `pipeline-runs/` directory missing | Report path error; do NOT silently create partial output |
| Lock file exists (stale from crash) | Report lock path; ask user to confirm removal before deleting |
| `offer_finder.py` exits non-zero | Surface exact stderr to user; do NOT present partial output as success |
| JSON output missing `ranked_md` field | Report malformed output; do NOT guess at field names |

## Error Contract

| Exit Condition | What Genie reports |
|----------------|--------------------|
| Input validation failure | "Invalid `<param>`: <value> — <rule broken>. Fix and retry." |
| Lock already held | "Concurrent run detected. Lock: `<path>`. Wait or remove stale lock." |
| Pipeline script not found | "offer_finder.py not found at expected path. Check smsads install." |
| Script exits non-zero | "Pipeline failed (exit <code>): <stderr>. No output written." |
| Output file unreadable/missing | "Pipeline completed but output not found at `<path>`." |
| Cortex storage fails | Log warning; still present ranked table to user (non-fatal). |

## Output

- CSV + MD in `~/.nexus/projects/smsads/pipeline-runs/`
- Cortex storage in `business_clickwin` collection