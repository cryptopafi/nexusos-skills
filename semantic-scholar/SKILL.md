---
name: semantic-scholar
description: "Academic paper search via Semantic Scholar API"
---

Academic paper search via Semantic Scholar API

# Semantic Scholar Academic Search

## When to Use
Academic research, technical papers, citation analysis, AI/ML/energy papers.

## API
```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/search?query=QUERY&fields=title,abstract,authors,year,citationCount,url&limit=20"
```

## Parameters
- query: search terms
- fields: title,abstract,authors,year,citationCount,url,tldr
- limit: 1-100
- year: filter by year range (e.g., 2024-2026)
- fieldsOfStudy: Computer Science, Economics, Engineer
