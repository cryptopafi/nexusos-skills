---
name: daily-digest
description: Morning intelligence briefing across all domains
version: 1.0.0
triggers: ["/daily-digest", "morning brief", "what happened overnight"]
domains: [crypto, finance, ai-research, health, business]
cli_tools: [~/.nexus/cli-tools/ccxt, ~/.nexus/cli-tools/stooq]
mcps_required: [arxiv, brave-search, exa]
schedule: "07:00 EET daily"
---

# Daily Digest Skill

## Objective
Generate a Tier 2 morning briefing (1500-3000 tokens) with high-signal updates from overnight activity.

## Process
1. Collect overnight crypto moves using CCXT and sentiment context.
2. Pull pre-open market context from Stooq and macro updates from FRED/ECB if available.
3. Get top Hacker News and technology headlines.
4. Fetch fresh arXiv papers for `cs.AI`, `cs.LG`, `q-bio`.
5. Sweep trusted RSS/news sources for business and health signals.
6. Deduplicate repeated stories and drop low-confidence items.
7. Add cross-domain links (example: macro -> crypto risk-on/risk-off).

## Output Format (Tier 2)
- `## Daily Research Digest — YYYY-MM-DD`
- `### Executive Summary` (3-5 bullets)
- `### 💹 Markets`
- `### 🪙 Crypto`
- `### 🤖 AI`
- `### 🧬 Health`
- `### 🏢 Business`
- `### ⚠️ Alerts`
- `### Sources`

## Rules
- Max 3 bullets per section.
- Every claim must include at least one source.
- Add confidence score `/10` for each section.
- Explicitly mark low-confidence items (`<6/10`).
