---
name: free-data-sources
description: "Consolidated guide for free research data sources used by OpenClaw agents"
---

Consolidated guide for free research data sources used by OpenClaw agents

# Free Data Sources

## Purpose
Use this skill to pick fast, no-key data sources for research, monitoring, and business intelligence.

## Mandatory Start
Always query Cortex first, then external sources:
```bash
curl -s -X POST http://localhost:6400/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"TOPIC","collection":"procedures","limit":5}'
```

## Source Catalog

### 1) GDELT (Global News)
- URL: `https://api.gdeltproject.org/api/v2/doc/doc`
- Best for: global news signals,
