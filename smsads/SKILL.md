---
name: smsads
description: Run the SMSads unified pipeline chain (P1-P4) for market/vertical analysis
user_invocable: true
---

# /smsads — SMSads Pipeline Chain

Run the full SMSads pipeline chain (P0 Market Discovery -> P1 Vertical Scanner -> P2 Offer Finder -> P3 Competitor Spy -> P4 Network Scout) and present the unified launch brief.

## Usage

```
/smsads <market> [vertical] [--depth standard|pro|deep] [--offer-url URL] [--skip p0,p3]
```

Examples:
- `/smsads bolivia` — discover everything automatically (P0 auto-selects best vertical)
- `/smsads bolivia trading_forex` — force a specific vertical
- `/smsads ecuador --depth deep` — deep research (~$3.90, best for new markets)
- `/smsads romania betting --offer-url https://marathonbet.com`

## Input Validation

Before executing, validate:

| Field | Rule | Reject if |
|-------|------|-----------|
| market | Non-empty string, alphanumeric + underscores | Missing or contains spaces/special chars |
| vertical | Alphanumeric + underscores only | Contains spaces or special chars |
| --depth | One of: `standard`, `pro`, `deep` | Any other value |
| --offer-url | Must start with `https://` | Malformed URL or `http://` |
| --skip | Comma-separated subset of `p0,p1,p2,p3,p4` | Unknown pipeline IDs |

If validation fails: stop, tell the user exactly which parameter is invalid, and show the correct format.

## Instructions

1. Parse the user's request to extract market, optional vertical, and flags.
2. Run the pipeline chain:

```bash
cd ~/.nexus/projects/smsads/pipelines && python3 smsads-chain.py --market {market} [--vertical {vertical}] [--depth {depth}] {extra_flags}
```

3. Read the generated launch brief markdown file from the JSON output's `brief` field.
4. Present the launch brief content directly in the conversation.
5. Highlight the **Launch Recommendation** section as the key takeaway.
6. If P0 ran, mention how many verticals/networks were discovered vs the static default of 5.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| market | Yes | Target market (bolivia, romania, ecuador, burkina_faso, etc.) |
| vertical | No | Primary vertical — if omitted, P0 auto-discovers the best one |
| --depth | No | Perplexity research depth: `standard` (~$0), `pro` (~$0.08, default), `deep` (~$3.90) |
| --offer-url | No | Specific offer URL for P3 competitor analysis |
| --skip | No | Comma-separated pipelines to skip (p0, p1, p2, p3, p4) |
| --delphi-output-path | No | Path to pre-run Delphi D2 output for market enrichment (Genie pre-dispatch). Sets `delphi_enriched: true` in P0 output. If path does not exist, gracefully falls back to standard P0. |
| --adapter | No | Data adapter override (auto, static, csv, perplexity, ahrefs, similarweb) |

## Output

The chain generates:
- P0 discovery report (verticals, networks, offers found) in `~/.nexus/projects/smsads/pipeline-runs/`
- Individual P1-P4 outputs (CSV + MD)
- A unified launch brief: `launch_brief_{market}_{vertical}_{date}.md`
- Cortex storage in `business_clickwin` collection

## Depth Guide

| Depth | Cost | Use Case |
|-------|------|----------|
| standard | ~$0 | Quick check on a known market |
| pro | ~$0.08 | Default — good balance for most runs |
| deep | ~$3.90 | New market entry — comprehensive discovery |

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| P0 finds zero verticals | Abort with message: "P0 returned no verticals for {market}. Try `--adapter perplexity` or specify vertical manually." |
| `brief` field missing from chain JSON output | Read the most recent `launch_brief_*.md` in the pipeline-runs directory as fallback |
| `--skip p0` with no vertical provided | Abort: "P0 skipped but no vertical specified. Add `vertical` argument or remove `--skip p0`." |
| `--depth deep` with `--skip p0,p1,p2` | Warn user: "deep depth has no effect when P0-P2 are skipped." Continue with remaining pipelines. |
| chain script not found at expected path | Abort: "smsads-chain.py not found. Run `/nexusos` to check system health." |
| market name contains space (e.g., `burkina faso`) | Reject at input validation. Instruct to use underscore: `burkina_faso`. |

## Error Contract

| Error | Source | Response |
|-------|--------|----------|
| `ModuleNotFoundError` | Python dependency missing | "Missing dependency. Run: `pip3 install -r ~/.nexus/projects/smsads/requirements.txt`" |
| `PerplexityAPIError` / rate limit | Perplexity API | Retry once after 5s. If still failing, fall back to `--depth standard` and notify user. |
| `FileNotFoundError` on brief path | Pipeline output missing | Report which pipeline failed (from JSON `status` field) and show partial outputs available. |
| Non-zero exit code from chain script | Pipeline crash | Show last 20 lines of chain stderr. Do not present partial brief as complete. |
| Cortex store fails | MCP unavailable | Log warning, continue — Cortex save is non-blocking for this skill. |

## Anti-Examples

**Do NOT do these:**

- `/smsads` with no market — always requires at least a market name.
- Running individual pipeline skills (`/smsads-vertical-scanner`, `/smsads-offer-finder`) when the user says `/smsads` — this skill runs the unified chain, not individual steps.
- Presenting a partial brief (only P1 output) as a full launch brief when P2-P4 also ran — always present the final unified `launch_brief_*.md`.
- Using `--depth deep` for a market the user has run before this session — waste of ~$3.90; suggest `pro` unless explicitly requested.
- Skipping the Launch Recommendation highlight step — it is the primary takeaway and must always be surfaced.