---
name: cross-domain-synthesis
description: Weekly Opus synthesis across all research domains
triggers: ["/synthesis", "weekly synthesis", "cross-domain"]
model: claude-opus-4-6
thinking_tokens: 8000
mcps_required: [cortex]
schedule: "Sunday 22:00 EET"
---

# Cross-Domain Synthesis Skill

## Objective
Produce a weekly deep synthesis of cross-domain signals from Cortex memory.

## Inputs
- Weekly domain summaries from: crypto, finance, health, AI, business.
- Priority signals from `cross_domain_signals`.

## Process
1. Retrieve top weekly findings per domain.
2. Identify:
- Tensions (conflicting signals)
- Amplifiers (one domain accelerating another)
- Surprises (out-of-consensus changes)
- Leading indicators (early warning trends)
3. Build coherent macro thesis update.
4. Add contrarian checks and confidence distribution.

## Output (Tier 3)
- `## Weekly Deep Research Report`
- Macro thesis update
- Domain deep dives with evidence chains
- Emerging cross-domain connections
- Contrarian signals
- Confidence distribution
- Knowledge gaps
- Recommended actions
