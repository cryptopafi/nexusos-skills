---
name: smsads-market-discovery
description: Run SMSads P0 Market Discovery — discover verticals, networks, and offers for a country
user_invocable: true
---

# /smsads-market-discovery — P0 Market Discovery

Discover all affiliate verticals, networks, and offers available in a target market using Perplexity Sonar.

## Usage

```
/smsads-market-discovery <market> [--depth standard|pro|deep]
```

Examples:
- `/smsads-market-discovery bolivia`
- `/smsads-market-discovery ecuador --depth deep`

## Input Validation

| Input | Rule | On Failure |
|-------|------|------------|
| market | Required, non-empty string, lowercase alpha (e.g. `bolivia`, `romania`) | Stop. Ask user: "Which market?" |
| --depth | One of: `standard`, `pro`, `deep` | Default to `pro`. Do not error. |

## Instructions

1. Parse market and optional depth from the user's request.
2. Run:

```bash
cd ~/.nexus/projects/smsads/pipelines && python3 market_discovery.py --market {market} --depth {depth} --adapter perplexity
```

3. Read the generated markdown from the JSON output's `md` field.
4. Present the discovery results in conversation — highlight total verticals, networks, and offers found.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| market | Yes | Target market (bolivia, romania, ecuador, etc.) |
| --depth | No | standard (~$0), pro (~$0.08, default), deep (~$3.90 for comprehensive discovery) |

## Output Contract

Files written to `~/.nexus/projects/smsads/pipeline-runs/`:

| File | Format | Fields |
|------|--------|--------|
| `{market}_discovery.csv` | CSV, UTF-8, header row | `vertical`, `network`, `offer_name`, `offer_url`, `payout`, `payout_type`, `geo`, `notes` |
| `{market}_discovery.md` | Markdown | H2 per vertical, table of networks/offers per vertical, summary totals at top |

Cortex storage: collection `business_clickwin`, metadata includes `market`, `depth`, `run_date`.

In-conversation summary must include: total verticals found, total networks, total offers, top 3 verticals by offer count.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Script exits non-zero | Stop. Show last 10 lines of stderr to user. Do not present partial results. |
| JSON output missing `md` field | Stop. Report: "Pipeline returned no markdown output — check `market_discovery.py` logs." |
| No offers found for market | Report: "0 offers found for {market}. Market may not be supported or Perplexity returned no results." |
| market contains spaces or special chars | Sanitize to lowercase, strip non-alpha before passing to script. |
| Perplexity API unavailable | Script will error. Report the script error verbatim. Do not retry automatically. |
| `pro` depth returns 0 results | Suggest re-running with `--depth deep`. |

## Error Contract

| Error | Signal | Action |
|-------|--------|--------|
| `ModuleNotFoundError` | Python missing dependency | Report: "Missing Python dependency. Run: `pip3 install -r requirements.txt` in `~/.nexus/projects/smsads/`" |
| `FileNotFoundError: market_discovery.py` | Wrong directory or missing file | Report path and ask user to verify smsads installation. |
| `PermissionError` | Pipeline-runs dir not writable | Report: "Cannot write to pipeline-runs/. Check directory permissions." |
| Non-zero exit, no stderr | Silent failure | Report: "Script exited with no error output. Check Perplexity API key and network connectivity." |
| Cortex store fails | mcp tool error | Log the failure in conversation, continue — Cortex storage is non-critical. |

## Anti-Examples

- **Do NOT** run with `--adapter openai` or any adapter other than `perplexity` — this pipeline is Perplexity-only.
- **Do NOT** present results if the script errored, even if a partial CSV was written.
- **Do NOT** re-run automatically on failure — always surface the error to the user first.
- **Do NOT** skip the in-conversation summary and just say "done" — always highlight verticals/networks/offers found.
- **Do NOT** infer market from context (e.g. prior conversation) if the user did not provide it in this invocation — ask explicitly.