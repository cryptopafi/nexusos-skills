---
name: smsads-competitor-spy
description: Run SMSads P3 Competitor Spy — competitor intel for an offer URL
user_invocable: true
---

# /smsads-competitor-spy — P3 Competitor Intelligence

Generate competitor intelligence brief for a specific offer URL in a target market. Use this when you have a concrete offer URL and need keyword gaps, ad angles, and competitor positioning data.

**Do NOT use for:** general market research (use `/smsads`), vertical scanning without a specific URL, or generating offers (use `/smsads-offer-finder`).

## Usage

```
/smsads-competitor-spy <offer-url> <market>
```

Examples:
- `/smsads-competitor-spy https://avatrade.com bolivia`
- `/smsads-competitor-spy https://marathonbet.com romania`

## Input Validation

Before running, validate:

| Check | Rule | Action if invalid |
|-------|------|-------------------|
| `offer-url` present | Non-empty string | Ask user for offer URL |
| `offer-url` format | Must start with `http://` or `https://` | Reject, ask for valid URL |
| `market` present | Non-empty string | Ask user for target market |
| `market` format | Single word or hyphenated (e.g. `romania`, `latin-america`) | Normalize to lowercase, remove spaces |

## Instructions

1. Parse offer URL and market from the user's request. Validate inputs per the table above before proceeding.
2. Run (timeout: 120s):

```bash
cd ~/.nexus/projects/smsads/pipelines && python3 competitor_spy.py --offer-url {offer_url} --market {market}
```

3. Read the generated brief from the JSON output's `brief` field.
4. Present the competitor brief in conversation — highlight keyword gaps and copy angles.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| offer-url | Yes | Offer/advertiser URL to analyze |
| market | Yes | Target market |

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| URL returns 404 / unreachable | Report error to user: "URL unreachable, check the offer is live" |
| Market not recognized by pipeline | Pipeline uses StaticAdapter fallback; note in output that data is scaffold |
| Script exits non-zero | Surface stderr to user, do not present partial brief |
| `brief` field missing from JSON | Report: "Pipeline returned no brief. Check pipeline logs." |
| Timeout exceeded (>120s) | Kill process, report timeout, suggest retry |
| Both API keys missing | Proceed with StaticAdapter; warn user real data unavailable |

## Error Contract

| Error | Cause | Resolution |
|-------|-------|------------|
| `ModuleNotFoundError` | Missing Python dependency | Run `pip3 install -r requirements.txt` in the pipeline directory |
| `FileNotFoundError: competitor_spy.py` | Wrong working directory or missing file | Verify `~/.nexus/projects/smsads/pipelines/` exists |
| `KeyError: brief` | Pipeline schema change | Read full JSON and surface raw output to user |
| Script timeout (120s) | Slow network or large domain | Report timeout, advise retry with a simpler URL |
| Permission denied | Script not executable | Run `chmod +x competitor_spy.py` |

## Notes

- Currently uses scaffold data (StaticAdapter)
- Will use real Ahrefs/SimilarWeb data when API keys are set (`AHREFS_API_KEY`, `SIMILARWEB_API_KEY`)

## Output

**Timeout:** 120 seconds.

**Files written:**
- MD brief in `~/.nexus/projects/smsads/pipeline-runs/`
- Cortex storage in `business_clickwin` collection

**JSON schema** (pipeline stdout):

```json
{
  "offer_url": "string",
  "market": "string",
  "brief": "string (markdown)",
  "keyword_gaps": ["string"],
  "copy_angles": ["string"],
  "competitors": [
    {
      "domain": "string",
      "traffic_rank": "number | null",
      "top_keywords": ["string"]
    }
  ],
  "data_source": "StaticAdapter | Ahrefs | SimilarWeb",
  "generated_at": "ISO8601 timestamp"
}
```