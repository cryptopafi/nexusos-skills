---
name: longevity-scan
description: Weekly longevity and health research scan
triggers: ["/longevity-scan", "health research", "longevity update"]
mcps_required: [openalex, arxiv]
# MCP TOGGLE-ON: run 'claude mcp add pubmed-eutils -s local -- npx tsx ~/.claude/mcp-servers/custom/pubmed-eutils/index.ts' before using
# MCP TOGGLE-ON: run 'claude mcp add clinicaltrials-v2 -s local -- npx tsx ~/.claude/mcp-servers/custom/clinicaltrials-v2/index.ts' before using
# MCP TOGGLE-ON: run 'claude mcp add hagr-longevity -s local -- npx tsx ~/.claude/mcp-servers/custom/hagr-longevity/index.ts' before using
schedule: "Sunday 20:00 EET"
---

# Longevity Scan Skill

## Objective
Generate a weekly evidence-focused scan of longevity and translational health research.

## Scope
- New papers from the last 7 days
- New/updated clinical trials
- Cross-check with HAGR DrugAge and GenAge context

## Priority Topics
- Caloric restriction
- Senolytics
- mTOR pathways
- NAD+ interventions
- GLP-1 and metabolic longevity

## Workflow
1. Query PubMed/OpenAlex/arXiv for weekly updates.
2. Query ClinicalTrials for active/recruiting studies.
3. Cross-reference compounds/genes against HAGR datasets.
4. Score each finding by evidence quality and translational relevance.
5. Return top 5 studies with short applicability notes.

## Output
- Top 5 studies (title, source, why it matters)
- Clinical trial watchlist updates
- DrugAge/GenAge cross-links
- Confidence scores and open questions
